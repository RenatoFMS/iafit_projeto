# 🏋️‍♂️ IAFit - Motor de Visão Computacional

O **IAFit - Motor de Visão Computacional** é o núcleo Back-end do Trabalho de Conclusão de Curso (TCC) focado no acompanhamento inteligente de treinos físicos. Utilizando o **Google MediaPipe Pose**, o motor realiza análise biomecânica tridimensional (3D) em tempo real através da webcam, efetuando contagem de repetições e tempo isométrico, deteção algorítmica de fadiga muscular, estimativa de gasto calórico, correção postural por voz natural, sincronização na nuvem via **Firebase Firestore** e validação contínua através de um sistema automatizado de **Quality Assurance (QA)**.

---

## ✨ Funcionalidades Principais

* 🎯 **Análise 3D de 30 Exercícios com MediaPipe Pose:** Mapeamento articular tridimensional (`x, y, z`) para exercícios compostos, isolados e isométricos, avaliando fases concêntricas, excêntricas, desvios posturais e assimetria bilateral.
* ⚡ **Deteção Algorítmica de Fadiga e Cálculo de Gasto Calórico:** Monitorização da cadência de execução para identificar perda de velocidade concêntrica (fadiga muscular) e estimativa precisa de gasto energético baseada no equivalente metabólico (MET) de cada exercício.
* 🛡️ **Fase de Calibração Inicial:** Máquina de estados que valida a presença e estabilidade das articulações-chave com alta confiança (`visibility > 0.7`) antes de iniciar a contagem, eliminando falsos positivos durante o posicionamento do utilizador.
* 🔊 **Feedback por Voz Natural (gTTS) em Tempo Real:** Orientação auditiva assíncrona com controlo de *cooldown* inteligente para corrigir erros biomecânicos e alertar sobre fadiga sem bloquear o processamento de vídeo.
* ☁️ **Integração na Nuvem (Firebase Firestore):** Sincronização automática dos dados da sessão (repetições válidas, tempo sob tensão, calorias, fadiga e histórico de erros) diretamente para o Firestore.
* 🧪 **Pipeline de Qualidade (QA) Automatizado com `yt-dlp`:** Ferramentas integradas para recolha automatizada de vídeos curtos de referência e execução de testes em lote sem necessidade de webcam.

---

## 🏗️ Arquitetura e Clean Code

O projeto foi desenhado em nível de produção seguindo rigorosamente os princípios de **Clean Code** e separação de responsabilidades:

* **Tipagem Estática (PEP 484):** Todas as assinaturas de funções, métodos e estruturas de dados possuem *Type Hints* explícitos (`typing`).
* **Documentação Padronizada:** Módulos, classes e funções documentados segundo o **Padrão Google de Docstrings** (`Args`, `Returns`).
* **Design Modular:**
  ```text
  iafit_projeto/
  ├── backend/                      # Motor Matemático e Biomecânico (Python)
  │   ├── core/
  │   │   ├── analise_biomecanica.py  # Geometria vetorial 3D, cálculo de ângulos, fadiga e calorias
  │   │   ├── config_exercicios.py    # Catálogo parametrizado dos 30 exercícios e valores MET
  │   │   ├── firebase_client.py      # Cliente de persistência na nuvem (Firebase Firestore)
  │   │   ├── math_utils.py           # Filtros de suavização temporal, contadores e cronómetros
  │   │   ├── motor_ia.py             # Máquina de estados, calibração e regras biomecânicas
  │   │   ├── ponte_flutter.py        # API HTTP local (POST /analisar_pose, /exercicio, /finalizar)
  │   │   └── voz_client.py           # Síntese e reprodução assíncrona de voz (gTTS / Pygame)
  │   ├── main.py                     # Ponto de entrada da API biomecânica (Edge Computing + Cloud)
  │   ├── baixar_videos.py            # Web scraper automatizado de vídeos curtos para QA (yt-dlp)
  │   ├── testador_lote.py            # Executor de testes biomecânicos em lote e gerador de relatórios
  │   └── requirements.txt            # Dependências do Back-end Python
  ├── mobile/                       # Aplicativo Front-end (Flutter + Google ML Kit Pose + SQLite)
  └── docs/                         # Documentação técnica, relatórios de QA e vídeos de teste
  ```

---

## ⚙️ Pré-requisitos e Instalação

Siga os passos abaixo para configurar o ambiente de desenvolvimento localmente:

### 1. Clonar o Repositório e Criar o Ambiente Virtual

```bash
git clone https://github.com/RenatoFMS/iafit_projeto.git
cd iafit_projeto/backend
python -m venv venv
```

### 2. Dependências de Áudio do Sistema (Linux / Ubuntu)

> ⚠️ **Aviso Importante (Linux):** Antes de instalar os pacotes Python, instale as bibliotecas de desenvolvimento de áudio do sistema necessárias para o funcionamento de captura e reprodução sonora:

```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio
```

### 3. Ativar o Ambiente Virtual e Instalar Dependências

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configuração Obrigatória do Firebase

Para habilitar a persistência na nuvem, coloque o ficheiro de credenciais da conta de serviço do Firebase na pasta `backend/` com o nome exato:

```text
iafit_projeto/backend/firebase_key.json
```

> 🔒 *Por razões de segurança, o ficheiro `firebase_key.json` está protegido no `.gitignore` e nunca deve ser comitado no repositório.*

---

## 🚀 Como Rodar o Projeto

Para iniciar o servidor da API biomecânica:

```bash
python backend/main.py
```

> 📲 **App Flutter (`mobile/`):** o `backend/main.py` expõe uma API local (porta `8765`) que permite ao app Flutter (`mobile/`) enviar os pontos articulares extraídos via ML Kit (`POST /analisar_pose`), escolher o exercício e importar os treinos concluídos. Veja [docs/INTEGRACAO_FLUTTER.md](docs/INTEGRACAO_FLUTTER.md).

---

## 🧪 Sistema de Quality Assurance (QA)

O projeto conta com uma suíte de automação de QA para validar a precisão matemática 3D e a contagem de repetições em alto desempenho (com renderização gráfica e saída de voz desativadas).

### 1. Baixar o Dataset de Vídeos de Teste

O script `baixar_videos.py` pesquisa e descarrega automaticamente vídeos curtos (`<= 60s`) em codec H.264 (`avc1`) para cada um dos 30 exercícios na pasta `dataset_qa/`, registando as respetivas origens em `dataset_qa/urls_mapeamento.json`:

```bash
python backend/baixar_videos.py
```

### 2. Executar a Validação em Lote

Para processar todos os vídeos do diretório `backend/dataset_qa/` sequencialmente e aferir a taxa de sucesso do motor biomecânico:

```bash
python backend/testador_lote.py
```

Também é possível testar um único ficheiro de vídeo isoladamente passando os argumentos `--video` e `--id`:

```bash
python backend/testador_lote.py --video backend/dataset_qa/3_1.mp4 --id 3
```

### 📊 Relatórios Históricos de QA

Ao concluir a execução em lote, o sistema apresenta o sumário estatístico no terminal e exporta automaticamente um ficheiro detalhado com carimbo de data e hora na pasta **`docs/relatorios_qa/`**:

```text
docs/relatorios_qa/relatorio_qa_YYYYMMDD_HHMM.txt
```

Cada relatório preserva o histórico de validação contendo o nome do vídeo, URL original do YouTube, total de repetições ou tempo isométrico, erros de postura contabilizados, deteção de fadiga, gasto calórico estimado e a taxa de sucesso global da bateria de testes.
