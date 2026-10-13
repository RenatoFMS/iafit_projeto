#!/usr/bin/env python3
# testador_lote.py
"""Script de automação de QA para testes biomecânicos em lote sem webcam.

Executa a inferência biomecânica em vídeos gravados, validando a matemática 3D,
contagem de repetições ou tempo isométrico, deteção de erros de postura,
fadiga muscular e estimativa de gasto calórico sem interface gráfica nem voz.
"""

import argparse
import os
import sys
import time
import warnings

# Configuração de variáveis de ambiente para suprimir avisos de terceiros (SDL, TF, Matplotlib)
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_qa"

warnings.filterwarnings("ignore")

import cv2

# 1. Desativa a saída de voz (falar()) antes das importações de motor_ia / math_utils
import core.voz_client
import core.motor_ia
import core.math_utils

core.voz_client.falar = lambda *args, **kwargs: None
core.motor_ia.falar = lambda *args, **kwargs: None
core.math_utils.falar = lambda *args, **kwargs: None

from core.config_exercicios import EXERCICIOS
from core.motor_ia import (
    processar_exercicio,
    PROCESSADORES_EXERCICIO,
    resetar_cooldown_voz,
)
from core.analise_biomecanica import (
    criar_detector_pose,
    landmarks_mediapipe_para_keypoints,
    calcular_calorias,
    verificar_fadiga,
)
from core.math_utils import FiltroSuavizacao, ContadorRepeticoes, CronometroIsometrico


def parse_args():
    parser = argparse.ArgumentParser(
        description="IAFit QA - Testador em Lote para Validação Biomecânica 3D."
    )
    parser.add_argument(
        "--video",
        type=str,
        required=True,
        help="Caminho para o ficheiro de vídeo (.mp4, .avi, etc.)."
    )
    parser.add_argument(
        "--id",
        type=str,
        required=True,
        help="Chave do exercício (de 1 a 30)."
    )
    return parser.parse_args()


