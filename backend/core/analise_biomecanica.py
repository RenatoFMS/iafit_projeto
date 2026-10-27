# core/analise_biomecanica.py
"""Módulo de Análise Biomecânica do IAFit.

Responsável pela extração de coordenadas, cálculo de ângulos articulares,
avaliação de assimetria muscular e validação de regras posturais para os exercícios.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from core.math_utils import calcular_angulo, calcular_porcentagem

# Constantes e índices anatômicos (padrão COCO / YOLOv8-pose)
BRACO_ESQ: Tuple[int, int, int] = (5, 7, 9)   # Ombro, Cotovelo, Pulso esquerdos
BRACO_DIR: Tuple[int, int, int] = (6, 8, 10)  # Ombro, Cotovelo, Pulso direitos
LIMITE_ASSIMETRIA: int = 15  # Diferença angular para alerta visual (graus)
LIMITE_ASSIMETRIA_VOZ: int = 25  # Diferença angular para alerta sonoro (graus)

# Mapeamento MediaPipe (33 landmarks) -> índices COCO (17 keypoints)
_MP_PARA_COCO: List[int] = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


def _obter_coord_conf(landmark: Any) -> Tuple[Tuple[float, float], float]:
    """Extrai ((x, y), confianca) de um landmark MediaPipe, dicionário ou array.

    Suporta objetos MediaPipe (com atributos x, y, visibility/confidence),
    listas/tuplas [x, y, z, visibilidade] (33 pontos) ou [x, y, conf],
    e dicionários {'x': ..., 'y': ..., 'z': ..., 'visibilidade'/'visibility': ...}.

    Args:
        landmark: Objeto MediaPipe, sequência ou dicionário contendo coordenadas.

    Returns:
        Tupla contendo ((x, y), confianca).
    """
    if hasattr(landmark, 'x') and hasattr(landmark, 'y'):
        conf = getattr(landmark, 'visibility', getattr(landmark, 'confidence', 1.0))
        return (float(landmark.x), float(landmark.y)), float(conf)
    elif isinstance(landmark, (list, tuple)):
        if len(landmark) >= 4:
            conf = landmark[3]
        elif len(landmark) > 2:
            conf = landmark[2]
        else:
            conf = 1.0
        return (float(landmark[0]), float(landmark[1])), float(conf)
    elif isinstance(landmark, dict):
        conf = landmark.get(
            'visibilidade',
            landmark.get(
                'visibility',
                landmark.get(
                    'likelihood',
                    landmark.get('confidence', landmark.get('conf', 1.0)),
                ),
            ),
        )
        return (float(landmark.get('x', 0.0)), float(landmark.get('y', 0.0))), float(conf)
    return (0.0, 0.0), 0.0


def _obter_z(landmark: Any) -> float:
    """Extrai a coordenada de profundidade Z de um landmark (ou 0.0 se inexistente).

    Args:
        landmark: Objeto MediaPipe, sequência [x, y, z, visibilidade] ou dicionário.

    Returns:
        Coordenada Z como float (ou 0.0 caso não esteja disponível).
    """
    if hasattr(landmark, 'z'):
        return float(landmark.z)
    if isinstance(landmark, dict):
        return float(landmark.get('z', 0.0))
    if isinstance(landmark, (list, tuple)) and len(landmark) >= 4:
        return float(landmark[2])
    return 0.0


def _pt(keypoint: Sequence[float]) -> Tuple[float, ...]:
    """Devolve o ponto articular de um keypoint [x, y, conf(, z)].

    Retorna (x, y, z) se o keypoint tiver profundidade (MediaPipe) ou (x, y) caso contrário
    (YOLO/COCO), o que ativa automaticamente o cálculo 2D de fallback em calcular_angulo.

    Args:
        keypoint: Keypoint no formato [x, y, conf(, z)].

    Returns:
        Tupla com as coordenadas articulares (x, y, z) ou (x, y).
    """
    if len(keypoint) > 3:
        return (keypoint[0], keypoint[1], keypoint[3])
    return (keypoint[0], keypoint[1])


def _ponto_acima(ponto: Sequence[float], deslocamento: float = 50.0) -> Tuple[float, ...]:
    """Cria um ponto de referência vertical imaginário acima de `ponto` (mesma profundidade Z).

    Args:
        ponto: Ponto de referência articular (x, y[, z]).
        deslocamento: Deslocamento vertical em pixels acima do ponto (padrão: 50.0).

    Returns:
        Coordenadas do ponto vertical imaginário gerado.
    """
    if len(ponto) > 2:
        return (ponto[0], ponto[1] - deslocamento, ponto[2])
    return (ponto[0], ponto[1] - deslocamento)


def criar_detector_pose(
    static_image_mode: bool = False,
    model_complexity: int = 1,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.7
) -> Any:
    """Cria e retorna uma instância otimizada do MediaPipe Pose.

    Configurações para máxima performance em tempo real (CPU):
    - static_image_mode=False: ativa o rastreamento contínuo entre frames.
    - model_complexity=1: equilíbrio ideal entre velocidade e acurácia.
    - min_detection_confidence=0.5: limiar de confiança para detecção inicial.
    - min_tracking_confidence=0.7: rastreamento robusto para evitar perda do corpo.

    Args:
        static_image_mode: Se True, trata cada imagem de forma estática independente.
        model_complexity: Complexidade do modelo Pose (0, 1 ou 2).
        min_detection_confidence: Confiança mínima para detecção inicial.
        min_tracking_confidence: Confiança mínima para rastreamento de pose.

    Returns:
        Instância inicializada de mediapipe.solutions.pose.Pose.
    """
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    return mp_pose.Pose(
        static_image_mode=static_image_mode,
        model_complexity=model_complexity,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )


def _normalizar_entrada_landmarks(landmarks: Any) -> Any:
    """Normaliza um dicionário JSON de landmarks numa lista indexada de 33 pontos.

    Args:
        landmarks: Lista, tupla, dicionário ou coleção de landmarks.

    Returns:
        Sequência indexável de landmarks.
    """
    if isinstance(landmarks, dict):
        if "landmarks" in landmarks:
            landmarks = landmarks["landmarks"]
        elif "pontos" in landmarks:
            landmarks = landmarks["pontos"]
        else:
            return [
                landmarks.get(
                    i,
                    landmarks.get(
                        str(i),
                        {"x": 0.0, "y": 0.0, "z": 0.0, "visibilidade": 0.0},
                    ),
                )
                for i in range(33)
            ]
    return landmarks


def landmarks_mediapipe_para_keypoints(
    landmarks: Any,
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[List[float]]:
    """Converte landmarks (33 pontos MediaPipe/ML Kit em objeto, dict ou array) para COCO (17 pontos).

    A confiança permanece no índice 2 (compatível com o formato COCO [x, y, conf]); a profundidade
    z é anexada no índice 3.
    Quando as coordenadas recebidas estão normalizadas em [0, 1], aplica a escala (largura, altura)
    fornecida ou a escala de referência (640x480) para preservar as proporções geométricas.
    Se os landmarks já estiverem no formato COCO (17 pontos), retorna-os diretamente.

    Args:
        landmarks: Lista/dicionário de 33 landmarks ou lista pré-existente de 17 keypoints COCO.
        largura: Largura da imagem em pixels para desnormalização (opcional).
        altura: Altura da imagem em pixels para desnormalização (opcional).

    Returns:
        Lista de 17 keypoints no formato [x, y, confianca, z].
    """
    if landmarks is None:
        return []
    landmarks = _normalizar_entrada_landmarks(landmarks)
    if len(landmarks) == 0:
        return []
    if len(landmarks) == 17 and isinstance(landmarks[0], (list, tuple)) and not hasattr(landmarks[0], 'x'):
        return list(landmarks)
    if len(landmarks) < 29:
        return []

    coords_extraidas: List[Tuple[float, float, float, float]] = []
    todos_normalizados = True
    for i in _MP_PARA_COCO:
        (x, y), conf = _obter_coord_conf(landmarks[i])
        z = _obter_z(landmarks[i])
        if conf > 0.0 and not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            todos_normalizados = False
        coords_extraidas.append((x, y, conf, z))

    largura_escala = float(largura) if largura is not None else (640.0 if todos_normalizados else 1.0)
    altura_escala = float(altura) if altura is not None else (480.0 if todos_normalizados else 1.0)

    kps: List[List[float]] = []
    for x, y, conf, z in coords_extraidas:
        if todos_normalizados:
            x = x * largura_escala
            y = y * altura_escala
            z = z * largura_escala
        kps.append([x, y, conf, z])
    return kps


def selecionar_melhor_lado(
    keypoints_data: Sequence[Sequence[float]],
    lados_config: Dict[str, Sequence[int]]
) -> Tuple[Optional[str], Optional[Sequence[int]]]:
    """Seleciona o lado ('esq' ou 'dir') que apresenta maior grau de confiança visual.

    Args:
        keypoints_data: Dados dos keypoints articulares no formato [x, y, conf, ...].
        lados_config: Dicionário associando identificador de lado aos índices anatômicos.

    Returns:
        Tupla (melhor_lado, indices) ou (None, None) se a visibilidade for insuficiente.
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


