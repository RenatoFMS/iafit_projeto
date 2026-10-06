import math
import numpy as np

# Supondo que já tem a função que calcula o ângulo entre 3 pontos (A, B, C)
def calcular_angulo(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radianos = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angulo = np.abs(radianos * 180.0 / np.pi)
    if angulo > 180.0:
        angulo = 360 - angulo
    return angulo

# Dentro do seu loop principal de processamento do MediaPipe:
def processar_desenvolvimento_ombro(landmarks):
    # 1. Obter coordenadas do braço ESQUERDO (Ombro, Cotovelo, Pulso)
    ombro_esq = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
    cotovelo_esq = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
    pulso_esq = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
    
    # 2. Obter coordenadas do braço DIREITO (Ombro, Cotovelo, Pulso)
    ombro_dir = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
    cotovelo_dir = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
    pulso_dir = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
    
    # 3. Calcular os ângulos simultaneamente
    angulo_esq = calcular_angulo(ombro_esq, cotovelo_esq, pulso_esq)
    angulo_dir = calcular_angulo(ombro_dir, cotovelo_dir, pulso_dir)
    
    # 4. Filtro de Assimetria (Diferença > 15 graus)
    diferenca = abs(angulo_esq - angulo_dir)
    alerta_assimetria = True if diferenca > 15 else False
    
    return {
        "angulo_esquerdo": angulo_esq,
        "angulo_direito": angulo_dir,
        "diferenca_graus": diferenca,
        "alerta_assimetria": alerta_assimetria
    }