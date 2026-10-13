import time
import cv2
import mediapipe as mp
from core.config_exercicios import EXERCICIOS
from core.motor_ia import processar_exercicio, resetar_cooldown_voz
from core.analise_biomecanica import (
    landmarks_mediapipe_para_keypoints,
    criar_detector_pose,
    calcular_calorias,
)
from core.math_utils import FiltroSuavizacao, ContadorRepeticoes, CronometroIsometrico
from core.firebase_client import salvar_treino
from core.voz_client import falar

# ==========================================
FONTE_DE_VIDEO = "teste_agachamento.mp4"  # Pode ser '0' para webcam, ou caminho de vídeo
# ==========================================

print("Carregando motor IA IAFit (MediaPipe Pose otimizado)...")
pose = criar_detector_pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.7
)
camera = cv2.VideoCapture(FONTE_DE_VIDEO)
id_atual = "1" 

filtros_memoria = {
    'amplitude': {'esq': FiltroSuavizacao(5), 'dir': FiltroSuavizacao(5)},
    'postura': {'esq': FiltroSuavizacao(5), 'dir': FiltroSuavizacao(5)},
    'repeticoes': {'total': ContadorRepeticoes()},
    'isometrico': {'total': CronometroIsometrico()}
}

def resetar_filtros():
    for cat in filtros_memoria.values():
        for filtro in cat.values():
            filtro.limpar()
    resetar_cooldown_voz()

def guardar_treino_atual():
    """Envia o exercício atual e as suas repetições ou tempo para a nuvem."""
    config = EXERCICIOS.get(id_atual, {})
    nome_ex = config.get("nome", "Exercício")
    met_ex = config.get("met", 3.0)
    if id_atual == "8":
        segundos = filtros_memoria['isometrico']['total'].segundos
        if segundos > 0:
            calorias = calcular_calorias(segundos, met_ex)
            print(f"Série concluída: {segundos}s | Gasto estimado: {calorias:.1f} kcal")
            salvar_treino(nome_ex, segundos, calorias=calorias)
    else:
        contador = filtros_memoria['repeticoes']['total']
        reps = contador.reps
        if reps > 0:
            agora = time.time()
            tempo_inicio = contador.tempo_inicio_serie if contador.tempo_inicio_serie is not None else contador.tempo_ultima_rep
            tempo_serie = max(0.0, agora - tempo_inicio)
            calorias = calcular_calorias(tempo_serie, met_ex)
            print(f"Série concluída: {reps} reps | Gasto estimado: {calorias:.1f} kcal")
            salvar_treino(nome_ex, reps, calorias=calorias)

print("\n====== MENU IAFIT ======")
for chave, dados in EXERCICIOS.items():
    print(f"[ {chave} ] - {dados['nome']}")
print("========================")

nome_janela = "IAFit - Scanner Profissional"
cv2.namedWindow(nome_janela)

