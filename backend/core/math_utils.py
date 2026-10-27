"""Núcleo Matemático, Trigonométrico e de Máquinas de Estado do IAFit.

Este módulo concentra os algoritmos fundamentais de cinemática angular, filtragem
digital de sinais e máquinas de estados finitos (FSM) que sustentam a avaliação
biomecânica do IAFit:

1. **Geometria Analítica e Trigonometria Vetorial (`calcular_angulo`):**
   Determina o ângulo interno formado por três marcos anatômicos consecutivos
   (ex.: Ombro–Cotovelo–Pulso) no espaço euclidiano tridimensional (R³) através
   do produto escalar entre vetores adjacentes ao vértice articular, recorrendo
   automaticamente à função arco-tangente de dois argumentos (`atan2`) em R²
   quando a coordenada de profundidade `Z` não está disponível.
2. **Normalização da Amplitude de Movimento — ROM (`calcular_porcentagem`):**
   Mapeia linearmente o ângulo articular instantâneo para uma escala percentual
   padronizada `[0%, 100%]`, abstraindo se a fase concêntrica ocorre por flexão
   (redução angular, como na Rosca Bíceps) ou por extensão/abdução (aumento
   angular, como no Desenvolvimento de Ombros).
3. **Filtragem Passa-Baixas (`FiltroSuavizacao`):**
   Aplica uma janela deslizante de Média Móvel Simples (filtro FIR) para atenuar
   oscilações de alta frequência (*jitter*) inerentes à inferência quadro a quadro.
4. **Máquina de Estados Finitos das Fases Concêntrica e Excêntrica (`ContadorRepeticoes`):**
   Modela o ciclo biomecânico completo (`base` -> `subida` [concêntrica] -> `topo`
   -> `descida` [excêntrica] -> `base`) com banda de histerese para contabilizar
   apenas repetições com amplitude efetiva e extrair a cadência temporal por repetição.
5. **Integração Temporal Condicionada (`CronometroIsometrico`):**
   Acumula o tempo sob tensão (*Time Under Tension*) exclusivamente nos intervalos
   em que o alinhamento postural permanece dentro dos limites biomecânicos seguros.
"""

import math
import time
from collections import deque
from typing import Deque, List, Optional, Sequence, Tuple, Union
import numpy as np
from core.voz_client import falar


def _calcular_angulo_2d(
    a: Sequence[float],
    b: Sequence[float],
    c: Sequence[float]
) -> float:
    """Calcula o ângulo planar 2D (em graus) no vértice `b` formado pelos segmentos `ba` e `bc`.

    Atua como mecanismo de *fallback* trigonométrico para extratores de pose puramente
    bidimensionais (como YOLOv8-pose no padrão COCO 2D), onde não há estimativa de
    profundidade (`Z`). Utiliza `math.atan2(dy, dx)` para obter a orientação polar de
    cada segmento anatômico em relação ao eixo horizontal no intervalo `[-π, π]`,
    evitando divisões por zero em segmentos perfeitamente verticais.

    Args:
        a: Coordenadas planares `(x, y, ...)` da articulação proximal (ex.: Ombro).
        b: Coordenadas planares `(x, y, ...)` do vértice articular central (ex.: Cotovelo).
        c: Coordenadas planares `(x, y, ...)` da articulação distal (ex.: Pulso).

    Returns:
        Ângulo articular interno convexo em graus, limitado ao intervalo `[0.0, 180.0]`.
    """
    # Subtrai os ângulos polares dos vetores bc = (c - b) e ba = (a - b)
    radianos = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])

    # Converte de radianos para graus em valor absoluto [0°, 360°]
    angulo = abs(math.degrees(radianos))

    # Garante sempre o menor ângulo interno convexo da articulação (<= 180°),
    # descartando o ângulo reflexo complementar externo (360° - θ).
    if angulo > 180.0:
        angulo = 360.0 - angulo
    return float(angulo)


