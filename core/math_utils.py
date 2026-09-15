import math
from collections import deque

def calcular_angulo(p1, p2, p3):
    """Calcula o ângulo trigonométrico formado por três pontos (x, y)."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    
    radianos = math.atan2(y3 - y2, x3 - x2) - math.atan2(y1 - y2, x1 - x2)
    angulo = abs(radianos * 180.0 / math.pi)
    
    if angulo > 180.0:
        angulo = 360.0 - angulo
        
    return angulo

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