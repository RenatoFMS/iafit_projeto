# core/analise_biomecanica.py
"""Módulo de Análise Biomecânica, Cinemática Articular e Validação Postural do IAFit.

Este ficheiro constitui o núcleo científico de avaliação biomecânica do sistema IAFit,
operando em conjunto com `core.math_utils` e `core.motor_ia` sob a arquitetura de
Computação de Borda (*Edge Computing*):

Fluxo Técnico de Avaliação (Pipeline Biomecânico):
    1. **Ingestão e Mapeamento Anatômico (`landmarks_mediapipe_para_keypoints`):**
       Recebe os 33 marcos anatômicos tridimensionais (`x, y, z, visibilidade`) extraídos
       no telemóvel via Google ML Kit Pose Detection (ou MediaPipe) e converte-os para a
       topologia canônica COCO de 17 pontos `[x, y, confianca, z]`, preservando a coordenada
       espacial `z` para geometria vetorial 3D livre de distorção de perspectiva.
    2. **Seleção Hemilateral por Confiança Óptica (`selecionar_melhor_lado`):**
       Soma os graus de visibilidade do hemicorpo esquerdo e direito para eleger
       dinamicamente o lado menos obstruído perante a câmara, exigindo confiança mínima
       individual (`>= 0.5`) em todas as articulações da cadeia cinética principal.
    3. **Cinemática das Fases Concêntrica e Excêntrica (`calcular_amplitude_movimento`):**
       Calcula o ângulo espacial 3D no vértice articular agonista via produto escalar
       (`θ = arccos((v1 · v2) / (||v1|| * ||v2||))`), atenua o ruído de alta frequência
       com `FiltroSuavizacao` e interpola linearmente o ângulo entre `inicio` (`0%`,
       posição alongada/base) e `fim` (`100%`, pico de contração concêntrica). Essa
       percentagem alimenta a Máquina de Estados Finitos (`ContadorRepeticoes`), que
       rastreia as transições `base -> subida (concêntrica) -> topo -> descida (excêntrica)
       -> base` para contabilizar apenas repetições completas e biomecanicamente válidas.
    4. **Deteção de Compensações e Erros de Postura (`analisar_seguranca_postura` e `validar_*`):**
       Em paralelo à contagem da fase concêntrica/excêntrica, monitoriza cadeias
       estabilizadoras secundárias (coluna lombar, abdução glenoumeral, alinhamento
       pélvico e extensão de joelhos) usando ângulos entre três articulações ou desvios
       angulares face a um eixo gravitacional virtual (`_ponto_acima`), sinalizando
       imediatamente compensações lesivas.
    5. **Assimetria Bilateral, Gasto Energético (MET) e Fadiga Neuromuscular:**
       Avalia desequilíbrios angulares entre membros homólogos (`> 15°` visual / `> 25°`
       sonoro), estima quilocalorias pela equação fisiológica do equivalente metabólico
       (`MET`) e identifica perda de velocidade de execução concêntrica/excêntrica (`> 1.6x`
       do ritmo basal) associada à fadiga periférica.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from core.math_utils import calcular_angulo, calcular_porcentagem

# ==============================================================================
# CONSTANTES E ÍNDICES ANATÔMICOS (TOPOLOGIA COCO 17 KEYPOINTS)
# ==============================================================================
# Índices COCO de referência utilizados em todo o módulo:
#   0: Nariz | 1: Olho Esq | 2: Olho Dir | 3: Orelha Esq | 4: Orelha Dir
#   5: Ombro Esq | 6: Ombro Dir | 7: Cotovelo Esq | 8: Cotovelo Dir
#   9: Pulso Esq | 10: Pulso Dir | 11: Quadril Esq | 12: Quadril Dir
#   13: Joelho Esq | 14: Joelho Dir | 15: Tornozelo Esq | 16: Tornozelo Dir

BRACO_ESQ: Tuple[int, int, int] = (5, 7, 9)   # Cadeia articular Ombro–Cotovelo–Pulso esquerda
BRACO_DIR: Tuple[int, int, int] = (6, 8, 10)  # Cadeia articular Ombro–Cotovelo–Pulso direita
LIMITE_ASSIMETRIA: int = 15       # Diferença angular bilateral (graus) para alerta visual na UI
LIMITE_ASSIMETRIA_VOZ: int = 25   # Diferença angular bilateral (graus) para intervenção por voz

# Tabela de correspondência direta dos 33 landmarks do MediaPipe / Google ML Kit
# para os 17 keypoints anatômicos equivalentes do padrão COCO:
#   [0:Nariz, 2:OlhoEsq, 5:OlhoDir, 7:OrelhaEsq, 8:OrelhaDir, 11:OmbroEsq, 12:OmbroDir,
#    13:CotoveloEsq, 14:CotoveloDir, 15:PulsoEsq, 16:PulsoDir, 23:QuadrilEsq, 24:QuadrilDir,
#    25:JoelhoEsq, 26:JoelhoDir, 27:TornozeloEsq, 28:TornozeloDir]
_MP_PARA_COCO: List[int] = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


# ==============================================================================
# FUNÇÕES AUXILIARES DE EXTRAÇÃO E GEOMETRIA ESPACIAL
# ==============================================================================

def _obter_coord_conf(landmark: Any) -> Tuple[Tuple[float, float], float]:
    """Extrai as coordenadas planares `(x, y)` e o índice de visibilidade/confiança `[0.0, 1.0]`.

    Projetada com polimorfismo estrutural para aceitar tanto objetos nativos do MediaPipe
    (usados nos scripts locais de QA) quanto *payloads* JSON desserializados enviados em
    tempo real pelo aplicativo Flutter (`POST /analisar_pose`) em formato de lista ou dicionário.

    Args:
        landmark: Ponto articular representado como objeto (`landmark.x`, `landmark.y`,
            `landmark.visibility`), sequência (`[x, y, z, visibilidade]` ou `[x, y, conf]`)
            ou dicionário JSON (`{'x': ..., 'y': ..., 'visibilidade': ...}`).

    Returns:
        Tupla `((x, y), confianca)` convertida para `float`. Devolve `((0.0, 0.0), 0.0)`
        caso a estrutura recebida seja nula ou irreconhecível.
    """
    # Caso 1: Objeto nativo da biblioteca MediaPipe Solutions (inferência local em vídeo QA)
    if hasattr(landmark, 'x') and hasattr(landmark, 'y'):
        conf = getattr(landmark, 'visibility', getattr(landmark, 'confidence', 1.0))
        return (float(landmark.x), float(landmark.y)), float(conf)

    # Caso 2: Array/Tupla compacto [x, y, z, visibilidade] (Edge JSON) ou [x, y, conf] (COCO)
    elif isinstance(landmark, (list, tuple)):
        if len(landmark) >= 4:
            # Em arrays de 4 posições vindos do ML Kit, o índice 2 é Z e o índice 3 é a visibilidade
            conf = landmark[3]
        elif len(landmark) > 2:
            # Em arrays COCO de 3 posições, o índice 2 armazena diretamente a confiança
            conf = landmark[2]
        else:
            conf = 1.0
        return (float(landmark[0]), float(landmark[1])), float(conf)

    # Caso 3: Dicionário JSON enviado pelo cliente móvel (aceita chaves em PT-BR e EN)
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
    """Extrai a coordenada espacial de profundidade `Z` de um marco anatômico.

    No modelo geométrico do Google ML Kit / MediaPipe Pose, o eixo `Z` representa a
    profundidade relativa ao centro do quadril na mesma escala métrica do eixo `X`.
    Essa componente permite calcular ângulos tridimensionais verdadeiros em `calcular_angulo`.

    Args:
        landmark: Objeto MediaPipe, sequência `[x, y, z, visibilidade]` ou dicionário JSON.

    Returns:
        Valor `float` da coordenada `Z`, ou `0.0` caso o formato de entrada seja estritamente 2D.
    """
    if hasattr(landmark, 'z'):
        return float(landmark.z)
    if isinstance(landmark, dict):
        return float(landmark.get('z', 0.0))
    if isinstance(landmark, (list, tuple)) and len(landmark) >= 4:
        return float(landmark[2])
    return 0.0


def _pt(keypoint: Sequence[float]) -> Tuple[float, ...]:
    """Reconstrói a tupla geométrica espacial `(x, y, z)` ou planar `(x, y)` de um keypoint COCO.

    No formato interno padronizado deste módulo, cada elemento de `keypoints_data` possui o
    layout `[x, y, confianca, z]`, mantendo a confiança na posição `2` por retrocompatibilidade
    com detectores 2D e anexando `z` na posição `3`. Esta função reorganiza os eixos espaciais
    para `(x, y, z)` antes de enviá-los ao cálculo vetorial em `calcular_angulo`.

    Args:
        keypoint: Sequência numérica no formato `[x, y, confianca]` ou `[x, y, confianca, z]`.

    Returns:
        Tupla tridimensional `(x, y, z)` quando há profundidade disponível, ou `(x, y)` para
        acionar automaticamente o *fallback* trigonométrico 2D (`atan2`).
    """
    if len(keypoint) > 3:
        # Descarta o índice 2 (confiança) e agrupa apenas os eixos cartesianos (x, y, z)
        return (keypoint[0], keypoint[1], keypoint[3])
    return (keypoint[0], keypoint[1])


def _ponto_acima(ponto: Sequence[float], deslocamento: float = 50.0) -> Tuple[float, ...]:
    """Projeta um ponto auxiliar na linha gravitacional vertical acima de uma articulação base.

    Fundamentação Geométrica:
        Para medir o ângulo de inclinação absoluta do tronco em relação à vertical (ex.: evitar
        inclinação lombar excessiva no Agachamento, Stiff ou Desenvolvimento de Ombros), são
        necessários três pontos para formar dois vetores concorrentes no quadril (`sp2`):
            1. `sp1`: Articulação do Ombro;
            2. `sp2`: Articulação do Quadril (vértice do ângulo);
            3. `sp3`: Ponto virtual verticalmente alinhado acima do Quadril (`y - deslocamento`,
               visto que no referencial matricial de imagem o eixo `Y` cresce de cima para baixo).
        Mantendo `x` e `z` idênticos aos de `sp2`, o vetor `sp3 - sp2 = (0, -deslocamento, 0)`
        aponta estritamente para o zênite vertical: tronco totalmente ereto resulta em `~0°`,
        enquanto inclinação à frente ou atrás aumenta o ângulo proporcionalmente.

    Args:
        ponto: Coordenadas `(x, y[, z])` da articulação de apoio (tipicamente o Quadril).
        deslocamento: Comprimento escalar do vetor vertical de referência em pixels (padrão: `50.0`).

    Returns:
        Tupla `(x, y - deslocamento, z)` em 3D ou `(x, y - deslocamento)` em 2D.
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
    """Instancia o extrator MediaPipe Pose para execução local de testes automatizados (QA).

    Nota Arquitetural:
        Na operação em produção com o telemóvel (Edge Computing), a extração do esqueleto
        ocorre no cliente Flutter via Google ML Kit, dispensando este detector no servidor.
        Esta função é mantida para o pipeline de validação em lote (`testador_lote.py`),
        permitindo aferir os mesmos algoritmos matemáticos contra vídeos de referência.

    Args:
        static_image_mode: Se `False`, reutiliza mapas de calor temporais entre frames sucessivos
            para reduzir latência de CPU; se `True`, executa deteção completa em cada imagem.
        model_complexity: Complexidade da rede BlazePose (`0` = Lite, `1` = Full, `2` = Heavy).
        min_detection_confidence: Probabilidade mínima `[0.0, 1.0]` para localizar a pessoa inicial.
        min_tracking_confidence: Limiar `[0.0, 1.0]` para sustentar o rastreamento inter-frames
            sem reinvocar o detector de corpo inteiro.

    Returns:
        Objeto `mediapipe.solutions.pose.Pose` configurado e pronto para inferência.
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
    """Converte estruturas heterogéneas de entrada JSON numa sequência indexada de 33 pontos.

    Aceita tanto envelopes JSON completos (`{"landmarks": [...]}` ou `{"pontos": [...]}`)
    quanto mapas indexados por chave inteira ou textual (`{"0": {...}, "1": {...}, ...}`),
    preenchendo eventuais índices ausentes com visibilidade nula para evitar `IndexError`.

    Args:
        landmarks: Payload bruto de landmarks recebido da API REST ou do motor local.

    Returns:
        Sequência posicional indexável de marcos anatômicos.
    """
    if isinstance(landmarks, dict):
        if "landmarks" in landmarks:
            landmarks = landmarks["landmarks"]
        elif "pontos" in landmarks:
            landmarks = landmarks["pontos"]
        else:
            # Reconstrói lista ordenada [0..32] a partir de dicionário esparso de índices
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
    """Converte os 33 landmarks do ML Kit / MediaPipe para os 17 keypoints canônicos COCO.

    Importância Geométrica da Escala de Aspecto:
        Redes como MediaPipe devolvem coordenadas normalizadas no intervalo `[0.0, 1.0]`
        em relação à largura e altura da imagem. Caso os ângulos fossem calculados diretamente
        no espaço normalizado de uma imagem retangular (ex.: `640x480` ou `1280x720`), a razão
        de aspecto não-unitária deformaria os vetores diagonais e alteraria os ângulos reais.
        Por isso, quando entradas normalizadas são detetadas, aplica-se a desnormalização isotrópica
        pelas dimensões reais do frame (`largura`, `altura`) ou pela proporção padrão `640x480`,
        escalando `z` pela largura conforme especificação oficial do BlazePose.

    Args:
        landmarks: Coleção de 33 pontos (objetos, dicionários ou listas) ou lista já convertida
            de 17 keypoints COCO (operação idempotente).
        largura: Largura real do frame capturado em pixels (opcional).
        altura: Altura real do frame capturado em pixels (opcional).

    Returns:
        Lista de 17 listas `[x, y, confianca, z]` mapeadas segundo `_MP_PARA_COCO`, ou lista
        vazia `[]` se o payload estiver vazio ou incompleto.
    """
    if landmarks is None:
        return []
    landmarks = _normalizar_entrada_landmarks(landmarks)
    if len(landmarks) == 0:
        return []

    # Idempotência: se os dados já estiverem no padrão COCO de 17 pontos numéricos, retorna-os
    if len(landmarks) == 17 and isinstance(landmarks[0], (list, tuple)) and not hasattr(landmarks[0], 'x'):
        return list(landmarks)

    # São necessários ao menos os índices até o tornozelo direito (índice 28 no MediaPipe)
    if len(landmarks) < 29:
        return []

    coords_extraidas: List[Tuple[float, float, float, float]] = []
    todos_normalizados = True
    for i in _MP_PARA_COCO:
        (x, y), conf = _obter_coord_conf(landmarks[i])
        z = _obter_z(landmarks[i])
        # Verifica se as coordenadas válidas já vieram em pixels (> 1.0) ou normalizadas [0, 1]
        if conf > 0.0 and not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            todos_normalizados = False
        coords_extraidas.append((x, y, conf, z))

    # Define fatores de projeção métrica em pixels preservando a proporção geométrica
    largura_escala = float(largura) if largura is not None else (640.0 if todos_normalizados else 1.0)
    altura_escala = float(altura) if altura is not None else (480.0 if todos_normalizados else 1.0)

    kps: List[List[float]] = []
    for x, y, conf, z in coords_extraidas:
        if todos_normalizados:
            x = x * largura_escala
            y = y * altura_escala
            # Na modelagem BlazePose/ML Kit, a magnitude de Z segue a mesma escala horizontal (X)
            z = z * largura_escala
        kps.append([x, y, conf, z])
    return kps


# ==============================================================================
# NÚCLEO CINEMÁTICO: SELEÇÃO DE LADO, AMPLITUDE CONCÊNTRICA/EXCÊNTRICA E POSTURA
# ==============================================================================

def selecionar_melhor_lado(
    keypoints_data: Sequence[Sequence[float]],
    lados_config: Dict[str, Sequence[int]]
) -> Tuple[Optional[str], Optional[Sequence[int]]]:
    """Elege dinamicamente o hemicorpo (`'esq'` ou `'dir'`) com melhor visibilidade óptica.

    Em filmagens de perfil ou meia-diagonal (necessárias em exercícios como Agachamento,
    Stiff, Rosca Bíceps e Afundo), o lado corporal mais distante da lente sofre auto-oclusão.
    Esta função soma a confiança dos 3 marcos anatômicos de cada lado e seleciona aquele
    mais visível, bloqueando a inferência caso qualquer articulação da tripla apresente
    confiança inferior a `0.5` (prevenção de ângulos espúrios por oclusão parcial).

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO `[x, y, confianca, z]` do frame atual.
        lados_config: Dicionário do catálogo mapeando `'esq'` e `'dir'` às tuplas de 3 índices
            anatômicos `(proximal, vertice, distal)`.

    Returns:
        Tupla `(melhor_lado, indices)` quando há visibilidade confiável, ou `(None, None)`
        quando ambos os lados estão parcialmente ocultos.
    """
    melhor_lado = None
    maior_confianca = 0

    # Soma as probabilidades de visibilidade [índice 2] das articulações de cada hemicorpo
    for lado, indices in lados_config.items():
        conf_total = sum(keypoints_data[i][2] for i in indices)
        if conf_total > maior_confianca:
            maior_confianca = conf_total
            melhor_lado = lado

    if not melhor_lado:
        return None, None

    indices = lados_config[melhor_lado]

    # Critério de corte de qualidade: rejeita o frame se qualquer articulação essencial < 50%
    if any(keypoints_data[idx][2] < 0.5 for idx in indices):
        return None, None

    return melhor_lado, indices


def calcular_amplitude_movimento(
    keypoints_data: Sequence[Sequence[float]],
    config_exercicio: Dict[str, Any],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[int, float, Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]]]:
    """Calcula o ângulo articular suavizado e o progresso percentual da repetição (`0%` a `100%`).

    Papel na Avaliação das Fases Concêntrica e Excêntrica:
        1. Extrai as coordenadas 3D `(p1, p2, p3)` da cadeia cinética agonista configurada
           em `config_exercicio["lados"][melhor_lado]`, onde `p2` é o eixo articular rotacional
           (ex.: Cotovelo na Rosca Bíceps; Joelho no Agachamento).
        2. Obtém o ângulo trigonométrico bruto `angulo_bruto` em R³ via `calcular_angulo`.
        3. Filtra oscilações de captura através da média móvel `FiltroSuavizacao` específica
           daquele lado anatômico, produzindo `angulo_suave`.
        4. Converte `angulo_suave` em percentagem normalizada `[0, 100]` (`calcular_porcentagem`)
           usando os marcos angulares `inicio` (`0%` — posição base/alongada) e `fim` (`100%` —
           pico da contração concêntrica).
        No `motor_ia.processar_exercicio`, essa percentagem é entregue ao `ContadorRepeticoes`,
        cuja máquina de estados identifica em tempo real se o atleta está na fase `'subida'`
        (concêntrica, percentagem crescente), `'topo'` (`>= 90%`), `'descida'` (excêntrica,
        percentagem decrescente) ou retorno completo à `'base'` (`<= 10%`, somando +1 repetição).

    Args:
        keypoints_data: Lista dos 17 keypoints COCO `[x, y, confianca, z]` do frame atual.
        config_exercicio: Parâmetros biomecânicos do exercício ativo (`lados`, `inicio`, `fim`).
        melhor_lado: Hemicorpo selecionado por `selecionar_melhor_lado` (`'esq'` ou `'dir'`).
        filtros: Dicionário de estado contendo os filtros de suavização sob a chave `'amplitude'`.

    Returns:
        Tupla `(porcentagem, angulo_suave, (p1, p2, p3))` com o percentual inteiro `[0, 100]`,
        o ângulo filtrado em graus e as coordenadas espaciais das três articulações avaliadas.
    """
    # Desempacota a tripla anatômica: extremidade proximal (p1), vértice (p2) e distal (p3)
    p1_idx, p2_idx, p3_idx = config_exercicio["lados"][melhor_lado]
    p1 = _pt(keypoints_data[p1_idx])
    p2 = _pt(keypoints_data[p2_idx])
    p3 = _pt(keypoints_data[p3_idx])

    # Cálculo trigonométrico vetorial 3D (ou 2D em fallback) no vértice p2
    angulo_bruto = calcular_angulo(p1, p2, p3)

    # Suavização temporal passa-baixas independente por lado anatômico
    filtro_amp = filtros.get('amplitude', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_amp.atualizar(angulo_bruto) if filtro_amp else angulo_bruto

    # Interpolação linear da amplitude entre o repouso ('inicio' -> 0%) e o ápice ('fim' -> 100%)
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
    """Emite telemetria em tempo real no terminal para calibração do Desenvolvimento de Ombros.

    Imprime quadro a quadro (`flush=True`) o estado atual da máquina de estados (`fase`),
    a percentagem normalizada, o total de repetições e os ângulos brutos/suavizados dos
    cotovelos `(5, 7, 9)/(6, 8, 10)`, ombros `(11, 5, 7)/(12, 6, 8)` e inclinação do tronco,
    permitindo aferir empiricamente os limiares em `config_exercicios.py` mesmo sem monitor de vídeo.

    Args:
        keypoints_data: Lista de 17 keypoints COCO `[x, y, conf(, z)]` do frame atual.
        fase: Fase corrente reportada pela FSM (`'calibracao'`, `'fora'`, `'base'`, `'subida'`,
            `'topo'` ou `'descida'`).
        porc: Percentual de execução da amplitude (`0` a `100%`).
        reps: Contagem acumulada de repetições concluídas na série.
        melhor_lado: Hemicorpo ativo utilizado pelo contador (`'esq'` ou `'dir'`).
        angulo_suave: Ângulo principal filtrado pelo `FiltroSuavizacao` (opcional).
        angulo_tronco: Desvio angular do tronco face ao eixo vertical em graus (opcional).
    """
    def _calc_tripla(i1: int, i2: int, i3: int, limiar: float = 0.2) -> str:
        """Formata o ângulo de uma tripla COCO usando limiar permissivo para depuração."""
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

    # Ângulos de extensão dos cotovelos e abdução/flexão glenoumeral dos ombros
    cot_esq = _calc_tripla(5, 7, 9)    # Ombro Esq - Cotovelo Esq - Pulso Esq
    cot_dir = _calc_tripla(6, 8, 10)   # Ombro Dir - Cotovelo Dir - Pulso Dir
    omb_esq = _calc_tripla(11, 5, 7)   # Quadril Esq - Ombro Esq - Cotovelo Esq
    omb_dir = _calc_tripla(12, 6, 8)   # Quadril Dir - Ombro Dir - Cotovelo Dir

    # Determina inclinação vertical da coluna caso não tenha sido pré-calculada
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
    """Orquestra a deteção de erros de postura e compensações biomecânicas durante a série.

    Mecanismo Técnico de Deteção de Erros Posturais:
        Enquanto `calcular_amplitude_movimento` mede a articulação motora primária, esta função
        fiscaliza as articulações estabilizadoras para detetar "roubos" (*cheating*) ou desvios
        potencialmente lesivos durante o esforço concêntrico/excêntrico:
        1. **Despacho Especializado (*Strategy Pattern*):** Caso o exercício possua regras
           anatômicas específicas (ex.: janela dupla `30°–75°` na Remada Curvada ou distância
           inter-maleolar no Agachamento Sumô), delega ao validador dedicado `validar_postura_*`.
        2. **Motor Paramétrico Geral (`config_exercicio["postura"]`):** Para os demais exercícios:
           - Se `postura_vertical=True`, mede o ângulo entre o segmento corporal `(sp1, sp2)` e
             o vetor gravitacional vertical gerado por `_ponto_acima(sp2)` (ex.: inclinação do
             tronco no Agachamento, Stiff e Desenvolvimento).
           - Se `postura_vertical=False`, mede o ângulo interno formado por três articulações
             estabilizadoras `(sp1, sp2, sp3)` (ex.: avanço do cotovelo `Quadril–Ombro–Cotovelo`
             na Rosca Bíceps, alinhamento `Ombro–Quadril–Tornozelo` na Flexão de Braço, ou flexão
             cervical `Nariz–Ombro–Quadril` no Abdominal Supra).
           - Após suavização temporal via `filtros['postura']`, compara o ângulo resultante com
             `limite_postura` segundo o operador relacional `regra_postura` (`"<"` ou `">"`).

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO `[x, y, confianca, z]` do frame atual.
        config_exercicio: Definição parametrizada do exercício (`postura`, `postura_vertical`,
            `limite_postura`, `regra_postura`).
        melhor_lado: Hemicorpo de maior confiança visual (`'esq'` ou `'dir'`).
        filtros: Dicionário contendo instâncias de `FiltroSuavizacao` sob a chave `'postura'`.

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_seguranca_suavizado)`, onde
        `postura_segura=False` sinaliza violação biomecânica para alerta visual/sonoro e
        contabilização de erro na série.
    """
    postura_segura = True
    coords_postura = None
    angulo_seg_suave = None

    # 1. Roteamento para validadores biomecânicos dedicados por família de movimento
    nome = config_exercicio.get("nome", "")
    # Nota: "Remada Alta" é verificada após "Remada" caso não haja distinção; aqui mantém-se
    # exatamente a árvore de decisão validada pelos testes de regressão do motor.
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

    # 2. Motor paramétrico genérico baseado nas regras declarativas de config_exercicios.py
    if not config_exercicio.get("postura"):
        return postura_segura, coords_postura, angulo_seg_suave

    # Verifica visibilidade mínima (> 0.5) dos dois primeiros marcos estabilizadores
    s1_idx, s2_idx = config_exercicio["postura"][melhor_lado][:2]
    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return postura_segura, coords_postura, angulo_seg_suave

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)

    ponto3_valido = True
    if config_exercicio.get("postura_vertical"):
        # Constrói eixo vertical virtual acima do vértice sp2 para aferir inclinação axial
        sp3 = _ponto_acima(sp2)
    else:
        # Utiliza uma terceira articulação anatômica real como referência angular relativa
        s3_idx = config_exercicio["postura"][melhor_lado][2]
        if keypoints_data[s3_idx][2] > 0.5:
            sp3 = _pt(keypoints_data[s3_idx])
        else:
            ponto3_valido = False

    if ponto3_valido:
        # Calcula e suaviza o ângulo postural antes de aplicar o comparador de limiar
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
    """Extrai as coordenadas espaciais dos membros superiores para renderização complementar.

    Em exercícios de membros inferiores (como o Agachamento), desenhar também o segmento
    dos braços auxilia na percepção visual do equilíbrio do tronco sem interferir no
    cálculo principal do joelho/quadril. Caso o pulso (`b3_idx`) esteja ocluído (`<= 0.5`),
    repete-se o cotovelo (`bp2`) para preservar a integridade da tupla de 3 pontos.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        config_exercicio: Dicionário do exercício contendo opcionalmente a chave `'bracos'`.
        melhor_lado: Hemicorpo ativo (`'esq'` ou `'dir'`).

    Returns:
        Tupla `(bp1, bp2, bp3)` com as coordenadas de ombro, cotovelo e pulso, ou `None`
        quando não aplicável ou sem visibilidade mínima.
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


# ==============================================================================
# AVALIAÇÃO DE ASSIMETRIA MUSCULAR BILATERAL
# ==============================================================================

def calcular_assimetria(
    keypoints_data: Sequence[Sequence[float]]
) -> Tuple[Optional[float], Optional[float], bool]:
    """Avalia o desequilíbrio angular instantâneo entre os cotovelos esquerdo e direito (COCO).

    Compara simultaneamente as cadeias `BRACO_ESQ (5, 7, 9)` e `BRACO_DIR (6, 8, 10)`
    durante movimentos bilaterais simétricos. Se o módulo da diferença entre os dois
    ângulos exceder `LIMITE_ASSIMETRIA` (`15°`), sinaliza alerta visual de compensação
    unilateral para que o atleta equilibre a velocidade concêntrica/excêntrica entre os lados.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO `[x, y, confianca, z]`.

    Returns:
        Tupla `(angulo_esq, angulo_dir, alerta_assimetria)`. Caso qualquer uma das 6
        articulações tenha confiança `< 0.5` (ex.: vista estritamente lateral), retorna
        `(None, None, False)` para evitar falsos alertas.
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
    """Deteta assimetria severa (`> 25°`) entre os membros superiores para aviso sonoro de voz.

    Diferencia-se de `calcular_assimetria` por utilizar um limiar mais conservador
    (`LIMITE_ASSIMETRIA_VOZ = 25°`, evitando fadiga auditiva por pequenas variações naturais)
    e por aceitar diretamente tanto os 33 landmarks brutos do MediaPipe/ML Kit (índices
    `11, 13, 15` e `12, 14, 16`) quanto os 17 keypoints COCO (`5, 7, 9` e `6, 8, 10`).

    Args:
        landmarks_ou_keypoints: Sequência de 33 landmarks MediaPipe/ML Kit ou 17 keypoints COCO.

    Returns:
        Tupla `(assimetria_detectada, diferenca_angular, angulo_esq, angulo_dir)`.
    """
    # Ramo 1: Entrada direta com 33 landmarks MediaPipe / ML Kit
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
        # Ramo 2: Entrada convertida no padrão COCO de 17 keypoints
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


# ==============================================================================
# VALIDADORES BIOMECÂNICOS ESPECIALIZADOS POR EXERCÍCIO
# ==============================================================================

def validar_postura_prancha(
    landmarks_ou_keypoints: Any,
    filtros: Optional[Dict[str, Any]] = None
) -> Optional[Tuple[bool, float, str, Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]]]]:
    """Avalia o alinhamento axial na Prancha Isométrica Ventral (`Ombro–Quadril–Tornozelo`).

    Critério Biomecânico:
        Na prancha ventral correta, tronco, pelve e membros inferiores formam uma linha quase
        colinear (`~180°`). Quando os músculos estabilizadores do *core* (transverso abdominal,
        reto abdominal e glúteos) entram em fadiga, a pelve sofre anteversão e queda gravitacional,
        fechando o ângulo no vértice do quadril (`< 160°`) e sobrecarregando as facetas lombares.
        Enquanto `angulo_suave >= 160.0°`, o `CronometroIsometrico` acumula tempo válido.

    Args:
        landmarks_ou_keypoints: Landmarks MediaPipe (33) ou keypoints COCO (17).
        filtros: Dicionário contendo filtros de suavização temporal (`'amplitude'`).

    Returns:
        Tupla `(postura_correta, angulo_suave, melhor_lado, (p1, p2, p3))`, ou `None` caso o
        corpo não esteja visível de perfil.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    lados_prancha = {"esq": (5, 11, 15), "dir": (6, 12, 16)}
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, lados_prancha)
    if not melhor_lado:
        return None

    p1 = _pt(keypoints_data[indices[0]])  # Ombro (extremidade cranial)
    p2 = _pt(keypoints_data[indices[1]])  # Quadril (vértice central de estabilização pélvica)
    p3 = _pt(keypoints_data[indices[2]])  # Tornozelo (extremidade caudal)

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
    """Valida a janela angular de inclinação do tronco na Remada Curvada (`30° <= θ <= 75°`).

    Critério Biomecânico:
        Na Remada Curvada livre, o tronco deve permanecer inclinado à frente por flexão de
        quadril (*hip hinge*):
        - Se `θ < 30°` em relação à vertical, o praticante ergueu excessivamente o tronco,
          desviando o vetor de carga do latíssimo do dorso para o trapézio superior ("roubo").
        - Se `θ > 75°`, há flexão/inclinação excessiva com risco elevado de cisalhamento lombar.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário contendo filtros de suavização postural (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    s1_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    s2_idx = 11 if melhor_lado == "esq" else 12  # Quadril (vértice)

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)
    sp3 = _ponto_acima(sp2)  # Vetor vertical de referência acima do quadril

    angulo_bruto = calcular_angulo(sp1, sp2, sp3)
    filtro_post = filtros.get('postura', {}).get(melhor_lado) if filtros else None
    angulo_suave = filtro_post.atualizar(angulo_bruto) if filtro_post else angulo_bruto

    # Exige permanência do tronco estritamente dentro da faixa biomecânica ótima [30°, 75°]
    postura_segura = 30.0 <= angulo_suave <= 75.0
    return postura_segura, coords_postura, angulo_suave


def validar_postura_supino(
    keypoints_data: Sequence[Sequence[float]],
    melhor_lado: str,
    filtros: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]], Optional[float]]:
    """Fiscaliza o ângulo de abdução glenoumeral no Supino com Halteres (`<= 90°`).

    Critério Biomecânico:
        Mede o ângulo `Quadril–Ombro–Cotovelo`. Aberturas de cotovelo superiores a `90°`
        ("supino em T" com cotovelos alinhados ou acima da linha clavicular) reduzem o espaço
        subacromial durante a fase excêntrica/concêntrica, aumentando o risco de impacto no
        manguito rotador (tendão do supraespinhal). Recomenda-se plano escapular (`<= 90°`).

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário contendo filtros de suavização postural (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro (vértice glenoumeral)
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
    """Limita a abdução máxima na Elevação Lateral à linha horizontal dos ombros (`<= 95°`).

    Critério Biomecânico:
        Na Elevação Lateral, o deltoide medial atinge pico de torque próximo aos `90°` de
        abdução (`Quadril–Ombro–Cotovelo`). Elevar os membros superiores acima de `95°`
        transfere o trabalho para o trapézio superior por rotação escapular superior e
        favorece impacto subacromial sob carga.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário contendo filtros de suavização postural (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro (vértice)
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
    """Previne hiperextensão lombar no topo concêntrico da Elevação Pélvica (`<= 185°`).

    Critério Biomecânico:
        Avalia o alinhamento `Ombro–Quadril–Joelho` no final da extensão de quadril. O objetivo
        concêntrico é atingir neutralidade pélvica/torácica (`~175°–180°`) por contração do
        glúteo máximo; ultrapassar `185°` indica arqueamento excessivo da coluna lombar.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário contendo filtros de suavização postural (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril (vértice)
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
    """Valida o afastamento podal característico do Agachamento Sumô (`dist_pes > dist_ombros`).

    Critério Antropométrico:
        Diferentemente do agachamento convencional, o Agachamento Sumô exige abdução coxofemoral
        ampla para recrutamento prioritário dos adutores magnos e glúteos. Compara-se no eixo
        horizontal `X` a distância inter-maleolar (tornozelos) com a distância biacromial
        (ombros): a postura só é considerada válida quando a base dos pés supera a largura
        dos ombros (`diferenca > 0`).

    Args:
        landmarks_ou_keypoints: Landmarks MediaPipe (33) ou keypoints COCO (17).
        melhor_lado: Mantido na assinatura por polimorfismo com os demais validadores.
        filtros: Dicionário de filtros (opcional).

    Returns:
        Tupla `(postura_segura, coords_postura, diferenca_largura)`.
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

    # Distâncias horizontais projetadas no plano frontal da câmara
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
    """Verifica a ultrapassagem da linha da barra no ápice concêntrico da Barra Fixa (*Pull-up*).

    Critério Cinemático:
        Na Barra Fixa, os pulsos permanecem fixos na barra horizontal (`y_barra` = média vertical
        dos pulsos visíveis). Como no sistema de coordenadas de imagem a origem `(0, 0)` situa-se
        no canto superior esquerdo (eixo `Y` cresce para baixo), o atleta atinge o topo válido
        quando a ordenada do nariz (`p_nariz[1]`) torna-se menor ou igual a `y_barra`.

    Args:
        landmarks_ou_keypoints: Landmarks MediaPipe (33) ou keypoints COCO (17).
        melhor_lado: Parâmetro opcional para compatibilidade de interface.
        filtros: Dicionário de filtros (opcional).

    Returns:
        Tupla `(queixo_acima, coords_visual, diferenca_y)`, onde `diferenca_y > 0` indica
        quantos pixels/unidades a cabeça subiu acima da linha da barra.
    """
    if len(landmarks_ou_keypoints) >= 33:
        p_nariz, conf_n = _obter_coord_conf(landmarks_ou_keypoints[0])
        p_pe, conf_pe = _obter_coord_conf(landmarks_ou_keypoints[15])
        p_pd, conf_pd = _obter_coord_conf(landmarks_ou_keypoints[16])
        if conf_n < 0.5 or (conf_pe < 0.5 and conf_pd < 0.5):
            return False, None, None
        pulsos_y = []
        if conf_pe >= 0.5:
            pulsos_y.append(p_pe[1])
        if conf_pd >= 0.5:
            pulsos_y.append(p_pd[1])
        y_barra = sum(pulsos_y) / len(pulsos_y)
        coords_visual = (p_nariz, (p_nariz[0], y_barra))
    else:
        kps = landmarks_ou_keypoints
        if kps[0][2] < 0.5 or (kps[9][2] < 0.5 and kps[10][2] < 0.5):
            return False, None, None
        p_nariz = _pt(kps[0])
        pulsos_y = []
        if kps[9][2] >= 0.5:
            pulsos_y.append(kps[9][1])
        if kps[10][2] >= 0.5:
            pulsos_y.append(kps[10][1])
        y_barra = sum(pulsos_y) / len(pulsos_y)
        coords_visual = (p_nariz, (p_nariz[0], y_barra))

    # No referencial matricial de imagem, menor valor de Y significa posição mais elevada
    queixo_acima = p_nariz[1] <= y_barra
    diferenca_y = y_barra - p_nariz[1]
    return queixo_acima, coords_visual, diferenca_y


def validar_postura_prancha_lateral(
    landmarks_ou_keypoints: Any,
    filtros: Optional[Dict[str, Any]] = None
) -> Optional[Tuple[bool, float, str, Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[float, ...]]]]:
    """Avalia o alinhamento coronal na Prancha Lateral Isométrica (`Ombro–Quadril–Tornozelo >= 160°`).

    Critério Biomecânico:
        Exige coaptação ativa do quadrado lombar, oblíquos e glúteo médio para sustentar a pelve
        alinhada à coluna e aos membros inferiores. Caso o quadril ceda em direção ao solo, o
        ângulo lateral `Ombro–Quadril–Tornozelo` cai abaixo de `160°`, pausando o cronômetro
        isométrico e disparando correção postural.

    Args:
        landmarks_ou_keypoints: Landmarks MediaPipe (33) ou keypoints COCO (17).
        filtros: Dicionário contendo filtros de suavização (`'amplitude'`).

    Returns:
        Tupla `(postura_correta, angulo_suave, melhor_lado, (p1, p2, p3))`, ou `None` se
        a visibilidade for insuficiente.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    lados_prancha = {"esq": (5, 11, 15), "dir": (6, 12, 16)}
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, lados_prancha)
    if not melhor_lado:
        return None

    p1 = _pt(keypoints_data[indices[0]])  # Ombro
    p2 = _pt(keypoints_data[indices[1]])  # Quadril (vértice de flexão lateral)
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
    """Deteta compensação por impulso lombar na Elevação Frontal (`Ombro–Quadril–Tornozelo >= 165°`).

    Critério Biomecânico:
        Quando a carga é excessiva ou instala-se fadiga no deltoide anterior, é comum o atleta
        projetar o quadril à frente e inclinar o tronco para trás durante a fase concêntrica,
        reduzindo o ângulo `Ombro–Quadril–Tornozelo` abaixo de `165°`.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    o_idx = 5 if melhor_lado == "esq" else 6     # Ombro
    q_idx = 11 if melhor_lado == "esq" else 12   # Quadril (vértice de oscilação do tronco)
    t_idx = 15 if melhor_lado == "esq" else 16   # Tornozelo

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
    """Garante a estabilização do úmero no Tríceps Testa (`Quadril–Ombro–Cotovelo <= 110°`).

    Critério Biomecânico:
        Para isolar as três cabeças do tríceps braquial, o úmero deve permanecer praticamente
        fixo (~90° em relação ao tronco deitado), movendo-se apenas o antebraço no cotovelo.
        Se o ângulo `Quadril–Ombro–Cotovelo` ultrapassar `110°`, o cotovelo deslocou-se
        excessivamente para trás da cabeça ou abriu, descaracterizando a alavanca pura de extensão.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro (vértice umeral)
    c_idx = 7 if melhor_lado == "esq" else 8    # Cotovelo

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
    """Protege a articulação do cotovelo e o tendão do bíceps no Crucifixo (`<= 165°`).

    Critério Biomecânico:
        No Crucifixo com Halteres, manter os cotovelos completamente bloqueados em `~180°`
        durante a abertura excêntrica cria um braço de alavanca excessivo sobre a cápsula
        anterior do ombro e a inserção distal do bíceps braquial. Exige-se uma semiflexão
        protetora constante (`Ombro–Cotovelo–Pulso <= 165°`).

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    o_idx = 5 if melhor_lado == "esq" else 6   # Ombro
    c_idx = 7 if melhor_lado == "esq" else 8   # Cotovelo (vértice)
    p_idx = 9 if melhor_lado == "esq" else 10  # Pulso

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
    """Limita a inclinação axial máxima no Stiff Unilateral (`Ombro–Quadril vs vertical <= 75°`).

    Critério Biomecânico:
        Na dobradiça de quadril (*hip hinge*) unilateral, inclinações do tronco além de `75°`
        em relação à vertical geralmente decorrem de perda da neutralidade pélvica e flexão
        compensatória da coluna lombar após esgotada a extensibilidade dos isquiotibiais.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    s1_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    s2_idx = 11 if melhor_lado == "esq" else 12  # Quadril (vértice)

    if keypoints_data[s1_idx][2] <= 0.5 or keypoints_data[s2_idx][2] <= 0.5:
        return True, None, None

    sp1 = _pt(keypoints_data[s1_idx])
    sp2 = _pt(keypoints_data[s2_idx])
    coords_postura = (sp1, sp2)
    sp3 = _ponto_acima(sp2)  # Eixo vertical acima do quadril

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
    """Valida a extensão dos joelhos na Flexão Plantar em Pé (`Quadril–Joelho–Tornozelo >= 160°`).

    Critério Biomecânico:
        O músculo gastrocnêmio é biarticular (cruza joelho e tornozelo). Dobrar os joelhos
        (`< 160°`) coloca o gastrocnêmio em insuficiência ativa e utiliza impulso elástico do
        quadríceps para subir o corpo, reduzindo o estímulo alvo no tríceps sural.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    j_idx = 13 if melhor_lado == "esq" else 14  # Joelho (vértice)
    t_idx = 15 if melhor_lado == "esq" else 16  # Tornozelo

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
    """Controla a inclinação anterior do tronco no Agachamento Búlgaro (`<= 45°` da vertical).

    Critério Biomecânico:
        Embora uma leve inclinação anterior favoreça o recrutamento glúteo, inclinações acima
        de `45°` em relação ao eixo gravitacional indicam colapso torácico sobre a coxa dianteira
        e perda de estabilidade pélvica.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    s1_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    s2_idx = 11 if melhor_lado == "esq" else 12  # Quadril (vértice)

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
    """Fiscaliza a estabilidade vertical do tronco no Encolhimento de Ombros (`<= 20°`).

    Critério Biomecânico:
        A elevação escapular para o trapézio descendente deve ocorrer puramente no eixo vertical.
        Inclinações do tronco superiores a `20°` denunciam balanço pendular para impulsionar a carga.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    s1_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    s2_idx = 11 if melhor_lado == "esq" else 12  # Quadril (vértice)

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


# ==============================================================================
# FISIOLOGIA DO EXERCÍCIO, ENQUADRAMENTO E DEMAIS VALIDADORES ESPECÍFICOS
# ==============================================================================

def calcular_calorias(
    tempo_segundos: float,
    met: float,
    peso_kg: float = 70.0
) -> float:
    """Estima o dispêndio energético da série em quilocalorias (`kcal`) pelo modelo MET.

    Fundamentação Fisiológica (*Compendium of Physical Activities* — Ainsworth et al.):
        `1 MET` equivale à taxa metabólica de repouso aproximada de `1 kcal / kg / hora`.
        Logo, convertendo a duração efetiva da série de segundos para horas (`t / 3600`),
        obtém-se o gasto energético total:
            `kcal = (tempo_segundos / 3600.0) * MET * peso_kg`

    Args:
        tempo_segundos: Tempo efetivo sob atividade durante a série (em segundos).
        met: Equivalente Metabólico da Tarefa parametrizado em `config_exercicios.py`.
        peso_kg: Massa corporal do utilizador em quilogramas (valor de referência: `70.0`).

    Returns:
        Gasto energético estimado em `kcal` arredondado a duas casas decimais (`0.0` para
        entradas não positivas).
    """
    if tempo_segundos <= 0 or met <= 0 or peso_kg <= 0:
        return 0.0
    calorias = (tempo_segundos / 3600.0) * met * peso_kg
    return round(calorias, 2)


def verificar_fora_enquadramento(
    keypoints_data: Any,
    config_exercicio: Dict[str, Any]
) -> bool:
    """Deteta ausência do praticante ou corte das articulações essenciais no campo de visão.

    Atua como *guard clause* de segurança no início de cada frame: se nenhuma das cadeias
    laterais do exercício apresentar confiança mínima `>= 0.3` em todos os seus pontos (ou, no
    caso global do Polichinelo, nos ombros, pulsos e tornozelos simultaneamente), suspende o
    cálculo de ângulos e reinicia a calibração para evitar contagens espúrias na borda da lente.

    Args:
        keypoints_data: Landmarks brutos (33 pontos) ou keypoints COCO (17 pontos) do frame.
        config_exercicio: Dicionário do exercício contendo as cadeias articulares obrigatórias.

    Returns:
        `True` se o atleta estiver fora de enquadramento ou sem visibilidade mínima; `False`
        quando há ao menos uma cadeia cinética íntegra para avaliação.
    """
    if keypoints_data is None or len(keypoints_data) == 0:
        return True

    # Normaliza automaticamente caso receba payload bruto de 33 landmarks do cliente
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
        # Exige enquadramento de corpo inteiro frontal: ombros (5,6), pulsos (9,10) e tornozelos (15,16)
        pontos_obrigatorios = [5, 6, 9, 10, 15, 16]
        for p in pontos_obrigatorios:
            if p >= len(keypoints_data) or keypoints_data[p][2] < 0.3:
                return True
        return False

    lados = config_exercicio.get("lados", {})
    if not lados:
        confs = [kp[2] for kp in keypoints_data if len(kp) > 2]
        return not confs or (sum(confs) / len(confs)) < 0.3

    # Basta que um dos hemicorpos ('esq' ou 'dir') tenha todas as articulações da tripla >= 0.3
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
    """Valida a extensão dos membros inferiores no Abdominal Infra (`Quadril–Joelho–Tornozelo >= 130°`).

    Critério Biomecânico:
        Na elevação de pernas em decúbito dorsal, flexionar acentuadamente os joelhos (`< 130°`)
        encurta o braço de resistência dos membros inferiores, reduzindo substancialmente o
        torque exigido da porção infraumbilical do reto abdominal.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    j_idx = 13 if melhor_lado == "esq" else 14  # Joelho (vértice)
    t_idx = 15 if melhor_lado == "esq" else 16  # Tornozelo

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
    """Verifica a manutenção do tronco ereto na Remada Alta (`Ombro–Quadril vs vertical <= 25°`).

    Critério Biomecânico:
        Impede que o praticante utilize hiperextensão lombar de impulso no final da puxada
        concêntrica vertical da barra ou halteres.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    s1_idx = 5 if melhor_lado == "esq" else 6    # Ombro
    s2_idx = 11 if melhor_lado == "esq" else 12  # Quadril (vértice)

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
    """Garante semiflexão controlada dos joelhos no exercício Bom Dia / *Good Morning* (`>= 150°`).

    Critério Biomecânico:
        O exercício Bom Dia visa a cadeia posterior (eretores da espinha, glúteos e isquiotibiais)
        via flexão pura de quadril. Caso o ângulo `Quadril–Joelho–Tornozelo` desça abaixo de `150°`,
        o movimento descaracteriza-se num agachamento híbrido.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    j_idx = 13 if melhor_lado == "esq" else 14  # Joelho (vértice)
    t_idx = 15 if melhor_lado == "esq" else 16  # Tornozelo

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
    """Assegura a elevação do braço paralelo ao tronco no Tríceps Coice (`Quadril–Ombro–Cotovelo >= 25°`).

    Critério Biomecânico:
        Para que a gravidade atue perpendicularmente ao antebraço no pico concêntrico da extensão
        do tríceps, o cotovelo deve permanecer elevado ao lado/atrás do tronco (`>= 25°`). Deixar
        o cotovelo cair verticalmente anula o torque resistivo no topo do movimento.

    Args:
        keypoints_data: Matriz dos 17 keypoints COCO do frame atual.
        melhor_lado: Hemicorpo selecionado (`'esq'` ou `'dir'`).
        filtros: Dicionário de filtros de postura (`'postura'`).

    Returns:
        Tupla `(postura_segura, coords_postura, angulo_suave)`.
    """
    q_idx = 11 if melhor_lado == "esq" else 12  # Quadril
    o_idx = 5 if melhor_lado == "esq" else 6    # Ombro (vértice)
    c_idx = 7 if melhor_lado == "esq" else 8    # Cotovelo

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
    """Avalia a sustentação na zona angular alvo do Agachamento Isométrico / *Wall Sit* (`75°–105°`).

    Critério Biomecânico:
        Exige flexão estática do joelho (`Quadril–Joelho–Tornozelo`) centrada em `90°` com
        margem fisiológica de `±15°`:
        - `> 105°`: Quadril alto demais (redução indevida do braço de momento patelofemoral);
          orienta `"Desca mais o quadril"`.
        - `< 75°`: Agachamento profundo abaixo da zona isométrica prescrita; orienta
          `"Suba um pouco o quadril"`.

    Args:
        landmarks_ou_keypoints: Landmarks MediaPipe (33) ou keypoints COCO (17).
        filtros: Dicionário contendo filtros de suavização (`'amplitude'`).

    Returns:
        Tupla `(postura_correta, angulo_suave, melhor_lado, (p1, p2, p3), msg_correcao)`,
        ou `None` caso não haja visibilidade suficiente.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    lados_joelho = {"esq": (11, 13, 15), "dir": (12, 14, 16)}
    melhor_lado, indices = selecionar_melhor_lado(keypoints_data, lados_joelho)
    if not melhor_lado:
        return None

    p1 = _pt(keypoints_data[indices[0]])  # Quadril
    p2 = _pt(keypoints_data[indices[1]])  # Joelho (vértice isométrico)
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
    """Modela a cinemática acoplada multiarticular e a coordenação motora do Polichinelo.

    Modelagem Matemática Híbrida (Invariante à Distância da Câmara):
        Todas as distâncias lineares são normalizadas pela largura biacromial instantânea
        (`larg_ombros`), tornando o algoritmo invariante à estatura do praticante e à sua
        distância até o telemóvel:
        1. **Componente Braquial (`porc_bracos`):** Elevação vertical dos pulsos desde a linha
           do quadril (`0%`) até meia largura de ombro acima da linha acromial (`100%`).
        2. **Componente Crural (`porc_pernas`):** Afastamento horizontal dos tornozelos desde
           a base fechada (`0.8 * larg_ombros` -> `0%`) até o salto aberto (`2.0 * larg_ombros`
           -> `100%`).
        3. **Fusão e Validação de Sincronia Coordenativa:** A amplitude global que alimenta a
           máquina de estados `ContadorRepeticoes` é a média ponderada `50%/50%` suavizada.
           Se a discrepância instantânea `|porc_bracos - porc_pernas|` exceder `45%`, deteta-se
           assincronia neuromotora (`"Sincronize bracos e pernas"`).

    Args:
        landmarks_ou_keypoints: Landmarks MediaPipe (33) ou keypoints COCO (17).
        filtros: Dicionário contendo filtros de suavização (`'amplitude'`).

    Returns:
        Tupla `(porc, postura_segura, coords_bracos, coords_pernas, msg_erro)` ou `None` se
        faltar visibilidade de corpo inteiro.
    """
    keypoints_data = landmarks_mediapipe_para_keypoints(landmarks_ou_keypoints)
    pontos_obrigatorios = [5, 6, 9, 10, 11, 12, 15, 16]
    if any(p >= len(keypoints_data) or keypoints_data[p][2] < 0.3 for p in pontos_obrigatorios):
        return None

    p_ombro_esq, p_ombro_dir = _pt(keypoints_data[5]), _pt(keypoints_data[6])
    p_pulso_esq, p_pulso_dir = _pt(keypoints_data[9]), _pt(keypoints_data[10])
    p_quadril_esq, p_quadril_dir = _pt(keypoints_data[11]), _pt(keypoints_data[12])
    p_tornozelo_esq, p_tornozelo_dir = _pt(keypoints_data[15]), _pt(keypoints_data[16])

    # Escala antropométrica de referência para invariância à distância focal
    larg_ombros = max(20.0, abs(p_ombro_dir[0] - p_ombro_esq[0]))
    y_ombros = (p_ombro_esq[1] + p_ombro_dir[1]) / 2.0
    y_quadril = (p_quadril_esq[1] + p_quadril_dir[1]) / 2.0
    y_pulsos = (p_pulso_esq[1] + p_pulso_dir[1]) / 2.0

    # 1. Amplitude percentual de abdução dos membros superiores no eixo Y
    altura_mov_bracos = max(1.0, y_quadril - (y_ombros - larg_ombros * 0.5))
    porc_bracos = max(0.0, min(100.0, ((y_quadril - y_pulsos) / altura_mov_bracos) * 100.0))

    # 2. Amplitude percentual de abdução dos membros inferiores no eixo X
    dist_tornozelos = abs(p_tornozelo_dir[0] - p_tornozelo_esq[0])
    abertura_min = larg_ombros * 0.8
    abertura_max = larg_ombros * 2.0
    porc_pernas = max(
        0.0,
        min(100.0, ((dist_tornozelos - abertura_min) / max(1.0, abertura_max - abertura_min)) * 100.0),
    )

    # 3. Fusão linear equiponderada e filtragem temporal passa-baixas
    porc_bruta = (porc_bracos * 0.5) + (porc_pernas * 0.5)
    filtro_amp = filtros.get('amplitude', {}).get('esq') if filtros else None
    porc_suave = filtro_amp.atualizar(porc_bruta) if filtro_amp else porc_bruta
    porc = int(max(0, min(100, porc_suave)))

    # 4. Verificação de coordenação inter-membros (braços e pernas devem abrir/fechar em fase)
    postura_segura = abs(porc_bracos - porc_pernas) <= 45.0
    msg_erro = "" if postura_segura else "Sincronize bracos e pernas"

    coords_bracos = (p_ombro_esq, p_pulso_esq)
    coords_pernas = (p_tornozelo_esq, p_tornozelo_dir)

    return porc, postura_segura, coords_bracos, coords_pernas, msg_erro


def verificar_fadiga(
    tempos_repeticoes: List[float]
) -> bool:
    """Deteta fadiga neuromuscular periférica pela queda de velocidade de execução (*VBT*).

    Fundamentação Biomecânica (*Velocity-Based Training*):
        À medida que as unidades motoras de contração rápida entram em fadiga metabólica
        durante uma série até próximo da falha, a velocidade da fase concêntrica reduz-se
        progressivamente, dilatando o tempo total de ciclo de cada repetição.
        Estabelece-se a cadência basal do próprio indivíduo a partir da média aritmética das
        `3` primeiras repetições válidas (`ritmo_base`); a partir da `4ª` repetição, caso a
        duração da repetição recém-concluída supere `1.6 * ritmo_base` (desaceleração `> 60%`),
        sinaliza-se instalação de fadiga.

    Args:
        tempos_repeticoes: Histórico cronológico das durações (em segundos) de cada repetição
            concluída na série atual, registado pelo `ContadorRepeticoes`.

    Returns:
        `True` quando há no mínimo 4 repetições e a última excede em mais de `60%` o ritmo
        médio inicial; `False` caso contrário.
    """
    if not tempos_repeticoes or len(tempos_repeticoes) < 4:
        return False

    # Cadência individual de referência nas 3 repetições iniciais sem fadiga acumulada
    ritmo_base = sum(tempos_repeticoes[:3]) / 3.0
    if ritmo_base <= 0:
        return False

    ultima_rep = tempos_repeticoes[-1]
    return ultima_rep > 1.6 * ritmo_base
