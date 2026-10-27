"""Suíte Completa de Testes Unitários e de Integração Biomecânica do IAFit (pytest).

Valida de ponta a ponta os módulos nucleares do motor matemático:
    - ``core/analise_biomecanica.py`` (conversão ML Kit 33 -> COCO 17, trigonometria 3D,
      amplitude concêntrica/excêntrica, regras posturais, assimetria, fadiga e MET);
    - ``core/config_exercicios.py`` (integridade contratual dos 30 exercícios parametrizados);
    - ``core/math_utils.py`` e ``core/motor_ia.py`` (máquina de estados finitos das fases
      ``base -> subida -> topo -> descida -> base`` e filtragem temporal).

Os dados simulados (*Mock Data*) reproduzem fielmente o payload de 33 landmarks espaciais
``[x, y, z, visibilidade]`` (e dicionários JSON equivalentes) extraídos em tempo real pelo
Google ML Kit Pose Detection no aplicativo Flutter, cobrindo os 4 cenários críticos:
    1. Repouso absoluto (estabilidade na base sem falsos positivos);
    2. Meia repetição (amplitude insuficiente < 90% não deve incrementar o contador);
    3. Repetição completa e perfeita (ciclo concêntrico + excêntrico íntegro e postura segura);
    4. Repetição com erro de postura (compensações articulares/axiais detetadas em tempo real).
"""

import math
import os
import sys
from typing import Any, Dict, List, Tuple

import pytest

# Garante resolução dos pacotes internos independentemente do diretório de invocação do pytest
_DIRETORIO_BACKEND = os.path.dirname(os.path.abspath(__file__))
if _DIRETORIO_BACKEND not in sys.path:
    sys.path.insert(0, _DIRETORIO_BACKEND)

import core.math_utils as math_utils
import core.motor_ia as motor_ia
from core.analise_biomecanica import (
    analisar_seguranca_postura,
    calcular_amplitude_movimento,
    calcular_assimetria,
    calcular_calorias,
    landmarks_mediapipe_para_keypoints,
    selecionar_melhor_lado,
    verificar_assimetria_bracos,
    verificar_fadiga,
    verificar_fora_enquadramento,
)
from core.config_exercicios import EXERCICIOS
from core.math_utils import (
    ContadorRepeticoes,
    CronometroIsometrico,
    FiltroSuavizacao,
    calcular_angulo,
    calcular_porcentagem,
)
from core.motor_ia import obter_calibrador, processar_exercicio

# Escala métrica padrão utilizada por landmarks_mediapipe_para_keypoints para coordenadas [0, 1]
_LARGURA_REF: float = 640.0
_ALTURA_REF: float = 480.0


# ==============================================================================
# GERADORES TRIGONOMÉTRICOS DE MOCK DATA (33 LANDMARKS GOOGLE ML KIT X, Y, Z)
# ==============================================================================

def _criar_esqueleto_base_mlkit(visibilidade: float = 0.98) -> List[List[float]]:
    """Cria um array base de 33 landmarks ML Kit ``[x, y, z, visibilidade]`` normalizados.

    Todos os pontos iniciam dentro do quadro válido ``[0.0, 1.0]`` com alta confiança óptica,
    permitindo que os geradores específicos posicionem com exatidão trigonométrica as cadeias
    cinéticas de membros superiores, tronco e membros inferiores.

    Args:
        visibilidade: Índice de confiança padrão atribuído aos 33 marcos anatômicos.

    Returns:
        Lista mutável de 33 listas ``[x_norm, y_norm, z_norm, visibilidade]``.
    """
    landmarks: List[List[float]] = [
        [0.50, 0.50, 0.00, visibilidade] for _ in range(33)
    ]
    # Cabeça / Rosto (Nariz=0, Olhos=2,5, Orelhas=7,8) no terço superior do enquadramento
    landmarks[0] = [320.0 / _LARGURA_REF, 110.0 / _ALTURA_REF, 0.0, visibilidade]
    landmarks[2] = [325.0 / _LARGURA_REF, 105.0 / _ALTURA_REF, 0.0, visibilidade]
    landmarks[5] = [315.0 / _LARGURA_REF, 105.0 / _ALTURA_REF, 0.0, visibilidade]
    landmarks[7] = [330.0 / _LARGURA_REF, 108.0 / _ALTURA_REF, 0.0, visibilidade]
    landmarks[8] = [310.0 / _LARGURA_REF, 108.0 / _ALTURA_REF, 0.0, visibilidade]
    return landmarks