while camera.isOpened():
    sucesso, frame = camera.read()
    
    if not sucesso: 
        if isinstance(FONTE_DE_VIDEO, str) and not FONTE_DE_VIDEO.startswith("http"):
            camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        else:
            break

    # Verificação de encerramento automático da série por inatividade (Timeout > 6.0s)
    if id_atual == "8":
        cronometro = filtros_memoria['isometrico']['total']
        if cronometro.segundos > 0 and (time.time() - cronometro.tempo_ultima_atividade) > 6.0:
            segundos_feitos = cronometro.segundos
            tempo_serie = segundos_feitos
            met_ex = EXERCICIOS[id_atual].get("met", 3.5)
            calorias = calcular_calorias(tempo_serie, met_ex)
            cronometro.limpar()
            falar("Série concluída")
            print(f"Série concluída: {segundos_feitos}s | Gasto estimado: {calorias:.1f} kcal")
            salvar_treino(EXERCICIOS[id_atual]["nome"], segundos_feitos, calorias=calorias)
    else:
        contador = filtros_memoria['repeticoes']['total']
        if contador.reps > 0 and (time.time() - contador.tempo_ultima_rep) > 6.0:
            reps_feitas = contador.reps
            agora = time.time()
            tempo_inicio = contador.tempo_inicio_serie if contador.tempo_inicio_serie is not None else contador.tempo_ultima_rep
            tempo_serie = max(0.0, agora - tempo_inicio)
            met_ex = EXERCICIOS[id_atual].get("met", 3.0)
            calorias = calcular_calorias(tempo_serie, met_ex)
            contador.reps = 0
            contador.tempo_ultima_rep = agora
            contador.tempo_inicio_serie = None
            falar("Série concluída")
            print(f"Série concluída: {reps_feitas} reps | Gasto estimado: {calorias:.1f} kcal")
            salvar_treino(EXERCICIOS[id_atual]["nome"], reps_feitas, calorias=calorias)


    # --- NOVO: REDIMENSIONAMENTO INTELIGENTE ---
    # Limita o tamanho máximo do vídeo para caber confortavelmente em monitores comuns
    altura_orig, largura_orig = frame.shape[:2]
    escala = min(900 / largura_orig, 700 / altura_orig)
    
    if escala < 1:
        frame = cv2.resize(frame, (int(largura_orig * escala), int(altura_orig * escala)))

    # Pega as novas dimensões do vídeo para desenhar a interface gráfica corretamente
    altura_atual, largura_atual = frame.shape[:2]
    # -------------------------------------------

    # Otimização MediaPipe: conversão BGR -> RGB com writeable=False para poupar memória RAM
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    results = pose.process(image)

    # Reverte para BGR para renderização de interface gráfica e OpenCV
    image.flags.writeable = True
    frame = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    config_atual = EXERCICIOS.get(id_atual)
    
    if not config_atual:
        id_atual = "1"
        config_atual = EXERCICIOS["1"]
        
    nome_exercicio = config_atual["nome"]
    
    if results.pose_landmarks:
        pontos_completos = landmarks_mediapipe_para_keypoints(
            results.pose_landmarks.landmark, largura=largura_atual, altura=altura_atual
        )
        resultados_ativos = processar_exercicio(pontos_completos, config_atual, filtros_memoria)
        
        if len(resultados_ativos) == 0:
            cv2.putText(frame, "Ajuste sua posicao (corpo nao encontrado)", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        else:
            feedback_final = ""
            cor_final = (255, 255, 255)
            alerta_assimetria = False
            reps_final, fase_final = 0, "base"
            
            for res in resultados_ativos:
                px, py = int(res["ponto_texto"][0]), int(res["ponto_texto"][1])
                cor = res["cor"]
                cv2.putText(frame, f"{res['porc']}%", (px + 20, py), cv2.FONT_HERSHEY_DUPLEX, 1.2, cor, 2)
                
                # 1. Desenha a Perna/Movimento Principal (Azul/Verde)
                pt1 = (int(res["coords"][0][0]), int(res["coords"][0][1]))
                pt2 = (int(res["coords"][1][0]), int(res["coords"][1][1]))
                pt3 = (int(res["coords"][2][0]), int(res["coords"][2][1]))
                cv2.line(frame, pt1, pt2, cor, 3)
                cv2.line(frame, pt2, pt3, cor, 3)
                cv2.circle(frame, pt1, 6, (0, 0, 255), -1)
                cv2.circle(frame, pt2, 6, (0, 0, 255), -1)
                cv2.circle(frame, pt3, 6, (0, 0, 255), -1)
                
                # 2. Desenha o Tronco/Postura (Amarelo)
                if res.get("coords_postura"):
                    cp1 = (int(res["coords_postura"][0][0]), int(res["coords_postura"][0][1]))
                    cp2 = (int(res["coords_postura"][1][0]), int(res["coords_postura"][1][1]))
                    cv2.line(frame, cp1, cp2, (0, 255, 255), 3) 
                    cv2.circle(frame, cp1, 6, (0, 255, 255), -1)
                    
                # 3. Desenha os Braços/Cotovelos (Roxo/Magenta)
                if res.get("coords_bracos"):
                    bp1 = (int(res["coords_bracos"][0][0]), int(res["coords_bracos"][0][1]))
                    bp2 = (int(res["coords_bracos"][1][0]), int(res["coords_bracos"][1][1]))
                    bp3 = (int(res["coords_bracos"][2][0]), int(res["coords_bracos"][2][1]))
                    cv2.line(frame, bp1, bp2, (255, 0, 255), 3)
                    cv2.line(frame, bp2, bp3, (255, 0, 255), 3)
                    cv2.circle(frame, bp2, 6, (255, 0, 255), -1)
                
                feedback_final = res["feedback"]
                cor_final = res["cor"]
                alerta_assimetria = alerta_assimetria or res.get("alerta_assimetria", False)
                reps_final, fase_final = res.get("reps", 0), res.get("fase", "base")
            
            if id_atual == "8":
                segundos_atuais = filtros_memoria['isometrico']['total'].segundos
                cv2.putText(frame, f"Tempo: {segundos_atuais}s  |  Fase: {fase_final}", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            else:
                cv2.putText(frame, f"Reps: {reps_final}  |  Fase: {fase_final}", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, feedback_final, (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_final, 2, cv2.LINE_AA)
            
            # Alerta de assimetria entre os braços (vermelho, dimensionado para caber no frame)
            if alerta_assimetria:
                texto_alerta = "ALERTA: ASSIMETRIA"
                escala_alerta, espessura_alerta = 0.8, 2
                (larg_txt, alt_txt), _ = cv2.getTextSize(texto_alerta, cv2.FONT_HERSHEY_DUPLEX, escala_alerta, espessura_alerta)
                ax = max(10, min(30, largura_atual - larg_txt - 10))
                ay = 135
                cv2.putText(frame, texto_alerta, (ax, ay), cv2.FONT_HERSHEY_DUPLEX, escala_alerta, (0, 0, 255), espessura_alerta, cv2.LINE_AA)
    else:
        cv2.putText(frame, "Ajuste sua posicao (corpo nao encontrado)", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    # --- NOVO: INTERFACE RESPONSIVA ---
    # A barra preta agora vai da coordenada 0 até a 'largura_atual' da janela
    cv2.rectangle(frame, (0, 0), (largura_atual, 45), (0, 0, 0), -1)
    cv2.putText(frame, f"Modo Atual: {nome_exercicio}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # O botão de SAIR usa a largura total para ficar ancorado sempre no canto direito
    cv2.rectangle(frame, (largura_atual - 140, 10), (largura_atual - 20, 35), (0, 0, 255), -1)
    cv2.putText(frame, "SAIR [Q]", (largura_atual - 125, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Menu de atalhos no rodapé: pressione o número para trocar de exercício
    cv2.rectangle(frame, (0, altura_atual - 30), (largura_atual, altura_atual), (0, 0, 0), -1)
    texto_menu = "  ".join(f"[{k}]{d['nome'].split()[0]}" for k, d in EXERCICIOS.items())
    cv2.putText(frame, f"Teclas: {texto_menu}", (10, altura_atual - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    # -----------------------------------

    cv2.imshow(nome_janela, frame)
    
    if cv2.getWindowProperty(nome_janela, cv2.WND_PROP_VISIBLE) < 1:
        guardar_treino_atual()
        break
    tecla = cv2.waitKey(1) & 0xFF
    letra_pressionada = chr(tecla)
    
    if tecla == ord('q') or tecla == ord('Q'):
        guardar_treino_atual()
        break
    elif letra_pressionada in EXERCICIOS and letra_pressionada != id_atual:
        guardar_treino_atual()  # Antes de reiniciar a contagem
        id_atual = letra_pressionada
        resetar_filtros()

camera.release()
pose.close()
cv2.destroyAllWindows()