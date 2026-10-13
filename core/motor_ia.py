# core/motor_ia.py
"""Controlador de IA do IAFit.

Atua como o orquestrador do sistema: recebe os dados de pose (MediaPipe / YOLO),
aciona a análise biomecânica, gerencia o cooldown de avisos sonoros e atualiza
os contadores de repetição e tempo isométrico.
"""

import time
from core.config_exercicios import EXERCICIOS
from core.voz_client import falar
from core.analise_biomecanica import (
    _obter_coord_conf,
    criar_detector_pose,
    landmarks_mediapipe_para_keypoints,
    selecionar_melhor_lado,
    calcular_amplitude_movimento,
    analisar_seguranca_postura,
    extrair_coordenadas_bracos,
    calcular_assimetria,
    verificar_assimetria_bracos,
    validar_postura_prancha,
)

# Cooldown global dos avisos de voz de postura e assimetria (4 segundos)
ultimo_aviso = 0


def resetar_cooldown_voz():
    """Reinicia o cooldown dos alertas de voz."""
    global ultimo_aviso
    ultimo_aviso = 0


def _executar_aviso_voz(mensagem, cooldown=4):
    """Aciona aviso sonoro respeitando a janela de cooldown."""
    global ultimo_aviso
    agora = time.time()
    if agora - ultimo_aviso > cooldown:
        falar(mensagem)
        ultimo_aviso = agora
        return True
    return False


def processar_exercicio(keypoints_data, config_exercicio, filtros):
    """Processa a execução de um exercício dinâmico ou isométrico.

    Orquestra a análise biomecânica, contagem de repetições e feedback sonoro.
    """
    global ultimo_aviso

    # Desvio para exercícios isométricos baseados em tempo
    if config_exercicio.get("tipo") == "isometrico" or "Prancha" in config_exercicio.get("nome", ""):
        return processar_prancha(keypoints_data, filtros)

    # 1. Seleção do melhor lado da câmera
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, config_exercicio["lados"])
    if not melhor_lado:
        return []

    # 2. Avaliação da amplitude e porcentagem
    porc, angulo_suave, coords = calcular_amplitude_movimento(
        keypoints_data, config_exercicio, melhor_lado, filtros
    )

    # 3. Contagem de repetições (fases subida/descida/topo/base)
    contador = filtros.get('repeticoes', {}).get('total')
    reps, fase = contador.atualizar(porc) if contador else (0, "base")

    # 4. Avaliação de segurança da postura
    postura_segura, coords_postura, _ = analisar_seguranca_postura(
        keypoints_data, config_exercicio, melhor_lado, filtros
    )

    # 5. Mapeamento extra de coordenadas dos braços
    coords_bracos = extrair_coordenadas_bracos(keypoints_data, config_exercicio, melhor_lado)

    # 6. Avaliação de assimetria dos braços
    if config_exercicio.get("ignorar_assimetria"):
        angulo_esq, angulo_dir, alerta_assimetria = None, None, False
    else:
        angulo_esq, angulo_dir, alerta_assimetria = calcular_assimetria(keypoints_data)
        if angulo_esq is not None and angulo_dir is not None:
            if abs(angulo_esq - angulo_dir) > 25:
                _executar_aviso_voz("Equilibre a força dos dois braços")

    # 7. Feedback visual e aviso de voz de postura
    if not postura_segura:
        feedback = config_exercicio.get("msg_erro", "ERRO: Corrija a postura!")
        cor = (0, 0, 255)  # Vermelho
        msg_voz = config_exercicio.get("msg_voz")
        if not msg_voz:
            msg_voz = feedback.replace("ERRO: ", "").replace("!", "").strip()
        _executar_aviso_voz(msg_voz)
    else:
        if porc == 100:
            feedback = config_exercicio["msg_fim"]
            cor = (0, 255, 0)  # Verde
        elif porc == 0:
            feedback = config_exercicio["msg_inicio"]
            cor = (0, 255, 255)  # Amarelo
        else:
            feedback = "Em movimento..."
            cor = (255, 0, 0)  # Azul

    p1, p2, p3 = coords
    return [{
        "lado": melhor_lado, "porc": porc, "feedback": feedback, "cor": cor,
        "coords": (p1, p2, p3), "coords_postura": coords_postura, "coords_bracos": coords_bracos, "ponto_texto": p2,
        "alerta_assimetria": alerta_assimetria, "angulo_braco_esq": angulo_esq, "angulo_braco_dir": angulo_dir,
        "reps": reps, "fase": fase
    }]


def processar_desenvolvimento_ombro(landmarks, filtros, largura=None, altura=None):
    """Desenvolvimento de Ombro (70° -> 160°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["4"], filtros)


def processar_rosca_biceps(landmarks, filtros, largura=None, altura=None):
    """Rosca Bíceps (160° -> 40°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["1"], filtros)


def processar_flexao(landmarks, filtros, largura=None, altura=None):
    """Flexão de Braço (160° -> 80°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["3"], filtros)


def processar_abdominal(landmarks, filtros, largura=None, altura=None):
    """Abdominal Supra (150° -> 70°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["5"], filtros)


def processar_agachamento(landmarks, filtros, largura=None, altura=None):
    """Agachamento (170° -> 80°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["2"], filtros)


def processar_afundo(landmarks, filtros, largura=None, altura=None):
    """Afundo / Lunge (160° -> 90°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["6"], filtros)


def processar_stiff(landmarks, filtros, largura=None, altura=None):
    """Stiff (170° -> 80°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["7"], filtros)


def processar_prancha(landmarks, filtros, largura=None, altura=None):
    """Prancha Isométrica (ângulo Ombro-Quadril-Tornozelo >= 160°)."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("8", {})

    validacao = validar_postura_prancha(keypoints_data, filtros)
    if not validacao:
        return []

    postura_correta, angulo_suave, melhor_lado, (p1, p2, p3) = validacao

    if postura_correta:
        feedback = config.get("msg_fim", "Postura correta!")
        cor = (0, 255, 0)  # Verde
        fase = "sustentando"
        porc = 100
    else:
        feedback = config.get("msg_erro", "ERRO: Levante o quadril!")
        cor = (0, 0, 255)  # Vermelho
        fase = "corrigir"
        porc = int(max(0, min(100, (angulo_suave / 160.0) * 100)))
        _executar_aviso_voz(config.get("msg_voz", "Levante o quadril"))

    cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
    if cronometro:
        cronometro.atualizar(postura_correta=postura_correta)
        segundos = cronometro.segundos
    else:
        segundos = 0

    return [{
        "lado": melhor_lado,
        "porc": porc,
        "feedback": feedback,
        "cor": cor,
        "coords": (p1, p2, p3),
        "coords_postura": (p1, p2),
        "coords_bracos": None,
        "ponto_texto": p2,
        "alerta_assimetria": False,
        "angulo_braco_esq": None,
        "angulo_braco_dir": None,
        "reps": segundos,
        "segundos": segundos,
        "postura_correta": postura_correta,
        "fase": fase
    }]


PROCESSADORES_EXERCICIO = {
    "1": processar_rosca_biceps,
    "2": processar_agachamento,
    "3": processar_flexao,
    "4": processar_desenvolvimento_ombro,
    "5": processar_abdominal,
    "6": processar_afundo,
    "7": processar_stiff,
    "8": processar_prancha,
}