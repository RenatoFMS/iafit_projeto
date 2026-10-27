# 🏛️ Arquitetura de Software do IAFit — Edge Computing & API Matemática

Este documento apresenta a modelagem arquitetural e comportamental do **IAFit**, concebida sob o paradigma de **Computação de Borda (*Edge Computing*)** aliada a um **Motor Matemático desacoplado** e **Persistência Híbrida (*Offline-First* + *Cloud*)**. Os diagramas abaixo detalham a distribuição de responsabilidades e o ciclo de vida em tempo real de uma sessão de análise biomecânica.

---

## 1. Diagrama de Arquitetura (Edge Computing + Persistência Híbrida)

```mermaid
flowchart LR
    subgraph EDGE["📱 Dispositivo Mobile — Edge Computing (Flutter)"]
        direction TB
        CAM["📷 Câmara Nativa (Stream YUV420 / NV21)"]
        MLKIT["🧠 Google ML Kit Pose (Extração Local de 33 Landmarks)"]
        UI["🖥️ Interface Reativa (HUD + Skeleton Overlay)"]
        ENG["🔌 EngineService (Cliente HTTP/REST)"]
        SQLITE[("🗄️ SQLite Local — Histórico Offline-First")]

        CAM -->|"Frames brutos em memória (0 bytes na rede)"| MLKIT
        MLKIT -->|"Coordenadas para renderização imediata"| UI
        MLKIT -->|"Vetor normalizado (x, y, z, visibilidade)"| ENG
        ENG -->|"Registo de séries concluídas"| SQLITE
        SQLITE -.->|"Consulta instantânea de evolução e gráficos"| UI
    end

    subgraph SERVER["⚙️ Motor Local — API Matemática (Python)"]
        direction TB
        HTTP["🌐 Servidor HTTP/REST (ponte_flutter.py — Porta 8765)"]
        MOTOR["🔄 Máquina de Estados (motor_ia.py + math_utils.py)"]
        BIO["📐 Geometria Vetorial 3D (analise_biomecanica.py)"]
        FBCLIENT["☁️ Camada de Persistência (firebase_client.py)"]

        HTTP -->|"Deserialização JSON"| MOTOR
        MOTOR <-->|"Trigonometria 3D, filtros e postura"| BIO
        MOTOR -->|"Consolidação da série e gasto MET"| FBCLIENT
    end

    subgraph CLOUD["☁️ Nuvem (Google Cloud Platform)"]
        FIRESTORE[("🔥 Firebase Firestore — Coleção treinos")]
    end

    ENG ==>|"HTTP/REST POST /analisar_pose — Payloads JSON leves (~2 KB de coordenadas)"| HTTP
    HTTP ==>|"Resposta JSON em sub-5ms — Feedback, Reps, Fase e Erros"| ENG
    ENG -.->|"GET /treinos e POST /finalizar"| HTTP
    FBCLIENT ==>|"Sincronização assíncrona TLS/gRPC"| FIRESTORE

    classDef edgeNode fill:#1e3a5f,stroke:#60a5fa,stroke-width:1.5px,color:#ffffff
    classDef serverNode fill:#1f3d2b,stroke:#4ade80,stroke-width:1.5px,color:#ffffff
    classDef storageNode fill:#4a2511,stroke:#fb923c,stroke-width:2px,color:#ffffff
    class CAM,MLKIT,UI,ENG edgeNode
    class HTTP,MOTOR,BIO,FBCLIENT serverNode
    class SQLITE,FIRESTORE storageNode
```

### Justificativa Arquitetural e Redução de Latência na Rede

Em arquiteturas tradicionais e monolíticas de visão computacional, o cliente atua apenas como um coletor de imagem que codifica e transmite continuamente quadros de vídeo (via MJPEG, WebRTC ou *frames* Base64) para um servidor processar a rede neural. Mesmo em resolução moderada (720p), cada quadro comprimido consome entre **80 KB e 300 KB**, gerando tráfego superior a **3 MB/s a 8 MB/s** a 30 FPS, além de acumular atrasos de compressão JPEG, contenção em redes Wi-Fi congestionadas e decodificação de matrizes de pixels no servidor.

Ao migrar a inferência de pose para a borda (**Flutter + Google ML Kit Pose Detection** acelerado pela NPU/GPU do próprio *smartphone*), o IAFit elimina integralmente o tráfego de vídeo na rede:

| Critério Técnico | Streaming Monolítico de Vídeo | Edge Computing + API Matemática (IAFit) |
| :--- | :--- | :--- |
| **Carga útil por frame na rede** | ~100 KB a 300 KB (imagem comprimida) | **~2 KB** (JSON com 33 pontos `x, y, z, vis`) |
| **Redução de largura de banda** | Referência base (100%) | **Superior a 98% de redução** |
| **Custo de CPU/GPU no servidor** | Alto (decodificação de vídeo + inferência CNN) | **Mínimo** (apenas álgebra vetorial e trigonometria `O(1)`) |
| **Privacidade (*Privacy by Design*)** | Imagens do utilizador trafegam pela rede | **Total** (nenhum pixel abandona o telemóvel) |
| **Resiliência de armazenamento** | Dependente de conectividade contínua | **Híbrida** (`SQLite` local instantâneo + `Firestore` assíncrono) |

