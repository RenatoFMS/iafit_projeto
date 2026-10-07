import math
import mediapipe as mp
from core.math_utils import calcular_angulo, calcular_porcentagem

mp_pose = mp.solutions.pose

# Índices COCO (YOLOv8-pose) dos braços, usados no filtro de assimetria
BRACO_ESQ = (5, 7, 9)   # Ombro, Cotovelo, Pulso esquerdos
BRACO_DIR = (6, 8, 10)  # Ombro, Cotovelo, Pulso direitos
LIMITE_ASSIMETRIA = 15  # graus

def calcular_assimetria(keypoints_data):
    """Extrai os dois braços em simultâneo e compara os ângulos do cotovelo.
    Retorna (angulo_esq, angulo_dir, alerta_assimetria)."""
    indices = BRACO_ESQ + BRACO_DIR
    if any(keypoints_data[i][2] < 0.5 for i in indices):
        return None, None, False  # Braço fora de enquadramento: sem alerta

    pts_esq = [keypoints_data[i][:2] for i in BRACO_ESQ]
    pts_dir = [keypoints_data[i][:2] for i in BRACO_DIR]
    angulo_esq = calcular_angulo(*pts_esq)
    angulo_dir = calcular_angulo(*pts_dir)
    alerta = abs(angulo_esq - angulo_dir) > LIMITE_ASSIMETRIA
    return angulo_esq, angulo_dir, alerta

def processar_exercicio(keypoints_data, config_exercicio, filtros):
    resultados = []
    melhor_lado = None
    maior_confianca = 0
    
    # 1. Escolhe o lado mais visível da câmera
    for lado, indices in config_exercicio["lados"].items():
        confianca_total = sum([keypoints_data[i][2] for i in indices])
        if confianca_total > maior_confianca:
            maior_confianca = confianca_total
            melhor_lado = lado
            
    if not melhor_lado: return []
        
    # 2. Avalia a Perna (Amplitude)
    p1_idx, p2_idx, p3_idx = config_exercicio["lados"][melhor_lado]
    if keypoints_data[p1_idx][2] < 0.5 or keypoints_data[p2_idx][2] < 0.5 or keypoints_data[p3_idx][2] < 0.5:
        return []

    p1, p2, p3 = keypoints_data[p1_idx][:2], keypoints_data[p2_idx][:2], keypoints_data[p3_idx][:2]
    angulo_bruto = calcular_angulo(p1, p2, p3)
    angulo_suave = filtros['amplitude'][melhor_lado].atualizar(angulo_bruto)
    porc = calcular_porcentagem(angulo_suave, config_exercicio["inicio"], config_exercicio["fim"])
    
    cor = (255, 0, 0)
    feedback = "Em movimento..."
    postura_segura = True
    coords_postura = None
    coords_bracos = None
    
    # 3. Análise de Segurança da Lombar (Referência Vertical)
    if config_exercicio.get("postura"):
        s1_idx, s2_idx = config_exercicio["postura"][melhor_lado][:2]
        if keypoints_data[s1_idx][2] > 0.5 and keypoints_data[s2_idx][2] > 0.5:
            sp1 = keypoints_data[s1_idx][:2] # Ombro
            sp2 = keypoints_data[s2_idx][:2] # Quadril
            coords_postura = (sp1, sp2) 
            
            # Cria a linha de gravidade imaginária puxando 50 pixels para cima do quadril
            if config_exercicio.get("postura_vertical"):
                sp3 = (sp2[0], sp2[1] - 50)
            else:
                s3_idx = config_exercicio["postura"][melhor_lado][2]
                sp3 = keypoints_data[s3_idx][:2]
                
            angulo_seg = calcular_angulo(sp1, sp2, sp3)
            angulo_seg_suave = filtros['postura'][melhor_lado].atualizar(angulo_seg)
            
            limite = config_exercicio["limite_postura"]
            if config_exercicio["regra_postura"] == "<" and angulo_seg_suave < limite: postura_segura = False
            elif config_exercicio["regra_postura"] == ">" and angulo_seg_suave > limite: postura_segura = False

    # 4. Mapeamento Extra (Braços/Cotovelos)
    if config_exercicio.get("bracos"):
        b1_idx, b2_idx, b3_idx = config_exercicio["bracos"][melhor_lado]
        if keypoints_data[b1_idx][2] > 0.5 and keypoints_data[b2_idx][2] > 0.5:
            bp1 = keypoints_data[b1_idx][:2]
            bp2 = keypoints_data[b2_idx][:2]
            # Tenta pegar o pulso, se não enxergar, usa o cotovelo de novo para não quebrar a linha
            bp3 = keypoints_data[b3_idx][:2] if keypoints_data[b3_idx][2] > 0.5 else bp2 
            coords_bracos = (bp1, bp2, bp3)

    # 5. Filtro de Assimetria (ambos os braços em simultâneo)
    angulo_esq, angulo_dir, alerta_assimetria = calcular_assimetria(keypoints_data)

    # 6. Definição do Alerta
    if not postura_segura:
        feedback = config_exercicio["msg_erro"]
        cor = (0, 0, 255) # Vermelho
    else:
        if porc == 100:
            feedback = config_exercicio["msg_fim"]
            cor = (0, 255, 0) # Verde
        elif porc == 0:
            feedback = config_exercicio["msg_inicio"]
            cor = (0, 255, 255) # Amarelo
        
    resultados.append({
        "lado": melhor_lado, "porc": porc, "feedback": feedback, "cor": cor,
        "coords": (p1, p2, p3), "coords_postura": coords_postura, "coords_bracos": coords_bracos, "ponto_texto": p2,
        "alerta_assimetria": alerta_assimetria, "angulo_braco_esq": angulo_esq, "angulo_braco_dir": angulo_dir
    })
        
    return resultados

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