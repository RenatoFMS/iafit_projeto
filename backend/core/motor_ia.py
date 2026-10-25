# core/motor_ia.py
"""Controlador de IA do IAFit.

Atua como o orquestrador do sistema: recebe os dados de pose (MediaPipe / YOLO),
aciona a análise biomecânica, gerencia o cooldown de avisos sonoros e atualiza
os contadores de repetição e tempo isométrico.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from core.config_exercicios import EXERCICIOS
from core.voz_client import falar
from core.analise_biomecanica import (
    _obter_coord_conf,
    _pt,
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
    verificar_fadiga,
    calcular_calorias,
)

# Cooldown global dos avisos de voz de postura e assimetria (4 segundos)
ultimo_aviso = 0

# Cooldown específico para avisos motivacionais de fadiga (pelo menos 10 segundos)
ultimo_aviso_fadiga = 0


class GerenciadorCalibracao:
    """Gerencia a fase inicial de calibração do utilizador antes do início da contagem.

    O motor inicia obrigatoriamente no estado 'Calibração' e só transita para 'Treinando'
    quando os landmarks anatómicos principais do exercício atual estiverem visíveis com
    alta confiança (> 0.7) durante um período contínuo de 1 a 2 segundos (padrão: 1.5s).
    """

    def __init__(self, duracao_minima: float = 1.5, limiar_conf: float = 0.7) -> None:
        """Inicializa o gerenciador de calibração.

        Args:
            duracao_minima: Tempo em segundos de visibilidade contínua para calibrar.
            limiar_conf: Confiança mínima necessária nos landmarks principais.
        """
        self.duracao_minima: float = duracao_minima
        self.limiar_conf: float = limiar_conf
        self.estado: str = "Calibração"
        self.tempo_inicio_visivel: Optional[float] = None

    def resetar(self) -> None:
        """Reinicia o estado para 'Calibração' e limpa o tempo acumulado."""
        self.estado = "Calibração"
        self.tempo_inicio_visivel = None

    def limpar(self) -> None:
        """Compatibilidade com o protocolo de filtros do IAFit."""
        self.resetar()

    def atualizar(
        self,
        keypoints_data: Any,
        config_exercicio: Dict[str, Any]
    ) -> Tuple[str, bool, int]:
        """Avalia os keypoints e atualiza o estado da máquina de calibração.

        Args:
            keypoints_data: Dados dos keypoints articulares no frame atual.
            config_exercicio: Configuração biomecânica do exercício.

        Returns:
            Tupla (estado, pronto_para_treino, progresso_porc).
        """
        if self.estado == "Treinando":
            return self.estado, True, 100

        visivel = _verificar_confianca_landmarks(keypoints_data, config_exercicio, self.limiar_conf)
        agora = time.time()

        if visivel:
            if self.tempo_inicio_visivel is None:
                self.tempo_inicio_visivel = agora
            tempo_decorrido = agora - self.tempo_inicio_visivel
            progresso = min(100, int((tempo_decorrido / self.duracao_minima) * 100))
            if tempo_decorrido >= self.duracao_minima:
                self.estado = "Treinando"
                return self.estado, True, 100
            return self.estado, False, progresso
        else:
            self.tempo_inicio_visivel = None
            return self.estado, False, 0


_calibrador_global = GerenciadorCalibracao()


def obter_calibrador(filtros: Optional[Dict[str, Any]]) -> GerenciadorCalibracao:
    """Obtém ou instancia o gerenciador de calibração associado aos filtros ou global.

    Args:
        filtros: Dicionário de filtros de memória da sessão (opcional).

    Returns:
        Instância ativa de GerenciadorCalibracao.
    """
    if filtros and isinstance(filtros, dict):
        if 'calibracao' not in filtros:
            filtros['calibracao'] = GerenciadorCalibracao()
        return filtros['calibracao']
    return _calibrador_global


def obter_landmarks_principais(
    keypoints_data: Sequence[Sequence[float]],
    config_exercicio: Dict[str, Any]
) -> List[int]:
    """Identifica os índices dos landmarks COCO fundamentais para o exercício atual.

    Args:
        keypoints_data: Dados dos keypoints articulares detectados no frame.
        config_exercicio: Dicionário de configuração do exercício atual.

    Returns:
        Lista com os índices anatômicos primários necessários para o exercício.
    """
    if not keypoints_data or len(keypoints_data) < 17:
        return []

    nome = config_exercicio.get("nome", "")
    if "Polichinelo" in nome:
        return [5, 6, 9, 10, 11, 12, 15, 16]

    lados = config_exercicio.get("lados", {})
    if not lados:
        return [5, 6, 11, 12]

    melhor_lado, _ = selecionar_melhor_lado(keypoints_data, lados)
    lado_alvo = melhor_lado if melhor_lado else "esq"

    indices = list(lados.get(lado_alvo, ()))
    postura = config_exercicio.get("postura", {})
    if lado_alvo in postura:
        for idx in postura[lado_alvo][:2]:
            if idx not in indices:
                indices.append(idx)

    return indices


def _verificar_confianca_landmarks(
    keypoints_data: Sequence[Sequence[float]],
    config_exercicio: Dict[str, Any],
    limiar_conf: float = 0.7
) -> bool:
    """Verifica se todos os landmarks principais estão visíveis com confiança > limiar_conf.

    Args:
        keypoints_data: Dados dos keypoints articulares detectados no frame.
        config_exercicio: Dicionário de configuração do exercício.
        limiar_conf: Limiar mínimo de confiança exigido (padrão: 0.7).

    Returns:
        True se todos os pontos chave tiverem confiança acima do limiar, False caso contrário.
    """
    if not keypoints_data or len(keypoints_data) < 17:
        return False

    indices = obter_landmarks_principais(keypoints_data, config_exercicio)
    if not indices:
        return False

    for idx in indices:
        if idx >= len(keypoints_data):
            return False
        conf = keypoints_data[idx][2]
        if conf <= limiar_conf:
            return False

    return True


def _gerar_resultado_calibracao(
    keypoints_data: Any,
    config_exercicio: Dict[str, Any],
    progresso: int,
    filtros: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Gera o dicionário de resultado no frame durante o estado de Calibração.

    Args:
        keypoints_data: Keypoints articulares no frame atual.
        config_exercicio: Dicionário de configuração do exercício atual.
        progresso: Porcentagem de conclusão da calibração (0 a 100).
        filtros: Dicionário contendo instâncias de contadores e cronômetros.

    Returns:
        Dicionário formatado com os dados visuais do estado de calibração.
    """
    contador = filtros.get('repeticoes', {}).get('total') if filtros else None
    cronometro = filtros.get('isometrico', {}).get('total') if filtros else None

    ponto_texto = (30, 90)
    melhor_lado = "esq"
    coords = None
    coords_postura = None
    coords_bracos = None

    if keypoints_data and len(keypoints_data) >= 17:
        lados = config_exercicio.get("lados", {})
        if lados:
            melhor_lado, _ = selecionar_melhor_lado(keypoints_data, lados)
            if not melhor_lado:
                melhor_lado = "esq"
            if melhor_lado in lados:
                c_idxs = lados[melhor_lado]
                if all(c < len(keypoints_data) and keypoints_data[c][2] > 0.3 for c in c_idxs):
                    coords = (_pt(keypoints_data[c_idxs[0]]), _pt(keypoints_data[c_idxs[1]]), _pt(keypoints_data[c_idxs[2]]))
                    ponto_texto = keypoints_data[c_idxs[1]][:2]

    feedback = f"Calibrando ({progresso}%)... Fique em posicao"
    if progresso == 0:
        feedback = "Calibracao: Posicione o corpo na camera"

    return {
        "lado": melhor_lado,
        "porc": progresso,
        "feedback": feedback,
        "cor": (0, 255, 255),
        "coords": coords,
        "coords_postura": coords_postura,
        "coords_bracos": coords_bracos,
        "ponto_texto": ponto_texto,
        "alerta_assimetria": False,
        "angulo_braco_esq": None,
        "angulo_braco_dir": None,
        "reps": contador.reps if contador else 0,
        "segundos": cronometro.segundos if cronometro else 0,
        "postura_correta": True,
        "fase": "calibracao",
        "estado": "Calibração",
        "fora_enquadramento": False,
        "fadiga_detectada": False
    }


