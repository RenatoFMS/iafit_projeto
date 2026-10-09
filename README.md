 IAFit - Motor de Visão Computacional 🏋️‍♂️👁️

O **IAFit** é o motor de inteligência artificial e visão computacional desenvolvido como parte do Trabalho de Conclusão de Curso (TCC) em Desenvolvimento de Sistemas. O objetivo do sistema é monitorizar, analisar e corrigir a execução de exercícios físicos em tempo real utilizando apenas a câmara web do utilizador, enviando os dados processados para um painel gamificado.

## ✨ Funcionalidades Principais

* **Rastreamento Biomecânico em Tempo Real:** Mapeamento de pontos articulares do corpo humano com alta precisão e baixa latência.
* **Módulo Matemático Independente:** Cálculo vetorial de ângulos para determinar as fases concêntricas e excêntricas de cada movimento.
* **Feedback de Postura e Assimetria:** Deteção de desvios no eixo corporal (ex: descida excessiva do quadril na flexão ou assimetria nos braços).
* **Arquitetura "Vertical Slice":** Sincronização automática e em tempo real dos treinos concluídos com a base de dados na nuvem.

## 🏋️ Exercícios Suportados (MVP)

O motor suporta atualmente 5 exercícios fundamentais (compostos e isolados):
1. **Rosca Bíceps** (Avaliação do ângulo do cotovelo e ombro)
2. **Agachamento** (Avaliação do ângulo do joelho e quadril)
3. **Flexão de Braços** (Avaliação de braços e alinhamento do tronco/quadril)
4. **Desenvolvimento de Ombros** (Avaliação de extensão vertical)
5. **Abdominal** (Avaliação da contração do tronco com limites de 150º a 70º)

## 🛠️ Tecnologias e Ferramentas

O sistema foi construído com uma arquitetura moderna e escalável:

* **Linguagem Core:** Python 3
* **Visão Computacional e IA:** OpenCV, Google MediaPipe, Ultralytics YOLOv8
* **Backend e Persistência:** Google Firebase (Firestore) via `firebase-admin`
* **Engenharia Assistida por IA:** O desenvolvimento da arquitetura, otimização de algoritmos matemáticos e refatoração do código foram acelerados com práticas avançadas de *Pair Programming* utilizando LLMs através da extensão **Antigravity** no VS Code.

## ☁️ Persistência de Dados (Google Firebase)

O motor de Visão Computacional está totalmente integrado com o **Firebase Firestore**. 
A arquitetura funciona através de um "Corte Vertical" (*Vertical Slice*): ao finalizar a execução de um exercício (trocando de movimento no teclado numérico ou fechando a aplicação com a tecla 'Q'), o sistema recolhe os dados locais e envia as repetições válidas e erros de postura automaticamente para a base de dados na nuvem, alimentando o Front-end (React) em tempo real.

**⚠️ Configuração Local (Segurança):**
Para que a comunicação funcione na sua máquina local, é obrigatório colocar o ficheiro de credenciais `firebase_key.json` na raiz do projeto. Por motivos de segurança cibernética e boas práticas, este ficheiro está blindado pelo `.gitignore` e nunca é versionado no repositório público.

## 🚀 Como Rodar o Projeto Localmente

1. Clone o repositório:
   ```bash
   git clone https://github.com/RenatoFMS/iafit_projeto.git
   ```
2. Entre na pasta do projeto e ative o seu ambiente virtual (venv):
   ```bash
   cd iafit_projeto
   source venv/bin/activate  # No Linux (Ubuntu)
   ```
3. Instale as dependências rigorosas (garantindo compatibilidade do Protobuf):
   ```bash
   pip install -r requirements.txt
   ```
4. Certifique-se de que o ficheiro `firebase_key.json` está na raiz do projeto.
5. Inicie o scanner da câmara:
   ```bash
   python main.py
   ```
*(Utilize as teclas de 1 a 5 para alternar os exercícios e 'Q' para guardar e sair).*
