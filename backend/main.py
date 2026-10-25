"""Servidor de API Matemática e Biomecânica do IAFit (Edge Computing + Cloud Backend).

Recebe os 33 pontos articulares extraídos na borda (Flutter + Google ML Kit Pose)
através do endpoint ``POST /analisar_pose``, executa os cálculos trigonométricos 3D,
atualiza os contadores de repetições, isometria, fadiga e erros de postura, e
persiste as séries concluídas no Firebase Firestore e no histórico local para o SQLite.
"""

import os
import signal
import threading
import time
from typing import Any, Dict, List, Optional

# Garante que caminhos relativos (firebase_key.json, treinos_locais.jsonl, áudios)
# funcionem mesmo quando iniciado a partir de mobile/ (../backend/venv/bin/python ../backend/main.py).
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from core.analise_biomecanica import (
    calcular_calorias,
    landmarks_mediapipe_para_keypoints,
)
from core.config_exercicios import EXERCICIOS
from core.firebase_client import salvar_treino
from core.math_utils import (
    ContadorRepeticoes,
    CronometroIsometrico,
    FiltroSuavizacao,
)
from core.motor_ia import processar_exercicio, resetar_cooldown_voz
from core.ponte_flutter import (
    atualizar_estado,
    consumir_comando,
    iniciar_servidor,
    registrar_finalizador_serie,
    registrar_processador_pose,
)
from core.voz_client import falar

_PID_PAI: int = int(os.environ.get("IAFIT_PARENT_PID", "0") or "0")
executando: bool = True

_lock_sessao = threading.Lock()
id_atual: str = "1"

filtros_memoria: Dict[str, Any] = {
    "amplitude": {"esq": FiltroSuavizacao(5), "dir": FiltroSuavizacao(5)},
    "postura": {"esq": FiltroSuavizacao(5), "dir": FiltroSuavizacao(5)},
    "repeticoes": {"total": ContadorRepeticoes()},
    "isometrico": {"total": CronometroIsometrico()},
}

# Contagem de erros de postura da série em curso (ocorrências por transição)
erros_serie: int = 0
em_erro_anterior: bool = False


def _eh_exercicio_isometrico(id_ex: str, config: Dict[str, Any]) -> bool:
    """Indica se o exercício é medido em segundos de isometria.

    Args:
        id_ex: Identificador do exercício no catálogo.
        config: Dicionário de configuração do exercício.

    Returns:
        True se o exercício for isométrico, False caso contrário.
    """
    return id_ex in ("8", "22", "29") or config.get("tipo") == "isometrico"


