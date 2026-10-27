# 📐 Modelagem UML e Entidade-Relacionamento — Projeto IAFit

Este documento compõe o caderno de engenharia de software do Trabalho de Conclusão de Curso (TCC) do sistema **IAFit**, reunindo as visões funcional (**Casos de Uso**), estrutural orientada a objetos (**Diagrama de Classes**) e de persistência relacional/documental (**Diagrama Entidade-Relacionamento — DER**).

---

## 1. Diagrama de Casos de Uso

```mermaid
graph TD
    Atleta["👤 Utilizador / Atleta (Ator Principal)"]
    MotorIA["🤖 Motor Python / ML Kit (Ator Secundário)"]

    subgraph IAFIT["Fronteira do Sistema IAFit (Edge + API Matemática)"]
        UC_AUTH(["Autenticar no Sistema"])
        UC_HIST(["Visualizar Histórico"])
        UC_TREINO(["Iniciar Treino"])
        UC_CALIB(["Calibrar Exercício"])
        UC_BIO(["Processar Biomecânica"])
        UC_REPS(["Contar Repetições"])
    end

    Atleta -->|"Credenciais / Perfil local"| UC_AUTH
    Atleta -->|"Seleciona rotina e série"| UC_TREINO
    Atleta -->|"Consulta evolução e métricas"| UC_HIST
    Atleta -->|"Posiciona-se no enquadramento"| UC_CALIB

    UC_TREINO -.->|"«include»"| UC_CALIB
    UC_TREINO -.->|"«include»"| UC_BIO
    UC_BIO -.->|"«include»"| UC_REPS

    MotorIA -->|"Extrai landmarks e avalia ângulos 3D"| UC_BIO
    MotorIA -->|"Valida fases concêntrica e excêntrica"| UC_REPS
    MotorIA -.->|"Verifica visibilidade inicial"| UC_CALIB

    classDef actorStyle fill:#1e3a5f,stroke:#60a5fa,stroke-width:2px,color:#ffffff
    classDef usecaseStyle fill:#1f3d2b,stroke:#4ade80,stroke-width:1.5px,color:#ffffff
    class Atleta,MotorIA actorStyle
    class UC_AUTH,UC_HIST,UC_TREINO,UC_CALIB,UC_BIO,UC_REPS usecaseStyle
```

### Descrição Académica — Visão Funcional

O **Diagrama de Casos de Uso** delimita as fronteiras funcionais do ecossistema **IAFit** e explicita a cooperação entre o agente humano e o subsistema inteligente de visão computacional:

* **Ator Principal (*Utilizador / Atleta*):** Interage diretamente com a camada de apresentação em Flutter para gerir o seu acesso e perfil antropométrico (**Autenticar no Sistema**), acompanhar gráficos de desempenho calórico e postural (**Visualizar Histórico**), posicionar-se perante a câmara (**Calibrar Exercício**) e conduzir as séries prescritas (**Iniciar Treino**).
* **Ator Secundário (*Motor Python / ML Kit*):** Representa o par cooperativo formado pelo extrator de pose na borda (*Google ML Kit*) e pela API matemática em Python, atuando autonomamente nos casos de uso internos incluídos (`«include»`) durante o treino: **Processar Biomecânica** (cálculo vetorial tridimensional e deteção de desvios posturais) e **Contar Repetições** (máquina de estados finitos das fases do movimento).

---

## 2. Diagrama de Classes (Núcleo do Sistema)

```mermaid
classDiagram
    direction TB

    class StatefulWidget {
        <<FlutterFramework>>
        +createState() State
    }

    class MovementCameraScreen {
        <<UI Layer - Flutter>>
        +String exerciseName
        +String exerciseId
        +int targetReps
        -bool isAnalyzing
        +iniciarSessao() Future~void~
        +processarFrameCamera() void
        +finalizarSerie() Future~void~
    }

    class PoseTrackingService {
        <<Edge AI - ML Kit>>
        -PoseDetector poseDetector
        -bool isBusy
        +extrairLandmarks(CameraImage image) Future~List~
        +normalizarCoordenadas() List~Map~
        +dispose() Future~void~
    }

    class EngineService {
        <<Singleton - HTTP Client>>
        +String defaultUrl
        +ValueNotifier~bool~ online
        +selecionarExercicio(String id) Future~EngineResult~
        +analisarPose(String id, List landmarks) Future~EngineLiveState~
        +finalizarSerie() Future~EngineResult~
        +sincronizarTreinos() Future~int~
    }

    class EngineLiveState {
        <<DTO>>
        +String exerciseId
        +int repetitions
        +int postureErrors
        +String phase
        +String feedback
        +double angle
    }

    class DatabaseHelper {
        <<SQLite - DatabaseService>>
        -Database database
        -int schemaVersion
        +initDatabase() Future~Database~
        +inserirTreino(WorkoutHistory treino) Future~int~
        +listarHistorico() Future~List~
        +obterPerfilUtilizador() Future~UserModel~
    }

    class AnalisadorBiomecanico {
        <<Python Core - Biomecanica>>
        +Dict catalogoExercicios
        +int errosSerie
        +calcularAngulo3D( List a, List b, List c ) float
        +processarExercicio( List keypoints, Dict config ) Dict
        +analisarSegurancaPostura( List keypoints, Dict config ) Tuple
        +calcularCalorias( float duracaoSeg, float met ) float
    }

    class FiltroSuavizacao {
        <<Python Math - math_utils>>
        -Deque historico
        +int tamanhoJanela
        +atualizar( float valor ) float
        +limpar() void
    }

    class ContadorRepeticoes {
        <<Python State Machine>>
        +int reps
        +String fase
        +List temposRepeticoes
        +atualizar( int porcentagem ) Tuple
        +verificarFadiga() bool
        +limpar() void
    }

    class FirebaseClient {
        <<Cloud Persistence - firebase_client>>
        -Client firestoreDb
        -String caminhoCredencial
        +salvarTreino( String exercicio, int reps, int erros, float kcal ) void
        -enviarFirestoreAssincrono( Dict dados ) void
    }

    StatefulWidget <|-- MovementCameraScreen : heranca
    MovementCameraScreen *-- PoseTrackingService : composicao
    MovementCameraScreen --> EngineService : associacao
    EngineService ..> EngineLiveState : instancia
    EngineService --> DatabaseHelper : persiste offline
    EngineService ..> AnalisadorBiomecanico : HTTP REST analisar_pose
    AnalisadorBiomecanico *-- ContadorRepeticoes : composicao
    AnalisadorBiomecanico *-- FiltroSuavizacao : composicao
    AnalisadorBiomecanico --> FirebaseClient : persiste na nuvem
```

