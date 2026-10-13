import math
import time
from core.math_utils import calcular_angulo, calcular_porcentagem
from core.config_exercicios import EXERCICIOS
from core.voz_client import falar

# Variável global para gerir o cooldown dos avisos de voz de postura (4 segundos)
ultimo_aviso = 0

# Índices COCO (YOLOv8-pose) dos braços, usados no filtro de assimetria
BRACO_ESQ = (5, 7, 9)   # Ombro, Cotovelo, Pulso esquerdos
BRACO_DIR = (6, 8, 10)  # Ombro, Cotovelo, Pulso direitos
LIMITE_ASSIMETRIA = 15  # graus

def calcular_assimetria(keypoints_data):
    """Extrai os dois braços em simultâneo e compara os ângulos do cotovelo.
    Retorna (angulo_esq, angulo_dir, alerta_assimetria)."""
    indices = BRACO_ESQ + BRACO_DIR
    if any(keypoints_data[i][2] < 0.5 for i in indices):
        return None, None, False  # Braço fora de enquadramento: sem alerta

    pts_esq = [keypoints_data[i][:2] for i in BRACO_ESQ]
    pts_dir = [keypoints_data[i][:2] for i in BRACO_DIR]
    angulo_esq = calcular_angulo(*pts_esq)
    angulo_dir = calcular_angulo(*pts_dir)
    alerta = abs(angulo_esq - angulo_dir) > LIMITE_ASSIMETRIA
    return angulo_esq, angulo_dir, alerta

