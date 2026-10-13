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
    },
    "13": {
        "nome": "Mergulho no Banco",
        "met": 3.0,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, # Ombro, Cotovelo, Pulso
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Tronco próximo ao banco
        "postura_vertical": True,
        "limite_postura": 40,
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 160, "fim": 90, # Braço estendido (160°) -> descida até 90°
        "msg_fim": "Profundidade OK! Suba.",
        "msg_inicio": "Desca flexionando os cotovelos.",
        "msg_erro": "ERRO: Mantenha o quadril proximo ao banco!",
        "msg_voz": "Aproxime o quadril"
    },
    "14": {
        "nome": "Rosca Martelo",
        "met": 2.8,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, # Ombro, Cotovelo, Pulso (pegada neutra)
        "postura": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Travar cotovelo ao lado do tronco
        "postura_vertical": False,
        "limite_postura": 35,
        "regra_postura": ">",
        "inicio": 160, "fim": 40,
        "msg_fim": "Boa contracao! Desca.",
        "msg_inicio": "Estique o braco!",
        "msg_erro": "ERRO: Cotovelo muito a frente!",
        "msg_voz": "Trave o cotovelo"
    },
    "15": {
        "nome": "Agachamento Sumo",
        "met": 5.0,
        "lados": {"esq": (11, 13, 15), "dir": (12, 14, 16)}, # Quadril, Joelho, Tornozelo
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Base dos pés mais aberta que os ombros
        "postura_vertical": True,
        "limite_postura": 45,
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 170, "fim": 85,
        "msg_fim": "Profundidade OK! Suba.",
        "msg_inicio": "Desca o quadril.",
        "msg_erro": "ERRO: Afaste mais os pes!",
        "msg_voz": "Afaste mais os pes"
    },
    "16": {
        "nome": "Barra Fixa",
        "met": 4.0,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, # Ombro, Cotovelo, Pulso
        "postura": {"esq": (5, 11), "dir": (6, 12)},
        "postura_vertical": True,
        "limite_postura": 35,
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 160, "fim": 65, # Pendurado braço estendido (160°) -> queixo acima da barra (65°)
        "msg_fim": "Queixo acima da barra! Desca.",
        "msg_inicio": "Puxe o corpo para cima.",
        "msg_erro": "ERRO: Passe o queixo da barra!",
        "msg_voz": "Passe o queixo da barra"
    },
    "17": {
        "nome": "Triceps Testa",
        "met": 3.0,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, # Ombro, Cotovelo, Pulso
        "postura": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Manter braços alinhados
        "postura_vertical": False,
        "limite_postura": 110,
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 160, "fim": 70, # Braços estendidos (160°) -> flexão até a testa (70°)
        "msg_fim": "Extensao total! Desca com controle.",
        "msg_inicio": "Estique os antebracos.",
        "msg_erro": "ERRO: Trave os cotovelos!",
        "msg_voz": "Trave os cotovelos"
    },
    "18": {
        "nome": "Crucifixo Halteres",
        "met": 3.0,
        "lados": {"esq": (5, 7, 9), "dir": (6, 8, 10)}, # Ombro, Cotovelo, Pulso
        "postura": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Abertura do peitoral
        "postura_vertical": False,
        "limite_postura": 165, # Não hiperestender os cotovelos
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 150, "fim": 85, # Halteres juntos (150°) -> abertura lateral dos braços (85°)
        "msg_fim": "Boa abertura! Feche os bracos.",
        "msg_inicio": "Abra os bracos com controle.",
        "msg_erro": "ERRO: Flexione levemente os cotovelos!",
        "msg_voz": "Flexione os cotovelos"
    },
    "19": {
        "nome": "Stiff Unilateral",
        "met": 4.0,
        "lados": {"esq": (5, 11, 13), "dir": (6, 12, 14)}, # Ombro, Quadril, Joelho (perna de apoio)
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Ombro, Quadril com a vertical
        "postura_vertical": True,
        "limite_postura": 75, # Não arredondar as costas na descida
        "regra_postura": ">",
        "inicio": 170, "fim": 85, # Em pé (170°) -> descida controlada (85°)
        "ignorar_assimetria": True,
        "msg_fim": "Boa descida! Suba.",
        "msg_inicio": "Incline o tronco a frente.",
        "msg_erro": "ERRO: Mantenha as costas retas!",
        "msg_voz": "Endireite as costas"
    },
    "20": {
        "nome": "Elevacao Frontal",
        "met": 2.8,
        "lados": {"esq": (11, 5, 7), "dir": (12, 6, 8)}, # Quadril, Ombro, Cotovelo
        "postura": {"esq": (5, 11, 15), "dir": (6, 12, 16)}, # Ombro, Quadril, Tornozelo (evitar balanço lombar)
        "postura_vertical": False,
        "limite_postura": 165, # Balanço do tronco para trás
        "regra_postura": "<",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 20, "fim": 90, # Braços baixos (20°) -> linha dos ombros (90°)
        "ignorar_assimetria": False,
        "msg_fim": "Boa altura! Desca devagar.",
        "msg_inicio": "Eleve ate os ombros.",
        "msg_erro": "ERRO: Nao balance o tronco!",
        "msg_voz": "Nao balance o tronco"
    },
    "21": {
        "nome": "Panturrilha em Pe",
        "met": 2.5,
        "lados": {"esq": (13, 15, 15), "dir": (14, 16, 16)}, # Joelho, Tornozelo, Pé
        "postura": {"esq": (5, 11, 13), "dir": (6, 12, 14)}, # Manter pernas estendidas
        "postura_vertical": False,
        "limite_postura": 160,
        "regra_postura": "<",
        "inicio": 90, "fim": 140, # Pé neutro (90°) -> elevação na ponta do pé (140°)
        "ignorar_assimetria": True,
        "msg_fim": "Contracao maxima! Desca.",
        "msg_inicio": "Suba na ponta dos pes.",
        "msg_erro": "ERRO: Mantenha os joelhos estendidos!",
        "msg_voz": "Estenda as pernas"
    },
    "22": {
        "nome": "Prancha Lateral",
        "tipo": "isometrico",
        "met": 3.5,
        "lados": {"esq": (5, 11, 15), "dir": (6, 12, 16)}, # Ombro, Quadril, Tornozelo
        "postura": {"esq": (5, 11, 15), "dir": (6, 12, 16)}, # Alinhamento lateral
        "postura_vertical": False,
        "limite_postura": 160, # Se ângulo < 160°, quadril caiu
        "regra_postura": "<",
        "inicio": 180, "fim": 160,
        "ignorar_assimetria": True,
        "msg_fim": "Postura lateral correta!",
        "msg_inicio": "Segure a posicao lateral.",
        "msg_erro": "ERRO: Suba o quadril lateral!",
        "msg_voz": "Suba o quadril"
    },
    "23": {
        "nome": "Agachamento Bulgaro",
        "met": 5.0,
        "lados": {"esq": (11, 13, 15), "dir": (12, 14, 16)}, # Quadril, Joelho, Tornozelo (perna dianteira)
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Tronco ereto
        "postura_vertical": True,
        "limite_postura": 45,
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 170, "fim": 90, # Em pé (170°) -> descida até 90° no joelho dianteiro
        "ignorar_assimetria": True,
        "msg_fim": "Profundidade OK! Suba.",
        "msg_inicio": "Desca o quadril.",
        "msg_erro": "ERRO: Tronco muito inclinado!",
        "msg_voz": "Endireite o tronco"
    },
    "24": {
        "nome": "Encolhimento Ombros",
        "met": 2.5,
        "lados": {"esq": (3, 5, 11), "dir": (4, 6, 12)}, # Orelha, Ombro, Quadril (elevação vertical dos ombros)
        "postura": {"esq": (5, 11), "dir": (6, 12)}, # Tronco estático
        "postura_vertical": True,
        "limite_postura": 20,
        "regra_postura": ">",
        "bracos": {"esq": (5, 7, 9), "dir": (6, 8, 10)},
        "inicio": 170, "fim": 135, # Ombros baixos (170°) -> ombros elevados (135°)
        "ignorar_assimetria": False,
        "msg_fim": "Contracao maxima! Desca.",
        "msg_inicio": "Encolha os ombros para cima.",
        "msg_erro": "ERRO: Nao incline o tronco!",
        "msg_voz": "Mantenha o tronco reto"
    }
}