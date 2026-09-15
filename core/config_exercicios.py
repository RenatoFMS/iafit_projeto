# core/config_exercicios.py

EXERCICIOS = {
    "1": {
        "nome": "Rosca Biceps",
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 160, "fim": 40,
        "msg_fim": "Boa contracao! Desca.",
        "msg_inicio": "Estique o braco!"
    },
    "2": {
        "nome": "Agachamento",
        "lados": {"esq": (11, 13, 15), "dir": (12, 14, 16)},
        "postura": {"esq": (5, 11), "dir": (6, 12)}, 
        "postura_vertical": True, 
        "limite_postura": 45,     
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 170, "fim": 80, 
        "msg_fim": "Profundidade OK! Suba.",
        "msg_inicio": "Desca o quadril.",
        "msg_erro": "ERRO: Tronco muito inclinado!"
    },
    "3": {
        "nome": "Flexao de Braco",
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, 
        "postura": {"esq": (5, 11, 15), "dir": (6, 12, 16)}, # Prancha: Ombro, Quadril, Tornozelo
        "postura_vertical": False,
        "limite_postura": 140, # Abaixo de 140 graus, o quadril caiu
        "regra_postura": "<",
        "inicio": 160, "fim": 80,
        "msg_fim": "Empurre o chao!",
        "msg_inicio": "Desca o peito.",
        "msg_erro": "ERRO: Alinhe o quadril!"
    },
    "4": {
        "nome": "Desenvolvimento Ombro",
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 70, "fim": 160,
        "msg_fim": "Peso no alto! Desca.",
        "msg_inicio": "Empurre para cima."
    },
    "5": {
        "nome": "Abdominal Supra",
        "lados": {"esq": (5, 11, 13), "dir": (6, 12, 14)}, # Tronco flexionando em direção ao joelho
        "inicio": 120, "fim": 70,
        "msg_fim": "Contracao OK! Desca.",
        "msg_inicio": "Suba o tronco."
    }
}