def processar_exercicio(keypoints_data, config_exercicio, filtros):
    global ultimo_aviso
    if config_exercicio.get("tipo") == "isometrico" or "Prancha" in config_exercicio.get("nome", ""):
        return processar_prancha(keypoints_data, filtros)
    resultados = []
    melhor_lado = None
    maior_confianca = 0
    
    # 1. Escolhe o lado mais visível da câmera
    for lado, indices in config_exercicio["lados"].items():
        confianca_total = sum([keypoints_data[i][2] for i in indices])
        if confianca_total > maior_confianca:
            maior_confianca = confianca_total
            melhor_lado = lado
            
    if not melhor_lado: return []
        
    # 2. Avalia a Perna (Amplitude)
    p1_idx, p2_idx, p3_idx = config_exercicio["lados"][melhor_lado]
    if keypoints_data[p1_idx][2] < 0.5 or keypoints_data[p2_idx][2] < 0.5 or keypoints_data[p3_idx][2] < 0.5:
        return []

    p1, p2, p3 = keypoints_data[p1_idx][:2], keypoints_data[p2_idx][:2], keypoints_data[p3_idx][:2]
    angulo_bruto = calcular_angulo(p1, p2, p3)
    angulo_suave = filtros['amplitude'][melhor_lado].atualizar(angulo_bruto)
    porc = calcular_porcentagem(angulo_suave, config_exercicio["inicio"], config_exercicio["fim"])

    # Contagem de repetições (fases subida/descida). Opcional: só se o contador existir em filtros.
    contador = filtros.get('repeticoes', {}).get('total')
    reps, fase = contador.atualizar(porc) if contador else (0, "base")
    
    cor = (255, 0, 0)
    feedback = "Em movimento..."
    postura_segura = True
    coords_postura = None
    coords_bracos = None
    
    # 3. Análise de Segurança da Postura
    if config_exercicio.get("postura"):
        s1_idx, s2_idx = config_exercicio["postura"][melhor_lado][:2]
        if keypoints_data[s1_idx][2] > 0.5 and keypoints_data[s2_idx][2] > 0.5:
            sp1 = keypoints_data[s1_idx][:2]
            sp2 = keypoints_data[s2_idx][:2]
            coords_postura = (sp1, sp2) 
            
            ponto3_valido = True
            # Cria a linha de gravidade imaginária puxando 50 pixels para cima do ponto de apoio
            if config_exercicio.get("postura_vertical"):
                sp3 = (sp2[0], sp2[1] - 50)
            else:
                s3_idx = config_exercicio["postura"][melhor_lado][2]
                if keypoints_data[s3_idx][2] > 0.5:
                    sp3 = keypoints_data[s3_idx][:2]
                else:
                    ponto3_valido = False
                
            if ponto3_valido:
                angulo_seg = calcular_angulo(sp1, sp2, sp3)
                filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
                angulo_seg_suave = filtro_post.atualizar(angulo_seg) if filtro_post else angulo_seg
                
                limite = config_exercicio["limite_postura"]
                if config_exercicio["regra_postura"] == "<" and angulo_seg_suave < limite:
                    postura_segura = False
                elif config_exercicio["regra_postura"] == ">" and angulo_seg_suave > limite:
                    postura_segura = False

    # 4. Mapeamento Extra (Braços/Cotovelos)
    if config_exercicio.get("bracos"):
        b1_idx, b2_idx, b3_idx = config_exercicio["bracos"][melhor_lado]
        if keypoints_data[b1_idx][2] > 0.5 and keypoints_data[b2_idx][2] > 0.5:
            bp1 = keypoints_data[b1_idx][:2]
            bp2 = keypoints_data[b2_idx][:2]
            # Tenta pegar o pulso, se não enxergar, usa o cotovelo de novo para não quebrar a linha
            bp3 = keypoints_data[b3_idx][:2] if keypoints_data[b3_idx][2] > 0.5 else bp2 
            coords_bracos = (bp1, bp2, bp3)

    # 5. Filtro de Assimetria (ambos os braços em simultâneo)
    if config_exercicio.get("ignorar_assimetria"):
        angulo_esq, angulo_dir, alerta_assimetria = None, None, False
    else:
        angulo_esq, angulo_dir, alerta_assimetria = calcular_assimetria(keypoints_data)
        if angulo_esq is not None and angulo_dir is not None:
            if abs(angulo_esq - angulo_dir) > 25:
                agora = time.time()
                if agora - ultimo_aviso > 4:
                    falar("Equilibre a força dos dois braços")
                    ultimo_aviso = agora

    # 6. Definição do Alerta e Feedback de Voz (Cooldown 4s)
    if not postura_segura:
        feedback = config_exercicio.get("msg_erro", "ERRO: Corrija a postura!")
        cor = (0, 0, 255) # Vermelho

        agora = time.time()
        if agora - ultimo_aviso > 4:
            msg_voz = config_exercicio.get("msg_voz")
            if not msg_voz:
                msg_voz = feedback.replace("ERRO: ", "").replace("!", "").strip()
            falar(msg_voz)
            ultimo_aviso = agora
    else:
        if porc == 100:
            feedback = config_exercicio["msg_fim"]
            cor = (0, 255, 0) # Verde
        elif porc == 0:
            feedback = config_exercicio["msg_inicio"]
            cor = (0, 255, 255) # Amarelo
        
    resultados.append({
        "lado": melhor_lado, "porc": porc, "feedback": feedback, "cor": cor,
        "coords": (p1, p2, p3), "coords_postura": coords_postura, "coords_bracos": coords_bracos, "ponto_texto": p2,
        "alerta_assimetria": alerta_assimetria, "angulo_braco_esq": angulo_esq, "angulo_braco_dir": angulo_dir,
        "reps": reps, "fase": fase
    })
        
    return resultados

def _obter_coord_conf(landmark):
    """Extrai ((x, y), confianca) de um landmark MediaPipe ou estrutura equivalente."""
    if hasattr(landmark, 'x') and hasattr(landmark, 'y'):
        conf = getattr(landmark, 'visibility', getattr(landmark, 'confidence', 1.0))
        return (landmark.x, landmark.y), conf
    elif isinstance(landmark, (list, tuple)):
        conf = landmark[2] if len(landmark) > 2 else 1.0
        return (landmark[0], landmark[1]), conf
    elif isinstance(landmark, dict):
        conf = landmark.get('visibility', landmark.get('confidence', landmark.get('conf', 1.0)))
        return (landmark['x'], landmark['y']), conf
    return (0, 0), 0.0

# Mapeamento MediaPipe (33 landmarks) -> índices COCO (17 keypoints) usados pelo motor
_MP_PARA_COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

