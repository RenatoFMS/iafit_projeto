import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Evita inicializar o Firebase duas vezes e causar erros
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def salvar_treino(exercicio, repeticoes, erros_postura=0, calorias=0.0):
    """Envia os dados finais do exercício para o banco de dados"""
    try:
        dados = {
            'exercicio': exercicio,
            'repeticoes': repeticoes,
            'erros_postura': erros_postura,
            'calorias': round(calorias, 2) if calorias is not None else 0.0,
            'data': firestore.SERVER_TIMESTAMP
        }
        doc_ref = db.collection('treinos').document()
        doc_ref.set(dados)
        print(f"\n✅ SUCESSO: Treino de {exercicio} guardado na Nuvem ({repeticoes} reps | {calorias:.1f} kcal)!\n")
    except Exception as e:
        print(f"\n❌ ERRO ao guardar na Nuvem: {e}\n")