def _processo_pai_ativo() -> bool:
    """Verifica se o processo pai do app Flutter (quando informado) segue em execução.

    Returns:
        True se não há PID monitorizado ou se o processo pai ainda existe.
    """
    if _PID_PAI <= 0:
        return True
    try:
        os.kill(_PID_PAI, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _solicitar_encerramento(_signum: int, _frame: Any) -> None:
    """Trata sinais SIGINT/SIGTERM para encerrar o servidor guardando a série ativa."""
    global executando
    executando = False


def resetar_erros_serie() -> None:
    """Zera o contador de erros de postura da série em curso."""
    global erros_serie, em_erro_anterior
    erros_serie = 0
    em_erro_anterior = False


def frame_tem_erro_postura(resultados: List[Dict[str, Any]]) -> bool:
    """Indica se algum resultado do frame representa um erro de postura.

    Mesma regra usada pelo testador_lote.py: ignora frames fora de enquadramento
    ou em calibração e considera erro o feedback 'ERRO:', a cor vermelha ou
    'postura_correta' falso.

    Args:
        resultados: Lista de resultados devolvida por processar_exercicio.

    Returns:
        True se houver erro de postura no frame.
    """
    for res in resultados:
        if res.get("fora_enquadramento") or res.get("fase") == "calibracao":
            continue
        if (
            str(res.get("feedback", "")).startswith("ERRO:")
            or res.get("cor") == (0, 0, 255)
            or (res.get("postura_correta") is False and "postura_correta" in res)
        ):
            return True
    return False


def resetar_filtros() -> None:
    """Reinicia o histórico de todos os filtros de memória e os cooldowns de áudio."""
    for cat in filtros_memoria.values():
        if isinstance(cat, dict):
            for filtro in cat.values():
                if hasattr(filtro, "limpar"):
                    filtro.limpar()
        elif hasattr(cat, "limpar"):
            cat.limpar()
    resetar_cooldown_voz()
    resetar_erros_serie()


def guardar_treino_atual() -> None:
    """Envia o exercício atual e as suas repetições ou tempo para a nuvem e histórico local.

    Calcula a estimativa de gasto calórico a partir do MET do exercício
    e armazena os dados da série concluída no Firebase Firestore e em
    ``treinos_locais.jsonl``, junto com a duração, o ID do exercício e os erros de postura.
    """
    config = EXERCICIOS.get(id_atual, {})
    nome_ex = config.get("nome", "Exercício")
    met_ex = config.get("met", 3.0)
    if _eh_exercicio_isometrico(id_atual, config):
        segundos = filtros_memoria["isometrico"]["total"].segundos
        if segundos > 0:
            calorias = calcular_calorias(segundos, met_ex)
            print(f"Série concluída: {segundos}s | Gasto estimado: {calorias:.1f} kcal")
            salvar_treino(
                nome_ex,
                segundos,
                erros_postura=erros_serie,
                calorias=calorias,
                duracao_seg=segundos,
                exercicio_id=id_atual,
                isometrico=True,
            )
    else:
        contador = filtros_memoria["repeticoes"]["total"]
        reps = contador.reps
        if reps > 0:
            agora = time.time()
            tempo_inicio = (
                contador.tempo_inicio_serie
                if contador.tempo_inicio_serie is not None
                else contador.tempo_ultima_rep
            )
            tempo_serie = max(0.0, agora - tempo_inicio)
            calorias = calcular_calorias(tempo_serie, met_ex)
            print(f"Série concluída: {reps} reps | Gasto estimado: {calorias:.1f} kcal")
            salvar_treino(
                nome_ex,
                reps,
                erros_postura=erros_serie,
                calorias=calorias,
                duracao_seg=int(round(tempo_serie)),
                exercicio_id=id_atual,
                isometrico=False,
            )


def _selecionar_exercicio_interno(novo_id: str) -> None:
    """Troca o exercício ativo guardando a série anterior e reiniciando os filtros.

    Args:
        novo_id: Chave do exercício no dicionário EXERCICIOS.
    """
    global id_atual
    if novo_id in EXERCICIOS and novo_id != id_atual:
        guardar_treino_atual()
        id_atual = novo_id
        resetar_filtros()
        config_novo = EXERCICIOS[novo_id]
        atualizar_estado(
            exercicio_id=id_atual,
            exercicio=config_novo["nome"],
            repeticoes=0,
            segundos=0,
            erros_postura=0,
            fase="calibracao",
            estado="Calibração",
            feedback="",
            isometrico=_eh_exercicio_isometrico(id_atual, config_novo),
        )
        print(f"📲 App Flutter selecionou: {config_novo['nome']}")


def aplicar_comando_externo(comando: Dict[str, Any]) -> None:
    """Aplica um comando recebido do app Flutter através da ponte local.

    Args:
        comando: Dicionário com 'acao' e, para 'selecionar', o 'id' do exercício.
    """
    acao = comando.get("acao")
    with _lock_sessao:
        if acao == "selecionar":
            novo_id = str(comando.get("id", "")).strip()
            _selecionar_exercicio_interno(novo_id)
        elif acao == "finalizar":
            guardar_treino_atual()
            resetar_filtros()
            print("📲 App Flutter finalizou a série.")


def processar_comandos_pendentes() -> None:
    """Consome e aplica todos os comandos pendentes enviados pelo app Flutter."""
    comando_externo = consumir_comando()
    while comando_externo is not None:
        aplicar_comando_externo(comando_externo)
        comando_externo = consumir_comando()


def verificar_timeout_inatividade() -> None:
    """Encerra e guarda automaticamente a série após 6 segundos de inatividade."""
    with _lock_sessao:
        config_atual = EXERCICIOS.get(id_atual, {})
        if _eh_exercicio_isometrico(id_atual, config_atual):
            cronometro = filtros_memoria["isometrico"]["total"]
            if cronometro.segundos > 0 and (time.time() - cronometro.tempo_ultima_atividade) > 6.0:
                segundos_feitos = cronometro.segundos
                met_ex = config_atual.get("met", 3.5)
                calorias = calcular_calorias(segundos_feitos, met_ex)
                cronometro.limpar()
                falar("Série concluída")
                print(f"Série concluída: {segundos_feitos}s | Gasto estimado: {calorias:.1f} kcal")
                salvar_treino(
                    config_atual.get("nome", "Exercício"),
                    segundos_feitos,
                    erros_postura=erros_serie,
                    calorias=calorias,
                    duracao_seg=segundos_feitos,
                    exercicio_id=id_atual,
                    isometrico=True,
                )
                resetar_erros_serie()
        else:
            contador = filtros_memoria["repeticoes"]["total"]
            if contador.reps > 0 and (time.time() - contador.tempo_ultima_rep) > 6.0:
                reps_feitas = contador.reps
                agora = time.time()
                tempo_inicio = (
                    contador.tempo_inicio_serie
                    if contador.tempo_inicio_serie is not None
                    else contador.tempo_ultima_rep
                )
                tempo_serie = max(0.0, agora - tempo_inicio)
                met_ex = config_atual.get("met", 3.0)
                calorias = calcular_calorias(tempo_serie, met_ex)
                contador.reps = 0
                contador.tempo_ultima_rep = agora
                contador.tempo_inicio_serie = None
                falar("Série concluída")
                print(f"Série concluída: {reps_feitas} reps | Gasto estimado: {calorias:.1f} kcal")
                salvar_treino(
                    config_atual.get("nome", "Exercício"),
                    reps_feitas,
                    erros_postura=erros_serie,
                    calorias=calorias,
                    duracao_seg=int(round(tempo_serie)),
                    exercicio_id=id_atual,
                    isometrico=False,
                )
                resetar_erros_serie()


def analisar_pose_recebida(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula ângulos, repetições e postura a partir dos 33 landmarks enviados pelo Flutter.

    Ignora qualquer captura de câmara ou inferência MediaPipe no servidor, operando
    exclusivamente sobre os pontos articulares extraídos pelo ML Kit no dispositivo.

    Args:
        payload: Dicionário contendo ``id_exercicio`` e ``landmarks`` (33 pontos
            com ``x``, ``y``, ``z`` e ``visibilidade``/``visibility``).

    Returns:
        Dicionário estruturado com repetições, segundos, fase, feedback, ângulo e erros.
    """
    global id_atual, erros_serie, em_erro_anterior

    processar_comandos_pendentes()

    with _lock_sessao:
        id_req = str(
            payload.get("id_exercicio")
            or payload.get("exercicio_id")
            or payload.get("id")
            or id_atual
        ).strip()
        if id_req in EXERCICIOS and id_req != id_atual:
            _selecionar_exercicio_interno(id_req)

        config_atual = EXERCICIOS.get(id_atual)
        if not config_atual:
            id_atual = "1"
            config_atual = EXERCICIOS["1"]

        nome_exercicio = config_atual["nome"]
        isometrico_atual = _eh_exercicio_isometrico(id_atual, config_atual)

        landmarks_brutos = payload.get("landmarks", payload.get("pontos"))
        largura_frame: Optional[int] = None
        altura_frame: Optional[int] = None
        if isinstance(payload.get("largura"), (int, float)) and isinstance(
            payload.get("altura"), (int, float)
        ):
            largura_frame = int(payload["largura"])
            altura_frame = int(payload["altura"])

        pontos_convertidos: Any = None
        if landmarks_brutos:
            if largura_frame and altura_frame:
                pontos_convertidos = landmarks_mediapipe_para_keypoints(
                    landmarks_brutos, largura=largura_frame, altura=altura_frame
                )
            else:
                pontos_convertidos = landmarks_brutos

        resultados_ativos = processar_exercicio(
            pontos_convertidos, config_atual, filtros_memoria
        )

        tem_erro_frame = frame_tem_erro_postura(resultados_ativos)
        if tem_erro_frame and not em_erro_anterior:
            erros_serie += 1
        em_erro_anterior = tem_erro_frame

        eh_fora = len(resultados_ativos) == 0 or any(
            res.get("fora_enquadramento", False) for res in resultados_ativos
        )

        res_principal = resultados_ativos[0] if resultados_ativos else {}
        reps_atuais = int(filtros_memoria["repeticoes"]["total"].reps)
        segundos_atuais = int(filtros_memoria["isometrico"]["total"].segundos)
        fase_final = (
            "pausado"
            if eh_fora
            else str(res_principal.get("fase", "base"))
        )
        feedback_final = (
            "FORA DE ENQUADRAMENTO"
            if eh_fora
            else str(res_principal.get("feedback", ""))
        )
        estado_final = (
            "Fora"
            if eh_fora
            else str(res_principal.get("estado", "Treinando"))
        )
        porc_atual = 0 if eh_fora else int(res_principal.get("porc", 0))
        angulo_atual = None if eh_fora else res_principal.get("angulo")
        alerta_assimetria = bool(
            not eh_fora and any(r.get("alerta_assimetria", False) for r in resultados_ativos)
        )
        fadiga_detectada = bool(
            not eh_fora and any(r.get("fadiga_detectada", False) for r in resultados_ativos)
        )

        resposta: Dict[str, Any] = {
            "ok": True,
            "id_exercicio": id_atual,
            "exercicio_id": id_atual,
            "exercicio": nome_exercicio,
            "repeticoes": reps_atuais,
            "segundos": segundos_atuais,
            "erros_postura": erros_serie,
            "porc": porc_atual,
            "angulo": angulo_atual,
            "fase": fase_final,
            "estado": estado_final,
            "feedback": feedback_final,
            "isometrico": isometrico_atual,
            "alerta_assimetria": alerta_assimetria,
            "fadiga_detectada": fadiga_detectada,
            "postura_correta": not tem_erro_frame,
            "fora_enquadramento": eh_fora,
        }

        atualizar_estado(**resposta)
        return resposta


def finalizar_serie_sincrona(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Persiste sincronicamente a série em curso no Firebase e no histórico local.

    Se o dispositivo móvel enviou contagens calculadas na borda (ML Kit) no corpo do
    pedido ``POST /finalizar`` e o contador em memória ainda estava a zero, utiliza
    esses valores como fallback para garantir a gravação no SQLite e no Firebase.

    Args:
        payload: Dicionário opcional com ``id_exercicio``, ``repeticoes``,
            ``duracao_seg`` e ``erros_postura``.

    Returns:
        Dicionário de confirmação para a resposta HTTP 202.
    """
    global id_atual
    dados = payload if isinstance(payload, dict) else {}
    processar_comandos_pendentes()

    with _lock_sessao:
        id_req = str(
            dados.get("id_exercicio")
            or dados.get("exercicio_id")
            or dados.get("id")
            or ""
        ).strip()
        if id_req in EXERCICIOS and id_req != id_atual:
            _selecionar_exercicio_interno(id_req)

        config = EXERCICIOS.get(id_atual, {})
        eh_iso = _eh_exercicio_isometrico(id_atual, config)
        valor_servidor = (
            int(filtros_memoria["isometrico"]["total"].segundos)
            if eh_iso
            else int(filtros_memoria["repeticoes"]["total"].reps)
        )

        if valor_servidor > 0:
            guardar_treino_atual()
        else:
            reps_borda = dados.get("repeticoes")
            if isinstance(reps_borda, (int, float)) and int(reps_borda) > 0:
                valor_borda = int(reps_borda)
                duracao_borda = dados.get("duracao_seg")
                duracao_final = (
                    max(1, int(duracao_borda))
                    if isinstance(duracao_borda, (int, float)) and int(duracao_borda) > 0
                    else (valor_borda if eh_iso else max(5, valor_borda * 3))
                )
                erros_borda = (
                    max(0, int(dados["erros_postura"]))
                    if isinstance(dados.get("erros_postura"), (int, float))
                    else erros_serie
                )
                met_ex = config.get("met", 3.5 if eh_iso else 3.0)
                calorias = calcular_calorias(duracao_final, met_ex)
                salvar_treino(
                    config.get("nome", "Exercício"),
                    valor_borda,
                    erros_postura=erros_borda,
                    calorias=calorias,
                    duracao_seg=duracao_final,
                    exercicio_id=id_atual,
                    isometrico=eh_iso,
                )

        resetar_filtros()
        atualizar_estado(
            exercicio_id=id_atual,
            exercicio=config.get("nome", "Exercício"),
            repeticoes=0,
            segundos=0,
            erros_postura=0,
            porc=0,
            angulo=None,
            fase="base",
            estado="Concluído",
            feedback="Série concluída!",
            isometrico=eh_iso,
        )
        print("📲 App Flutter finalizou a série.")
        return {"id_exercicio": id_atual}


registrar_processador_pose(analisar_pose_recebida)
registrar_finalizador_serie(finalizar_serie_sincrona)


def iniciar_motor_api() -> None:
    """Inicia o servidor HTTP da API matemática e mantém o ciclo de gestão de sessão."""
    signal.signal(signal.SIGTERM, _solicitar_encerramento)
    signal.signal(signal.SIGINT, _solicitar_encerramento)

    iniciar_servidor()
    config_inicial = EXERCICIOS.get(id_atual, EXERCICIOS["1"])
    atualizar_estado(
        exercicio_id=id_atual,
        exercicio=config_inicial["nome"],
        repeticoes=0,
        segundos=0,
        erros_postura=0,
        porc=0,
        angulo=None,
        fase="calibracao",
        estado="Calibração",
        feedback="Aguardando pontos articulares do ML Kit...",
        isometrico=_eh_exercicio_isometrico(id_atual, config_inicial),
    )

    print("🚀 Motor Matemático IAFit ativo (Edge Computing + API POST /analisar_pose)")
    ultimo_check_pai = time.time()

    while executando:
        if (time.time() - ultimo_check_pai) > 2.0:
            ultimo_check_pai = time.time()
            if not _processo_pai_ativo():
                print("🛑 App Flutter encerrado. Finalizando motor IAFit...")
                break

        processar_comandos_pendentes()
        verificar_timeout_inatividade()
        time.sleep(0.2)

    with _lock_sessao:
        guardar_treino_atual()


if __name__ == "__main__":
    iniciar_motor_api()