def calcular_angulo(
    a: Sequence[float],
    b: Sequence[float],
    c: Sequence[float]
) -> float:
    """Calcula o ângulo articular (em graus) no vértice `b` definido pelos pontos `a`, `b` e `c`.

    Fundamentação Matemática:
        Quando os três pontos possuem coordenadas tridimensionais `(x, y, z)` (como nos
        33 landmarks extraídos pelo Google ML Kit / MediaPipe), o cálculo opera em R³
        construindo dois vetores originados no centro de rotação articular `b`:
            - `v1 = a - b` (segmento anatômico proximal)
            - `v2 = c - b` (segmento anatômico distal)
        Pela definição algébrica do produto escalar euclidiano (`v1 · v2 = ||v1|| ||v2|| cos θ`),
        isola-se o ângulo espacial real:
            `θ = arccos( (v1 · v2) / (||v1|| * ||v2||) )`
        Essa abordagem espacial compensa distorções de projeção de perspectiva (*foreshortening*)
        quando o atleta não está posicionado estritamente paralelo ao plano focal da câmara.
        Caso qualquer ponto contenha apenas `(x, y)`, delega-se ao cálculo planar `_calcular_angulo_2d`.

    Args:
        a: Coordenadas `(x, y[, z])` do primeiro marco anatômico.
        b: Coordenadas `(x, y[, z])` do vértice articular onde o ângulo é medido.
        c: Coordenadas `(x, y[, z])` do terceiro marco anatômico.

    Returns:
        Ângulo articular em graus no intervalo fechado `[0.0, 180.0]`. Retorna `0.0`
        se algum dos vetores for degenerado (norma nula por sobreposição de pontos).
    """
    if len(a) >= 3 and len(b) >= 3 and len(c) >= 3:
        # Extrai apenas as componentes espaciais (x, y, z) como vetores NumPy de precisão dupla
        pa = np.array(a[:3], dtype=float)
        pb = np.array(b[:3], dtype=float)
        pc = np.array(c[:3], dtype=float)

        # Vetores orientados a partir do centro articular b para as extremidades a e c
        vetor1 = pa - pb  # Segmento b -> a
        vetor2 = pc - pb  # Segmento b -> c

        # Normas euclidianas (comprimentos instantâneos dos segmentos ósseos em R³)
        norma1 = np.linalg.norm(vetor1)
        norma2 = np.linalg.norm(vetor2)

        # Proteção contra singularidade numérica (divisão por zero se dois pontos coincidirem)
        if norma1 == 0 or norma2 == 0:
            return 0.0

        # Cosseno diretor entre os segmentos; np.clip evita erros de domínio (NaN) em arccos
        # causados por imprecisões de ponto flutuante IEEE 754 (ex.: 1.0000000000000002)
        cos_angulo = np.dot(vetor1, vetor2) / (norma1 * norma2)
        return float(np.degrees(np.arccos(np.clip(cos_angulo, -1.0, 1.0))))

    # Fallback planar 2D caso não exista componente de profundidade Z
    return _calcular_angulo_2d(a, b, c)


def calcular_porcentagem(
    angulo: float,
    angulo_inicio: float,
    angulo_fim: float
) -> int:
    """Normaliza o ângulo articular atual numa percentagem linear de amplitude `[0, 100]`.

    Permite que a máquina de estados (`ContadorRepeticoes`) opere de forma agnóstica à
    direção anatômica do exercício:
        - `0%` representa sempre a posição anatômica alongada / base inicial da repetição.
        - `100%` representa sempre o pico da contração **concêntrica** (alvo biomecânico).

    Casos Geométricos Tratados:
        1. **Fase concêntrica por redução angular (`angulo_inicio > angulo_fim`):**
           Exemplos: Rosca Bíceps (`160° -> 40°`) e Agachamento (`170° -> 80°`, onde a descida
           até `80°` corresponde ao alcance da profundidade alvo `100%` antes da subida).
        2. **Fase concêntrica por aumento angular (`angulo_inicio < angulo_fim`):**
           Exemplos: Desenvolvimento de Ombros (`70° -> 160°`) e Elevação Lateral (`20° -> 90°`).

    Args:
        angulo: Ângulo articular instantâneo (já suavizado) medido em graus.
        angulo_inicio: Limiar angular correspondente ao repouso / base do movimento (`0%`).
        angulo_fim: Limiar angular correspondente ao ápice da amplitude alvo (`100%`).

    Returns:
        Percentagem inteira saturada (*clamped*) no intervalo `[0, 100]`.
    """
    if angulo_inicio > angulo_fim:
        # Movimentos onde o progresso até o ápice diminui o ângulo articular (ex.: 160° -> 40°)
        if angulo > angulo_inicio:
            return 0
        if angulo < angulo_fim:
            return 100
        return 100 - int(((angulo - angulo_fim) / (angulo_inicio - angulo_fim)) * 100)
    else:
        # Movimentos onde o progresso até o ápice aumenta o ângulo articular (ex.: 70° -> 160°)
        if angulo < angulo_inicio:
            return 0
        if angulo > angulo_fim:
            return 100
        return int(((angulo - angulo_inicio) / (angulo_fim - angulo_inicio)) * 100)


