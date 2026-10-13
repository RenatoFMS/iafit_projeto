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
    validar_postura_remada,
    validar_postura_supino,
    validar_postura_elevacao_lateral,
    validar_postura_elevacao_pelvica,
    validar_postura_sumo,
    validar_barra_fixa,
    validar_postura_prancha_lateral,
    validar_postura_elevacao_frontal,
    validar_postura_triceps_testa,
    validar_postura_crucifixo,
    validar_postura_stiff_unilateral,
    validar_postura_panturrilha,
    validar_postura_bulgaro,
    validar_postura_encolhimento,
    validar_postura_abdominal_infra,
    validar_postura_remada_alta,
    validar_postura_bom_dia,
    validar_postura_triceps_coice,
    validar_postura_agachamento_isometrico,
    validar_polichinelo,
    verificar_fora_enquadramento,
    calcular_calorias,
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

    # Deteção de Saída de Enquadramento
    if verificar_fora_enquadramento(keypoints_data, config_exercicio):
        eh_isometrico = config_exercicio.get("tipo") == "isometrico" or "Prancha" in config_exercicio.get("nome", "")
        if eh_isometrico:
            cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
            if cronometro:
                cronometro.ultimo_tempo = None
        _executar_aviso_voz("Atenção, volte para a câmara")
        contador = filtros.get('repeticoes', {}).get('total') if filtros else None
        cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
        return [{
            "fora_enquadramento": True,
            "feedback": "FORA DE ENQUADRAMENTO",
            "cor": (0, 0, 255),
            "porc": 0,
            "coords": None,
            "coords_postura": None,
            "coords_bracos": None,
            "ponto_texto": (30, 90),
            "alerta_assimetria": False,
            "angulo_braco_esq": None,
            "angulo_braco_dir": None,
            "reps": contador.reps if contador else 0,
            "segundos": cronometro.segundos if cronometro else 0,
            "fase": "fora"
        }]

    # Desvio para exercícios isométricos baseados em tempo
    if config_exercicio.get("tipo") == "isometrico" or "Prancha" in config_exercicio.get("nome", ""):
        if "Lateral" in config_exercicio.get("nome", ""):
            return processar_prancha_lateral(keypoints_data, filtros)
        elif "Agachamento" in config_exercicio.get("nome", ""):
            return processar_agachamento_isometrico(keypoints_data, filtros)
        return processar_prancha(keypoints_data, filtros)

    # Desvio para exercício com lógica mista (Polichinelo)
    if "Polichinelo" in config_exercicio.get("nome", ""):
        return processar_polichinelo(keypoints_data, filtros)

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

    if verificar_fora_enquadramento(keypoints_data, config):
        cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
        if cronometro:
            cronometro.ultimo_tempo = None
        _executar_aviso_voz("Atenção, volte para a câmara")
        segundos = cronometro.segundos if cronometro else 0
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": segundos, "segundos": segundos, "postura_correta": False, "fase": "fora"
        }]

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


def processar_remada_curvada(landmarks, filtros, largura=None, altura=None):
    """Remada Curvada com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["9"], filtros)


def processar_supino(landmarks, filtros, largura=None, altura=None):
    """Supino com Halteres com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["10"], filtros)


def processar_elevacao_lateral(landmarks, filtros, largura=None, altura=None):
    """Elevação Lateral (20° -> 90°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["11"], filtros)


def processar_elevacao_pelvica(landmarks, filtros, largura=None, altura=None):
    """Elevação Pélvica (110° -> 175°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["12"], filtros)


def processar_mergulho_banco(landmarks, filtros, largura=None, altura=None):
    """Mergulho no Banco (160° -> 90°) com MediaPipe."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["13"], filtros)


def processar_rosca_martelo(landmarks, filtros, largura=None, altura=None):
    """Rosca Martelo (160° -> 40°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["14"], filtros)