def calcular_amplitude_movimento(
    keypoints_data: Sequence[Sequence[float]],
    config_exercicio: Dict[str, Any],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[int, float, Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]]]:
    """Calcula o ângulo articular do movimento principal e a porcentagem de execução (0-100%).

    Args:
        keypoints_data: Dados dos keypoints articulares no frame atual.
        config_exercicio: Dicionário com a configuração biomecânica do exercício.
        melhor_lado: Lado anatômico com maior visibilidade selecionado ('esq' ou 'dir').
        filtros: Dicionário com filtros de suavização de amplitude (opcional).

    Returns:
        Tupla contendo (porcentagem, angulo_suave, (ponto1, ponto2, ponto3)).
    """
    p1_idx, p2_idx, p3_idx = config_exercicio["lados"][melhor_lado]
    p1 = _pt(keypoints_data[p1_idx])
    p2 = _pt(keypoints_data[p2_idx])
    p3 = _pt(keypoints_data[p3_idx])

    angulo_bruto = calcular_angulo(p1, p2, p3)
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto
    porc = calcular_porcentagem(angulo_suave, config_exercicio["inicio"], config_exercicio["fim"])

    return porc, angulo_suave, (p1, p2, p3)


def log_calibracao_desenvolvimento(
    keypoints_data: Optional[Sequence[Sequence[float]]],
    fase: str,
    porc: int = 0,
    reps: int = 0,
    melhor_lado: Optional[str] = None,
    angulo_suave: Optional[float] = None,
    angulo_tronco: Optional[float] = None,
) -> None:
    """Imprime temporariamente no terminal a fase e os ângulos de cotovelos/ombros em tempo real.

    Auxilia na calibração empírica dos limiares ('inicio', 'fim' e 'limite_postura')
    do exercício Desenvolvimento de Ombros em config_exercicios.py.

    Args:
        keypoints_data: Lista de 17 keypoints COCO [x, y, conf(, z)] do frame atual.
        fase: Nome da fase atual ('calibracao', 'fora', 'base', 'subida', 'topo', 'descida').
        porc: Percentual atual de execução (ou progresso de calibração).
        reps: Total acumulado de repetições na série.
        melhor_lado: Lado ativo selecionado pelo motor ('esq' ou 'dir').
        angulo_suave: Ângulo principal suavizado usado pelo contador (opcional).
        angulo_tronco: Ângulo de inclinação vertical do tronco (opcional).
    """
    def _calc_tripla(i1: int, i2: int, i3: int, limiar: float = 0.2) -> str:
        if not keypoints_data or len(keypoints_data) <= max(i1, i2, i3):
            return "  N/D "
        if (
            keypoints_data[i1][2] < limiar
            or keypoints_data[i2][2] < limiar
            or keypoints_data[i3][2] < limiar
        ):
            return "  N/D "
        ang = calcular_angulo(
            _pt(keypoints_data[i1]),
            _pt(keypoints_data[i2]),
            _pt(keypoints_data[i3]),
        )
        return f"{ang:5.1f}°"

    cot_esq = _calc_tripla(5, 7, 9)    # Ombro Esq - Cotovelo Esq - Pulso Esq
    cot_dir = _calc_tripla(6, 8, 10)   # Ombro Dir - Cotovelo Dir - Pulso Dir
    omb_esq = _calc_tripla(11, 5, 7)   # Quadril Esq - Ombro Esq - Cotovelo Esq
    omb_dir = _calc_tripla(12, 6, 8)   # Quadril Dir - Ombro Dir - Cotovelo Dir

    if angulo_tronco is not None:
        tronco_str = f"{angulo_tronco:5.1f}°"
    elif keypoints_data and len(keypoints_data) > 12:
        lado_ref = (5, 11) if keypoints_data[5][2] >= keypoints_data[6][2] else (6, 12)
        if keypoints_data[lado_ref[0]][2] >= 0.2 and keypoints_data[lado_ref[1]][2] >= 0.2:
            sp1 = _pt(keypoints_data[lado_ref[0]])
            sp2 = _pt(keypoints_data[lado_ref[1]])
            ang_t = calcular_angulo(sp1, sp2, _ponto_acima(sp2))
            tronco_str = f"{ang_t:5.1f}°"
        else:
            tronco_str = "  N/D "
    else:
        tronco_str = "  N/D "

    suave_str = (
        f" (Suave {melhor_lado}: {angulo_suave:5.1f}°)"
        if angulo_suave is not None and melhor_lado
        else ""
    )

    print(
        f"[DESENVOLVIMENTO] Fase: {fase:<10} | Porc: {porc:3d}% | Reps: {reps:2d} "
        f"| Cotovelo(E/D): {cot_esq} / {cot_dir}{suave_str} "
        f"| Ombro(E/D): {omb_esq} / {omb_dir} "
        f"| Tronco: {tronco_str}",
        flush=True,
    )