class FiltroSuavizacao:
    """Filtro passa-baixas de Média Móvel Simples (FIR) para estabilização temporal de ângulos.

    Redes neurais de estimativa de pose sofrem pequenas flutuações quadro a quadro
    (*keypoint jitter*) devido a variações de iluminação, borrão de movimento (*motion blur*)
    e quantização de pixels. Este filtro mantém uma fila circular (`deque`) das últimas `N`
    leituras angulares e devolve a média aritmética, suavizando a trajetória cinemática sem
    introduzir atraso perceptível na interface.
    """

    def __init__(self, tamanho: int = 5) -> None:
        """Inicializa o buffer circular do filtro com janela de comprimento fixo.

        Args:
            tamanho: Quantidade máxima de frames retidos na janela deslizante (padrão: `5`).
        """
        self.historico: Deque[float] = deque(maxlen=tamanho)

    def atualizar(self, valor: float) -> float:
        """Insere uma nova amostra angular na janela e calcula a média móvel atualizada.

        Args:
            valor: Medição angular bruta do frame corrente (em graus ou percentagem).

        Returns:
            Média aritmética das amostras presentes na janela deslizante.
        """
        self.historico.append(valor)
        return sum(self.historico) / len(self.historico)

    def limpar(self) -> None:
        """Esvazia o histórico de amostras (acionado na troca de exercício ou fim de série)."""
        self.historico.clear()


class ContadorRepeticoes:
    """Máquina de Estados Finitos (FSM) para avaliação das fases concêntrica e excêntrica.

    Em vez de utilizar um simples cruzamento de limiar único — que geraria contagens falsas
    por tremores corporais ou repetições incompletas (*meias repetições*) — esta classe
    implementa uma FSM determinística com dupla zona de transição e banda de histerese:

    Estados Biomecânicos (`self.fase`):
        - `'base'` (`porcentagem <= limite_baixo`, padrão `<= 10%`):
          Articulação na posição inicial / final de extensão ou alongamento.
        - `'subida'` (`Δporcentagem > +tolerancia`):
          Progressão ativa em direção ao ápice (tipicamente a **fase concêntrica**, onde o
          músculo agonista vence a resistência, ou descida controlada rumo à profundidade
          alvo em agachamentos).
        - `'topo'` (`porcentagem >= limite_alto`, padrão `>= 90%`):
          Ápice da amplitude alcançado; ativa o *latch* booleano interno `_atingiu_topo = True`.
        - `'descida'` (`Δporcentagem < -tolerancia`):
          Retorno controlado à posição inicial (tipicamente a **fase excêntrica**, onde há
          alongamento muscular sob tensão).

    Critério de Contabilização de Repetição:
        O contador `self.reps` só é incrementado quando o atleta cumpre o ciclo completo
        `base -> subida -> topo (_atingiu_topo=True) -> descida -> base`, garantindo que
        tanto o pico de contração quanto o retorno completo à base foram respeitados.
    """

    def __init__(
        self,
        limite_baixo: int = 10,
        limite_alto: int = 90,
        tolerancia: int = 2
    ) -> None:
        """Inicializa a máquina de estados e os cronômetros de cadência de repetição.

        Args:
            limite_baixo: Percentual máximo (`0-100`) que caracteriza o retorno à `'base'`.
            limite_alto: Percentual mínimo (`0-100`) exigido para validar o `'topo'` da repetição.
            tolerancia: Banda morta de histerese (em pontos percentuais) para filtrar micro-oscilações
                antes de alternar entre os estados `'subida'` e `'descida'`.
        """
        self.limite_baixo: int = limite_baixo
        self.limite_alto: int = limite_alto
        self.tolerancia: int = tolerancia
        self.tempo_ultima_rep: float = time.time()
        self.tempo_inicio_serie: Optional[float] = None
        self.tempos_repeticoes: List[float] = []
        self.ultimo_timestamp_rep: Optional[float] = None
        self.reps: int = 0
        self.fase: str = "base"
        self._atingiu_topo: bool = False
        self._ultima: Optional[float] = None
        self.limpar()

    def atualizar(self, porcentagem: float) -> Tuple[int, str]:
        """Processa a amplitude percentual do frame atual e avança o estado biomecânico.

        Args:
            porcentagem: Percentual normalizado de amplitude do movimento (`0` a `100%`).

        Returns:
            Tupla `(reps, fase)` contendo o total acumulado de repetições válidas e o
            identificador textual da fase corrente (`'base'`, `'subida'`, `'topo'` ou `'descida'`).
        """
        # Marca o início cronológico efetivo da série assim que o atleta sai da zona de repouso
        if self.tempo_inicio_serie is None and porcentagem > self.limite_baixo:
            self.tempo_inicio_serie = time.time()

        # 1. Verificação de entrada no Ápice ('topo' >= 90%): habilita a flag de meio-ciclo concluído
        if porcentagem >= self.limite_alto:
            self.fase = "topo"
            self._atingiu_topo = True
            if self.tempo_inicio_serie is None:
                self.tempo_inicio_serie = time.time()

        # 2. Verificação de retorno à Posição Inicial ('base' <= 10%): consolida a repetição completa
        elif porcentagem <= self.limite_baixo:
            if self._atingiu_topo:
                self.reps += 1
                agora = time.time()
                self.tempo_ultima_rep = agora
                if self.tempo_inicio_serie is None:
                    self.tempo_inicio_serie = agora

                # Regista o tempo gasto nesta repetição (concêntrica + excêntrica) para
                # posterior deteção algorítmica de fadiga neuromuscular em verificar_fadiga()
                tempo_ref = (
                    self.ultimo_timestamp_rep
                    if self.ultimo_timestamp_rep is not None
                    else self.tempo_inicio_serie
                )
                duracao_rep = agora - tempo_ref
                self.tempos_repeticoes.append(round(duracao_rep, 2))
                self.ultimo_timestamp_rep = agora

                # Feedback auditivo imediato informando a contagem ao praticante
                falar(str(self.reps))
                self._atingiu_topo = False
            self.fase = "base"

        # 3. Zona intermediária (10% < porcentagem < 90%): avalia derivada discreta com histerese
        elif self._ultima is not None:
            if porcentagem > self._ultima + self.tolerancia:
                self.fase = "subida"
                if self.tempo_inicio_serie is None:
                    self.tempo_inicio_serie = time.time()
            elif porcentagem < self._ultima - self.tolerancia:
                self.fase = "descida"

        # Atualiza memória da amostra anterior para cálculo diferencial no próximo frame
        self._ultima = porcentagem
        return self.reps, self.fase

    def limpar(self) -> None:
        """Restaura a máquina de estados, o contador e os registos temporais ao estado inicial."""
        self.reps = 0
        self.fase = "base"
        self._atingiu_topo = False
        self._ultima = None
        self.tempo_ultima_rep = time.time()
        self.tempo_inicio_serie = None
        self.tempos_repeticoes = []
        self.ultimo_timestamp_rep = None