def resetar_cooldown_voz() -> None:
    """Reinicia o cooldown dos alertas de voz, fadiga e calibração."""
    global ultimo_aviso, ultimo_aviso_fadiga
    ultimo_aviso = 0
    ultimo_aviso_fadiga = 0
    _calibrador_global.resetar()


def _executar_aviso_voz(mensagem: str, cooldown: float = 4.0) -> bool:
    """Aciona aviso sonoro respeitando a janela de cooldown.

    Args:
        mensagem: Texto falado a ser emitido pelo sintetizador.
        cooldown: Intervalo mínimo em segundos entre avisos sonoros (padrão: 4.0).

    Returns:
        True se o áudio foi acionado, False caso esteja dentro do intervalo de cooldown.
    """
    global ultimo_aviso
    agora = time.time()
    if agora - ultimo_aviso > cooldown:
        falar(mensagem)
        ultimo_aviso = agora
        return True
    return False


def _executar_aviso_fadiga(
    mensagem: str = "Força, não desista, mantenha o ritmo!",
    cooldown_fadiga: float = 10.0,
    cooldown_global: float = 4.0
) -> bool:
    """Aciona aviso sonoro de incentivo à fadiga respeitando o cooldown específico (10s) e global (4s).

    Args:
        mensagem: Frase motivacional a ser falada.
        cooldown_fadiga: Cooldown específico para alertas de fadiga (padrão: 10.0s).
        cooldown_global: Cooldown global para qualquer aviso sonoro (padrão: 4.0s).

    Returns:
        True se o aviso motivacional foi disparado, False caso contrário.
    """
    global ultimo_aviso, ultimo_aviso_fadiga
    agora = time.time()
    if agora - ultimo_aviso_fadiga > cooldown_fadiga and agora - ultimo_aviso > cooldown_global:
        falar(mensagem)
        ultimo_aviso_fadiga = agora
        ultimo_aviso = agora
        return True
    return False