Essa decisão arquitetural reduz o tempo de ida e volta (*Round-Trip Time*) de centenas de milissegundos para poucos milissegundos (especialmente via rede local ou túnel físico `adb reverse`), permitindo evolução independente das regras biomecânicas em Python sem necessidade de recompilar ou redistribuir o aplicativo móvel.

---

## 2. Diagrama de Sequência (Fluxo de Execução em Tempo Real)

```mermaid
sequenceDiagram
    autonumber
    actor User as Utilizador
    participant UI as "UI Flutter (MovementCameraScreen)"
    participant CamML as "Câmara Nativa + Google ML Kit"
    participant Engine as "EngineService (Cliente REST)"
    participant API as "Motor Python (ponte_flutter + motor_ia)"
    participant Bio as "Cálculo Biomecânico (analise_biomecanica)"
    participant SQLite as "SQLite Local (Dispositivo)"
    participant Cloud as "Firebase Firestore (Nuvem)"

    User->>UI: Inicia Sessão de Exercício
    activate UI
    UI->>Engine: selecionarExercicio(idExercicio)
    Engine->>API: POST /exercicio (Sincroniza catálogo e reinicia filtros)
    API-->>Engine: HTTP 200 OK (Estado inicial pronto)
    UI->>CamML: Inicializa CameraPreview + startImageStream()
    activate CamML

    loop Loop de Captura da Câmara Nativa (Frame a Frame)
        CamML->>CamML: Extrai 33 landmarks articulares na borda (ML Kit)
        CamML-->>UI: Renderiza esqueleto sobreposto localmente sem atraso de rede
        CamML->>Engine: Envia pose detetada (controle de concorrência in-flight)
        Engine->>API: Envio do POST /analisar_pose (id_exercicio + 33 coordenadas JSON)
        activate API
        API->>Bio: processar_exercicio(landmarks, config, filtros_memoria)
        activate Bio
        Bio->>Bio: Cálculo Biomecânico de Ângulos 3D, Suavização e Postura
        Bio-->>API: Retorna fase, amplitude (%), repetições, erros e fadiga
        deactivate Bio
        API-->>Engine: HTTP 200 JSON — Feedback (Repetições/Erros, Fase e Ângulo)
        deactivate API
        Engine-->>UI: Entrega EngineLiveState atualizado
        UI->>UI: setState() — Atualiza contador de Reps, Fase e Alertas na UI
    end

    User->>UI: Finaliza a Série
    deactivate CamML
    UI->>Engine: finalizarSerie()
    Engine->>API: POST /finalizar (Consolida repetições, duração e calorias MET)
    activate API
    par Persistência Assíncrona em Nuvem
        API->>Cloud: Persiste documento na coleção treinos (Thread não-bloqueante)
    and Retorno Imediato ao Cliente
        API-->>Engine: HTTP 200 JSON (Resumo consolidado da série)
    end
    deactivate API
    Engine->>SQLite: Grava histórico consolidado localmente (sqflite)
    Engine-->>UI: Confirma conclusão da série
    UI->>UI: setState() / Navigator.pop(true) — Atualiza progresso de séries (ex. 2/3)
    UI-->>User: Exibe Resumo Biomecânico da Série
    deactivate UI
```

### Análise do Fluxo de Execução e Controle de Latência

O fluxo temporal acima foi projetado para desacoplar a **taxa de quadros visual (UI a 60 FPS)** da **taxa de amostragem cinemática da rede**, evitando travamentos (*jank*) ou filas de pacotes atrasados (*bufferbloat*):

1. **Renderização Local Imediata:** Assim que o `CameraController` entrega um frame em memória ao **Google ML Kit**, o esqueleto anatômico é desenhado imediatamente sobre o `CameraPreview` no próprio dispositivo, garantindo percepção visual de latência zero para o utilizador.
2. **Controle de Concorrência (*Backpressure*):** O `EngineService` envia o `POST /analisar_pose` com um único objeto JSON compacto contendo o `id_exercicio` e as 33 coordenadas tridimensionais normalizadas, descartando quadros excedentes caso uma requisição ainda esteja em trânsito — o que elimina atrasos cumulativos em redes Wi-Fi instáveis.
3. **Processamento Determinístico em Memória:** No Back-end Python, o servidor ignora qualquer etapa pesada de visão computacional e executa apenas operações algébricas de produto escalar vetorial, filtragem de média móvel (`FiltroSuavizacao`) e transições da máquina de estados (`base` → `subida` → `topo` → `descida`), respondendo em frações de milissegundo para acionar o `setState()` no Flutter.
4. **Persistência Não-Bloqueante no Encerramento:** Ao concluir a série (`POST /finalizar`), o envio para o **Firebase Firestore** ocorre em *thread* secundária assíncrona enquanto o **SQLite** local é atualizado de imediato no telemóvel, assegurando que a transição de ecrã e o avanço do contador de séries ocorram instantaneamente mesmo sem acesso à internet.
