# core/analise_biomecanica.py
"""Módulo de Análise Biomecânica do IAFit.

Responsável pela extração de coordenadas, cálculo de ângulos articulares,
avaliação de assimetria muscular e validação de regras posturais para os exercícios.
"""

from core.math_utils import calcular_angulo, calcular_porcentagem

# Constantes e índices anatômicos (padrão COCO / YOLOv8-pose)
BRACO_ESQ = (5, 7, 9)   # Ombro, Cotovelo, Pulso esquerdos
BRACO_DIR = (6, 8, 10)  # Ombro, Cotovelo, Pulso direitos
LIMITE_ASSIMETRIA = 15  # Diferença angular para alerta visual (graus)
LIMITE_ASSIMETRIA_VOZ = 25  # Diferença angular para alerta sonoro (graus)

# Mapeamento MediaPipe (33 landmarks) -> índices COCO (17 keypoints)
_MP_PARA_COCO = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


def _obter_coord_conf(landmark):
    """Extrai ((x, y), confianca) de um landmark MediaPipe ou estrutura equivalente.

    Suporta objetos MediaPipe (com atributos x, y, visibility/confidence),
    listas/tuplas [x, y, conf] ou dicionários {'x': ..., 'y': ...}.
    """
    if hasattr(landmark, 'x') and hasattr(landmark, 'y'):
        conf = getattr(landmark, 'visibility', getattr(landmark, 'confidence', 1.0))
        return (landmark.x, landmark.y), conf
    elif isinstance(landmark, (list, tuple)):
        conf = landmark[2] if len(landmark) > 2 else 1.0
        return (landmark[0], landmark[1]), conf
    elif isinstance(landmark, dict):
        conf = landmark.get('visibility', landmark.get('confidence', landmark.get('conf', 1.0)))
        return (landmark['x'], landmark['y']), conf
    return (0.0, 0.0), 0.0


def criar_detector_pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.7
):
    """Cria e retorna uma instância otimizada do MediaPipe Pose.

    Configurações para máxima performance em tempo real (CPU):
    - static_image_mode=False: ativa o rastreamento contínuo entre frames.
    - model_complexity=1: equilíbrio ideal entre velocidade e acurácia.
    - min_detection_confidence=0.5: limiar de confiança para detecção inicial.
    - min_tracking_confidence=0.7: rastreamento robusto para evitar perda do corpo.
    """
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    return mp_pose.Pose(
        static_image_mode=static_image_mode,
        model_complexity=model_complexity,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )


def landmarks_mediapipe_para_keypoints(landmarks, largura=None, altura=None):
    """Converte landmarks do MediaPipe (33 pontos) para o formato [x, y, confiança] do COCO (17 pontos).

    Se largura e altura forem fornecidas, converte as coordenadas normalizadas [0, 1]
    para as coordenadas de pixel da imagem.
    Se os landmarks já estiverem no formato COCO (17 pontos), retorna-os diretamente.
    """
    if len(landmarks) == 17 and isinstance(landmarks[0], (list, tuple)) and not hasattr(landmarks[0], 'x'):
        return landmarks
    kps = []
    for i in _MP_PARA_COCO:
        (x, y), conf = _obter_coord_conf(landmarks[i])
        if largura is not None and altura is not None:
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                x = x * largura
                y = y * altura
        kps.append([x, y, conf])
    return kps


def selecionar_melhor_lado(keypoints_data, lados_config):
    """Seleciona o lado ('esq' ou 'dir') que apresenta maior grau de confiança visual.

    Retorna (melhor_lado, indices) ou (None, None) se a visibilidade for insuficiente.
    """
    melhor_lado = None
    maior_confianca = 0
    for lado, indices in lados_config.items():
        conf_total = sum(keypoints_data[i][2] for i in indices)
        if conf_total > maior_confianca:
            maior_confianca = conf_total
            melhor_lado = lado

    if not melhor_lado:
        return None, None

    indices = lados_config[melhor_lado]
    # Valida se os pontos principais atingem a confiança mínima de 0.5
    if any(keypoints_data[idx][2] < 0.5 for idx in indices):
        return None, None

    return melhor_lado, indices


def calcular_amplitude_movimento(keypoints_data, config_exercicio, melhor_lado, filtros=None):
    """Calcula o ângulo articular do movimento principal e a porcentagem de execução (0-100%).

    Retorna (porc, angulo_suave, (p1, p2, p3)).
    """
    p1_idx, p2_idx, p3_idx = config_exercicio["lados"][melhor_lado]
    p1 = keypoints_data[p1_idx][:2]
    p2 = keypoints_data[p2_idx][:2]
    p3 = keypoints_data[p3_idx][:2]

    angulo_bruto = calcular_angulo(p1, p2, p3)
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto
    porc = calcular_porcentagem(angulo_suave, config_exercicio["inicio"], config_exercicio["fim"])

    return porc, angulo_suave, (p1, p2, p3)