def analisar_seguranca_postura(
    keypoints_data: Sequence[Sequence[float]],
    config_exercicio: Dict[str, Any],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], ...]], Optional[float]]:
    """Avalia o alinhamento corporal e a segurança da postura segundo a configuração do exercício.

    Args:
        keypoints_data: Dados de keypoints articulares no frame atual.
        config_exercicio: Dicionário com configurações e regras do exercício.
        melhor_lado: Lado anatômico com maior visibilidade selecionado ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_seguranca_suavizado).
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
    elif "Elevacao Frontal" in nome:
        return validar_postura_elevacao_frontal(keypoints_data, melhor_lado, filtros)
    elif "Triceps Testa" in nome:
        return validar_postura_triceps_testa(keypoints_data, melhor_lado, filtros)
    elif "Crucifixo" in nome:
        return validar_postura_crucifixo(keypoints_data, melhor_lado, filtros)
    elif "Stiff Unilateral" in nome:
        return validar_postura_stiff_unilateral(keypoints_data, melhor_lado, filtros)
    elif "Panturrilha" in nome:
        return validar_postura_panturrilha(keypoints_data, melhor_lado, filtros)
    elif "Bulgaro" in nome or "Búlgaro" in nome:
        return validar_postura_bulgaro(keypoints_data, melhor_lado, filtros)
    elif "Encolhimento" in nome:
        return validar_postura_encolhimento(keypoints_data, melhor_lado, filtros)
    elif "Abdominal Infra" in nome:
        return validar_postura_abdominal_infra(keypoints_data, melhor_lado, filtros)
    elif "Remada Alta" in nome:
        return validar_postura_remada_alta(keypoints_data, melhor_lado, filtros)
    elif "Bom Dia" in nome:
        return validar_postura_bom_dia(keypoints_data, melhor_lado, filtros)
    elif "Triceps Coice" in nome:
        return validar_postura_triceps_coice(keypoints_data, melhor_lado, filtros)

    if not config_exercicio.get("postura"):
        return postura_segura, coords_postura, angulo_seg_suave

    s1_idx, s2_idx = config_exercicio["postura"][melhor_lado][:2]
    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return postura_segura, coords_postura, angulo_seg_suave

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)

    ponto3_valido = True
    if config_exercicio.get("postura_vertical"):
        # Cria uma linha vertical imaginária 50 pixels acima do ponto de apoio
        sp3 = _ponto_acima(sp2)
    else:
        s3_idx = config_exercicio["postura"][melhor_lado][2]
        if keypoints_data[s3_idx][2] > 0.5:
            sp3 = _pt(keypoints_data[s3_idx])
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


def extrair_coordenadas_bracos(
    keypoints_data: Sequence[Sequence[float]],
    config_exercicio: Dict[str, Any],
    melhor_lado: str
) -> Optional[Tuple[Tuple[float, ...], ...]]:
    """Extrai coordenadas dos braços para visualização no frame.

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        config_exercicio: Dicionário com mapeamento anatômico do exercício.
        melhor_lado: Lado de melhor enquadramento ('esq' ou 'dir').

    Returns:
        Tupla com as coordenadas dos pontos articulares dos braços ou None.
    """
    if not config_exercicio.get("bracos"):
        return None

    b1_idx, b2_idx, b3_idx = config_exercicio["bracos"][melhor_lado]
    if keypoints_data[b1_idx][2] > 0.5 and keypoints_data[b2_idx][2] > 0.5:
        bp1 = _pt(keypoints_data[b1_idx])
        bp2 = _pt(keypoints_data[b2_idx])
        bp3 = _pt(keypoints_data[b3_idx]) if keypoints_data[b3_idx][2] > 0.5 else bp2
        return (bp1, bp2, bp3)
    return None


def calcular_assimetria(
    keypoints_data: Sequence[Sequence[float]]
) -> Tuple[Optional[float], Optional[float], bool]:
    """Extrai os dois cotovelos em simultâneo no formato COCO e calcula a assimetria.

    Args:
        keypoints_data: Keypoints articulares detectados no frame.

    Returns:
        Tupla (angulo_esq, angulo_dir, alerta_assimetria).
    """
    indices = BRACO_ESQ + BRACO_DIR
    if any(keypoints_data[i][2] < 0.5 for i in indices):
        return None, None, False

    pts_esq = [_pt(keypoints_data[i]) for i in BRACO_ESQ]
    pts_dir = [_pt(keypoints_data[i]) for i in BRACO_DIR]
    angulo_esq = calcular_angulo(*pts_esq)
    angulo_dir = calcular_angulo(*pts_dir)
    alerta = abs(angulo_esq - angulo_dir) > LIMITE_ASSIMETRIA
    return angulo_esq, angulo_dir, alerta


def verificar_assimetria_bracos(
    landmarks_ou_keypoints: Any
) -> Tuple[bool, float, Optional[float], Optional[float]]:
    """Verifica se há assimetria muscular excessiva (> 25 graus) entre o braço esquerdo e direito.

    Suporta landmarks originais do MediaPipe (11, 13, 15 / 12, 14, 16) ou COCO.

    Args:
        landmarks_ou_keypoints: Coleção de landmarks do MediaPipe ou lista de keypoints.

    Returns:
        Tupla (assimetria_detectada, diferenca_angular, angulo_esq, angulo_dir).
    """
    # Se receber 33 landmarks do MediaPipe
    if len(landmarks_ou_keypoints) >= 33:
        indices_bracos = [11, 13, 15, 12, 14, 16]
        coords_confs = {idx: _obter_coord_conf(landmarks_ou_keypoints[idx]) for idx in indices_bracos}
        if any(coords_confs[idx][1] <= 0.5 for idx in indices_bracos):
            return False, 0.0, None, None

        def _xyz(idx: int) -> Tuple[float, ...]:
            (x, y), _ = coords_confs[idx]
            return (x, y, _obter_z(landmarks_ou_keypoints[idx]))

        p_ombro_esq, p_cotovelo_esq, p_pulso_esq = _xyz(11), _xyz(13), _xyz(15)
        p_ombro_dir, p_cotovelo_dir, p_pulso_dir = _xyz(12), _xyz(14), _xyz(16)
    else:
        # Formato COCO (17 keypoints)
        indices_bracos = BRACO_ESQ + BRACO_DIR
        if any(landmarks_ou_keypoints[i][2] <= 0.5 for i in indices_bracos):
            return False, 0.0, None, None

        p_ombro_esq = _pt(landmarks_ou_keypoints[5])
        p_cotovelo_esq = _pt(landmarks_ou_keypoints[7])
        p_pulso_esq = _pt(landmarks_ou_keypoints[9])
        p_ombro_dir = _pt(landmarks_ou_keypoints[6])
        p_cotovelo_dir = _pt(landmarks_ou_keypoints[8])
        p_pulso_dir = _pt(landmarks_ou_keypoints[10])

    angulo_esq = calcular_angulo(p_ombro_esq, p_cotovelo_esq, p_pulso_esq)
    angulo_dir = calcular_angulo(p_ombro_dir, p_cotovelo_dir, p_pulso_dir)
    diferenca = abs(angulo_esq - angulo_dir)
    assimetria_detectada = diferenca > LIMITE_ASSIMETRIA_VOZ

    return assimetria_detectada, diferenca, angulo_esq, angulo_dir


def validar_postura_prancha(
    landmarks_ou_keypoints: Any,
    filtros: Optional[Dict[str, Any]] = None
) -> Optional[Tuple[bool, float, str, Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]]]]:
    """Valida a postura da Prancha Isométrica baseando-se no ângulo Ombro-Quadril-Tornozelo.

    Suporta landmarks originais do MediaPipe (33 pontos) ou formato COCO (17 pontos).
    Regra da Prancha:
    - Se o ângulo for >= 160°, postura correta (True).
    - Se o ângulo for < 160°, postura incorreta (False, quadril caiu).

    Args:
        landmarks_ou_keypoints: Landmarks do MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo instâncias de FiltroSuavizacao (opcional).

    Returns:
        Tupla (postura_correta, angulo_suave, melhor_lado, (p1, p2, p3)) ou None se insuficiente.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    lados_prancha = {"esq": (5, 11, 15), "dir": (6, 12, 16)}
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, lados_prancha)
    if not melhor_lado:
        return None

    p1 = _pt(keypoints_data[indices[0]])  # Ombro
    p2 = _pt(keypoints_data[indices[1]])  # Quadril
    p3 = _pt(keypoints_data[indices[2]])  # Tornozelo

    angulo_bruto = calcular_angulo(p1, p2, p3)
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto

    postura_correta = angulo_suave >= 160.0
    return postura_correta, angulo_suave, melhor_lado, (p1, p2, p3)


