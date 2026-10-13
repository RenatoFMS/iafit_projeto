# core/config_exercicios.py

EXERCICIOS = {
    "1": {
        "nome": "Rosca Biceps",
        "met": 2.8,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "postura": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Quadril, Ombro, Cotovelo (travar cotovelo ao lado do corpo)
        "postura_vertical": False,
        "limite_postura": 35,
        "regra_postura": ">",
        "inicio": 160, "fim": 40,
        "msg_fim": "Boa contracao! Desca.",
        "msg_inicio": "Estique o braco!",
        "msg_erro": "ERRO: Cotovelo muito a frente!",
        "msg_voz": "Trave o cotovelo"
    },
    "2": {
        "nome": "Agachamento",
        "met": 5.0,
        "lados": {"esq": (11, 13, 15), "dir": (12, 14, 16)},
        "postura": {"esq": (5, 11), "dir": (6, 12)}, 
        "postura_vertical": True, 
        "limite_postura": 45,     
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 170, "fim": 80, 
        "msg_fim": "Profundidade OK! Suba.",
        "msg_inicio": "Desca o quadril.",
        "msg_erro": "ERRO: Tronco muito inclinado!",
        "msg_voz": "Endireite as costas"
    },
    "3": {
        "nome": "Flexao de Braco",
        "met": 3.8,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, 
        "postura": {"esq": (5, 11, 15), "dir": (6, 12, 16)}, # Prancha: Ombro, Quadril, Tornozelo
        "postura_vertical": False,
        "limite_postura": 140, # Abaixo de 140 graus, o quadril caiu
        "regra_postura": "<",
        "inicio": 160, "fim": 80,
        "msg_fim": "Empurre o chao!",
        "msg_inicio": "Desca o peito.",
        "msg_erro": "ERRO: Alinhe o quadril!",
        "msg_voz": "Abaixe o quadril"
    },
    "4": {
        "nome": "Desenvolvimento Ombro",
        "met": 3.0,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Ombro, Quadril
        "postura_vertical": True,
        "limite_postura": 20, # Tronco inclinado para trás ao empurrar
        "regra_postura": ">",
        "inicio": 70, "fim": 160,
        "msg_fim": "Peso no alto! Desca.",
        "msg_inicio": "Empurre para cima.",
        "msg_erro": "ERRO: Tronco muito inclinado!",
        "msg_voz": "Endireite o tronco"
    },
    "5": {
        "nome": "Abdominal Supra",
        "met": 2.8,
        "lados": {"esq": (5, 11, 13), "dir": (6, 12, 14)}, # Tronco flexionando em direção ao joelho
        "postura": {"esq": (0, 5, 11), "dir": (0, 6, 12)}, # Nariz, Ombro, Quadril (evitar puxar a cervical)
        "postura_vertical": False,
        "limite_postura": 130, # Puxando o queixo em direção ao peito
        "regra_postura": "<",
        "inicio": 150, "fim": 70,
        "ignorar_assimetria": True, # De perfil, um lado pode estar obstruído: usa só o lado mais confiável
        "msg_fim": "Contracao OK! Desca.",
        "msg_inicio": "Suba o tronco.",
        "msg_erro": "ERRO: Nao puxe o pescoco!",
        "msg_voz": "Nao puxe o pescoco"
    },
    "6": {
        "nome": "Afundo (Lunge)",
        "met": 4.0,
        "lados": {"esq": (11, 13, 15), "dir": (12, 14, 16)}, # Quadril, Joelho, Tornozelo
        "postura": {"esq": (5, 11, 14), "dir": (6, 12, 13)}, # Ombro, Quadril, Joelho traseiro
        "postura_vertical": False,
        "limite_postura": 145, # Alinhamento tronco-coxa traseira (180° reto; < 145° inclinação excessiva)
        "regra_postura": "<",
        "inicio": 160, "fim": 90, # Desce perto de 90 graus no joelho
        "ignorar_assimetria": True,
        "msg_fim": "Profundidade OK! Suba.",
        "msg_inicio": "Desca o quadril.",
        "msg_erro": "ERRO: Tronco muito inclinado!",
        "msg_voz": "Endireite o tronco"
    },
    "7": {
        "nome": "Stiff",
        "met": 4.0,
        "lados": {"esq": (5, 11, 13), "dir": (6, 12, 14)}, # Ombro, Quadril, Joelho (extensão do quadril)
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Ombro, Quadril em relação à vertical
        "postura_vertical": True,
        "limite_postura": 75, # Margem segura de inclinação para manter a curvatura lombar neutra
        "regra_postura": ">",
        "inicio": 170, "fim": 80,
        "ignorar_assimetria": True,
        "msg_fim": "Boa descida! Suba.",
        "msg_inicio": "Desca o tronco.",
        "msg_erro": "ERRO: Mantenha as costas retas!",
        "msg_voz": "Endireite as costas"
    },
    "8": {
        "nome": "Prancha Isométrica",
        "tipo": "isometrico",
        "met": 3.5,
        "lados": {"esq": (5, 11, 15), "dir": (6, 12, 16)}, # Ombro, Quadril, Tornozelo
        "postura": {"esq": (5, 11, 15), "dir": (6, 12, 16)},
        "postura_vertical": False,
        "limite_postura": 160, # Se ângulo < 160°, o quadril caiu
        "regra_postura": "<",
        "inicio": 180, "fim": 160,
        "ignorar_assimetria": True,
        "msg_fim": "Postura correta!",
        "msg_inicio": "Segure a posicao.",
        "msg_erro": "ERRO: Levante o quadril!",
        "msg_voz": "Levante o quadril"
    },
    "9": {
        "nome": "Remada Curvada",
        "met": 3.5,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, # Ombro, Cotovelo, Pulso
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Ombro, Quadril em relação à vertical
        "postura_vertical": True,
        "limite_postura": 75, # Tronco deve manter inclinação controlada sem arredondar as costas
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 160, "fim": 70, # Braço estendido (160°) -> puxada completa (70°)
        "msg_fim": "Boa puxada! Estique o braco.",
        "msg_inicio": "Puxe os cotovelos.",
        "msg_erro": "ERRO: Mantenha as costas retas!",
        "msg_voz": "Mantenha as costas retas"
    },
    "10": {
        "nome": "Supino Halteres",
        "met": 3.0,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, # Ombro, Cotovelo, Pulso
        "postura": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Quadril, Ombro, Cotovelo (ângulo de abertura dos cotovelos)
        "postura_vertical": False,
        "limite_postura": 90, # Evitar abrir os cotovelos a 90° ou mais para proteger os ombros
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 80, "fim": 160, # Halteres no peito (80°) -> empurrada no topo (160°)
        "msg_fim": "Boa subida! Desca com controle.",
        "msg_inicio": "Empurre para cima.",
        "msg_erro": "ERRO: Feche um pouco os cotovelos!",
        "msg_voz": "Feche os cotovelos"
    },
    "11": {
        "nome": "Elevacao Lateral",
        "met": 2.8,
        "lados": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Quadril, Ombro, Cotovelo (90º no topo)
        "postura": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Braço não deve passar da linha horizontal dos ombros
        "postura_vertical": False,
        "limite_postura": 95, # Não passar da linha dos ombros (95°)
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 20, "fim": 90, # Braços ao lado do corpo (20°) -> linha dos ombros (90°)
        "ignorar_assimetria": False,
        "msg_fim": "Boa altura! Desca devagar.",
        "msg_inicio": "Eleve ate os ombros.",
        "msg_erro": "ERRO: Nao eleve acima dos ombros!",
        "msg_voz": "Abaixo dos ombros"
    },
    "12": {
        "nome": "Elevacao Pelvica",
        "met": 3.5,
        "lados": {"esq": (5, 11, 13), "dir": (6, 12, 14)}, # Ombro, Quadril, Joelho (extensão do quadril no topo)
        "postura": {"esq": (5, 11, 13), "dir": (6, 12, 14)}, # Evitar hiperextensão lombar no topo
        "postura_vertical": False,
        "limite_postura": 185, # Não ultrapassar 185° para não hiperestender a lombar
        "regra_postura": ">",
        "inicio": 110, "fim": 175, # No chão flexionado (110°) -> extensão completa do quadril (175°)
        "ignorar_assimetria": True,
        "msg_fim": "Extensao total! Desca.",
        "msg_inicio": "Eleve o quadril.",
        "msg_erro": "ERRO: Nao hiperestenda a lombar!",
        "msg_voz": "Alinhe a coluna"
    }
}