def analisar_seguranca_postura(keypoints_data, config_exercicio, melhor_lado, filtros=None):
    """Avalia o alinhamento corporal e a segurança da postura segundo a configuração do exercício.

    Retorna (postura_segura, coords_postura, angulo_seg_suave).
    """
    postura_segura = True
    coords_postura = None
    angulo_seg_suave = None

    nome = config_exercicio.get("nome", "")
    if "Remada" in nome:
        return validar_postura_remada(keypoints_data, melhor_lado, filtros)
    elif "Supino" in nome:
        return validar_postura_supino(keypoints_data, melhor_lado, filtros)
    elif "Elevacao Lateral" in nome:
        return validar_postura_elevacao_lateral(keypoints_data, melhor_lado, filtros)
    elif "Elevacao Pelvica" in nome:
        return validar_postura_elevacao_pelvica(keypoints_data, melhor_lado, filtros)
    elif "Sumo" in nome or "Sumô" in nome:
        return validar_postura_sumo(keypoints_data, melhor_lado, filtros)

    if not config_exercicio.get("postura"):
        return postura_segura, coords_postura, angulo_seg_suave

    s1_idx, s2_idx = config_exercicio["postura"][melhor_lado][:2]
    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return postura_segura, coords_postura, angulo_seg_suave

    sp1 = keypoints_data[s1_idx][:2]
    sp2 = keypoints_data[s2_idx][:2]
    coords_postura = (sp1, sp2)

    ponto3_valido = True
    if config_exercicio.get("postura_vertical"):
        # Cria uma linha vertical imaginária 50 pixels acima do ponto de apoio
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
        regra = config_exercicio["regra_postura"]
        if regra == "<" and angulo_seg_suave < limite:
            postura_segura = False
        elif regra == ">" and angulo_seg_suave > limite:
            postura_segura = False

    return postura_segura, coords_postura, angulo_seg_suave


def extrair_coordenadas_bracos(keypoints_data, config_exercicio, melhor_lado):
    """Extrai coordenadas dos braços para visualização no frame."""
    if not config_exercicio.get("bracos"):
        return None

    b1_idx, b2_idx, b3_idx = config_exercicio["bracos"][melhor_lado]
    if keypoints_data[b1_idx][2] > 0.5 and keypoints_data[b2_idx][2] > 0.5:
        bp1 = keypoints_data[b1_idx][:2]
        bp2 = keypoints_data[b2_idx][:2]
        bp3 = keypoints_data[b3_idx][:2] if keypoints_data[b3_idx][2] > 0.5 else bp2
        return (bp1, bp2, bp3)
    return None


def calcular_assimetria(keypoints_data):
    """Extrai os dois cotovelos em simultâneo no formato COCO e calcula a assimetria.

    Retorna (angulo_esq, angulo_dir, alerta_assimetria).
    """
    indices = BRACO_ESQ + BRACO_DIR
    if any(keypoints_data[i][2] < 0.5 for i in indices):
        return None, None, False

    pts_esq = [keypoints_data[i][:2] for i in BRACO_ESQ]
    pts_dir = [keypoints_data[i][:2] for i in BRACO_DIR]
    angulo_esq = calcular_angulo(*pts_esq)
    angulo_dir = calcular_angulo(*pts_dir)
    alerta = abs(angulo_esq - angulo_dir) > LIMITE_ASSIMETRIA
    return angulo_esq, angulo_dir, alerta


def verificar_assimetria_bracos(landmarks_ou_keypoints):
    """Verifica se há assimetria muscular excessiva (> 25 graus) entre o braço esquerdo e direito.

    Suporta landmarks originais do MediaPipe (11, 13, 15 / 12, 14, 16) ou COCO.
    Retorna (assimetria_detectada, diferenca, angulo_esq, angulo_dir).
    """
    # Se receber 33 landmarks do MediaPipe
    if len(landmarks_ou_keypoints) >= 33:
        indices_bracos = [11, 13, 15, 12, 14, 16]
        coords_confs = {idx: _obter_coord_conf(landmarks_ou_keypoints[idx]) for idx in indices_bracos}
        if any(coords_confs[idx][1] <= 0.5 for idx in indices_bracos):
            return False, 0.0, None, None

        p_ombro_esq, p_cotovelo_esq, p_pulso_esq = (
            coords_confs[11][0], coords_confs[13][0], coords_confs[15][0]
        )
        p_ombro_dir, p_cotovelo_dir, p_pulso_dir = (
            coords_confs[12][0], coords_confs[14][0], coords_confs[16][0]
        )
    else:
        # Formato COCO (17 keypoints)
        indices_bracos = BRACO_ESQ + BRACO_DIR
        if any(landmarks_ou_keypoints[i][2] <= 0.5 for i in indices_bracos):
            return False, 0.0, None, None

        p_ombro_esq = landmarks_ou_keypoints[5][:2]
        p_cotovelo_esq = landmarks_ou_keypoints[7][:2]
        p_pulso_esq = landmarks_ou_keypoints[9][:2]
        p_ombro_dir = landmarks_ou_keypoints[6][:2]
        p_cotovelo_dir = landmarks_ou_keypoints[8][:2]
        p_pulso_dir = landmarks_ou_keypoints[10][:2]

    angulo_esq = calcular_angulo(p_ombro_esq, p_cotovelo_esq, p_pulso_esq)
    angulo_dir = calcular_angulo(p_ombro_dir, p_cotovelo_dir, p_pulso_dir)
    diferenca = abs(angulo_esq - angulo_dir)
    assimetria_detectada = diferenca > LIMITE_ASSIMETRIA_VOZ

    return assimetria_detectada, diferenca, angulo_esq, angulo_dir