def processar_exercicio(
    keypoints_data: Any,
    config_exercicio: Dict[str, Any],
    filtros: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Processa a execução de um exercício dinâmico ou isométrico.

    Aceita diretamente 33 landmarks (em formato dicionário, array [x, y, z, visibilidade]
    ou objetos MediaPipe) ou 17 keypoints COCO, orquestrando a análise biomecânica,
    contagem de repetições e feedback sonoro sem depender da deteção de vídeo local.

    Args:
        keypoints_data: Landmarks de 33 pontos (dict/array/MediaPipe) ou 17 keypoints COCO.
        config_exercicio: Dicionário com todas as configurações biomecânicas do exercício.
        filtros: Dicionário com contadores, cronômetros e instâncias de suavização.

    Returns:
        Lista com dicionários de telemetria e renderização visual para o frame.
    """
    global ultimo_aviso

    if keypoints_data is not None:
        if isinstance(keypoints_data, dict):
            keypoints_data = landmarks_mediapipe_para_keypoints(keypoints_data)
        elif len(keypoints_data) > 0 and (
            hasattr(keypoints_data[0], "x")
            or isinstance(keypoints_data[0], dict)
            or len(keypoints_data) >= 33
        ):
            keypoints_data = landmarks_mediapipe_para_keypoints(keypoints_data)

    # Deteção de Saída de Enquadramento
    if verificar_fora_enquadramento(keypoints_data, config_exercicio):
        calibrador = obter_calibrador(filtros)
        calibrador.resetar()
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
            "fase": "fora",
            "estado": "Fora"
        }]

    # Fase de Calibração Inicial (estado 'Calibração' -> 'Treinando')
    calibrador = obter_calibrador(filtros)
    estado_anterior = calibrador.estado
    estado, pronto, progresso = calibrador.atualizar(keypoints_data, config_exercicio)
    if not pronto:
        return [_gerar_resultado_calibracao(keypoints_data, config_exercicio, progresso, filtros)]

    if estado_anterior == "Calibração" and estado == "Treinando":
        _executar_aviso_voz("Calibração concluída! Inicie o exercício")

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
    reps_anteriores = contador.reps if contador else 0
    reps, fase = contador.atualizar(porc) if contador else (0, "base")

    # Deteção Algorítmica de Fadiga
    fadiga_detectada = False
    if contador and reps > reps_anteriores:
        if verificar_fadiga(contador.tempos_repeticoes):
            fadiga_detectada = True
            _executar_aviso_fadiga("Força, não desista, mantenha o ritmo!")

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
        "lado": melhor_lado, "porc": porc, "angulo": round(float(angulo_suave), 1), "feedback": feedback, "cor": cor,
        "coords": (p1, p2, p3), "coords_postura": coords_postura, "coords_bracos": coords_bracos, "ponto_texto": p2,
        "alerta_assimetria": alerta_assimetria, "angulo_braco_esq": angulo_esq, "angulo_braco_dir": angulo_dir,
        "reps": reps, "fase": fase, "fadiga_detectada": fadiga_detectada, "estado": "Treinando"
    }]


def processar_desenvolvimento_ombro(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Desenvolvimento de Ombro (70° -> 160°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["4"], filtros)


def processar_rosca_biceps(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Rosca Bíceps (160° -> 40°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["1"], filtros)


def processar_flexao(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Flexão de Braço (160° -> 80°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["3"], filtros)


def processar_abdominal(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Abdominal Supra (150° -> 70°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["5"], filtros)


def processar_agachamento(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Agachamento (170° -> 80°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["2"], filtros)


def processar_afundo(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Afundo / Lunge (160° -> 90°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["6"], filtros)


def processar_stiff(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Stiff (170° -> 80°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["7"], filtros)


def processar_prancha(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Prancha Isométrica (ângulo Ombro-Quadril-Tornozelo >= 160°).

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("8", {})

    if verificar_fora_enquadramento(keypoints_data, config):
        cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
        if cronometro:
            cronometro.ultimo_tempo = None
        calibrador = obter_calibrador(filtros)
        calibrador.resetar()
        _executar_aviso_voz("Atenção, volte para a câmara")
        segundos = cronometro.segundos if cronometro else 0
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": segundos, "segundos": segundos, "postura_correta": False, "fase": "fora",
            "estado": "Fora"
        }]

    calibrador = obter_calibrador(filtros)
    estado_anterior = calibrador.estado
    estado, pronto, progresso = calibrador.atualizar(keypoints_data, config)
    if not pronto:
        return [_gerar_resultado_calibracao(keypoints_data, config, progresso, filtros)]

    if estado_anterior == "Calibração" and estado == "Treinando":
        _executar_aviso_voz("Calibração concluída! Inicie o exercício")

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


def processar_remada_curvada(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Remada Curvada com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["9"], filtros)


def processar_supino(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Supino com Halteres com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["10"], filtros)


def processar_elevacao_lateral(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Elevação Lateral (20° -> 90°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["11"], filtros)


def processar_elevacao_pelvica(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Elevação Pélvica (110° -> 175°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["12"], filtros)


def processar_mergulho_banco(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Mergulho no Banco (160° -> 90°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["13"], filtros)


def processar_rosca_martelo(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Rosca Martelo (160° -> 40°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["14"], filtros)


def processar_agachamento_sumo(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Agachamento Sumô com MediaPipe e validação da largura da base dos pés.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    postura_ok, _, _ = validar_postura_sumo(landmarks if len(landmarks) >= 33 else keypoints_data)
    if not postura_ok:
        _executar_aviso_voz("Afaste mais os pés")

    return processar_exercicio(keypoints_data, EXERCICIOS["15"], filtros)


def processar_barra_fixa(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Barra Fixa com MediaPipe e validação do queixo acima da barra.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
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


def processar_triceps_testa(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Tríceps Testa (160° -> 70°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["17"], filtros)


def processar_crucifixo(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Crucifixo Halteres (150° -> 85°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["18"], filtros)


def processar_stiff_unilateral(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Stiff Unilateral (170° -> 85°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["19"], filtros)


def processar_elevacao_frontal(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Elevação Frontal (20° -> 90°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["20"], filtros)


def processar_panturrilha(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Panturrilha em Pé (90° -> 140°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["21"], filtros)


def processar_prancha_lateral(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Prancha Lateral (ângulo Ombro-Quadril-Tornozelo >= 160°).

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("22", {})

    if verificar_fora_enquadramento(keypoints_data, config):
        cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
        if cronometro:
            cronometro.ultimo_tempo = None
        calibrador = obter_calibrador(filtros)
        calibrador.resetar()
        _executar_aviso_voz("Atenção, volte para a câmara")
        segundos = cronometro.segundos if cronometro else 0
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": segundos, "segundos": segundos, "postura_correta": False, "fase": "fora",
            "estado": "Fora"
        }]

    calibrador = obter_calibrador(filtros)
    estado_anterior = calibrador.estado
    estado, pronto, progresso = calibrador.atualizar(keypoints_data, config)
    if not pronto:
        return [_gerar_resultado_calibracao(keypoints_data, config, progresso, filtros)]

    if estado_anterior == "Calibração" and estado == "Treinando":
        _executar_aviso_voz("Calibração concluída! Inicie o exercício")

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


def processar_agachamento_bulgaro(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Agachamento Búlgaro (170° -> 90°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["23"], filtros)


def processar_encolhimento(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Encolhimento de Ombros (170° -> 135°) com MediaPipe e foco no eixo Y.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
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


def processar_abdominal_infra(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Abdominal Infra (165° -> 85°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["25"], filtros)


def processar_remada_alta(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Remada Alta (25° -> 95°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["26"], filtros)


def processar_bom_dia(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Bom Dia (170° -> 95°) com MediaPipe.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["27"], filtros)


def processar_triceps_coice(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Tríceps Coice (90° -> 165°) com MediaPipe e deteção de assimetria dos braços.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    assimetria, _, _, _ = verificar_assimetria_bracos(landmarks)
    if assimetria:
        _executar_aviso_voz("Equilibre a força dos dois braços")

    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    return processar_exercicio(keypoints_data, EXERCICIOS["28"], filtros)


def processar_agachamento_isometrico(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Agachamento Isométrico (Wall Sit) com ângulo mantido a ~90°.

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("29", {})

    if verificar_fora_enquadramento(keypoints_data, config):
        cronometro = filtros.get('isometrico', {}).get('total') if filtros else None
        if cronometro:
            cronometro.ultimo_tempo = None
        calibrador = obter_calibrador(filtros)
        calibrador.resetar()
        _executar_aviso_voz("Atenção, volte para a câmara")
        segundos = cronometro.segundos if cronometro else 0
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": segundos, "segundos": segundos, "postura_correta": False, "fase": "fora",
            "estado": "Fora"
        }]

    calibrador = obter_calibrador(filtros)
    estado_anterior = calibrador.estado
    estado, pronto, progresso = calibrador.atualizar(keypoints_data, config)
    if not pronto:
        return [_gerar_resultado_calibracao(keypoints_data, config, progresso, filtros)]

    if estado_anterior == "Calibração" and estado == "Treinando":
        _executar_aviso_voz("Calibração concluída! Inicie o exercício")

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
        "fase": fase,
        "estado": "Treinando"
    }]


def processar_polichinelo(
    landmarks: Any,
    filtros: Optional[Dict[str, Any]],
    largura: Optional[int] = None,
    altura: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Polichinelo (lógica mista: braços no eixo Y e pernas na distância dos pés).

    Args:
        landmarks: Dados brutos de landmarks MediaPipe ou keypoints COCO.
        filtros: Dicionário contendo os filtros de suavização e contadores.
        largura: Largura do frame em pixels para desnormalização de coordenadas (opcional).
        altura: Altura do frame em pixels para desnormalização de coordenadas (opcional).

    Returns:
        Lista com dicionários de telemetria e coordenadas para renderização visual.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks, largura, altura)
    config = EXERCICIOS.get("30", {})

    if verificar_fora_enquadramento(keypoints_data, config):
        calibrador = obter_calibrador(filtros)
        calibrador.resetar()
        _executar_aviso_voz("Atenção, volte para a câmara")
        contador = filtros.get('repeticoes', {}).get('total') if filtros else None
        return [{
            "fora_enquadramento": True, "feedback": "FORA DE ENQUADRAMENTO", "cor": (0, 0, 255),
            "porc": 0, "coords": None, "coords_postura": None, "coords_bracos": None, "ponto_texto": (30, 90),
            "alerta_assimetria": False, "angulo_braco_esq": None, "angulo_braco_dir": None,
            "reps": contador.reps if contador else 0, "segundos": 0, "fase": "fora",
            "estado": "Fora"
        }]

    calibrador = obter_calibrador(filtros)
    estado_anterior = calibrador.estado
    estado, pronto, progresso = calibrador.atualizar(keypoints_data, config)
    if not pronto:
        return [_gerar_resultado_calibracao(keypoints_data, config, progresso, filtros)]

    if estado_anterior == "Calibração" and estado == "Treinando":
        _executar_aviso_voz("Calibração concluída! Inicie o exercício")

    res_poli = validar_polichinelo(keypoints_data, filtros)
    if not res_poli:
        return []

    porc, postura_segura, coords_bracos, coords_pernas, msg_erro = res_poli

    contador = filtros.get('repeticoes', {}).get('total')
    reps_anteriores = contador.reps if contador else 0
    reps, fase = contador.atualizar(porc) if contador else (0, "base")

    # Deteção Algorítmica de Fadiga
    fadiga_detectada = False
    if contador and reps > reps_anteriores:
        if verificar_fadiga(contador.tempos_repeticoes):
            fadiga_detectada = True
            _executar_aviso_fadiga("Força, não desista, mantenha o ritmo!")

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
        "fase": fase,
        "fadiga_detectada": fadiga_detectada,
        "estado": "Treinando"
    }]


PROCESSADORES_EXERCICIO.update({
    "25": processar_abdominal_infra,
    "26": processar_remada_alta,
    "27": processar_bom_dia,
    "28": processar_triceps_coice,
    "29": processar_agachamento_isometrico,
    "30": processar_polichinelo,
})