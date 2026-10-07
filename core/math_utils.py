import math
from collections import deque
import numpy as np

def calcular_angulo(a, b, c):
    """Calcula o ângulo exato entre três pontos articulares."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radianos = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angulo = np.abs(radianos * 180.0 / np.pi)
    if angulo > 180.0:
        angulo = 360.0 - angulo
    return float(angulo)


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