def validar_postura_prancha(landmarks_ou_keypoints, filtros=None):
    """Valida a postura da Prancha Isométrica baseando-se no ângulo Ombro-Quadril-Tornozelo.

    Suporta landmarks originais do MediaPipe (33 pontos) ou formato COCO (17 pontos).
    Regra da Prancha:
    - Se o ângulo for >= 160°, postura correta (True).
    - Se o ângulo for < 160°, postura incorreta (False, quadril caiu).

    Retorna (postura_correta, angulo_suave, melhor_lado, (p1, p2, p3)) ou None se visibilidade insuficiente.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    lados_prancha = {"esq": (5, 11, 15), "dir": (6, 12, 16)}
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, lados_prancha)
    if not melhor_lado:
        return None

    p1 = keypoints_data[indices[0]][:2]  # Ombro
    p2 = keypoints_data[indices[1]][:2]  # Quadril
    p3 = keypoints_data[indices[2]][:2]  # Tornozelo

    angulo_bruto = calcular_angulo(p1, p2, p3)
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto

    postura_correta = angulo_suave >= 160.0
    return postura_correta, angulo_suave, melhor_lado, (p1, p2, p3)


def validar_postura_remada(keypoints_data, melhor_lado, filtros=None):
    """Valida a inclinação do tronco na Remada Curvada (Ombro-Quadril vs vertical).

    Garante que as costas não arredondem (> 75°) e que o tronco mantenha inclinação segura (>= 30°).
    Retorna (postura_segura, coords_postura, angulo_suave).
    """
    s1_idx = 5 if melhor_lado == "esq" else 6   # Ombro
    s2_idx = 11 if melhor_lado == "esq" else 12 # Quadril

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = keypoints_data[s1_idx][:2]
    sp2 = keypoints_data[s2_idx][:2]
    coords_postura = (sp1, sp2)
    sp3 = (sp2[0], sp2[1] - 50)  # Linha vertical imaginária

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = 30.0 <= angulo_suave <= 75.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_supino(keypoints_data, melhor_lado, filtros=None):
    """Valida a abertura dos cotovelos no Supino com Halteres (Quadril-Ombro-Cotovelo).

    Garante que os cotovelos não abram a mais de 90° em relação ao tronco para proteger os ombros.
    Retorna (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    c_idx = 7 if melhor_lado == "esq" else 8    # Cotovelo

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, o_idx, c_idx)):
        return True, None, None

    p_quadril = keypoints_data[q_idx][:2]
    p_ombro = keypoints_data[o_idx][:2]
    p_cotovelo = keypoints_data[c_idx][:2]
    coords_postura = (p_ombro, p_cotovelo)

    angulo_bruto = calcular_angulo(p_quadril, p_ombro, p_cotovelo)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 90.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_elevacao_lateral(keypoints_data, melhor_lado, filtros=None):
    """Valida a altura dos braços na Elevação Lateral (Quadril-Ombro-Cotovelo).

    Garante que os braços não passem da linha horizontal dos ombros (> 95°).
    Retorna (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    c_idx = 7 if melhor_lado == "esq" else 8    # Cotovelo

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, o_idx, c_idx)):
        return True, None, None

    p_quadril = keypoints_data[q_idx][:2]
    p_ombro = keypoints_data[o_idx][:2]
    p_cotovelo = keypoints_data[c_idx][:2]
    coords_postura = (p_ombro, p_cotovelo)

    angulo_bruto = calcular_angulo(p_quadril, p_ombro, p_cotovelo)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 95.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_elevacao_pelvica(keypoints_data, melhor_lado, filtros=None):
    """Valida o alinhamento da extensão na Elevação Pélvica (Ombro-Quadril-Joelho).

    Garante que não ocorra hiperextensão da coluna lombar no topo (> 185°).
    Retorna (postura_segura, coords_postura, angulo_suave).
    """
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    j_idx = 13 if melhor_lado == "esq" else 14  # Joelho

    if any(keypoints_data[i][2] <= 0.5 for i in (o_idx, q_idx, j_idx)):
        return True, None, None

    p_ombro = keypoints_data[o_idx][:2]
    p_quadril = keypoints_data[q_idx][:2]
    p_joelho = keypoints_data[j_idx][:2]
    coords_postura = (p_ombro, p_quadril)

    angulo_bruto = calcular_angulo(p_ombro, p_quadril, p_joelho)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 185.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_sumo(landmarks_ou_keypoints, melhor_lado=None, filtros=None):
    """Valida a postura do Agachamento Sumô verificando a largura da base dos pés.

    Regra do Sumô: A distância entre os tornozelos (MediaPipe 27 e 28 / COCO 15 e 16)
    deve ser maior que a distância entre os ombros (MediaPipe 11 e 12 / COCO 5 e 6).
    Retorna (postura_segura, coords_postura, diferenca_largura).
    """
    if len(landmarks_ou_keypoints) >= 33:
        p_oe, conf_oe = _obter_coord_conf(landmarks_ou_keypoints[11])
        p_od, conf_od = _obter_coord_conf(landmarks_ou_keypoints[12])
        p_te, conf_te = _obter_coord_conf(landmarks_ou_keypoints[27])
        p_td, conf_td = _obter_coord_conf(landmarks_ou_keypoints[28])
        if any(c < 0.5 for c in (conf_oe, conf_od, conf_te, conf_td)):
            return True, None, None
    else:
        kps = landmarks_ou_keypoints
        if any(kps[i][2] < 0.5 for i in (5, 6, 15, 16)):
            return True, None, None
        p_oe = kps[5][:2]
        p_od = kps[6][:2]
        p_te = kps[15][:2]
        p_td = kps[16][:2]

    dist_ombros = abs(p_oe[0] - p_od[0])
    dist_pes = abs(p_te[0] - p_td[0])

    diferenca = dist_pes - dist_ombros
    postura_segura = dist_pes > dist_ombros
    coords_postura = (p_te, p_td)
    return postura_segura, coords_postura, diferenca


def validar_barra_fixa(landmarks_ou_keypoints, melhor_lado=None, filtros=None):
    """Valida a conclusão da repetição na Barra Fixa baseando-se no alinhamento vertical.

    Regra da Barra Fixa: O nariz ou boca (landmarks 0 a 2) deve ultrapassar no eixo Y
    a altura dos pulsos (MediaPipe 15 e 16 / COCO 9 e 10) no topo do movimento.
    Retorna (queixo_acima, coords_visual, diferenca_y).
    """
    if len(landmarks_ou_keypoints) >= 33:
        p_nariz, conf_n = _obter_coord_conf(landmarks_ou_keypoints[0])
        p_pe, conf_pe = _obter_coord_conf(landmarks_ou_keypoints[15])
        p_pd, conf_pd = _obter_coord_conf(landmarks_ou_keypoints[16])
        if conf_n < 0.5 or (conf_pe < 0.5 and conf_pd < 0.5):
            return False, None, None
        pulsos_y = []
        if conf_pe >= 0.5: pulsos_y.append(p_pe[1])
        if conf_pd >= 0.5: pulsos_y.append(p_pd[1])
        y_barra = sum(pulsos_y) / len(pulsos_y)
        coords_visual = (p_nariz, (p_nariz[0], y_barra))
    else:
        kps = landmarks_ou_keypoints
        if kps[0][2] < 0.5 or (kps[9][2] < 0.5 and kps[10][2] < 0.5):
            return False, None, None
        p_nariz = kps[0][:2]
        pulsos_y = []
        if kps[9][2] >= 0.5: pulsos_y.append(kps[9][1])
        if kps[10][2] >= 0.5: pulsos_y.append(kps[10][1])
        y_barra = sum(pulsos_y) / len(pulsos_y)
        coords_visual = (p_nariz, (p_nariz[0], y_barra))

    # Menor Y no OpenCV indica posição verticalmente mais alta
    queixo_acima = p_nariz[1] <= y_barra
    diferenca_y = y_barra - p_nariz[1]
    return queixo_acima, coords_visual, diferenca_y


def calcular_calorias(tempo_segundos, met, peso_kg=70.0):
    """Calcula a estimativa de gasto calórico (kcal) a partir do MET e da duração.

    Fórmula: calorias = (tempo_segundos / 3600) * met * peso_kg
    """
    if tempo_segundos <= 0 or met <= 0 or peso_kg <= 0:
        return 0.0
    calorias = (tempo_segundos / 3600.0) * met * peso_kg
    return round(calorias, 2)

