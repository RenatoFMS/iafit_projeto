import math
import time
from collections import deque
import numpy as np
from core.voz_client import falar

def _calcular_angulo_2d(a, b, c):
    """Plano B: ângulo 2D (X, Y) via math.atan2, para modelos sem profundidade (YOLO/COCO)."""
    radianos = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
    angulo = abs(math.degrees(radianos))
    if angulo > 180.0:
        angulo = 360.0 - angulo
    return float(angulo)


def calcular_angulo(a, b, c):
    """Calcula o ângulo (em graus) no vértice b formado pelos pontos a, b e c.

    - Pontos 3D (X, Y, Z): usa vetores com numpy, ângulo = arccos(dot / (norm1 * norm2)),
      o que evita a distorção de perspetiva do cálculo 2D.
    - Pontos 2D (X, Y) ou dimensões mistas: recorre ao cálculo 2D com math.atan2.
    """
    if len(a) >= 3 and len(b) >= 3 and len(c) >= 3:
        pa = np.array(a[:3], dtype=float)
        pb = np.array(b[:3], dtype=float)
        pc = np.array(c[:3], dtype=float)
        vetor1 = pa - pb  # ponto 1 -> ponto 2 (vértice)
        vetor2 = pc - pb  # ponto 3 -> ponto 2 (vértice)
        norma1 = np.linalg.norm(vetor1)
        norma2 = np.linalg.norm(vetor2)
        if norma1 == 0 or norma2 == 0:
            return 0.0
        cos_angulo = np.dot(vetor1, vetor2) / (norma1 * norma2)
        return float(np.degrees(np.arccos(np.clip(cos_angulo, -1.0, 1.0))))
    return _calcular_angulo_2d(a, b, c)


def calcular_porcentagem(angulo, angulo_inicio, angulo_fim):
    """Converte o ângulo em uma porcentagem de 0 a 100%."""
    if angulo_inicio > angulo_fim:
        if angulo > angulo_inicio: return 0
        if angulo < angulo_fim: return 100
        return 100 - int(((angulo - angulo_fim) / (angulo_inicio - angulo_fim)) * 100)
    else:
        if angulo < angulo_inicio: return 0
        if angulo > angulo_fim: return 100
        return int(((angulo - angulo_inicio) / (angulo_fim - angulo_inicio)) * 100)

class FiltroSuavizacao:
    """Filtro de Média Móvel para estabilizar os tremores da câmera."""
    def __init__(self, tamanho=5):
        self.historico = deque(maxlen=tamanho)
        
    def atualizar(self, valor):
        self.historico.append(valor)
        return sum(self.historico) / len(self.historico)
        
    def limpar(self):
        self.historico.clear()


class ContadorRepeticoes:
    """Conta repetições a partir da percentagem de amplitude (0-100).

    Fases: 'subida' (percentagem a aumentar), 'descida' (a diminuir),
    'topo' (>= limite_alto) e 'base' (<= limite_baixo).
    Uma repetição é contada quando o movimento chega ao topo e volta à base.
    """
    def __init__(self, limite_baixo=10, limite_alto=90, tolerancia=2):
        self.limite_baixo = limite_baixo
        self.limite_alto = limite_alto
        self.tolerancia = tolerancia
        self.tempo_ultima_rep = time.time()
        self.tempo_inicio_serie = None
        self.tempos_repeticoes = []
        self.ultimo_timestamp_rep = None
        self.limpar()

    def atualizar(self, porcentagem):
        # Guarda o tempo em que a primeira repetição começou
        if self.tempo_inicio_serie is None and porcentagem > self.limite_baixo:
            self.tempo_inicio_serie = time.time()

        if porcentagem >= self.limite_alto:
            self.fase = "topo"
            self._atingiu_topo = True
            if self.tempo_inicio_serie is None:
                self.tempo_inicio_serie = time.time()
        elif porcentagem <= self.limite_baixo:
            if self._atingiu_topo:
                self.reps += 1
                agora = time.time()
                self.tempo_ultima_rep = agora
                if self.tempo_inicio_serie is None:
                    self.tempo_inicio_serie = agora

                # Grava a duração desta repetição
                tempo_ref = self.ultimo_timestamp_rep if self.ultimo_timestamp_rep is not None else self.tempo_inicio_serie
                duracao_rep = agora - tempo_ref
                self.tempos_repeticoes.append(round(duracao_rep, 2))
                self.ultimo_timestamp_rep = agora

                falar(str(self.reps))
                self._atingiu_topo = False
            self.fase = "base"
        elif self._ultima is not None:
            if porcentagem > self._ultima + self.tolerancia:
                self.fase = "subida"
                if self.tempo_inicio_serie is None:
                    self.tempo_inicio_serie = time.time()
            elif porcentagem < self._ultima - self.tolerancia:
                self.fase = "descida"
        self._ultima = porcentagem
        return self.reps, self.fase

    def limpar(self):
        self.reps = 0
        self.fase = "base"
        self._atingiu_topo = False
        self._ultima = None
        self.tempo_ultima_rep = time.time()
        self.tempo_inicio_serie = None
        self.tempos_repeticoes = []
        self.ultimo_timestamp_rep = None


class CronometroIsometrico:
    """Cronômetro para exercícios isométricos baseados em tempo (ex: Prancha).

    Acumula o tempo total (em segundos) usando time.time(), avançando apenas
    quando recebe postura_correta=True.
    """
    def __init__(self):
        self.tempo_acumulado = 0.0
        self.ultimo_tempo = None
        self.tempo_ultima_atividade = time.time()
        self.tempo_ultima_rep = self.tempo_ultima_atividade
        self.limpar()

    def acumular(self, postura_correta=True):
        agora = time.time()
        if self.ultimo_tempo is not None:
            delta = agora - self.ultimo_tempo
            if postura_correta and 0 < delta < 1.0:
                self.tempo_acumulado += delta
                self.tempo_ultima_atividade = agora
                self.tempo_ultima_rep = agora
        self.ultimo_tempo = agora
        return self.tempo_acumulado

    def atualizar(self, postura_correta=True):
        return self.acumular(postura_correta)

    @property
    def segundos(self):
        return int(self.tempo_acumulado)

    def limpar(self):
        self.tempo_acumulado = 0.0
        self.ultimo_tempo = None
        self.tempo_ultima_atividade = time.time()
        self.tempo_ultima_rep = self.tempo_ultima_atividade