def validar_postura_remada(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a inclinação do tronco na Remada Curvada (Ombro-Quadril vs vertical).

    Garante que as costas não arredondem (> 75°) e que o tronco mantenha inclinação segura (>= 30°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    s1_idx = 5 if melhor_lado == "esq" else 6   # Ombro
    s2_idx = 11 if melhor_lado == "esq" else 12 # Quadril

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)
    sp3 = _ponto_acima(sp2)  # Linha vertical imaginária

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = 30.0 <= angulo_suave <= 75.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_supino(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a abertura dos cotovelos no Supino com Halteres (Quadril-Ombro-Cotovelo).

    Garante que os cotovelos não abram a mais de 90° em relação ao tronco para proteger os ombros.

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    c_idx = 7 if melhor_lado == "esq" else 8    # Cotovelo

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, o_idx, c_idx)):
        return True, None, None

    p_quadril = _pt(keypoints_data[q_idx])
    p_ombro = _pt(keypoints_data[o_idx])
    p_cotovelo = _pt(keypoints_data[c_idx])
    coords_postura = (p_ombro, p_cotovelo)

    angulo_bruto = calcular_angulo(p_quadril, p_ombro, p_cotovelo)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 90.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_elevacao_lateral(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a altura dos braços na Elevação Lateral (Quadril-Ombro-Cotovelo).

    Garante que os braços não passem da linha horizontal dos ombros (> 95°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    c_idx = 7 if melhor_lado == "esq" else 8    # Cotovelo

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, o_idx, c_idx)):
        return True, None, None

    p_quadril = _pt(keypoints_data[q_idx])
    p_ombro = _pt(keypoints_data[o_idx])
    p_cotovelo = _pt(keypoints_data[c_idx])
    coords_postura = (p_ombro, p_cotovelo)

    angulo_bruto = calcular_angulo(p_quadril, p_ombro, p_cotovelo)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 95.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_elevacao_pelvica(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida o alinhamento da extensão na Elevação Pélvica (Ombro-Quadril-Joelho).

    Garante que não ocorra hiperextensão da coluna lombar no topo (> 185°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    j_idx = 13 if melhor_lado == "esq" else 14  # Joelho

    if any(keypoints_data[i][2] <= 0.5 for i in (o_idx, q_idx, j_idx)):
        return True, None, None

    p_ombro = _pt(keypoints_data[o_idx])
    p_quadril = _pt(keypoints_data[q_idx])
    p_joelho = _pt(keypoints_data[j_idx])
    coords_postura = (p_ombro, p_quadril)

    angulo_bruto = calcular_angulo(p_ombro, p_quadril, p_joelho)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 185.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_sumo(
    landmarks_ou_keypoints: Any,
    melhor_lado: Optional[str] = None,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a postura do Agachamento Sumô verificando a largura da base dos pés.

    Regra do Sumô: A distância entre os tornozelos (MediaPipe 27 e 28 / COCO 15 e 16)
    deve ser maior que a distância entre os ombros (MediaPipe 11 e 12 / COCO 5 e 6).

    Args:
        landmarks_ou_keypoints: Landmarks do MediaPipe ou keypoints COCO.
        melhor_lado: Lado anatômico preferencial (opcional).
        filtros: Dicionário contendo filtros de suavização (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, diferenca_largura).
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
        p_oe = _pt(kps[5])
        p_od = _pt(kps[6])
        p_te = _pt(kps[15])
        p_td = _pt(kps[16])

    dist_ombros = abs(p_oe[0] - p_od[0])
    dist_pes = abs(p_te[0] - p_td[0])

    diferenca = dist_pes - dist_ombros
    postura_segura = dist_pes > dist_ombros
    coords_postura = (p_te, p_td)
    return postura_segura, coords_postura, diferenca


def validar_barra_fixa(
    landmarks_ou_keypoints: Any,
    melhor_lado: Optional[str] = None,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a conclusão da repetição na Barra Fixa baseando-se no alinhamento vertical.

    Regra da Barra Fixa: O nariz ou boca (landmarks 0 a 2) deve ultrapassar no eixo Y
    a altura dos pulsos (MediaPipe 15 e 16 / COCO 9 e 10) no topo do movimento.

    Args:
        landmarks_ou_keypoints: Landmarks do MediaPipe ou keypoints COCO.
        melhor_lado: Lado anatômico preferencial (opcional).
        filtros: Dicionário contendo filtros de suavização (opcional).

    Returns:
        Tupla (queixo_acima, coords_visual, diferenca_y).
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
        p_nariz = _pt(kps[0])
        pulsos_y = []
        if kps[9][2] >= 0.5: pulsos_y.append(kps[9][1])
        if kps[10][2] >= 0.5: pulsos_y.append(kps[10][1])
        y_barra = sum(pulsos_y) / len(pulsos_y)
        coords_visual = (p_nariz, (p_nariz[0], y_barra))

    # Menor Y no OpenCV indica posição verticalmente mais alta
    queixo_acima = p_nariz[1] <= y_barra
    diferenca_y = y_barra - p_nariz[1]
    return queixo_acima, coords_visual, diferenca_y


def validar_postura_prancha_lateral(
    landmarks_ou_keypoints: Any,
    filtros: Optional[Dict[str, Any]] = None
) -> Optional[Tuple[bool, float, str, Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]]]]:
    """Valida a postura da Prancha Lateral baseando-se no ângulo Ombro-Quadril-Tornozelo.

    Regra da Prancha Lateral:
    - Se o ângulo for >= 160°, postura correta (True).
    - Se o ângulo for < 160°, postura incorreta (False, quadril caiu lateralmente).

    Args:
        landmarks_ou_keypoints: Landmarks do MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo filtros de suavização (opcional).

    Returns:
        Tupla (postura_correta, angulo_suave, melhor_lado, (p1, p2, p3)) ou None se insuficiente.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    lados_prancha = {"esq": (5, 11, 15), "dir": (6, 12, 16)}
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, lados_prancha)
    if not melhor_lado:
        return None

    p1 = _pt(keypoints_data[indices[0]])  # Ombro
    p2 = _pt(keypoints_data[indices[1]])  # Quadril
    p3 = _pt(keypoints_data[indices[2]])  # Tornozelo

    angulo_bruto = calcular_angulo(p1, p2, p3)
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto

    postura_correta = angulo_suave >= 160.0
    return postura_correta, angulo_suave, melhor_lado, (p1, p2, p3)


def validar_postura_elevacao_frontal(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a estabilidade do tronco na Elevação Frontal (Ombro-Quadril-Tornozelo).

    Garante que o tronco não balance para trás (< 165°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    o_idx = 5 if melhor_lado == "esq" else 6
    q_idx = 11 if melhor_lado == "esq" else 12
    t_idx = 15 if melhor_lado == "esq" else 16

    if any(keypoints_data[i][2] <= 0.5 for i in (o_idx, q_idx, t_idx)):
        return True, None, None

    sp1 = _pt(keypoints_data[o_idx])
    sp2 = _pt(keypoints_data[q_idx])
    sp3 = _pt(keypoints_data[t_idx])
    coords_postura = (sp1, sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave >= 165.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_triceps_testa(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida o alinhamento dos braços no Tríceps Testa (Quadril-Ombro-Cotovelo).

    Garante que os cotovelos permaneçam travados e alinhados (ângulo <= 110°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12
    o_idx = 5 if melhor_lado == "esq" else 6
    c_idx = 7 if melhor_lado == "esq" else 8

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, o_idx, c_idx)):
        return True, None, None

    sp1 = _pt(keypoints_data[q_idx])
    sp2 = _pt(keypoints_data[o_idx])
    sp3 = _pt(keypoints_data[c_idx])
    coords_postura = (sp2, sp3)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 110.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_crucifixo(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida que os cotovelos não hiperestendam no Crucifixo (Ombro-Cotovelo-Pulso <= 165°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    o_idx = 5 if melhor_lado == "esq" else 6
    c_idx = 7 if melhor_lado == "esq" else 8
    p_idx = 9 if melhor_lado == "esq" else 10

    if any(keypoints_data[i][2] <= 0.5 for i in (o_idx, c_idx, p_idx)):
        return True, None, None

    sp1 = _pt(keypoints_data[o_idx])
    sp2 = _pt(keypoints_data[c_idx])
    sp3 = _pt(keypoints_data[p_idx])
    coords_postura = (sp1, sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 165.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_stiff_unilateral(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a inclinação lombar no Stiff Unilateral (Ombro-Quadril vs vertical <= 75°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    s1_idx = 5 if melhor_lado == "esq" else 6
    s2_idx = 11 if melhor_lado == "esq" else 12

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)
    sp3 = _ponto_acima(sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 75.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_panturrilha(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a extensão dos joelhos na Panturrilha em Pé (Quadril-Joelho-Tornozelo >= 160°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12
    j_idx = 13 if melhor_lado == "esq" else 14
    t_idx = 15 if melhor_lado == "esq" else 16

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, j_idx, t_idx)):
        return True, None, None

    sp1 = _pt(keypoints_data[q_idx])
    sp2 = _pt(keypoints_data[j_idx])
    sp3 = _pt(keypoints_data[t_idx])
    coords_postura = (sp1, sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave >= 160.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_bulgaro(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a inclinação do tronco no Agachamento Búlgaro (Ombro-Quadril vs vertical <= 45°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    s1_idx = 5 if melhor_lado == "esq" else 6
    s2_idx = 11 if melhor_lado == "esq" else 12

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)
    sp3 = _ponto_acima(sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 45.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_encolhimento(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a postura ereta no Encolhimento de Ombros (Ombro-Quadril vs vertical <= 20°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    s1_idx = 5 if melhor_lado == "esq" else 6
    s2_idx = 11 if melhor_lado == "esq" else 12

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)
    sp3 = _ponto_acima(sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 20.0
    return postura_segura, coords_postura, angulo_suave


def calcular_calorias(
    tempo_segundos: float,
    met: float,
    peso_kg: float = 70.0
) -> float:
    """Calcula a estimativa de gasto calórico (kcal) a partir do MET e da duração.

    Fórmula: calorias = (tempo_segundos / 3600) * met * peso_kg

    Args:
        tempo_segundos: Duração da execução do exercício em segundos.
        met: Equivalente metabólico da tarefa (MET) do exercício.
        peso_kg: Peso corporal do utilizador em quilogramas (padrão: 70.0).

    Returns:
        Gasto calórico estimado em quilocalorias (kcal) arredondado a 2 casas decimais.
    """
    if tempo_segundos <= 0 or met <= 0 or peso_kg <= 0:
        return 0.0
    calorias = (tempo_segundos / 3600.0) * met * peso_kg
    return round(calorias, 2)


def verificar_fora_enquadramento(
    keypoints_data: Any,
    config_exercicio: Dict[str, Any]
) -> bool:
    """Verifica se landmarks existem e se a visibilidade dos pontos principais é < 0.3.

    Args:
        keypoints_data: Dados de keypoints ou landmarks no frame atual.
        config_exercicio: Dicionário de configuração com os lados e articulações alvo.

    Returns:
        True se o usuário saiu do enquadramento ou não foi detectado, False caso contrário.
    """
    if keypoints_data is None or len(keypoints_data) == 0:
        return True

    # Suporta se receber landmarks (33 pontos em objeto, dicionário ou array) diretamente
    if (
        isinstance(keypoints_data, dict)
        or hasattr(keypoints_data[0], 'x')
        or isinstance(keypoints_data[0], dict)
        or len(keypoints_data) >= 33
    ):
        keypoints_data = landmarks_mediapipe_para_keypoints(keypoints_data)
    if not keypoints_data:
        return True

    nome = config_exercicio.get("nome", "")
    if "Polichinelo" in nome:
        # Pontos principais do polichinelo: ombros (5, 6), pulsos (9, 10), tornozelos (15, 16)
        pontos_obrigatorios = [5, 6, 9, 10, 15, 16]
        for p in pontos_obrigatorios:
            if p >= len(keypoints_data) or keypoints_data[p][2] < 0.3:
                return True
        return False

    lados = config_exercicio.get("lados", {})
    if not lados:
        confs = [kp[2] for kp in keypoints_data if len(kp) > 2]
        return not confs or (sum(confs) / len(confs)) < 0.3

    # Verifica se há pelo menos um lado onde TODOS os pontos principais tenham confiança >= 0.3
    lado_valido = False
    for indices in lados.values():
        if all(idx < len(keypoints_data) and keypoints_data[idx][2] >= 0.3 for idx in indices):
            lado_valido = True
            break

    return not lado_valido


def validar_postura_abdominal_infra(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a postura no Abdominal Infra (joelhos estendidos >= 130°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12
    j_idx = 13 if melhor_lado == "esq" else 14
    t_idx = 15 if melhor_lado == "esq" else 16

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, j_idx, t_idx)):
        return True, None, None

    sp1 = _pt(keypoints_data[q_idx])
    sp2 = _pt(keypoints_data[j_idx])
    sp3 = _pt(keypoints_data[t_idx])
    coords_postura = (sp1, sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave >= 130.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_remada_alta(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a postura ereta na Remada Alta (Ombro-Quadril vs vertical <= 25°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    s1_idx = 5 if melhor_lado == "esq" else 6
    s2_idx = 11 if melhor_lado == "esq" else 12

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)
    sp3 = _ponto_acima(sp2)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave <= 25.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_bom_dia(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida as pernas retas no exercício Bom Dia (Quadril-Joelho-Tornozelo >= 150°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12
    j_idx = 13 if melhor_lado == "esq" else 14
    t_idx = 15 if melhor_lado == "esq" else 16

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, j_idx, t_idx)):
        return True, None, None

    sp1 = _pt(keypoints_data[q_idx])
    sp2 = _pt(keypoints_data[j_idx])
    sp3 = _pt(keypoints_data[t_idx])
    coords_postura = (sp2, sp3)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave >= 150.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_triceps_coice(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Valida a altura do cotovelo no Tríceps Coice (Quadril-Ombro-Cotovelo >= 25°).

    Args:
        keypoints_data: Keypoints articulares detectados no frame.
        melhor_lado: Lado anatômico com maior visibilidade ('esq' ou 'dir').
        filtros: Dicionário de filtros de postura (opcional).

    Returns:
        Tupla (postura_segura, coords_postura, angulo_suave).
    """
    q_idx = 11 if melhor_lado == "esq" else 12
    o_idx = 5 if melhor_lado == "esq" else 6
    c_idx = 7 if melhor_lado == "esq" else 8

    if any(keypoints_data[i][2] <= 0.5 for i in (q_idx, o_idx, c_idx)):
        return True, None, None

    sp1 = _pt(keypoints_data[q_idx])
    sp2 = _pt(keypoints_data[o_idx])
    sp3 = _pt(keypoints_data[c_idx])
    coords_postura = (sp2, sp3)

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    postura_segura = angulo_suave >= 25.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_agachamento_isometrico(
    landmarks_ou_keypoints: Any,
    filtros: Optional[Dict[str, Any]] = None
) -> Optional[Tuple[bool, float, str, Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]], str]]:
    """Valida a postura do Agachamento Isométrico (ângulo Joelho ~90°: entre 75° e 105°).

    Args:
        landmarks_ou_keypoints: Landmarks do MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo filtros de amplitude (opcional).

    Returns:
        Tupla (postura_correta, angulo_suave, melhor_lado, (p1, p2, p3), msg_correcao) ou None.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    lados_joelho = {"esq": (11, 13, 15), "dir": (12, 14, 16)}
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, lados_joelho)
    if not melhor_lado:
        return None

    p1 = _pt(keypoints_data[indices[0]])  # Quadril
    p2 = _pt(keypoints_data[indices[1]])  # Joelho
    p3 = _pt(keypoints_data[indices[2]])  # Tornozelo

    angulo_bruto = calcular_angulo(p1, p2, p3)
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto

    if 75.0 <= angulo_suave <= 105.0:
        postura_correta = True
        msg_correcao = ""
    elif angulo_suave > 105.0:
        postura_correta = False
        msg_correcao = "Desca mais o quadril"
    else:
        postura_correta = False
        msg_correcao = "Suba um pouco o quadril"

    return postura_correta, angulo_suave, melhor_lado, (p1, p2, p3), msg_correcao


def validar_polichinelo(
    landmarks_ou_keypoints: Any,
    filtros: Optional[Dict[str, Any]] = None
) -> Optional[Tuple[int, bool, Tuple[Tuple[float, ...], Tuple[float, ...]], Tuple[Tuple[float, ...], Tuple[float, ...]], str]]:
    """Calcula porcentagem de execução e validação do Polichinelo.

    Lógica mista: braços sobem no eixo Y e pernas abrem na distância dos tornozelos.

    Args:
        landmarks_ou_keypoints: Landmarks do MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo filtros de amplitude (opcional).

    Returns:
        Tupla (porc, postura_segura, coords_bracos, coords_pernas, msg_erro) ou None se invisível.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    pontos_obrigatorios = [5, 6, 9, 10, 11, 12, 15, 16]
    if any(p >= len(keypoints_data) or keypoints_data[p][2] < 0.3 for p in pontos_obrigatorios):
        return None

    p_ombro_esq, p_ombro_dir = _pt(keypoints_data[5]), _pt(keypoints_data[6])
    p_pulso_esq, p_pulso_dir = _pt(keypoints_data[9]), _pt(keypoints_data[10])
    p_quadril_esq, p_quadril_dir = _pt(keypoints_data[11]), _pt(keypoints_data[12])
    p_tornozelo_esq, p_tornozelo_dir = _pt(keypoints_data[15]), _pt(keypoints_data[16])

    larg_ombros = max(20.0, abs(p_ombro_dir[0] - p_ombro_esq[0]))
    y_ombros = (p_ombro_esq[1] + p_ombro_dir[1]) / 2.0
    y_quadril = (p_quadril_esq[1] + p_quadril_dir[1]) / 2.0
    y_pulsos = (p_pulso_esq[1] + p_pulso_dir[1]) / 2.0

    # 1. Porcentagem braços
    altura_mov_bracos = max(1.0, y_quadril - (y_ombros - larg_ombros * 0.5))
    porc_bracos = max(0.0, min(100.0, ((y_quadril - y_pulsos) / altura_mov_bracos) * 100.0))

    # 2. Porcentagem pernas
    dist_tornozelos = abs(p_tornozelo_dir[0] - p_tornozelo_esq[0])
    abertura_min = larg_ombros * 0.8
    abertura_max = larg_ombros * 2.0
    porc_pernas = max(0.0, min(100.0, ((dist_tornozelos - abertura_min) / max(1.0, abertura_max - abertura_min)) * 100.0))

    # Porcentagem mista combinada
    porc_bruta = (porc_bracos * 0.5) + (porc_pernas * 0.5)
    filtro_amp = filtros.get('amplitude', {}).get('esq') if filtros else None
    porc_suave = filtro_amp.atualizar(porc_bruta) if filtro_amp else porc_bruta
    porc = int(max(0, min(100, porc_suave)))

    # Validação de sincronia: braços e pernas devem abrir/fechar juntos
    postura_segura = abs(porc_bracos - porc_pernas) <= 45.0
    msg_erro = "" if postura_segura else "Sincronize bracos e pernas"

    coords_bracos = (p_ombro_esq, p_pulso_esq)
    coords_pernas = (p_tornozelo_esq, p_tornozelo_dir)

    return porc, postura_segura, coords_bracos, coords_pernas, msg_erro


def verificar_fadiga(
    tempos_repeticoes: List[float]
) -> bool:
    """Verifica se há fadiga muscular pela desaceleração das repetições.

    Se houver pelo menos 4 repetições registadas, calcula o tempo médio das 3 primeiras
    (ritmo base). Se a última repetição demorar mais de 1.6x (60% mais lenta) do que
    o ritmo base, retorna True (fadiga detetada). Caso contrário, retorna False.

    Args:
        tempos_repeticoes: Lista contendo as durações em segundos das repetições concluídas.

    Returns:
        True se a última repetição for > 1.6x o ritmo base das 3 primeiras repetições.
    """
    if not tempos_repeticoes or len(tempos_repeticoes) < 4:
        return False

    ritmo_base = sum(tempos_repeticoes[:3]) / 3.0
    if ritmo_base <= 0:
        return False

    ultima_rep = tempos_repeticoes[-1]
    return ultima_rep > 1.6 * ritmo_base


