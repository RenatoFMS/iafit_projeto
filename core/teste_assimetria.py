import cv2
import mediapipe as mp
import numpy as np

# 1. Inicialização do Motor MediaPipe
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def calcular_angulo(a, b, c):
    """Calcula o ângulo exato entre três pontos articulares."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radianos = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angulo = np.abs(radianos * 180.0 / np.pi)
    if angulo > 180.0:
        angulo = 360 - angulo
    return int(angulo) # Retorna número inteiro para facilitar a leitura 

# 2. Configuração da Captura de Vídeo (Webcam 0)
cap = cv2.VideoCapture('teste_agachamento.mp4')

# Iniciar instância do MediaPipe com margens de confiança rigorosas
with mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7) as pose:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # FORÇAR RESOLUÇÃO PADRÃO DE WEBCAM PARA TERMOS ESPAÇO
        frame = cv2.resize(frame, (640, 480))
        
        # Otimização: Converter frame para RGB...
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
        # Otimização: Converter frame para RGB para o MediaPipe processar mais rápido
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        
        # Reverter para BGR para o OpenCV conseguir desenhar na imagem
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        try:
            landmarks = results.pose_landmarks.landmark
            
            # 3. Extração Simultânea de Coordenadas
            # Braço Esquerdo
            ombro_esq = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            cotovelo_esq = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            pulso_esq = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            
            # Braço Direito
            ombro_dir = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
            cotovelo_dir = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
            pulso_dir = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
            
            # 4. Cálculo Angular Refatorado
            angulo_esq = calcular_angulo(ombro_esq, cotovelo_esq, pulso_esq)
            angulo_dir = calcular_angulo(ombro_dir, cotovelo_dir, pulso_dir)
            
            # 5. Lógica do Filtro de Assimetria
            diferenca = abs(angulo_esq - angulo_dir)
            alerta_assimetria = diferenca > 15

            # 6. Renderização de Interface (HUD) Normalizada
            cor_status = (0, 0, 255) if alerta_assimetria else (0, 255, 0) 
            
            escala = 0.6 
            espessura = 2
            
            cv2.putText(image, f'Esq: {angulo_esq}', (15, 30), cv2.FONT_HERSHEY_SIMPLEX, escala, (255, 255, 255), espessura)
            cv2.putText(image, f'Dir: {angulo_dir}', (15, 60), cv2.FONT_HERSHEY_SIMPLEX, escala, (255, 255, 255), espessura)
            cv2.putText(image, f'Dif: {diferenca}', (15, 90), cv2.FONT_HERSHEY_SIMPLEX, escala, cor_status, espessura)
            
            if alerta_assimetria:
                cv2.putText(image, 'ALERTA: ASSIMETRIA', (15, 130), cv2.FONT_HERSHEY_SIMPLEX, escala + 0.1, (0, 0, 255), espessura + 1)

        except Exception as e:
            pass # Ignora erros quando a pessoa sai do enquadramento do vídeo

        # Desenhar o esqueleto do MediaPipe por cima do corpo
        if results.pose_landmarks:
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        cv2.imshow('IAFit - Filtro de Assimetria (V2)', image)

        # Tecla de segurança para encerrar o programa (Pressione 'q')
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()