#!/usr/bin/env python3
# testador_lote.py
"""Script de automação de QA para testes biomecânicos em lote sem webcam.

Executa a inferência biomecânica em vídeos gravados, validando a matemática 3D,
contagem de repetições ou tempo isométrico, deteção de erros de postura,
fadiga muscular e estimativa de gasto calórico sem interface gráfica nem voz.
Pode ser executado para um vídeo individual (--video e --id) ou em lote sequencial
para todos os vídeos da pasta 'dataset_qa/'.
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
        default=None,
        help="Caminho para o ficheiro de vídeo (.mp4, .avi, etc.). Se omitido, processa a pasta dataset_qa/."
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Chave do exercício (de 1 a 30). Se omitido, extrai do nome do ficheiro em dataset_qa/."
    )
    return parser.parse_args()


def executar_teste(video_path, id_ex):
    """Processa um único vídeo e imprime o respetivo relatório de QA."""
    # Validação do arquivo de vídeo
    if not os.path.isfile(video_path):
        print(f"Erro: O ficheiro de vídeo '{video_path}' não foi encontrado.")
        return None

    id_str = str(id_ex).strip()
    if id_str not in EXERCICIOS:
        print(f"Erro: Exercício ID '{id_str}' inválido. IDs válidos: 1 a {len(EXERCICIOS)}.")
        return None

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
        return {
            "id": id_str,
            "video": os.path.basename(video_path),
            "nome": nome_exercicio,
            "eh_isometrico": eh_isometrico,
            "resultado_str": "Erro ao abrir vídeo",
            "reps": 0,
            "segundos": 0,
            "erros_postura": 0,
            "fadiga": "Não",
            "calorias": 0.0,
            "sucesso": False,
        }

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
                    if res.get("fora_enquadramento") or res.get("fase") == "calibracao":
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
        sucesso_teste = segundos_isom > 0
        total_reps = 0
    else:
        contador = filtros['repeticoes']['total']
        total_reps = contador.reps
        total_metrica_str = str(total_reps)
        segundos_isom = 0

        # Tempo de execução da série para cálculo calórico
        if total_reps > 0 and contador.tempo_inicio_serie is not None:
            tempo_serie = max(0.0, video_time[0] - contador.tempo_inicio_serie)
        else:
            tempo_serie = tempo_total_video

        # Verificação final de fadiga na lista de durações de repetições
        if verificar_fadiga(contador.tempos_repeticoes):
            fadiga_detectada = True
        fadiga_str = "Sim" if fadiga_detectada else "Não"
        sucesso_teste = total_reps > 0

    gasto_calorico = calcular_calorias(tempo_serie, met_ex, peso_kg=70.0)

    campo_metrica = "Tempo Isométrico" if eh_isometrico else "Total de Repetições"
    relatorio_texto = (
        "\n" + "=" * 50 + "\n"
        "            RELATÓRIO DE QA - IAFIT\n"
        + "=" * 50 + "\n"
        f"Vídeo: {os.path.basename(video_path)}\n"
        f"Nome do Exercício: {nome_exercicio}\n"
        f"{campo_metrica}: {total_metrica_str}\n"
        f"Erros de Postura contabilizados: {erros_postura}\n"
        f"Fadiga Detetada (Sim/Não): {fadiga_str}\n"
        f"Gasto Calórico Estimado: {gasto_calorico:.1f} kcal\n"
        + "=" * 50 + "\n"
    )
    print(relatorio_texto)

    return {
        "id": id_str,
        "video": os.path.basename(video_path),
        "nome": nome_exercicio,
        "eh_isometrico": eh_isometrico,
        "resultado_str": total_metrica_str,
        "reps": total_reps,
        "segundos": segundos_isom,
        "erros_postura": erros_postura,
        "fadiga": fadiga_str,
        "calorias": gasto_calorico,
        "sucesso": sucesso_teste,
        "relatorio_texto": relatorio_texto,
    }


def executar_lote_pasta(pasta_dataset="dataset_qa"):
    """Itera e processa sequencialmente todos os vídeos .mp4 da pasta informada."""
    if not os.path.isdir(pasta_dataset):
        print(f"Erro: A diretoria '{pasta_dataset}' não foi encontrada.")
        sys.exit(1)

    ficheiros = [f for f in os.listdir(pasta_dataset) if f.lower().endswith(".mp4")]
    if not ficheiros:
        print(f"Aviso: Nenhum ficheiro .mp4 encontrado na diretoria '{pasta_dataset}'.")
        sys.exit(0)

    # Ordenação natural dos arquivos numéricos (ex: 1.mp4, 2.mp4, 10.mp4)
    def chave_ordenacao(nome):
        base = os.path.splitext(nome)[0]
        return (0, int(base)) if base.isdigit() else (1, base)

    ficheiros_ordenados = sorted(ficheiros, key=chave_ordenacao)

    print("\n" + "=" * 50)
    print(f"   INICIANDO TESTES EM LOTE: {len(ficheiros_ordenados)} VÍDEOS ENCONTRADOS")
    print("=" * 50)

    resultados_lote = []
    relatorios_detalhados = []
    bem_sucedidos = 0
    falhas = 0
    falhas_detalhes = []

    for nome_arquivo in ficheiros_ordenados:
        id_ex = os.path.splitext(nome_arquivo)[0]
        caminho_video = os.path.join(pasta_dataset, nome_arquivo)

        if id_ex not in EXERCICIOS:
            print(f"\n[Aviso] Ficheiro '{nome_arquivo}' ignorado: ID '{id_ex}' não existe no catálogo de exercícios.")
            continue

        print(f">>> Processando [{id_ex}] {EXERCICIOS[id_ex]['nome']} ({nome_arquivo})...")
        try:
            res = executar_teste(caminho_video, id_ex)
            if res is not None:
                resultados_lote.append(res)
                if res.get("relatorio_texto"):
                    relatorios_detalhados.append(res["relatorio_texto"])
                if res["sucesso"]:
                    bem_sucedidos += 1
                else:
                    falhas += 1
                    falhas_detalhes.append(f"ID {id_ex} - {res['nome']} ({nome_arquivo})")
        except Exception as e:
            falhas += 1
            nome_ex = EXERCICIOS.get(id_ex, {}).get("nome", "Desconhecido")
            falhas_detalhes.append(f"ID {id_ex} - {nome_ex} (Erro: {e})")
            print(f"Erro inesperado no vídeo {nome_arquivo}: {e}")

    total_processados = len(resultados_lote)
    taxa_sucesso = (bem_sucedidos / total_processados * 100.0) if total_processados > 0 else 0.0

    # Sumário final
    sumario_texto = (
        "\n" + "=" * 50 + "\n"
        "             SUMÁRIO TOTAL DE QA\n"
        + "=" * 50 + "\n"
        f"Total de Vídeos Processados: {total_processados}\n"
        f"Testes Bem-Sucedidos: {bem_sucedidos}\n"
        f"Testes que Falharam (0 repetições detetadas): {falhas}\n"
        f"Taxa de Sucesso: {taxa_sucesso:.1f}%\n"
    )
    if falhas_detalhes:
        sumario_texto += "-" * 50 + "\n"
        sumario_texto += "Exercícios com Falha (0 repetições detetadas):\n"
        for f in falhas_detalhes:
            sumario_texto += f" - {f}\n"
    sumario_texto += "=" * 50 + "\n"

    print(sumario_texto)

    # Exportação de todo o relatório detalhado e do sumário final para relatorio_qa.txt
    caminho_exportacao = "relatorio_qa.txt"
    conteudo_completo = "".join(relatorios_detalhados) + "\n" + sumario_texto
    try:
        with open(caminho_exportacao, "w", encoding="utf-8") as f:
            f.write(conteudo_completo)
        print(f"Relatório de QA exportado com sucesso para: {caminho_exportacao}\n")
    except Exception as e:
        print(f"Erro ao exportar {caminho_exportacao}: {e}\n")


def main():
    args = parse_args()

    # Se ambos os argumentos forem nulos (None), processa todos os vídeos de dataset_qa/
    if args.video is None and args.id is None:
        executar_lote_pasta("dataset_qa")
    elif args.video is not None and args.id is not None:
        res = executar_teste(args.video, args.id)
        if res is None:
            sys.exit(1)
    else:
        print("Erro: Forneça ambos os argumentos (--video e --id) para testar um vídeo individual,")
        print("ou omita ambos para processar sequencialmente todos os vídeos da pasta 'dataset_qa/'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
