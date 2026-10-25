"""Ponte de comunicação entre o motor Python (main.py) e o app Flutter (fitness-app).

O módulo usa apenas a biblioteca padrão e expõe uma API HTTP local:

    GET  /saude                -> verificação de disponibilidade do motor
    GET  /exercicios           -> catálogo dos exercícios (id, nome, tipo, MET)
    GET  /estado               -> estado ao vivo da série em curso
    GET  /video_feed           -> stream MJPEG (legado/opcional)
    GET  /treinos?limite=N     -> últimos N treinos concluídos (ordem cronológica)
    POST /analisar_pose        -> recebe id_exercicio + 33 landmarks e devolve telemetria
    POST /exercicio            -> {"id": "3"}  seleciona o exercício (id_atual)
    POST /finalizar            -> encerra e guarda a série em curso

O fluxo de dados (Edge Computing + Cloud/API Backend) é:
    Flutter (ML Kit Pose) --POST /analisar_pose--> processar_exercicio() --> resposta JSON
    Flutter --POST /exercicio / /finalizar--> fila de comandos --> main.py
    main.py --salvar_treino--> Firebase Firestore + registrar_treino() (treinos_locais.jsonl)
    Flutter --GET /treinos--> importa para o SQLite (histórico e gráficos)

Variáveis de ambiente (todas opcionais):
    IAFIT_API_HOST   Interface de escuta (padrão: 127.0.0.1; use 0.0.0.0 para
                     aceitar telemóveis na mesma rede).
    IAFIT_API_PORT   Porta TCP (padrão: 8765).
    IAFIT_API_TOKEN  Se definido, todos os pedidos têm de enviar o cabeçalho
                     ``X-IAFit-Token`` (ou ``?token=`` em /video_feed).
    IAFIT_TREINOS_FILE  Caminho do ficheiro JSON Lines (padrão: treinos_locais.jsonl).
"""

import json
import os
import queue
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from core.config_exercicios import EXERCICIOS

HOST_PADRAO: str = "127.0.0.1"
PORTA_PADRAO: int = 8765
LIMITE_PADRAO_TREINOS: int = 200
LIMITE_MAXIMO_TREINOS: int = 1000
TAMANHO_MAXIMO_CORPO: int = 65536
BOUNDARY_MJPEG: str = "iafitframe"

_RAIZ_PROJETO: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_lock_treinos = threading.Lock()
_treinos_em_memoria: Optional[List[Dict[str, Any]]] = None

_fila_comandos: "queue.Queue[Dict[str, Any]]" = queue.Queue()

_lock_estado = threading.Lock()
_estado_atual: Dict[str, Any] = {}

_condicao_frame = threading.Condition()
_ultimo_frame_jpeg: Optional[bytes] = None
_sequencia_frame: int = 0

_processador_pose: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
_finalizador_serie: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None


def _caminho_treinos() -> str:
    """Devolve o caminho do ficheiro JSON Lines com os treinos concluídos.

    Returns:
        Caminho configurado em IAFIT_TREINOS_FILE ou 'treinos_locais.jsonl' na raiz do projeto.
    """
    padrao = os.path.join(_RAIZ_PROJETO, "treinos_locais.jsonl")
    return os.environ.get("IAFIT_TREINOS_FILE", padrao)


def _carregar_treinos() -> List[Dict[str, Any]]:
    """Carrega (uma única vez) os treinos persistidos em disco para a memória.

    Linhas corrompidas são ignoradas para que um ficheiro parcialmente escrito
    nunca impeça o arranque do motor.

    Returns:
        Lista mutável partilhada de treinos, em ordem cronológica.
    """
    global _treinos_em_memoria
    if _treinos_em_memoria is not None:
        return _treinos_em_memoria

    treinos: List[Dict[str, Any]] = []
    caminho = _caminho_treinos()
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registro = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if isinstance(registro, dict) and registro.get("id"):
                    treinos.append(registro)
    _treinos_em_memoria = treinos
    return treinos


