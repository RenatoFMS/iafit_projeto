import os
import threading
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from core.ponte_flutter import registrar_treino

_RAIZ_PROJETO: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CAMINHO_CHAVE: str = (
    "firebase_key.json"
    if os.path.exists("firebase_key.json")
    else os.path.join(_RAIZ_PROJETO, "firebase_key.json")
)

db: Any = None
try:
    if not firebase_admin._apps and os.path.exists(_CAMINHO_CHAVE):
        cred = credentials.Certificate(_CAMINHO_CHAVE)
        firebase_admin.initialize_app(cred)
    if firebase_admin._apps:
        db = firestore.client()
except Exception as erro_fb:
    print(f"⚠️ Firebase indisponível ({erro_fb}). Treinos serão guardados localmente.")


def salvar_treino(
    exercicio: str,
    repeticoes: int,
    erros_postura: int = 0,
    calorias: float = 0.0,
    duracao_seg: int = 0,
    exercicio_id: Optional[str] = None,
    isometrico: bool = False,
) -> None:
    """Envia os dados finais do exercício para o banco de dados.

    O treino é gravado primeiro no ficheiro local lido pela ponte com o app
    Flutter (assim o histórico do app não depende da ligação à nuvem) e depois
    no Firebase Firestore.

    Args:
        exercicio: Nome oficial do exercício no catálogo.
        repeticoes: Repetições concluídas ou segundos (exercícios isométricos).
        erros_postura: Quantidade de desvios posturais detetados na série.
        calorias: Gasto energético estimado em kcal.
        duracao_seg: Duração da série em segundos.
        exercicio_id: Chave do exercício no catálogo (ex.: "3").
        isometrico: True quando 'repeticoes' representa segundos.
    """
    dados: Dict[str, Any] = {
        'exercicio': exercicio,
        'repeticoes': repeticoes,
        'erros_postura': erros_postura,
        'calorias': round(calorias, 2) if calorias is not None else 0.0,
        'duracao_seg': int(duracao_seg),
        'exercicio_id': exercicio_id,
        'isometrico': bool(isometrico),
    }

    try:
        registrar_treino(dados)
    except Exception as e:
        print(f"\n⚠️ AVISO: não foi possível guardar o treino para o app Flutter: {e}\n")

    if db is None:
        return

    def _enviar_firestore() -> None:
        try:
            doc_ref = db.collection('treinos').document()
            doc_ref.set({**dados, 'data': firestore.SERVER_TIMESTAMP})
            print(f"\n✅ SUCESSO: Treino de {exercicio} guardado na Nuvem ({repeticoes} reps | {calorias:.1f} kcal)!\n")
        except Exception as e:
            print(f"\n❌ ERRO ao guardar na Nuvem: {e}\n")

    threading.Thread(target=_enviar_firestore, name="iafit-firestore", daemon=True).start()