def _definir_ponto_px(
    landmarks: List[List[float]],
    indice_mp: int,
    x_px: float,
    y_px: float,
    z_px: float = 0.0,
    visibilidade: float = 0.98,
) -> None:
    """Converte coordenadas métricas em pixels ``(640x480)`` para o espaço normalizado ML Kit."""
    landmarks[indice_mp] = [
        x_px / _LARGURA_REF,
        y_px / _ALTURA_REF,
        z_px / _LARGURA_REF,
        visibilidade,
    ]


def gerar_mock_mlkit_rosca_biceps(
    angulo_cotovelo_esq: float,
    angulo_avanco_umero_graus: float = 10.0,
    angulo_cotovelo_dir: float | None = None,
    angulo_rotacao_z_graus: float = 0.0,
    visibilidade: float = 0.98,
) -> List[List[float]]:
    """Sintetiza 33 landmarks ML Kit ``[x, y, z, vis]`` para o exercício Rosca Bíceps (ID ``"1"``).

    Constrói uma base ortonormal no espaço euclidiano 3D para posicionar Quadril, Ombro,
    Cotovelo e Pulso de modo que:
        - O ângulo ``Quadril–Ombro–Cotovelo`` (regra postural de cotovelo fixo ao tronco) seja
          exatamente ``angulo_avanco_umero_graus``;
        - O ângulo ``Ombro–Cotovelo–Pulso`` (articulação agonista da fase concêntrica/excêntrica)
          seja exatamente ``angulo_cotovelo_esq`` (e ``angulo_cotovelo_dir`` no braço oposto);
        - Opcionalmente rotaciona todo o corpo em torno do eixo vertical ``Y`` por
          ``angulo_rotacao_z_graus``, introduzindo profundidade ``Z`` real para testar a
          invariância espacial 3D do cálculo vetorial.

    Args:
        angulo_cotovelo_esq: Ângulo alvo do cotovelo esquerdo em graus (``160°`` base -> ``40°`` topo).
        angulo_avanco_umero_graus: Ângulo ``Quadril–Ombro–Cotovelo`` em graus (seguro ``<= 35°``).
        angulo_cotovelo_dir: Ângulo do cotovelo direito (se ``None``, espelha o esquerdo).
        angulo_rotacao_z_graus: Rotação oblíqua da câmara no plano ``XZ`` em graus.
        visibilidade: Confiança óptica dos pontos gerados.

    Returns:
        Matriz de 33 pontos ``[x, y, z, visibilidade]`` normalizados no padrão Google ML Kit.
    """
    if angulo_cotovelo_dir is None:
        angulo_cotovelo_dir = angulo_cotovelo_esq

    landmarks = _criar_esqueleto_base_mlkit(visibilidade=visibilidade)

    ox, oy = 320.0, 170.0   # Posição do Ombro no plano métrico 640x480
    qx, qy = 320.0, 310.0   # Quadril alinhado verticalmente abaixo do Ombro
    comp_umero = 85.0
    comp_antebraco = 80.0

    alfa = math.radians(angulo_avanco_umero_graus)
    rot_z = math.radians(angulo_rotacao_z_graus)

    def _rotacionar_y(dx: float, dy: float) -> Tuple[float, float, float]:
        """Aplica rotação 3D em torno do eixo vertical Y preservando comprimentos e ângulos."""
        rx = dx * math.cos(rot_z)
        rz = dx * math.sin(rot_z)
        return rx, dy, rz

    def _calcular_cadeia_braco(ang_cot: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        # Vetor Ombro -> Cotovelo inclinado por alfa em relação ao eixo tronco (Ombro -> Quadril)
        ux = comp_umero * math.sin(alfa)
        uy = comp_umero * math.cos(alfa)

        # Base ortonormal centrada no Cotovelo:
        # e1 aponta de volta para o Ombro; e2 é ortogonal no sentido anatômico da flexão
        e1x, e1y = -math.sin(alfa), -math.cos(alfa)
        e2x, e2y = math.cos(alfa), -math.sin(alfa)

        beta = math.radians(ang_cot)
        ax = comp_antebraco * (math.cos(beta) * e1x + math.sin(beta) * e2x)
        ay = comp_antebraco * (math.cos(beta) * e1y + math.sin(beta) * e2y)

        cx_rel, cy_rel, cz_rel = _rotacionar_y(ux, uy)
        px_rel, py_rel, pz_rel = _rotacionar_y(ux + ax, uy + ay)
        return (ox + cx_rel, oy + cy_rel, cz_rel), (ox + px_rel, oy + py_rel, pz_rel)

    cot_esq, pul_esq = _calcular_cadeia_braco(angulo_cotovelo_esq)
    cot_dir, pul_dir = _calcular_cadeia_braco(angulo_cotovelo_dir)

    # Hemicorpo esquerdo (ligeiramente mais confiável para seleção determinística de lado)
    _definir_ponto_px(landmarks, 11, ox, oy, 0.0, visibilidade)
    _definir_ponto_px(landmarks, 23, qx, qy, 0.0, visibilidade)
    _definir_ponto_px(landmarks, 13, *cot_esq, visibilidade)
    _definir_ponto_px(landmarks, 15, *pul_esq, visibilidade)
    _definir_ponto_px(landmarks, 25, qx, 390.0, 0.0, visibilidade)
    _definir_ponto_px(landmarks, 27, qx, 455.0, 0.0, visibilidade)

    # Hemicorpo direito (Z deslocado em profundidade para separar os membros em 3D)
    vis_dir = max(0.0, visibilidade - 0.03)
    _definir_ponto_px(landmarks, 12, ox, oy, 30.0, vis_dir)
    _definir_ponto_px(landmarks, 24, qx, qy, 30.0, vis_dir)
    _definir_ponto_px(landmarks, 14, cot_dir[0], cot_dir[1], cot_dir[2] + 30.0, vis_dir)
    _definir_ponto_px(landmarks, 16, pul_dir[0], pul_dir[1], pul_dir[2] + 30.0, vis_dir)
    _definir_ponto_px(landmarks, 26, qx, 390.0, 30.0, vis_dir)
    _definir_ponto_px(landmarks, 28, qx, 455.0, 30.0, vis_dir)

    return landmarks


def gerar_mock_mlkit_agachamento(
    angulo_joelho_graus: float,
    inclinacao_tronco_graus: float = 15.0,
    visibilidade: float = 0.98,
) -> List[Dict[str, float]]:
    """Sintetiza 33 landmarks ML Kit em formato dicionário JSON para o Agachamento (ID ``"2"``).

    Exercita simultaneamente o parser de dicionários JSON (idêntico ao payload HTTP enviado
    pelo ``EngineService`` do Flutter) e o cálculo axial vertical (``postura_vertical=True``):
        - O ângulo ``Quadril–Joelho–Tornozelo`` vale exatamente ``angulo_joelho_graus``
          (``170°`` em pé -> ``80°`` agachamento profundo);
        - O ângulo ``Ombro–Quadril–Vertical`` vale exatamente ``inclinacao_tronco_graus``
          (seguro ``<= 45°``, erro postural se ``> 45°``).

    Args:
        angulo_joelho_graus: Ângulo interno do joelho em graus.
        inclinacao_tronco_graus: Inclinação anterior do tronco face ao eixo vertical em graus.
        visibilidade: Grau de confiança atribuído aos pontos.

    Returns:
        Lista de 33 dicionários ``{"x": ..., "y": ..., "z": ..., "visibilidade": ...}``.
    """
    raw = _criar_esqueleto_base_mlkit(visibilidade=visibilidade)

    jx, jy = 330.0, 335.0   # Joelho como pivô central da cadeia inferior
    tx, ty = 330.0, 430.0   # Tornozelo verticalmente abaixo do joelho (vetor e1 = (0, +1))
    comp_coxa = 95.0
    comp_tronco = 105.0

    # Posiciona o Quadril a partir do Joelho formando exatamente angulo_joelho_graus
    gama = math.radians(angulo_joelho_graus)
    qx = jx - comp_coxa * math.sin(gama)
    qy = jy + comp_coxa * math.cos(gama)

    # Posiciona o Ombro a partir do Quadril formando exatamente inclinacao_tronco_graus com a vertical
    teta = math.radians(inclinacao_tronco_graus)
    ox = qx + comp_tronco * math.sin(teta)
    oy = qy - comp_tronco * math.cos(teta)

    # Braços à frente para equilíbrio natural
    cx, cy = ox + 45.0, oy + 35.0
    px, py = cx + 40.0, cy - 10.0

    _definir_ponto_px(raw, 11, ox, oy, 0.0, visibilidade)
    _definir_ponto_px(raw, 13, cx, cy, 0.0, visibilidade)
    _definir_ponto_px(raw, 15, px, py, 0.0, visibilidade)
    _definir_ponto_px(raw, 23, qx, qy, 0.0, visibilidade)
    _definir_ponto_px(raw, 25, jx, jy, 0.0, visibilidade)
    _definir_ponto_px(raw, 27, tx, ty, 0.0, visibilidade)

    vis_dir = max(0.0, visibilidade - 0.04)
    _definir_ponto_px(raw, 12, ox, oy, 25.0, vis_dir)
    _definir_ponto_px(raw, 14, cx, cy, 25.0, vis_dir)
    _definir_ponto_px(raw, 16, px, py, 25.0, vis_dir)
    _definir_ponto_px(raw, 24, qx, qy, 25.0, vis_dir)
    _definir_ponto_px(raw, 26, jx, jy, 25.0, vis_dir)
    _definir_ponto_px(raw, 28, tx, ty, 25.0, vis_dir)

    return [
        {"x": pt[0], "y": pt[1], "z": pt[2], "visibilidade": pt[3]}
        for pt in raw
    ]


# ==============================================================================
# FIXTURES PYTEST DE ISOLAMENTO E ESTADO LIMPO
# ==============================================================================

@pytest.fixture(autouse=True)
def silenciar_sintese_voz(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Intercepta chamadas de áudio (TTS) para testes rápidos, determinísticos e offline.

    Returns:
        Lista cronológica com todas as mensagens de voz emitidas durante o teste.
    """
    mensagens_emitidas: List[str] = []

    def _mock_falar(texto: str) -> None:
        mensagens_emitidas.append(texto)

    monkeypatch.setattr(math_utils, "falar", _mock_falar)
    monkeypatch.setattr(motor_ia, "falar", _mock_falar)
    motor_ia.resetar_cooldown_voz()
    return mensagens_emitidas


@pytest.fixture
def filtros_sessao_treinando() -> Dict[str, Any]:
    """Cria estrutura de filtros limpa já posicionada no estado ativo ``'Treinando'``.

    Utiliza janela unitária (``FiltroSuavizacao(1)``) por padrão para permitir verificação
    algébrica exata quadro a quadro, sem mascarar erros nos testes unitários.
    """
    filtros: Dict[str, Any] = {
        "amplitude": {"esq": FiltroSuavizacao(1), "dir": FiltroSuavizacao(1)},
        "postura": {"esq": FiltroSuavizacao(1), "dir": FiltroSuavizacao(1)},
        "repeticoes": {"total": ContadorRepeticoes()},
        "isometrico": {"total": CronometroIsometrico()},
    }
    calibrador = obter_calibrador(filtros)
    calibrador.estado = "Treinando"
    return filtros


# ==============================================================================
# OS 4 CENÁRIOS CRÍTICOS DE VALIDAÇÃO BIOMECÂNICA
# ==============================================================================

class TestQuatroCenariosCriticos:
    """Valida os 4 cenários biomecânicos fundamentais exigidos para certificação do motor."""

    def test_cenario_1_repouso_absoluto(self, filtros_sessao_treinando: Dict[str, Any]) -> None:
        """Cenário 1: Atleta em repouso absoluto na base não deve acionar fases nem repetições.

        Simula 30 frames consecutivos na posição inicial anatômica da Rosca Bíceps (~165°,
        com micro-oscilações naturais de ±0.8° inferiores à histerese da máquina de estados)
        e do Agachamento (~175° em pé). Verifica estabilidade em ``fase == 'base'``,
        ``porc == 0``, ``reps == 0`` e ``postura_segura == True``.
        """
        config_rosca = EXERCICIOS["1"]  # Rosca Bíceps: inicio=160°, fim=40°

        for frame_idx in range(30):
            # Simula micro-ruído fisiológico/óptico (164.2° a 165.8° -> sempre acima de 160° => 0%)
            oscilacao = 0.8 * math.sin(frame_idx)
            landmarks = gerar_mock_mlkit_rosca_biceps(
                angulo_cotovelo_esq=165.0 + oscilacao,
                angulo_avanco_umero_graus=8.0,
            )
            resultado = processar_exercicio(landmarks, config_rosca, filtros_sessao_treinando)[0]

            assert resultado["estado"] == "Treinando"
            assert resultado["porc"] == 0
            assert resultado["fase"] == "base"
            assert resultado["reps"] == 0
            assert resultado["feedback"] == config_rosca["msg_inicio"]
            assert resultado["cor"] != (0, 0, 255), "Não deve acusar erro postural em repouso alinhado"
            assert resultado["alerta_assimetria"] is False

        # O cronômetro interno da série nem sequer deve ter sido disparado em repouso absoluto
        contador: ContadorRepeticoes = filtros_sessao_treinando["repeticoes"]["total"]
        assert contador.tempo_inicio_serie is None
        assert contador.reps == 0

    @pytest.mark.parametrize(
        "angulos_meia_rep,descricao",
        [
            # Sobe apenas até 100° (50% da amplitude 160°->40°) e retorna à base
            ([165.0, 140.0, 115.0, 100.0, 120.0, 145.0, 165.0], "50% de amplitude"),
            # Chega a 55° (87% da amplitude — muito perto, mas abaixo do limiar de topo de 90%!)
            ([165.0, 120.0, 80.0, 55.0, 85.0, 130.0, 165.0], "87% de amplitude (quase no topo)"),
        ],
    )
    def test_cenario_2_meia_repeticao_nao_deve_contar(
        self,
        filtros_sessao_treinando: Dict[str, Any],
        angulos_meia_rep: List[float],
        descricao: str,
    ) -> None:
        """Cenário 2: Meia repetição (amplitude < 90%) jamais deve incrementar o contador.

        Executa 3 ciclos consecutivos de execução parcial (fase concêntrica interrompida antes
        do ``limite_alto=90%`` seguida de fase excêntrica até à base ``0%``). Confirma que a
        máquina de estados transita por ``subida`` e ``descida``, nunca atinge ``topo`` e mantém
        ``reps == 0``.
        """
        config_rosca = EXERCICIOS["1"]
        fases_observadas: List[str] = []

        # Repete 3 meias-repetições seguidas para garantir ausência de acumulação indevida
        for _ in range(3):
            for angulo in angulos_meia_rep:
                landmarks = gerar_mock_mlkit_rosca_biceps(
                    angulo_cotovelo_esq=angulo,
                    angulo_avanco_umero_graus=10.0,
                )
                res = processar_exercicio(landmarks, config_rosca, filtros_sessao_treinando)[0]
                fases_observadas.append(res["fase"])
                assert res["porc"] < 90, f"Falha na parametrização de {descricao}"
                assert res["reps"] == 0, f"Meia repetição ({descricao}) foi contabilizada indevidamente!"

        assert "subida" in fases_observadas, "Deve detetar o início da fase concêntrica"
        assert "descida" in fases_observadas, "Deve detetar o retorno na fase excêntrica"
        assert "topo" not in fases_observadas, "Não pode atingir estado 'topo' em meia repetição"
        assert filtros_sessao_treinando["repeticoes"]["total"].reps == 0

    def test_cenario_3_repeticao_completa_perfeita(
        self,
        filtros_sessao_treinando: Dict[str, Any],
        silenciar_sintese_voz: List[str],
    ) -> None:
        """Cenário 3: Repetição completa e biomecanicamente perfeita na fase concêntrica e excêntrica.

        Simula uma trajetória contínua em 3D (com rotação oblíqua da câmara de 25° no eixo Z)
        cumprindo integralmente:
            - Base inicial (``165°`` -> ``0%``);
            - Fase concêntrica progressiva (``130°`` -> ``25%``, ``85°`` -> ``62%``);
            - Pico de contração no topo (``35°`` -> ``100%``);
            - Fase excêntrica controlada (``85°`` -> ``62%``, ``130°`` -> ``25%``);
            - Retorno completo à base (``165°`` -> ``0%``).
        Valida a sequência exata de estados, contagem ``reps == 1``, ausência total de alertas
        posturais e registo da cadência temporal.
        """
        config_rosca = EXERCICIOS["1"]
        trajetoria_perfeita = [165.0, 130.0, 85.0, 35.0, 85.0, 130.0, 165.0]
        historico_fases: List[str] = []
        historico_feedbacks: List[str] = []

        for angulo in trajetoria_perfeita:
            landmarks_3d = gerar_mock_mlkit_rosca_biceps(
                angulo_cotovelo_esq=angulo,
                angulo_avanco_umero_graus=12.0,  # <= 35° (cotovelo perfeitamente estabilizado)
                angulo_rotacao_z_graus=25.0,     # Perspectiva oblíqua 3D real (Z != 0)
            )
            res = processar_exercicio(landmarks_3d, config_rosca, filtros_sessao_treinando)[0]
            historico_fases.append(res["fase"])
            historico_feedbacks.append(res["feedback"])

            # Nenhum frame pode acusar erro postural ou assimetria
            assert not res["feedback"].startswith("ERRO:")
            assert res["cor"] != (0, 0, 255)
            assert res["alerta_assimetria"] is False

        # Verifica sequência canônica exata da Máquina de Estados Finitos
        assert historico_fases == [
            "base",     # 165° (0%)
            "subida",   # 130° (25% - fase concêntrica)
            "subida",   # 85°  (62% - fase concêntrica)
            "topo",     # 35°  (100% - contração máxima)
            "descida",  # 85°  (62% - fase excêntrica)
            "descida",  # 130° (25% - fase excêntrica)
            "base",     # 165° (0% - ciclo fechado -> +1 repetição!)
        ]

        contador: ContadorRepeticoes = filtros_sessao_treinando["repeticoes"]["total"]
        assert contador.reps == 1
        assert len(contador.tempos_repeticoes) == 1
        assert config_rosca["msg_fim"] in historico_feedbacks
        assert "1" in silenciar_sintese_voz

    def test_cenario_4_repeticao_com_erro_postura_rosca_e_agachamento(
        self,
        filtros_sessao_treinando: Dict[str, Any],
    ) -> None:
        """Cenário 4: Execução da repetição com compensação postural ("roubo") em 2 modalidades.

        Parte A — Erro Angular Relativo (Rosca Bíceps, ``postura_vertical=False``):
            Durante a fase concêntrica, o atleta projeta o cotovelo à frente do tronco
            (``Quadril–Ombro–Cotovelo = 52° > limite_postura 35°``).
        Parte B — Erro Axial Gravitacional (Agachamento, ``postura_vertical=True``):
            Ao descer até 75° no joelho, o atleta inclina excessivamente a coluna lombar
            (``Ombro–Quadril vs Vertical = 58° > limite_postura 45°``).

        Valida que ambos os desvios são imediatamente sinalizados com ``postura_segura=False``,
        mensagem ``ERRO: ...`` específica do catálogo e cor vermelha ``(0, 0, 255)``.
        """
        # --- PARTE A: Rosca Bíceps com avanço lesivo de cotovelo (52° > 35°) ---
        config_rosca = EXERCICIOS["1"]
        trajetoria_rosca_com_roubo = [
            (165.0, 10.0, True),   # Base alinhada
            (110.0, 22.0, True),   # Início da subida ainda dentro do limite (<= 35°)
            (40.0, 52.0, False),   # Topo roubando com ombro/cotovelo projetado à frente (> 35°)
            (105.0, 48.0, False),  # Descida mantendo compensação postural (> 35°)
            (165.0, 10.0, True),   # Retorno à base corrigindo postura
        ]

        erros_rosca = 0
        for ang_cot, ang_umero, esperado_seguro in trajetoria_rosca_com_roubo:
            lm_rosca = gerar_mock_mlkit_rosca_biceps(
                angulo_cotovelo_esq=ang_cot,
                angulo_avanco_umero_graus=ang_umero,
            )
            kps = landmarks_mediapipe_para_keypoints(lm_rosca)
            postura_ok, _, ang_postura = analisar_seguranca_postura(kps, config_rosca, "esq")
            assert postura_ok is esperado_seguro
            assert ang_postura == pytest.approx(ang_umero, abs=0.5)

            res = processar_exercicio(lm_rosca, config_rosca, filtros_sessao_treinando)[0]
            if not esperado_seguro:
                erros_rosca += 1
                assert res["feedback"] == config_rosca["msg_erro"]
                assert res["cor"] == (0, 0, 255)

        assert erros_rosca == 2

        # --- PARTE B: Agachamento com flexão excessiva do tronco à frente (58° > 45°) ---
        filtros_agachamento: Dict[str, Any] = {
            "amplitude": {"esq": FiltroSuavizacao(1), "dir": FiltroSuavizacao(1)},
            "postura": {"esq": FiltroSuavizacao(1), "dir": FiltroSuavizacao(1)},
            "repeticoes": {"total": ContadorRepeticoes()},
            "isometrico": {"total": CronometroIsometrico()},
        }
        obter_calibrador(filtros_agachamento).estado = "Treinando"
        config_agachamento = EXERCICIOS["2"]

        lm_agachamento_erro = gerar_mock_mlkit_agachamento(
            angulo_joelho_graus=75.0,        # Profundidade máxima atingida (100%)
            inclinacao_tronco_graus=58.0,    # Tronco muito inclinado (> 45°)
        )
        kps_agach = landmarks_mediapipe_para_keypoints(lm_agachamento_erro)
        postura_agach_ok, _, ang_tronco = analisar_seguranca_postura(
            kps_agach, config_agachamento, "esq"
        )
        assert postura_agach_ok is False
        assert ang_tronco == pytest.approx(58.0, abs=0.5)

        res_agach = processar_exercicio(
            lm_agachamento_erro, config_agachamento, filtros_agachamento
        )[0]
        assert res_agach["porc"] == 100
        assert res_agach["fase"] == "topo"
        assert res_agach["feedback"] == config_agachamento["msg_erro"]
        assert res_agach["cor"] == (0, 0, 255)


# ==============================================================================
# TESTES DE CONTRATO DO CATÁLOGO (config_exercicios.py) E UNIDADES MATEMÁTICAS
# ==============================================================================

class TestIntegridadeCatalogoEUnidades:
    """Garante a consistência estrutural de ``config_exercicios.py`` e funções auxiliares."""

    def test_contrato_todos_os_30_exercicios_config(self) -> None:
        """Valida que todos os 30 exercícios possuem esquema íntegro e índices COCO válidos."""
        assert len(EXERCICIOS) == 30, "O catálogo oficial do IAFit deve conter 30 exercícios"

        chaves_obrigatorias = {
            "nome",
            "met",
            "lados",
            "postura",
            "postura_vertical",
            "limite_postura",
            "regra_postura",
            "inicio",
            "fim",
            "msg_fim",
            "msg_inicio",
            "msg_erro",
            "msg_voz",
        }

        for ex_id, cfg in EXERCICIOS.items():
            assert ex_id.isdigit(), f"Chave inválida no catálogo: {ex_id}"
            faltantes = chaves_obrigatorias - set(cfg.keys())
            assert not faltantes, f"Exercício {ex_id} ({cfg.get('nome')}) sem chaves: {faltantes}"

            assert isinstance(cfg["nome"], str) and len(cfg["nome"]) > 0
            assert isinstance(cfg["met"], (int, float)) and cfg["met"] > 0
            assert cfg["regra_postura"] in {"<", ">"}
            assert set(cfg["lados"].keys()) == {"esq", "dir"}

            # Todos os índices articulares devem pertencer ao intervalo COCO [0..16]
            for lado, tripla in cfg["lados"].items():
                assert len(tripla) == 3, f"Exercício {ex_id} lado {lado} deve ter 3 índices"
                assert all(0 <= idx <= 16 for idx in tripla)

            for lado, indices_post in cfg["postura"].items():
                esperado_min = 2 if cfg["postura_vertical"] else 3
                assert len(indices_post) >= esperado_min
                assert all(0 <= idx <= 16 for idx in indices_post)

    def test_invariancia_trigonometrica_3d_sob_rotacao_camera(self) -> None:
        """Comprova que ``calcular_angulo`` em 3D preserva o ângulo exato mesmo sob rotação Z."""
        for rotacao_camera in (0.0, 20.0, 45.0, 65.0):
            lm = gerar_mock_mlkit_rosca_biceps(
                angulo_cotovelo_esq=72.5,
                angulo_avanco_umero_graus=15.0,
                angulo_rotacao_z_graus=rotacao_camera,
            )
            kps = landmarks_mediapipe_para_keypoints(lm)
            melhor_lado, _ = selecionar_melhor_lado(kps, EXERCICIOS["1"]["lados"])
            assert melhor_lado == "esq"

            _, angulo_medido, _ = calcular_amplitude_movimento(kps, EXERCICIOS["1"], "esq")
            assert angulo_medido == pytest.approx(72.5, abs=1e-4)

    def test_detecao_assimetria_bilateral_visual_e_sonora(self) -> None:
        """Valida os limiares de assimetria entre braços (> 15° visual e > 25° voz)."""
        # Diferença de 20° (60° vs 80°): aciona alerta visual (> 15°), mas não alerta de voz (<= 25°)
        lm_moderada = gerar_mock_mlkit_rosca_biceps(
            angulo_cotovelo_esq=60.0, angulo_cotovelo_dir=80.0
        )
        kps_mod = landmarks_mediapipe_para_keypoints(lm_moderada)
        ang_e, ang_d, alerta_visual = calcular_assimetria(kps_mod)
        alerta_voz, dif, _, _ = verificar_assimetria_bracos(kps_mod)
        alerta_voz_raw, _, _, _ = verificar_assimetria_bracos(lm_moderada)

        assert ang_e == pytest.approx(60.0, abs=0.2)
        assert ang_d == pytest.approx(80.0, abs=0.2)
        assert alerta_visual is True
        assert alerta_voz is False
        assert alerta_voz_raw is False
        assert dif == pytest.approx(20.0, abs=0.2)

        # Diferença de 35° (50° vs 85°): aciona tanto alerta visual quanto alerta de voz (> 25°)
        lm_severa = gerar_mock_mlkit_rosca_biceps(
            angulo_cotovelo_esq=50.0, angulo_cotovelo_dir=85.0
        )
        kps_sev = landmarks_mediapipe_para_keypoints(lm_severa)
        alerta_voz_sev, dif_sev, _, _ = verificar_assimetria_bracos(kps_sev)
        alerta_voz_sev_raw, _, _, _ = verificar_assimetria_bracos(lm_severa)
        assert alerta_voz_sev is True
        assert alerta_voz_sev_raw is True
        assert dif_sev == pytest.approx(35.0, abs=0.2)

    def test_fora_de_enquadramento_fadiga_e_calorias(self) -> None:
        """Testa cláusula de saída de enquadramento (< 0.3), equação MET e fadiga (> 1.6x)."""
        # 1. Fora de enquadramento quando visibilidade cai abaixo de 0.3
        lm_invisivel = gerar_mock_mlkit_rosca_biceps(angulo_cotovelo_esq=90.0, visibilidade=0.15)
        assert verificar_fora_enquadramento(lm_invisivel, EXERCICIOS["1"]) is True

        # 2. Equação fisiológica MET: 30 min (1800s) a MET=4.0 para atleta de 75 kg = 150.0 kcal
        assert calcular_calorias(tempo_segundos=1800.0, met=4.0, peso_kg=75.0) == 150.0
        assert calcular_calorias(tempo_segundos=0.0, met=4.0, peso_kg=75.0) == 0.0

        # 3. Deteção de fadiga por desaceleração concêntrica/excêntrica (> 1.6x ritmo basal)
        assert verificar_fadiga([2.0, 2.0, 2.0, 3.1]) is False  # 1.55x <= 1.6x (ritmo normal)
        assert verificar_fadiga([2.0, 2.0, 2.0, 3.4]) is True   # 1.70x > 1.6x (fadiga instalada)

    def test_normalizacao_porcentagem_ambos_sentidos(self) -> None:
        """Verifica ``calcular_porcentagem`` para exercícios decrescentes e crescentes."""
        # Sentido decrescente (ex.: Rosca Bíceps 160° -> 40°)
        assert calcular_porcentagem(170.0, 160.0, 40.0) == 0
        assert calcular_porcentagem(100.0, 160.0, 40.0) == 50
        assert calcular_porcentagem(35.0, 160.0, 40.0) == 100

        # Sentido crescente (ex.: Desenvolvimento de Ombros 70° -> 160°)
        assert calcular_porcentagem(60.0, 70.0, 160.0) == 0
        assert calcular_porcentagem(115.0, 70.0, 160.0) == 50
        assert calcular_porcentagem(165.0, 70.0, 160.0) == 100
        assert calcular_angulo((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)) == 0.0