def processar_agachamento_sumo(landmarks, filtros, largura=None, altura=None):
    """Agachamento Sumô com MediaPipe e validação da largura da base dos pés."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    postura_ok, _, _ = validar_postura_sumo(landmarks if len(landmarks) >= 33 else keypoints_data)
    if not postura_ok:
        _executar_aviso_voz("Afaste mais os pés")

    return processar_exercicio(keypoints_data, EXERCICIOS["15"], filtros)


def processar_barra_fixa(landmarks, filtros, largura=None, altura=None):
    """Barra Fixa com MediaPipe e validação do queixo acima da barra."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    queixo_acima, _, _ = validar_barra_fixa(landmarks)
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    resultados = processar_exercicio(keypoints_data, EXERCICIOS["16"], filtros)

    if resultados:
        porc = resultados[0].get("porc", 0)
        if porc >= 80 and not queixo_acima:
            resultados[0]["feedback"] = "ERRO: Passe o queixo da barra!"
            resultados[0]["cor"] = (0, 0, 255)
            _executar_aviso_voz("Passe o queixo da barra")
        elif queixo_acima and porc >= 70:
            resultados[0]["feedback"] = "Queixo acima da barra! Desça."
            resultados[0]["cor"] = (0, 255, 0)

    return resultados


PROCESSADORES_EXERCICIO = {
    "1": processar_rosca_biceps,
    "2": processar_agachamento,
    "3": processar_flexao,
    "4": processar_desenvolvimento_ombro,
    "5": processar_abdominal,
    "6": processar_afundo,
    "7": processar_stiff,
    "8": processar_prancha,
    "9": processar_remada_curvada,
    "10": processar_supino,
    "11": processar_elevacao_lateral,
    "12": processar_elevacao_pelvica,
    "13": processar_mergulho_banco,
    "14": processar_rosca_martelo,
    "15": processar_agachamento_sumo,
    "16": processar_barra_fixa,
}


def processar_triceps_testa(landmarks, filtros, largura=None, altura=None):
    """Tríceps Testa (160° -> 70°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["17"], filtros)


def processar_crucifixo(landmarks, filtros, largura=None, altura=None):
    """Crucifixo Halteres (150° -> 85°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["18"], filtros)


def processar_stiff_unilateral(landmarks, filtros, largura=None, altura=None):
    """Stiff Unilateral (170° -> 85°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["19"], filtros)


def processar_elevacao_frontal(landmarks, filtros, largura=None, altura=None):
    """Elevação Frontal (20° -> 90°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["20"], filtros)


def processar_panturrilha(landmarks, filtros, largura=None, altura=None):
    """Panturrilha em Pé (90° -> 140°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["21"], filtros)


def processar_prancha_lateral(landmarks, filtros, largura=None, altura=None):
    """Prancha Lateral (ângulo Ombro-Quadril-Tornozelo >= 160°)."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("22", {})

    if verificar_fora_enquadramento(keypoints_data, config):
        cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
        if cronometro:
            cronometro.ultimo_tempo = None
        _executar_aviso_voz("Atenção, volte para a câmara")
        segundos = cronometro.segundos if cronometro else 0
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": segundos, "segundos": segundos, "postura_correta": False, "fase": "fora"
        }]

    validacao = validar_postura_prancha_lateral(keypoints_data, filtros)
    if not validacao:
        return []

    postura_correta, angulo_suave, melhor_lado, (p1, p2, p3) = validacao

    if postura_correta:
        feedback = config.get("msg_fim", "Postura lateral correta!")
        cor = (0, 255, 0)  # Verde
        fase = "sustentando"
        porc = 100
    else:
        feedback = config.get("msg_erro", "ERRO: Suba o quadril lateral!")
        cor = (0, 0, 255)  # Vermelho
        fase = "corrigir"
        porc = int(max(0, min(100, (angulo_suave / 160.0) * 100)))
        _executar_aviso_voz(config.get("msg_voz", "Suba o quadril"))

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


def processar_agachamento_bulgaro(landmarks, filtros, largura=None, altura=None):
    """Agachamento Búlgaro (170° -> 90°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["23"], filtros)


def processar_encolhimento(landmarks, filtros, largura=None, altura=None):
    """Encolhimento de Ombros (170° -> 135°) com MediaPipe e foco no eixo Y."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["24"], filtros)


PROCESSADORES_EXERCICIO.update({
    "17": processar_triceps_testa,
    "18": processar_crucifixo,
    "19": processar_stiff_unilateral,
    "20": processar_elevacao_frontal,
    "21": processar_panturrilha,
    "22": processar_prancha_lateral,
    "23": processar_agachamento_bulgaro,
    "24": processar_encolhimento,
})