### Descrição Académica — Arquitetura Orientada a Objetos e Modularidade

O **Diagrama de Classes** evidencia a aplicação dos princípios **SOLID** e de **Separação de Preocupações (*Separation of Concerns*)** entre o cliente móvel (Dart/Flutter) e o servidor matemático (Python):

* **Camada Front-end (Flutter):** A classe `MovementCameraScreen` especializa `StatefulWidget` (**herança**) para gerir o ciclo de vida reativo da interface durante a execução da série, compondo uma instância dedicada de `PoseTrackingService` (**composição**) encarregada de extrair localmente os 33 marcos anatômicos via Google ML Kit. A comunicação externa e a orquestração local são abstraídas pelo *Singleton* `EngineService`, que converte respostas HTTP em objetos imutáveis `EngineLiveState` e delega a gravação relacional ao `DatabaseHelper` (`DatabaseService` / `sqflite`).
* **Camada Back-end (Python):** O módulo central representado por `AnalisadorBiomecanico` agrega por **composição** os objetos de estado `ContadorRepeticoes` (responsável pela máquina de estados `base → subida → topo → descida` e deteção algorítmica de fadiga concêntrica) e `FiltroSuavizacao` (janela deslizante de média móvel para supressão de ruído de captura). Ao término da série, associa-se ao `FirebaseClient` para persistência não-bloqueante na nuvem.

---

## 3. Diagrama Entidade-Relacionamento (DER)

```mermaid
erDiagram
    Utilizador ||--o{ Treino : "realiza"
    Treino ||--|{ Serie_Exercicio : "possui"

    Utilizador {
        int id PK "Identificador unico do utilizador"
        string nome "Nome completo do atleta"
        string email "Endereco eletronico unico de acesso"
        float peso_kg "Massa corporal para calculo calorico MET"
        float altura_cm "Estatura em centimetros"
        string objetivo "Meta fisica principal do perfil"
    }

    Treino {
        int id PK "Identificador unico da sessao de treino"
        int utilizador_id FK "Chave estrangeira para Utilizador"
        datetime data "Carimbo temporal de realizacao da sessao"
        float calorias "Gasto energetico total consolidado (kcal)"
        int duracao_seg "Tempo total de atividade em segundos"
        string remote_id "Identificador de sincronizacao com Firestore"
    }

    Serie_Exercicio {
        int id PK "Identificador unico da serie executada"
        int treino_id FK "Chave estrangeira para Treino"
        string nome_exercicio "Designacao oficial no catalogo biomecanico"
        int repeticoes "Repeticoes validas ou segundos em isometria"
        int erros_postura "Total de desvios biomecanicos registados"
        boolean isometrico "Indicador de exercicio estatico por tempo"
    }
```

### Descrição Académica — Modelo de Dados e Persistência

O **Diagrama Entidade-Relacionamento (DER)** formaliza o modelo conceitual e lógico dos dados biométricos e cinemáticos recolhidos pelo **IAFit**, estruturado na Terceira Forma Normal (3FN) com cardinalidades **1 para N (`1:N`)**:

* **`Utilizador` → `Treino` (`1:N`):** Um utilizador registado pode realizar zero ou várias sessões de treino ao longo do tempo, enquanto cada registo em `Treino` pertence exclusivamente a um único atleta (`utilizador_id`), preservando parâmetros antropométricos essenciais para a estimativa individualizada de quilocalorias via índice **MET (*Metabolic Equivalent of Task*)**.
* **`Treino` → `Serie_Exercicio` (`1:N`):** Cada sessão de treino agrega uma ou múltiplas séries granulares em `Serie_Exercicio` (`treino_id`), permitindo rastreabilidade analítica por movimento (`nome_exercicio`), volume efetivo (`repeticoes`) e qualidade técnica de execução (`erros_postura`). No dispositivo móvel, esta estrutura sustenta as consultas SQL em **SQLite** para exibição imediata offline, ao passo que os resumos consolidados e o identificador `remote_id` asseguram idempotência e consistência eventual com a coleção `treinos` no **Firebase Firestore**.
