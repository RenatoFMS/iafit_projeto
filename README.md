# 🏋️‍♂️ IAFit - Sistema de Análise Biomecânica Inteligente

O **IAFit** é uma solução completa de engenharia de software e visão computacional desenvolvida como Trabalho de Conclusão de Curso (TCC). O sistema adota a arquitetura de **Edge Computing (Computação de Borda)** combinada com uma **API Matemática Back-end**, permitindo a avaliação postural, contagem de repetições e acompanhamento de treinos físicos em tempo real com alta precisão, baixa latência e privacidade.

A extração de pontos articulares é realizada diretamente no dispositivo do utilizador (Edge AI com Google ML Kit Pose e Flutter), eliminando a necessidade de transmissão contínua de fluxo de vídeo para a rede. Os dados cinemáticos normalizados são processados pela API matemática em Python, que executa os cálculos trigonométricos tridimensionais, deteção de fadiga e persistência em nuvem e local.

---

## 🏛️ Arquitetura do Monorepo

O projeto está estruturado no formato **Monorepo**, garantindo isolamento de responsabilidades, versionamento unificado e princípios de *Clean Code*:

```text
iafit_projeto/
├── backend/                      # Motor Matemático e API Biomecânica (Python)
│   ├── core/
│   │   ├── analise_biomecanica.py  # Geometria vetorial 3D, ângulos e gasto calórico
│   │   ├── config_exercicios.py    # Catálogo parametrizado dos 30 exercícios e METs
│   │   ├── firebase_client.py      # Integração e persistência na nuvem (Firestore)
│   │   ├── math_utils.py           # Filtros de suavização temporal e contadores
│   │   ├── motor_ia.py             # Máquina de estados, calibração e biomecânica
│   │   ├── ponte_flutter.py        # API HTTP local (POST /analisar_pose, /finalizar)
│   │   └── voz_client.py           # Síntese e feedback sonoro assíncrono (gTTS)
│   ├── main.py                     # Servidor HTTP da API matemática
│   ├── baixar_videos.py            # Coletor automatizado de vídeos de QA (yt-dlp)
│   ├── testador_lote.py            # Validação em lote da inferência biomecânica
│   ├── dataset_qa/                 # Banco de vídeos curtos para testes de QA
│   └── requirements.txt            # Dependências Python
│
├── mobile/                       # Aplicação Cliente (Flutter + Google ML Kit)
│   ├── lib/
│   │   ├── models/                 # Modelos de dados e mapeamento do catálogo
│   │   ├── screens/                # Ecrãs (Treinos, Exercícios, Histórico, Câmera)
│   │   ├── services/               # Rastreamento ML Kit, API Engine e SQLite
│   │   └── widgets/                # Componentes visuais e sobreposição do esqueleto
│   ├── test/                       # Testes de unidade, integração e UI
│   └── pubspec.yaml                # Dependências do ecossistema Flutter
│
└── docs/                         # Documentação Técnica e Artefatos do Projeto
    ├── ESTRUTURA_FIREBASE.md       # Modelagem dos dados no Firestore
    ├── INTEGRACAO_FLUTTER.md       # Especificação do protocolo e rotas HTTP
    ├── relatorios_qa/              # Logs históricos gerados pelos testes em lote
    └── *.mp4                       # Vídeos e gravações de teste
```

### Divisão de Responsabilidades
* **`backend/`**: Implementa o servidor de cálculo vetorial tridimensional, máquinas de estado de exercícios, deteção algorítmica de fadiga concêntrica, controle de calibração biomecânica, persistência remota no Firebase Firestore e rotinas de automação de Quality Assurance (QA).
* **`mobile/`**: Responsável pela captura de vídeo no dispositivo, inferência de visão computacional na borda (extração de 33 landmarks corporais via Google ML Kit), interface rica e responsiva, persistência offline-first via SQLite e renderização do esqueleto articular ao vivo.
* **`docs/`**: Centraliza manuais de arquitetura, guias de integração, especificações de banco de dados, relatórios históricos de testes automatizados e mídias de validação.

