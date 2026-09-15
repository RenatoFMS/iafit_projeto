# 🏋️‍♂️ IAFit - Scanner Biomecânico Profissional

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLOv8-00FFFF?style=for-the-badge&logo=YOLO&logoColor=black)

O **IAFit** é um sistema de visão computacional desenvolvido como Trabalho de Conclusão de Curso (TCC) no curso técnico de Desenvolvimento de Sistemas na ETEC Zona Leste. 

O projeto atua como um "Personal Trainer" digital. Utilizando o modelo de Inteligência Artificial **YOLOv8-pose**, o sistema mapeia as articulações do corpo em tempo real para calcular a amplitude dos movimentos, contar repetições e, principalmente, **prevenir lesões através da análise de segurança da postura**.

## ✨ Principais Funcionalidades

*   **Análise de 5 Exercícios Base:** Suporte nativo para Rosca Bíceps, Agachamento, Flexão de Braço, Desenvolvimento de Ombro e Abdominal Supra.
*   **Segurança Biomecânica Ativa:** O motor inteligente calcula a "Linha de Prumo" da gravidade. Se o usuário curvar o tronco de forma perigosa (ex: durante o agachamento), o sistema bloqueia a contagem e emite um alerta visual na tela.
*   **Filtro de Suavização (Média Móvel):** Algoritmo matemático implementado para estabilizar tremores de câmeras comuns, garantindo uma precisão contínua da porcentagem de movimento.
*   **Múltiplas Fontes de Vídeo:** O sistema é flexível e pode ser alimentado via Webcam do computador, arquivos de vídeo gravados (`.mp4`) ou transmissão ao vivo pelo celular (Câmera IP).
*   **Arquitetura Data-Driven:** Adicionar novos exercícios não requer alteração na lógica da IA, apenas a inserção das coordenadas no banco de configurações.

## 🛠️ Tecnologias Utilizadas

*   **Linguagem:** Python 3
*   **Visão Computacional:** OpenCV (`cv2`)
*   **Inteligência Artificial (Pose Estimation):** Ultralytics (YOLOv8)
*   **Matemática e Filtros:** NumPy & Collections

---

## 🚀 Como Instalar e Rodar o Projeto

Siga os passos abaixo para testar o IAFit na sua máquina.

### 1. Clone o repositório
Abra o seu terminal e rode o comando:
```bash
git clone [https://github.com/RenatoFMS/iafit_projeto.git](https://github.com/RenatoFMS/iafit_projeto.git)
cd iafit_projeto
```

### 2. Crie um Ambiente Virtual (Recomendado)
Para evitar conflitos com outras bibliotecas do seu computador, crie e ative um `venv`:
```bash
# No Linux/macOS
python3 -m venv venv
source venv/bin/activate

# No Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instale as Dependências
Instale o OpenCV, Ultralytics e NumPy de uma só vez usando o arquivo de requisitos:
```bash
pip install -r requirements.txt
```

### 4. Execute a Aplicação
Com tudo instalado, basta iniciar o arquivo principal:
```bash
python main.py
```
*(Nota: Na primeira execução, o sistema fará o download automático do modelo `yolov8n-pose.pt`, o que leva apenas alguns segundos).*

---

## 🎮 Como Usar

Ao iniciar a aplicação, a janela de vídeo será aberta. 

**Controles do Teclado:**
*   Aperte a tecla correspondente ao exercício desejado a qualquer momento:
    *   `1` - Rosca Bíceps
    *   `2` - Agachamento (Ativa análise de postura do tronco)
    *   `3` - Flexão de Braço
    *   `4` - Desenvolvimento Ombro
    *   `5` - Abdominal Supra
*   `Q` - Encerra a aplicação.

**Trocando a Fonte de Vídeo:**
Para testar vídeos diferentes, abra o arquivo `main.py` em um editor de texto e altere a variável `FONTE_DE_VIDEO` (linha 14):
```python
# Para Webcam:
FONTE_DE_VIDEO = 0 

# Para um vídeo salvo na pasta:
FONTE_DE_VIDEO = "teste_agachamento.mp4" 

```

## 👨‍💻 Autor

Desenvolvido por **Renato Felipe Martins Silva**.