def landmarks_mediapipe_para_keypoints(landmarks):
    """Converte landmarks do MediaPipe para o formato [x, y, confiança] do YOLO/COCO."""
    if len(landmarks) == 17 and isinstance(landmarks[0], (list, tuple)) and not hasattr(landmarks[0], 'x'):
        return landmarks
    kps = []
    for i in _MP_PARA_COCO:
        (x, y), conf = _obter_coord_conf(landmarks[i])
        kps.append([x, y, conf])
    return kps

# Dentro do seu loop principal de processamento do MediaPipe:
def processar_desenvolvimento_ombro(landmarks, filtros):
    """Desenvolvimento de Ombro (70° -> 160°) com MediaPipe.

    Extrai ombro, cotovelo e pulso dos dois lados, calcula a percentagem de amplitude,
    a contagem de repetições e o alerta_assimetria (diferença > 15°), devolvendo a
    mesma lista de resultados que processar_exercicio.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    return processar_exercicio(keypoints_data, EXERCICIOS["4"], filtros)


def processar_rosca_biceps(landmarks, filtros):
    """Rosca Bíceps (160° -> 40°) com MediaPipe.

    Extrai ombro, cotovelo e pulso dos dois lados, calcula a percentagem de amplitude
    (o ângulo diminui à medida que o movimento avança: 160° = braço esticado = 0%,
    40° = contração no topo = 100%), a contagem de repetições e o alerta_assimetria
    (diferença > 15°), devolvendo a mesma lista de resultados que processar_exercicio.
    """
    global ultimo_aviso

    # Deteção de assimetria muscular de movimento (braço esquerdo: 11, 13, 15; braço direito: 12, 14, 16)
    indices_bracos = [11, 13, 15, 12, 14, 16]
    coords_confs = {idx: _obter_coord_conf(landmarks[idx]) for idx in indices_bracos}

    if all(coords_confs[idx][1] > 0.5 for idx in indices_bracos):
        p_ombro_esq = coords_confs[11][0]
        p_cotovelo_esq = coords_confs[13][0]
        p_pulso_esq = coords_confs[15][0]
        p_ombro_dir = coords_confs[12][0]
        p_cotovelo_dir = coords_confs[14][0]
        p_pulso_dir = coords_confs[16][0]

        angulo_esq = calcular_angulo(p_ombro_esq, p_cotovelo_esq, p_pulso_esq)
        angulo_dir = calcular_angulo(p_ombro_dir, p_cotovelo_dir, p_pulso_dir)

        if abs(angulo_esq - angulo_dir) > 25:
            agora = time.time()
            if agora - ultimo_aviso > 4:
                falar("Equilibre a força dos dois braços")
                ultimo_aviso = agora

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    return processar_exercicio(keypoints_data, EXERCICIOS["1"], filtros)

def processar_flexao(landmarks, filtros):
    """Flexão de Braço (160° -> 80°) com MediaPipe.

    Extrai ombro, cotovelo e pulso dos dois lados, calcula a percentagem de amplitude
    (160° = braços esticados = 0%, 80° = fundo = 100%), a contagem de repetições, a
    segurança do quadril (config '3') e o alerta_assimetria (diferença > 15°),
    devolvendo a mesma lista de resultados que processar_exercicio.
    """
    global ultimo_aviso

    # Deteção de assimetria muscular de movimento (braço esquerdo: 11, 13, 15; braço direito: 12, 14, 16)
    indices_bracos = [11, 13, 15, 12, 14, 16]
    coords_confs = {idx: _obter_coord_conf(landmarks[idx]) for idx in indices_bracos}

    if all(coords_confs[idx][1] > 0.5 for idx in indices_bracos):
        p_ombro_esq = coords_confs[11][0]
        p_cotovelo_esq = coords_confs[13][0]
        p_pulso_esq = coords_confs[15][0]
        p_ombro_dir = coords_confs[12][0]
        p_cotovelo_dir = coords_confs[14][0]
        p_pulso_dir = coords_confs[16][0]

        angulo_esq = calcular_angulo(p_ombro_esq, p_cotovelo_esq, p_pulso_esq)
        angulo_dir = calcular_angulo(p_ombro_dir, p_cotovelo_dir, p_pulso_dir)

        if abs(angulo_esq - angulo_dir) > 25:
            agora = time.time()
            if agora - ultimo_aviso > 4:
                falar("Equilibre a força dos dois braços")
                ultimo_aviso = agora

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    return processar_exercicio(keypoints_data, EXERCICIOS["3"], filtros)

def processar_abdominal(landmarks, filtros):
    """Abdominal Supra (150° -> 70°) com MediaPipe, ângulo Ombro-Quadril-Joelho.

    Executado de perfil, um dos lados pode ficar obstruído: o processar_exercicio escolhe
    o lado com maior confiança na deteção e o alerta de assimetria fica desativado
    (config '5' com ignorar_assimetria). Devolve a mesma lista de resultados dos restantes.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    return processar_exercicio(keypoints_data, EXERCICIOS["5"], filtros)