---

## 🛠️ Tecnologias Utilizadas

* **[Python 3.11+](https://www.python.org/):** Núcleo matemático, processamento trigonométrico vetorial e servidor HTTP assíncrono.
* **[Flutter](https://flutter.dev/) (Dart):** Framework multiplataforma para interface nativa de alta performance no cliente (Android, iOS e Desktop).
* **[Google ML Kit Pose Detection](https://developers.google.com/ml-kit/vision/pose-detection):** Módulo de Visão Computacional embarcado para extração em tempo real dos 33 marcos anatômicos sem dependência de rede.
* **[Firebase Firestore](https://firebase.google.com/docs/firestore):** Armazenamento em nuvem NoSQL para histórico de sessões, métricas agregadas e persistência distribuída.
* **[SQLite](https://www.sqlite.org/) (`sqflite`):** Banco de dados relacional local integrado no aplicativo móvel, garantindo operação offline e importação instantânea de métricas.

---

## 🚀 Como Executar o Back-end (API Python)

O Back-end atua como uma API REST local para o processamento cinemático das coordenadas articulares.

### 1. Aceder ao Diretório do Back-end
```bash
cd backend
```

### 2. Configurar o Ambiente Virtual
```bash
# Criação do ambiente virtual
python -m venv venv

# Ativação do ambiente virtual (Linux/macOS)
source venv/bin/activate

# Ativação no Windows (PowerShell/CMD)
# .\venv\Scripts\Activate.ps1
```

### 3. Dependências do Sistema (Apenas Linux / Ubuntu)
Caso execute em distribuições Linux, instale as bibliotecas de desenvolvimento de áudio do sistema:
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio
```

### 4. Instalar as Dependências Python
```bash
pip install -r requirements.txt
```

### 5. Configurar Credenciais do Firebase (Opcional)
Para sincronização em nuvem, insira a chave da conta de serviço em:
```text
backend/firebase_key.json
```
*(Caso o ficheiro não esteja presente, o sistema manterá o salvamento local em `backend/treinos_locais.jsonl` de forma transparente).*

### 6. Iniciar o Servidor da API
```bash
python main.py
```
O servidor ficará disponível em `http://127.0.0.1:8765`, aguardando requisições `POST /analisar_pose` e comandos de controle da sessão.

---

## 📱 Como Executar o Front-end (Mobile)

A aplicação Flutter pode ser executada em emuladores, dispositivos físicos (Android/iOS) ou em ambiente Desktop de desenvolvimento.

### 1. Aceder ao Diretório Mobile
```bash
cd mobile
```

### 2. Instalar os Pacotes do Flutter
```bash
flutter pub get
```

### 3. Executar em Modo de Desenvolvimento
Conecte o seu smartphone com a depuração USB ativada (ou inicie um emulador/dispositivo desktop) e execute:
```bash
flutter run
```

> 💡 **Dica de Conexão:**
> * No **Linux Desktop**, o aplicativo inicia o processo do motor Python em segundo plano automaticamente caso a API local não esteja em execução.
> * Ao executar em um **dispositivo móvel físico**, certifique-se de que o telemóvel e o computador estão na mesma rede Wi-Fi e altere o endereço da API em **Configurações** para o IP do seu computador (ex.: `http://192.168.1.X:8765`).

### 4. Gerar Pacote de Instalação (APK Android)
Para compilar o binário otimizado para Android:
```bash
flutter build apk --release
```
O arquivo `.apk` final será gerado em `mobile/build/app/outputs/flutter-apk/app-release.apk`.

---

## 🧪 Pipeline de Quality Assurance (QA)

Para assegurar a precisão biomecânica sem depender da captura contínua por câmara, o projeto conta com ferramentas automatizadas de validação:

* **Download de Dataset de Teste:**
  ```bash
  python backend/baixar_videos.py
  ```
* **Execução dos Testes em Lote:**
  ```bash
  python backend/testador_lote.py
  ```
Os relatórios consolidados de precisão, contagem e consistência postural são salvos automaticamente em `docs/relatorios_qa/`.
