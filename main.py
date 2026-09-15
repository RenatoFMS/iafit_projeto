import cv2
from ultralytics import YOLO
from core.config_exercicios import EXERCICIOS
from core.motor_ia import processar_exercicio
from core.math_utils import FiltroSuavizacao

# ==========================================
FONTE_DE_VIDEO = "teste_agachamento.mp4" 
# ==========================================

print("Carregando motor IA IAFit...")
modelo = YOLO('yolov8n-pose.pt')
camera = cv2.VideoCapture(FONTE_DE_VIDEO)
id_atual = "1" 

filtros_memoria = {
    'amplitude': {'esq': FiltroSuavizacao(5), 'dir': FiltroSuavizacao(5)},
    'postura': {'esq': FiltroSuavizacao(5), 'dir': FiltroSuavizacao(5)}
}

def resetar_filtros():
    for cat in filtros_memoria.values():
        for filtro in cat.values():
            filtro.limpar()

print("\n====== MENU IAFIT ======")
for chave, dados in EXERCICIOS.items():
    print(f"[ {chave} ] - {dados['nome']}")
print("========================")

nome_janela = "IAFit - Scanner Profissional"
cv2.namedWindow(nome_janela)

while True:
    sucesso, frame = camera.read()
    
    if not sucesso: 
        if isinstance(FONTE_DE_VIDEO, str) and not FONTE_DE_VIDEO.startswith("http"):
            camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        else:
            break

    # --- NOVO: REDIMENSIONAMENTO INTELIGENTE ---
    # Limita o tamanho máximo do vídeo para caber confortavelmente em monitores comuns
    altura_orig, largura_orig = frame.shape[:2]
    escala = min(900 / largura_orig, 700 / altura_orig)
    
    if escala < 1:
        frame = cv2.resize(frame, (int(largura_orig * escala), int(altura_orig * escala)))

    # Pega as novas dimensões do vídeo para desenhar a interface gráfica corretamente
    altura_atual, largura_atual = frame.shape[:2]
    # -------------------------------------------

    resultados = modelo(frame, verbose=False)
    config_atual = EXERCICIOS.get(id_atual)
    
    if not config_atual:
        id_atual = "1"
        config_atual = EXERCICIOS["1"]
        
    nome_exercicio = config_atual["nome"]
    
    for r in resultados:
        if r.keypoints is not None and len(r.keypoints.data) > 0:
            pontos_completos = r.keypoints.data[0].cpu().numpy()
            resultados_ativos = processar_exercicio(pontos_completos, config_atual, filtros_memoria)
            
            if len(resultados_ativos) == 0:
                cv2.putText(frame, "Ajuste sua posicao (corpo nao encontrado)", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
                feedback_final = ""
                cor_final = (255, 255, 255)
                
                for res in resultados_ativos:
                    px, py = int(res["ponto_texto"][0]), int(res["ponto_texto"][1])
                    cor = res["cor"]
                    cv2.putText(frame, f"{res['porc']}%", (px + 20, py), cv2.FONT_HERSHEY_DUPLEX, 1.2, cor, 2)
                    
                    # 1. Desenha a Perna (Azul/Verde)
                    pt1 = (int(res["coords"][0][0]), int(res["coords"][0][1]))
                    pt2 = (int(res["coords"][1][0]), int(res["coords"][1][1]))
                    pt3 = (int(res["coords"][2][0]), int(res["coords"][2][1]))
                    cv2.line(frame, pt1, pt2, cor, 3)
                    cv2.line(frame, pt2, pt3, cor, 3)
                    cv2.circle(frame, pt1, 6, (0, 0, 255), -1)
                    cv2.circle(frame, pt2, 6, (0, 0, 255), -1)
                    cv2.circle(frame, pt3, 6, (0, 0, 255), -1)
                    
                    # 2. Desenha o Tronco (Amarelo)
                    if res.get("coords_postura"):
                        cp1 = (int(res["coords_postura"][0][0]), int(res["coords_postura"][0][1]))
                        cp2 = (int(res["coords_postura"][1][0]), int(res["coords_postura"][1][1]))
                        cv2.line(frame, cp1, cp2, (0, 255, 255), 3) 
                        cv2.circle(frame, cp1, 6, (0, 0, 255), -1)
                        
                    # 3. Desenha os Braços/Cotovelos (Roxo/Magenta)
                    if res.get("coords_bracos"):
                        bp1 = (int(res["coords_bracos"][0][0]), int(res["coords_bracos"][0][1]))
                        bp2 = (int(res["coords_bracos"][1][0]), int(res["coords_bracos"][1][1]))
                        bp3 = (int(res["coords_bracos"][2][0]), int(res["coords_bracos"][2][1]))
                        cv2.line(frame, bp1, bp2, (255, 0, 255), 3)
                        cv2.line(frame, bp2, bp3, (255, 0, 255), 3)
                        cv2.circle(frame, bp2, 6, (0, 0, 255), -1)
                    
                    feedback_final = res["feedback"]
                    cor_final = res["cor"]
                
                cv2.putText(frame, feedback_final, (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_final, 2, cv2.LINE_AA)

    # --- NOVO: INTERFACE RESPONSIVA ---
    # A barra preta agora vai da coordenada 0 até a 'largura_atual' da janela
    cv2.rectangle(frame, (0, 0), (largura_atual, 45), (0, 0, 0), -1)
    cv2.putText(frame, f"Modo Atual: {nome_exercicio}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # O botão de SAIR usa a largura total para ficar ancorado sempre no canto direito
    cv2.rectangle(frame, (largura_atual - 140, 10), (largura_atual - 20, 35), (0, 0, 255), -1)
    cv2.putText(frame, "SAIR [Q]", (largura_atual - 125, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    # -----------------------------------

    cv2.imshow(nome_janela, frame)
    
    if cv2.getWindowProperty(nome_janela, cv2.WND_PROP_VISIBLE) < 1: break
    tecla = cv2.waitKey(1) & 0xFF
    letra_pressionada = chr(tecla)
    
    if tecla == ord('q') or tecla == ord('Q'): break
    elif letra_pressionada in EXERCICIOS and letra_pressionada != id_atual:
        id_atual = letra_pressionada
        resetar_filtros()

camera.release()
cv2.destroyAllWindows()