class CronometroIsometrico:
    """Integrador temporal para exercícios isométricos estáticos (ex.: Pranchas e Agachamento Isométrico).

    Em exercícios isométricos não há ciclos concêntricos/excêntricos; o estímulo fisiológico
    decorre do tempo contínuo de sustentação sob alinhamento articular correto. Este cronômetro
    integra o delta de tempo (`Δt`) entre frames sucessivos apenas quando `postura_correta=True`,
    pausando automaticamente a contagem sempre que o quadril cede ou o atleta perde a forma.
    """

    def __init__(self) -> None:
        """Inicializa o acumulador de tempo sob tensão zerado."""
        self.tempo_acumulado: float = 0.0
        self.ultimo_tempo: Optional[float] = None
        self.tempo_ultima_atividade: float = time.time()
        self.tempo_ultima_rep: float = self.tempo_ultima_atividade
        self.limpar()

    def acumular(self, postura_correta: bool = True) -> float:
        """Integra o intervalo de tempo decorrido desde o último frame caso a postura seja válida.

        Inclui proteção contra saltos temporais (`0 < delta < 1.0`), evitando que pausas
        longas de rede, saída de enquadramento ou bloqueios de I/O somem segundos artificiais.

        Args:
            postura_correta: Indica se os ângulos de alinhamento corporal estão dentro da zona segura.

        Returns:
            Tempo acumulado exato em segundos (ponto flutuante).
        """
        agora = time.time()
        if self.ultimo_tempo is not None:
            delta = agora - self.ultimo_tempo
            if postura_correta and 0 < delta < 1.0:
                self.tempo_acumulado += delta
                self.tempo_ultima_atividade = agora
                self.tempo_ultima_rep = agora
        self.ultimo_tempo = agora
        return self.tempo_acumulado

    def atualizar(self, postura_correta: bool = True) -> float:
        """Alias de fachada para `acumular()`, mantendo interface uniforme com os demais filtros.

        Args:
            postura_correta: Indica se a postura articular permanece biomecanicamente válida.

        Returns:
            Tempo total acumulado em segundos.
        """
        return self.acumular(postura_correta)

    @property
    def segundos(self) -> int:
        """Devolve o tempo acumulado sob postura correta truncado em segundos inteiros."""
        return int(self.tempo_acumulado)

    def limpar(self) -> None:
        """Reinicia o acumulador isométrico e os marcadores temporais da série."""
        self.tempo_acumulado = 0.0
        self.ultimo_tempo = None
        self.tempo_ultima_atividade = time.time()
        self.tempo_ultima_rep = self.tempo_ultima_atividade
