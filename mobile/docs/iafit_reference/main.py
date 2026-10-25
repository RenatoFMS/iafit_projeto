import cv2
import numpy as np
from ultralytics import YOLO
import time

model = YOLO("yolo11n-pose.pt")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

contador = 0
estado = None
exercicio = "squat"

descanso = False
tempo_inicio_descanso = 0
DURACAO_DESCANSO = 120

aviso_postura = ""


# =========================
# ANGULO
# =========================
def calcular_angulo(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    angulo = np.degrees(
        np.arctan2(c[1] - b[1], c[0] - b[0]) -
        np.arctan2(a[1] - b[1], a[0] - b[0])
    )

    angulo = abs(angulo)
    if angulo > 180:
        angulo = 360 - angulo

    return angulo


# =========================
# FEEDBACK
# =========================
def feedback_postura(exercicio, angulo):
    global aviso_postura

    if exercicio == "squat":
        if angulo < 70:
            aviso_postura = "DESCIDA MUITO PROFUNDA"
        elif angulo > 170:
            aviso_postura = "POSICAO INICIAL OK"
        else:
            aviso_postura = "FASE IDEAL"

    elif exercicio == "biceps":
        if angulo > 160:
            aviso_postura = "BRACO ESTENDIDO"
        elif angulo < 50:
            aviso_postura = "CONTRACAO MAXIMA"
        else:
            aviso_postura = "MOVIMENTO OK"

    elif exercicio == "shoulder":
        if angulo > 160:
            aviso_postura = "BRACO BAIXO"
        elif angulo < 80:
            aviso_postura = "BRACO ALTO"
        else:
            aviso_postura = "EXECUCAO OK"

    elif exercicio == "abdominal":
        if angulo > 160:
            aviso_postura = "CORPO ABERTO"
        elif angulo < 100:
            aviso_postura = "CONTRACAO ATIVA"
        else:
            aviso_postura = "FASE IDEAL"

    elif exercicio == "lateral":
        if angulo < 40:
            aviso_postura = "BRACO BAIXO"
        elif angulo > 90:
            aviso_postura = "ELEVACAO OK"
        else:
            aviso_postura = "MOVIMENTO BOM"


# =========================
# EXERCÍCIOS
# =========================

def squat(kps, contador, estado):
    quadril, joelho, tornozelo = kps[11], kps[13], kps[15]
    angulo = calcular_angulo(quadril, joelho, tornozelo)

    feedback_postura("squat", angulo)

    if angulo > 160:
        estado = "em_pe"
    if angulo < 90 and estado == "em_pe":
        estado = "baixo"
        contador += 1

    return contador, estado


def biceps(kps, contador, estado):
    ombro, cotovelo, punho = kps[5], kps[7], kps[9]
    angulo = calcular_angulo(ombro, cotovelo, punho)

    feedback_postura("biceps", angulo)

    if angulo > 160:
        estado = "aberto"
    if angulo < 50 and estado == "aberto":
        estado = "fechado"
        contador += 1

    return contador, estado


def shoulder(kps, contador, estado):
    quadril, ombro, cotovelo = kps[11], kps[5], kps[7]
    angulo = calcular_angulo(quadril, ombro, cotovelo)

    feedback_postura("shoulder", angulo)

    if angulo > 160:
        estado = "baixo"
    if angulo < 80 and estado == "baixo":
        estado = "alto"
        contador += 1

    return contador, estado


def abdominal(kps, contador, estado):
    ombro, quadril, joelho = kps[5], kps[11], kps[13]
    angulo = calcular_angulo(ombro, quadril, joelho)

    feedback_postura("abdominal", angulo)

    if angulo > 160:
        estado = "aberto"
    if angulo < 100 and estado == "aberto":
        estado = "fechado"
        contador += 1

    return contador, estado


def lateral(kps, contador, estado):
    ombro, cotovelo, punho = kps[5], kps[7], kps[9]
    angulo = calcular_angulo(ombro, cotovelo, punho)

    feedback_postura("lateral", angulo)

    if angulo < 40:
        estado = "baixo"
    if angulo > 90 and estado == "baixo":
        estado = "alto"
        contador += 1

    return contador, estado


# =========================
# ESQUELETO
# =========================
def desenhar_esqueleto(frame, kps):
    for p in kps:
        cv2.circle(frame, (int(p[0]), int(p[1])), 4, (0, 255, 255), -1)

    conexoes = [
        (5, 7), (7, 9),
        (6, 8), (8, 10),
        (11, 13), (13, 15),
        (12, 14), (14, 16),
        (5, 11), (6, 12)
    ]

    for a, b in conexoes:
        xa, ya = int(kps[a][0]), int(kps[a][1])
        xb, yb = int(kps[b][0]), int(kps[b][1])
        cv2.line(frame, (xa, ya), (xb, yb), (0, 255, 0), 2)


# =========================
# HUD
# =========================
def desenhar_hud(frame, exercicio, contador):
    h, w, _ = frame.shape

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (380, h), (20, 20, 20), -1)
    frame[:] = cv2.addWeighted(overlay, 0.75, frame, 0.25, 0)

    cv2.putText(frame, "AI FITNESS PRO",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 255, 255), 2)

    cv2.putText(frame, exercicio.upper(),
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9, (0, 255, 200), 2)

    cv2.rectangle(frame, (20, 120), (350, 240), (40, 40, 40), -1)
    cv2.putText(frame, "REPETICOES",
                (40, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (180, 180, 180), 1)

    cv2.putText(frame, str(contador),
                (40, 210),
                cv2.FONT_HERSHEY_SIMPLEX,
                2.2, (0, 255, 0), 3)

    max_rep = 20
    progresso = min(int((contador / max_rep) * 260), 260)

    cv2.rectangle(frame, (40, 260), (300, 285), (60, 60, 60), -1)
    cv2.rectangle(frame, (40, 260), (40 + progresso, 285), (0, 255, 120), -1)

    cv2.putText(frame, f"{contador}/{max_rep}",
                (40, 310),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (200, 200, 200), 1)

    cv2.rectangle(frame, (20, 340), (350, 410), (30, 30, 30), -1)
    cv2.putText(frame, "POSTURA",
                (40, 370),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (200, 200, 200), 1)

    cv2.putText(frame, aviso_postura,
                (40, 400),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 255, 255), 2)

    if descanso:
        tempo_restante = DURACAO_DESCANSO - int(time.time() - tempo_inicio_descanso)

        cv2.rectangle(frame, (20, 450), (350, 520), (0, 0, 0), -1)
        cv2.putText(frame, "DESCANSO",
                    (40, 480),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 0, 255), 2)

        cv2.putText(frame, f"{tempo_restante}s",
                    (40, 510),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2, (0, 0, 255), 3)

    cv2.putText(frame, "1-5 exercicios | Q sair",
                (20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (200, 200, 200), 1)


# =========================
# LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    if descanso:
        tempo_restante = DURACAO_DESCANSO - int(time.time() - tempo_inicio_descanso)
        if tempo_restante <= 0:
            descanso = False
            contador = 0
            estado = None

    results = model(frame, verbose=False)

    for r in results:
        if r.keypoints is not None:
            kps = r.keypoints.xy[0].cpu().numpy()

            desenhar_esqueleto(frame, kps)

            if not descanso:
                if exercicio == "squat":
                    contador, estado = squat(kps, contador, estado)
                elif exercicio == "biceps":
                    contador, estado = biceps(kps, contador, estado)
                elif exercicio == "shoulder":
                    contador, estado = shoulder(kps, contador, estado)
                elif exercicio == "abdominal":
                    contador, estado = abdominal(kps, contador, estado)
                elif exercicio == "lateral":
                    contador, estado = lateral(kps, contador, estado)

    if contador >= 20 and not descanso:
        descanso = True
        tempo_inicio_descanso = time.time()

    desenhar_hud(frame, exercicio, contador)

    cv2.imshow("AI FITNESS PRO", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        break
    elif key == ord('1'):
        exercicio = "squat"; contador = 0; estado = None
    elif key == ord('2'):
        exercicio = "biceps"; contador = 0; estado = None
    elif key == ord('3'):
        exercicio = "shoulder"; contador = 0; estado = None
    elif key == ord('4'):
        exercicio = "abdominal"; contador = 0; estado = None
    elif key == ord('5'):
        exercicio = "lateral"; contador = 0; estado = None


cap.release()
cv2.destroyAllWindows()