def processar_agachamento(landmarks, filtros):
    """Agachamento (170° -> 80°) com MediaPipe.

    Avalia a amplitude do joelho, segurança da coluna lombar e alinhamento,
    devolvendo a mesma lista de resultados que processar_exercicio.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    return processar_exercicio(keypoints_data, EXERCICIOS["2"], filtros)

def processar_afundo(landmarks, filtros):
    """Afundo / Lunge (160° -> 90°) com MediaPipe.

    Avalia a flexão do joelho (Quadril-Joelho-Tornozelo) e o alinhamento postural
    (Ombro-Quadril-Joelho traseiro) para evitar inclinação excessiva do tronco,
    mantendo a mesma estrutura de contagem, suavização e cooldown de voz que usamos no Agachamento.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    return processar_exercicio(keypoints_data, EXERCICIOS["6"], filtros)

def processar_stiff(landmarks, filtros):
    """Stiff (170° -> 80°) com MediaPipe.

    Avalia a extensão/flexão do quadril (Ombro-Quadril-Joelho) e a segurança postural
    das costas (ângulo Ombro-Quadril em relação à vertical), mantendo a mesma estrutura
    de contagem, suavização e cooldown de voz que usamos no Agachamento.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    return processar_exercicio(keypoints_data, EXERCICIOS["7"], filtros)

def processar_prancha(landmarks, filtros):
    """Prancha Isométrica (ângulo Ombro-Quadril-Tornozelo >= 160°).

    Calcula o ângulo principal Ombro-Quadril-Tornozelo.
    Se o ângulo for >= 160°, a postura está correta (o cronômetro avança).
    Se for < 160°, o quadril caiu; a postura fica incorreta (o cronômetro pausa)
    e o sistema usa a variável de cooldown (ultimo_aviso) para acionar falar('Levante o quadril').
    """
    global ultimo_aviso

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks)
    config = EXERCICIOS.get("8", {})

    # 1. Identifica o melhor lado visível
    melhor_lado = None
    maior_conf = 0
    lados = config.get("lados", {"esq": (5, 11, 15), "dir": (6, 12, 16)})
    for lado, indices in lados.items():
        conf_total = sum(keypoints_data[i][2] for i in indices)
        if conf_total > maior_conf:
            maior_conf = conf_total
            melhor_lado = lado

    if not melhor_lado:
        return []

    p1_idx, p2_idx, p3_idx = lados[melhor_lado]
    if (keypoints_data[p1_idx][2] < 0.5 or
        keypoints_data[p2_idx][2] < 0.5 or
        keypoints_data[p3_idx][2] < 0.5):
        return []

    p1 = keypoints_data[p1_idx][:2]  # Ombro
    p2 = keypoints_data[p2_idx][:2]  # Quadril
    p3 = keypoints_data[p3_idx][:2]  # Tornozelo

    # 2. Ângulo principal Ombro-Quadril-Tornozelo
    angulo_bruto = calcular_angulo(p1, p2, p3)
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto

    # 3. Regra da Prancha: >= 160° postura correta, < 160° quadril caiu
    postura_correta = angulo_suave >= 160.0

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

        agora = time.time()
        if agora - ultimo_aviso > 4:
            falar(config.get("msg_voz", "Levante o quadril"))
            ultimo_aviso = agora

    # 4. Cronômetro Isométrico (avança se postura_correta=True, pausa se False)
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

def resetar_cooldown_voz():
    """Reinicia o cooldown dos alertas de voz de postura."""
    global ultimo_aviso
    ultimo_aviso = 0

# Exercícios com função dedicada (id da config_exercicios -> função de processamento)
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