def registrar_treino(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Persiste localmente um treino concluído para o app Flutter importar.

    Args:
        dados: Campos do treino (exercicio, repeticoes, erros_postura, calorias,
            duracao_seg, exercicio_id, isometrico).

    Returns:
        O registro gravado, já com 'id' único e 'data' em ISO 8601 (UTC).
    """
    registro = dict(dados)
    registro["id"] = uuid.uuid4().hex
    registro["data"] = datetime.now(timezone.utc).isoformat()

    with _lock_treinos:
        treinos = _carregar_treinos()
        with open(_caminho_treinos(), "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        treinos.append(registro)
    return registro


def listar_treinos(limite: int = LIMITE_PADRAO_TREINOS) -> List[Dict[str, Any]]:
    """Lista os treinos mais recentes em ordem cronológica.

    Args:
        limite: Quantidade máxima de treinos devolvidos (limitada a 1000).

    Returns:
        Cópia da lista dos últimos ``limite`` treinos.
    """
    limite = max(1, min(int(limite), LIMITE_MAXIMO_TREINOS))
    with _lock_treinos:
        return list(_carregar_treinos()[-limite:])


def enviar_comando(comando: Dict[str, Any]) -> None:
    """Coloca um comando na fila para ser aplicado pelo loop principal.

    Quando o comando seleciona um novo exercício diferente do atual, limpa o
    último frame JPEG em cache e pré-atualiza a identificação em ``_estado_atual``
    para que ``/video_feed`` e ``/estado`` nunca exibam o exercício anterior.

    Args:
        comando: Dicionário com a chave 'acao' ('selecionar' ou 'finalizar').
    """
    if comando.get("acao") == "selecionar":
        novo_id = str(comando.get("id", "")).strip()
        if novo_id in EXERCICIOS:
            config = EXERCICIOS[novo_id]
            limpar_frame_anterior = False
            with _lock_estado:
                id_anterior = str(_estado_atual.get("exercicio_id", "")).strip()
                if id_anterior != novo_id:
                    limpar_frame_anterior = bool(id_anterior)
                    _estado_atual.update(
                        exercicio_id=novo_id,
                        exercicio=config["nome"],
                        repeticoes=0,
                        segundos=0,
                        erros_postura=0,
                        fase="calibracao",
                        feedback="",
                        isometrico=_eh_isometrico(novo_id, config),
                    )
            if limpar_frame_anterior:
                with _condicao_frame:
                    global _ultimo_frame_jpeg
                    _ultimo_frame_jpeg = None
    _fila_comandos.put(comando)


def consumir_comando() -> Optional[Dict[str, Any]]:
    """Retira o próximo comando pendente sem bloquear o loop de vídeo.

    Returns:
        O comando mais antigo ou None se a fila estiver vazia.
    """
    try:
        return _fila_comandos.get_nowait()
    except queue.Empty:
        return None


def atualizar_estado(**campos: Any) -> None:
    """Atualiza o estado ao vivo exposto em GET /estado.

    Args:
        **campos: Pares chave/valor serializáveis em JSON.
    """
    with _lock_estado:
        _estado_atual.update(campos)


def obter_estado() -> Dict[str, Any]:
    """Devolve uma cópia do estado ao vivo da série em curso.

    Returns:
        Dicionário com exercício atual, repetições/segundos e erros de postura.
    """
    with _lock_estado:
        return dict(_estado_atual)


def publicar_frame(frame_jpeg: bytes) -> None:
    """Publica o último frame codificado em JPEG para os clientes de /video_feed.

    Args:
        frame_jpeg: Bytes da imagem JPEG já processada pelo MediaPipe/OpenCV.
    """
    global _ultimo_frame_jpeg, _sequencia_frame
    if not frame_jpeg:
        return
    with _condicao_frame:
        _ultimo_frame_jpeg = frame_jpeg
        _sequencia_frame += 1
        _condicao_frame.notify_all()


def obter_ultimo_frame() -> Optional[bytes]:
    """Devolve os bytes JPEG do frame mais recente publicado pelo motor.

    Returns:
        Bytes JPEG ou None se nenhum frame foi publicado ainda.
    """
    with _condicao_frame:
        return _ultimo_frame_jpeg


def registrar_processador_pose(
    processador: Callable[[Dict[str, Any]], Dict[str, Any]]
) -> None:
    """Regista a função de cálculo biomecânico acionada por POST /analisar_pose.

    Args:
        processador: Função que recebe o dicionário do payload e devolve a resposta JSON.
    """
    global _processador_pose
    _processador_pose = processador


def registrar_finalizador_serie(
    finalizador: Callable[[Dict[str, Any]], Dict[str, Any]]
) -> None:
    """Regista o callback síncrono acionado por POST /finalizar para persistir a série.

    Args:
        finalizador: Função que recebe o corpo opcional do pedido e guarda o treino.
    """
    global _finalizador_serie
    _finalizador_serie = finalizador


def _eh_isometrico(id_ex: str, config: Dict[str, Any]) -> bool:
    """Indica se o exercício é medido em tempo (isométrico) em vez de repetições.

    Args:
        id_ex: Chave do exercício no catálogo.
        config: Configuração do exercício.

    Returns:
        True para exercícios isométricos.
    """
    return config.get("tipo") == "isometrico" or id_ex in ("8", "22", "29")


def catalogo_exercicios() -> List[Dict[str, Any]]:
    """Monta o catálogo público de exercícios do motor.

    Returns:
        Lista com id, nome, tipo ('reps' ou 'tempo') e MET de cada exercício.
    """
    return [
        {
            "id": id_ex,
            "nome": config["nome"],
            "tipo": "tempo" if _eh_isometrico(id_ex, config) else "reps",
            "met": config.get("met", 3.0),
        }
        for id_ex, config in EXERCICIOS.items()
    ]


class _ManipuladorAPI(BaseHTTPRequestHandler):
    """Manipulador HTTP da API local do motor IAFit."""

    server_version = "IAFitMotor/1.0"

    def log_message(self, formato: str, *args: Any) -> None:
        """Silencia o log por pedido para não poluir o terminal do treino."""

    def _enviar_json(self, status: int, corpo: Any) -> None:
        """Serializa e envia uma resposta JSON com cabeçalhos CORS.

        Args:
            status: Código HTTP.
            corpo: Objeto serializável em JSON.
        """
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self._enviar_cabecalhos_cors()
        self.end_headers()
        self.wfile.write(dados)

    def _enviar_cabecalhos_cors(self) -> None:
        """Permite chamadas do Flutter Web e Desktop (origem configurável por ambiente)."""
        origem = os.environ.get("IAFIT_API_CORS_ORIGIN", "*")
        self.send_header("Access-Control-Allow-Origin", origem)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-IAFit-Token")

    def _autorizado(self) -> bool:
        """Valida o token opcional da API via cabeçalho ou query string.

        Returns:
            True se não há token configurado ou se o token informado coincide.
        """
        token = os.environ.get("IAFIT_API_TOKEN")
        if not token:
            return True
        if self.headers.get("X-IAFit-Token") == token:
            return True
        consulta = parse_qs(urlparse(self.path).query)
        token_url = consulta.get("token", [""])[0]
        return token_url == token

    def _transmitir_mjpeg(self) -> None:
        """Transmite continuamente os frames JPEG processados em multipart/x-mixed-replace."""
        self.send_response(200)
        self.send_header(
            "Content-Type",
            f"multipart/x-mixed-replace; boundary={BOUNDARY_MJPEG}",
        )
        self.send_header(
            "Cache-Control",
            "no-store, no-cache, must-revalidate, max-age=0",
        )
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self._enviar_cabecalhos_cors()
        self.end_headers()

        ultimo_enviado = -1
        try:
            while True:
                with _condicao_frame:
                    if _sequencia_frame == ultimo_enviado:
                        _condicao_frame.wait(timeout=1.0)
                    frame_atual = _ultimo_frame_jpeg
                    seq_atual = _sequencia_frame

                if frame_atual is None or seq_atual == ultimo_enviado:
                    continue

                ultimo_enviado = seq_atual
                cabecalho_parte = (
                    f"--{BOUNDARY_MJPEG}\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame_atual)}\r\n\r\n"
                ).encode("ascii")
                self.wfile.write(cabecalho_parte)
                self.wfile.write(frame_atual)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _ler_json(self) -> Optional[Dict[str, Any]]:
        """Lê o corpo do pedido como objeto JSON.

        Returns:
            Dicionário decodificado ou None se o corpo for inválido/excessivo.
        """
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if tamanho <= 0 or tamanho > TAMANHO_MAXIMO_CORPO:
            return None
        try:
            corpo = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return corpo if isinstance(corpo, dict) else None

    def do_OPTIONS(self) -> None:
        """Responde ao pré-voo CORS."""
        self.send_response(204)
        self._enviar_cabecalhos_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        """Trata os endpoints de consulta (saúde, catálogo, estado, vídeo e treinos)."""
        if not self._autorizado():
            self._enviar_json(401, {"erro": "token inválido"})
            return

        url = urlparse(self.path)
        if url.path == "/saude":
            self._enviar_json(200, {"ok": True, "servico": "iafit-motor"})
        elif url.path == "/exercicios":
            self._enviar_json(200, {"exercicios": catalogo_exercicios()})
        elif url.path == "/estado":
            self._enviar_json(200, obter_estado())
        elif url.path == "/video_feed":
            consulta = parse_qs(url.query)
            id_ex_stream = consulta.get("exercicio", [""])[0].strip()
            if id_ex_stream in EXERCICIOS and obter_estado().get("exercicio_id") != id_ex_stream:
                enviar_comando({"acao": "selecionar", "id": id_ex_stream})
            self._transmitir_mjpeg()
        elif url.path == "/treinos":
            consulta = parse_qs(url.query)
            try:
                limite = int(consulta.get("limite", [LIMITE_PADRAO_TREINOS])[0])
            except ValueError:
                limite = LIMITE_PADRAO_TREINOS
            self._enviar_json(200, {"treinos": listar_treinos(limite)})
        else:
            self._enviar_json(404, {"erro": "rota não encontrada"})

    def do_POST(self) -> None:
        """Trata os comandos de controlo (selecionar exercício e finalizar série)."""
        if not self._autorizado():
            self._enviar_json(401, {"erro": "token inválido"})
            return

        caminho = urlparse(self.path).path
        if caminho == "/analisar_pose":
            corpo = self._ler_json()
            if corpo is None:
                self._enviar_json(400, {"erro": "corpo JSON inválido ou ausente"})
                return
            id_ex = str(
                corpo.get("id_exercicio")
                or corpo.get("exercicio_id")
                or corpo.get("id")
                or ""
            ).strip()
            if id_ex and id_ex not in EXERCICIOS:
                self._enviar_json(400, {"erro": f"exercício '{id_ex}' inexistente"})
                return
            landmarks = corpo.get("landmarks", corpo.get("pontos"))
            if landmarks is not None and not isinstance(landmarks, (list, dict)):
                self._enviar_json(400, {"erro": "formato de landmarks inválido"})
                return
            if _processador_pose is None:
                self._enviar_json(503, {"erro": "processador biomecânico não inicializado"})
                return
            resposta = _processador_pose(corpo)
            self._enviar_json(200, resposta)
        elif caminho == "/exercicio":
            corpo = self._ler_json()
            id_ex = str(corpo.get("id", "")).strip() if corpo else ""
            if id_ex not in EXERCICIOS:
                self._enviar_json(400, {"erro": f"exercício '{id_ex}' inexistente"})
                return
            enviar_comando({"acao": "selecionar", "id": id_ex})
            self._enviar_json(202, {"aceito": True, "id": id_ex, "nome": EXERCICIOS[id_ex]["nome"]})
        elif caminho == "/finalizar":
            corpo = self._ler_json() or {}
            if _finalizador_serie is not None:
                resultado = _finalizador_serie(corpo)
                self._enviar_json(202, {"aceito": True, **resultado})
            else:
                enviar_comando({"acao": "finalizar", **corpo})
                self._enviar_json(202, {"aceito": True})
        else:
            self._enviar_json(404, {"erro": "rota não encontrada"})


def iniciar_servidor(
    host: Optional[str] = None, porta: Optional[int] = None
) -> Optional[ThreadingHTTPServer]:
    """Inicia a API local numa thread daemon sem bloquear o loop de vídeo.

    Args:
        host: Interface de escuta (padrão: IAFIT_API_HOST ou 127.0.0.1).
        porta: Porta TCP (padrão: IAFIT_API_PORT ou 8765).

    Returns:
        A instância do servidor em execução ou None se a porta não puder ser aberta.
    """
    host_final = host if host is not None else os.environ.get("IAFIT_API_HOST", HOST_PADRAO)
    porta_final = porta if porta is not None else int(os.environ.get("IAFIT_API_PORT", PORTA_PADRAO))
    try:
        servidor = ThreadingHTTPServer((host_final, porta_final), _ManipuladorAPI)
    except OSError as erro:
        print(f"⚠️ API Flutter indisponível em {host_final}:{porta_final} ({erro}). O motor segue sem a ponte.")
        return None

    threading.Thread(target=servidor.serve_forever, name="iafit-api", daemon=True).start()
    aviso_token = "com token" if os.environ.get("IAFIT_API_TOKEN") else "sem token"
    porta_real = servidor.server_address[1]
    print(f"🔌 Ponte Flutter ativa em http://{host_final}:{porta_real} ({aviso_token})")
    return servidor