def executar_teste(video_path, id_ex):
    # Validação do arquivo de vídeo
    if not os.path.isfile(video_path):
        print(f"Erro: O ficheiro de vídeo '{video_path}' não foi encontrado.")
        sys.exit(1)

    id_str = str(id_ex).strip()
    if id_str not in EXERCICIOS:
        print(f"Erro: Exercício ID '{id_str}' inválido. IDs válidos: 1 a {len(EXERCICIOS)}.")
        sys.exit(1)

    config = EXERCICIOS[id_str]
    nome_exercicio = config.get("nome", f"Exercício {id_str}")
    met_ex = config.get("met", 3.0)
    eh_isometrico = (
        config.get("tipo") == "isometrico"
        or "Prancha" in nome_exercicio
        or id_str in ("8", "22", "29")
    )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Erro: Falha ao abrir o ficheiro de vídeo '{video_path}'.")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps is None or fps <= 0 or (isinstance(fps, float) and (fps != fps)):
        fps = 30.0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Inicialização dos filtros de memória e IA
    filtros = {
        'amplitude': {'esq': FiltroSuavizacao(5), 'dir': FiltroSuavizacao(5)},
        'postura': {'esq': FiltroSuavizacao(5), 'dir': FiltroSuavizacao(5)},
        'repeticoes': {'total': ContadorRepeticoes()},
        'isometrico': {'total': CronometroIsometrico()}
    }
    resetar_cooldown_voz()

    pose = criar_detector_pose(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.7,
    )

    erros_postura = 0
    em_erro_anterior = False
    fadiga_detectada = False
    frame_count = 0

    # Sincronização temporal do vídeo: mock de time.time() para refletir a cadência real do vídeo
    video_time = [0.0]
    tempo_real = time.time
    time.time = lambda: video_time[0]

    try:
        while cap.isOpened():
            sucesso, frame = cap.read()
            if not sucesso or frame is None:
                break

            frame_count += 1
            video_time[0] = frame_count / fps

            # Redimensionamento proporcional se necessário para estabilizar coordenadas
            altura_orig, largura_orig = frame.shape[:2]
            escala = min(900 / largura_orig, 700 / altura_orig)
            if escala < 1:
                frame = cv2.resize(frame, (int(largura_orig * escala), int(altura_orig * escala)))

            altura_atual, largura_atual = frame.shape[:2]

            # Inferência MediaPipe otimizada BGR -> RGB com writeable=False
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)

            # Roteamento para o processador do exercício
            if results.pose_landmarks:
                processador = PROCESSADORES_EXERCICIO.get(id_str)
                if processador:
                    resultados = processador(
                        results.pose_landmarks.landmark,
                        filtros,
                        largura=largura_atual,
                        altura=altura_atual
                    )
                else:
                    pontos = landmarks_mediapipe_para_keypoints(
                        results.pose_landmarks.landmark,
                        largura=largura_atual,
                        altura=altura_atual
                    )
                    resultados = processar_exercicio(pontos, config, filtros)
            else:
                resultados = processar_exercicio(None, config, filtros)

            # Avaliação de erros de postura e flag de fadiga no frame
            tem_erro_frame = False
            if resultados:
                for res in resultados:
                    if res.get("fora_enquadramento"):
                        continue

                    if res.get("fadiga_detectada"):
                        fadiga_detectada = True

                    feedback = str(res.get("feedback", ""))
                    cor = res.get("cor")
                    postura_correta = res.get("postura_correta")

                    if (
                        feedback.startswith("ERRO:")
                        or cor == (0, 0, 255)
                        or (postura_correta is False and "postura_correta" in res)
                    ):
                        tem_erro_frame = True
                        break

            # Contabilização de erros por transição (ocorrências de erro de postura)
            if tem_erro_frame and not em_erro_anterior:
                erros_postura += 1
            em_erro_anterior = tem_erro_frame

    finally:
        # Restaura a função de tempo do sistema
        time.time = tempo_real
        cap.release()
        pose.close()

    # Cálculo dos resultados finais
    tempo_total_video = frame_count / fps if fps > 0 else 0.0

    if eh_isometrico:
        cronometro = filtros['isometrico']['total']
        segundos_isom = cronometro.segundos
        total_metrica_str = f"{segundos_isom}s"
        tempo_serie = float(segundos_isom) if segundos_isom > 0 else tempo_total_video
        fadiga_str = "Não"
    else:
        contador = filtros['repeticoes']['total']
        total_reps = contador.reps
        total_metrica_str = str(total_reps)

        # Tempo de execução da série para cálculo calórico
        if total_reps > 0 and contador.tempo_inicio_serie is not None:
            tempo_serie = max(0.0, video_time[0] - contador.tempo_inicio_serie)
        else:
            tempo_serie = tempo_total_video

        # Verificação final de fadiga na lista de durações de repetições
        if verificar_fadiga(contador.tempos_repeticoes):
            fadiga_detectada = True
        fadiga_str = "Sim" if fadiga_detectada else "Não"

    gasto_calorico = calcular_calorias(tempo_serie, met_ex, peso_kg=70.0)

    # Relatório formatado no terminal
    print("\n" + "=" * 50)
    print("            RELATÓRIO DE QA - IAFIT")
    print("=" * 50)
    print(f"Nome do Exercício: {nome_exercicio}")
    if eh_isometrico:
        print(f"Tempo Isométrico: {total_metrica_str}")
    else:
        print(f"Total de Repetições: {total_metrica_str}")
    print(f"Erros de Postura contabilizados: {erros_postura}")
    print(f"Fadiga Detetada (Sim/Não): {fadiga_str}")
    print(f"Gasto Calórico Estimado: {gasto_calorico:.1f} kcal")
    print("=" * 50 + "\n")


def main():
    args = parse_args()
    executar_teste(args.video, args.id)


if __name__ == "__main__":
    main()