def processar_abdominal_infra(landmarks, filtros, largura=None, altura=None):
    """Abdominal Infra (165° -> 85°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["25"], filtros)


def processar_remada_alta(landmarks, filtros, largura=None, altura=None):
    """Remada Alta (25° -> 95°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["26"], filtros)


def processar_bom_dia(landmarks, filtros, largura=None, altura=None):
    """Bom Dia (170° -> 95°) com MediaPipe."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["27"], filtros)


def processar_triceps_coice(landmarks, filtros, largura=None, altura=None):
    """Tríceps Coice (90° -> 165°) com MediaPipe e deteção de assimetria dos braços."""
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["28"], filtros)


def processar_agachamento_isometrico(landmarks, filtros, largura=None, altura=None):
    """Agachamento Isométrico (Wall Sit) com ângulo mantido a ~90°."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("29", {})

    if verificar_fora_enquadramento(keypoints_data, config):
        cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
        if cronometro:
            cronometro.ultimo_tempo = None
        _executar_aviso_voz("Atenção, volte para a câmara")
        segundos = cronometro.segundos if cronometro else 0
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": segundos, "segundos": segundos, "postura_correta": False, "fase": "fora"
        }]

    validacao = validar_postura_agachamento_isometrico(keypoints_data, filtros)
    if not validacao:
        return []

    postura_correta, angulo_suave, melhor_lado, (p1, p2, p3), msg_correcao = validacao

    if postura_correta:
        feedback = config.get("msg_fim", "Posicao isometrica correta!")
        cor = (0, 255, 0)  # Verde
        fase = "sustentando"
        porc = 100
    else:
        feedback = f"ERRO: {msg_correcao}"
        cor = (0, 0, 255)  # Vermelho
        fase = "corrigir"
        porc = int(max(0, min(100, 100 - abs(angulo_suave - 90))))
        _executar_aviso_voz(msg_correcao)

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


def processar_polichinelo(landmarks, filtros, largura=None, altura=None):
    """Polichinelo (lógica mista: braços no eixo Y e pernas na distância dos pés)."""
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("30", {})

    if verificar_fora_enquadramento(keypoints_data, config):
        _executar_aviso_voz("Atenção, volte para a câmara")
        contador = filtros.get('repeticoes', {}).get('total') if filtros else None
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": contador.reps if contador else 0, "segundos": 0, "fase": "fora"
        }]

    res_poli = validar_polichinelo(keypoints_data, filtros)
    if not res_poli:
        return []

    porc, postura_segura, coords_bracos, coords_pernas, msg_erro = res_poli

    contador = filtros.get('repeticoes', {}).get('total')
    reps, fase = contador.atualizar(porc) if contador else (0, "base")

    if not postura_segura:
        feedback = f"ERRO: {msg_erro}"
        cor = (0, 0, 255)
        _executar_aviso_voz(msg_erro)
    else:
        if porc >= 80:
            feedback = config.get("msg_fim", "Boa abertura! Feche.")
            cor = (0, 255, 0)
        elif porc <= 20:
            feedback = config.get("msg_inicio", "Abra bracos e pernas.")
            cor = (0, 255, 255)
        else:
            feedback = "Em movimento..."
            cor = (255, 0, 0)

    p_ombro_esq = keypoints_data[5][:2]
    p_ombro_dir = keypoints_data[6][:2]
    ponto_texto = ((p_ombro_esq[0] + p_ombro_dir[0]) / 2, p_ombro_esq[1] - 30)

    p1 = keypoints_data[5][:2]
    p2 = keypoints_data[7][:2]
    p3 = keypoints_data[9][:2]

    return [{
        "lado": "esq",
        "porc": porc,
        "feedback": feedback,
        "cor": cor,
        "coords": (p1, p2, p3),
        "coords_postura": coords_pernas,
        "coords_bracos": (keypoints_data[5][:2], keypoints_data[7][:2], keypoints_data[9][:2]),
        "ponto_texto": ponto_texto,
        "alerta_assimetria": False,
        "angulo_braco_esq": None,
        "angulo_braco_dir": None,
        "reps": reps,
        "fase": fase
    }]


PROCESSADORES_EXERCICIO.update({
    "25": processar_abdominal_infra,
    "26": processar_remada_alta,
    "27": processar_bom_dia,
    "28": processar_triceps_coice,
    "29": processar_agachamento_isometrico,
    "30": processar_polichinelo,
})