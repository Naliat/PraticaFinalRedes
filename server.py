import socket
import threading
import random
import csv
import time
from datetime import datetime
import os

# ------------------------------------------
# Configuração para Descoberta via UDP
# ------------------------------------------
UDP_PORT = 54321       # Porta para descoberta UDP
TCP_PORT = 12345       # Porta do servidor TCP
BROADCAST_MSG = "DISCOVER_SERVER"
RESPONSE_MSG = f"SERVER_FOUND:{TCP_PORT}"

def udp_discovery():
    """
    Aguarda requisições UDP de descoberta e responde com as informações do servidor.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", UDP_PORT))
    print(f"[UDP] Servidor de descoberta iniciado na porta {UDP_PORT}...")
    while True:
        try:
            data, addr = udp_socket.recvfrom(1024)
            if data.decode() == BROADCAST_MSG:
                udp_socket.sendto(RESPONSE_MSG.encode(), addr)
                print(f"[UDP] Respondendo a descoberta para {addr}")
        except Exception as e:
            print(f"[UDP] Erro: {e}")
            break

# ------------------------------------------
# Ranking Global em Tempo Real
# ------------------------------------------
RANKING = {}

def atualizar_ranking(game, winning_team):
    """
    Atualiza o ranking global com os pontos da dupla vencedora.
    Dupla 1: jogadores nos índices 0 e 2.
    Dupla 2: jogadores nos índices 1 e 3.
    """
    indices = [0, 2] if winning_team == 1 else [1, 3]
    for i in indices:
        if i < len(game.player_names):
            nome = game.player_names[i]
            RANKING[nome] = RANKING.get(nome, 0) + 1
    print(f"[RANKING] Ranking atualizado: {RANKING}")

def obter_ranking_formatado():
    if not RANKING:
        return "Ranking vazio."
    ranking_str = "Ranking em Tempo Real:\n"
    for nome, pontos in sorted(RANKING.items(), key=lambda x: x[1], reverse=True):
        ranking_str += f"{nome}: {pontos} vitória(s)\n"
    return ranking_str

# ------------------------------------------
# Classe do Jogo - Dourado
# ------------------------------------------
class DouradoGame:
    def __init__(self, mode=20, singleplayer=False):
        self.players = []             # Sockets dos jogadores
        self.deck = []                # Baralho de cartas
        self.trump_card = None        # Carta virada (Bebi)
        self.trump_suit = None        # Naipe principal
        self.history = []             # Histórico da partida (rodadas)
        self.mode = mode              # Modalidade: 20 ou 52 cartas
        self.hands = []               # Mãos dos jogadores (lista de listas)
        self.montes = [0, 0]          # Pontuação por dupla
        self.game_start_time = None
        self.game_end_time = None
        self.player_names = []        # Nomes dos jogadores
        self.played_cards = []        # Histórico das jogadas (cada rodada)
        self.cards_played = {}        # {nome: [cartas jogadas]}
        self.singleplayer = singleplayer
        self.finished = False         # Partida finalizada
        self.started = False          # Partida iniciada
        self.lock = threading.Lock()  # Para sincronização
        # Controle de rodada (para multiplayer)
        self.current_round = {}       # {player_index: carta_jogada}
        self.round_condition = threading.Condition(self.lock)
        self.round_result_computed = False
        self.current_turn = 0         # Índice do jogador cuja vez é
        self.leading_suit = None      # Naipe inicial da rodada

    def create_deck(self):
        """Cria o baralho conforme a modalidade."""
        suits = ['Ouros', 'Espadas', 'Copas', 'Paus']
        values = ['1','2','3','4','5','6','7','8','9','10','Q','J','K','A']
        if self.mode == 20:
            deck = [card for card in [(v, s) for s in suits for v in values] if card[0] in ['K','J','Q','A']]
            extras = [('3', 'Espadas'), ('3', 'Paus'), ('2', 'Paus'), ('2', 'Espadas')]
            deck += extras
        else:
            deck = [(v, s) for s in suits for v in values]
        random.shuffle(deck)
        self.deck = deck
        print(f"[GAME] Baralho criado com {len(deck)} cartas.")

    def start_game(self):
        """Inicializa o jogo, criando o baralho e definindo a carta virada."""
        with self.lock:
            self.create_deck()
            if not self.deck:
                raise ValueError("O baralho está vazio.")
            self.trump_card = self.deck.pop()
            self.trump_suit = self.trump_card[1]
            self.history.append(f"Carta virada (Bebi): {self.format_card(self.trump_card)}")
            self.history.append(f"Naipe principal: {self.trump_suit}")
            self.game_start_time = datetime.now()
            self.current_turn = 0
            print("[GAME] Jogo iniciado.")
            print(f"[GAME] Naipe da virada: {self.trump_suit}")

    def deal_cards(self):
        """Distribui as cartas para os 4 jogadores."""
        num_cards = 3 if self.mode == 20 else 9
        self.hands = []
        if len(self.deck) < num_cards * 4:
            raise ValueError("Cartas insuficientes para distribuir.")
        for _ in range(4):
            hand = [self.deck.pop() for _ in range(num_cards)]
            self.hands.append(hand)
        print("[GAME] Cartas distribuídas:")
        for i in range(4):
            try:
                self.players[i].send(f"Suas cartas: {self.get_hand(i)}\n".encode())
            except Exception as e:
                print(f"[GAME] Erro ao enviar cartas para o Jogador {i+1}: {e}")
        return self.hands

    def add_player(self, player_socket, player_name):
        """Adiciona um jogador à partida."""
        with self.lock:
            self.players.append(player_socket)
            self.player_names.append(player_name)
            self.cards_played[player_name] = []
            print(f"[GAME] Jogador adicionado: {player_name}")

    def broadcast(self, message):
        """Envia uma mensagem para todos os jogadores."""
        for player in self.players:
            try:
                player.send(message.encode())
            except Exception:
                pass

    def format_card(self, card):
        """Formata a carta para exibição."""
        value, suit = card
        value_map = {
            '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
            '6': '6', '7': '7', '8': '8', '9': '9', '10': '10',
            'Q': 'Q', 'J': 'J', 'K': 'K', 'A': 'A'
        }
        return f"{value_map.get(value, value)} de {suit}"

    def get_hand(self, player_index):
        """Retorna a mão do jogador de forma legível."""
        return ", ".join([self.format_card(card) for card in self.hands[player_index]])

    def reveal_hands(self):
        """Envia a todos os jogadores as mãos distribuídas e a carta virada."""
        hands_summary = "\n".join([f"Jogador {i+1}: {self.get_hand(i)}" for i in range(len(self.hands))])
        self.broadcast(f"Cartas Distribuídas:\n{hands_summary}\n")
        self.history.append(f"Cartas distribuídas:\n{hands_summary}")
        self.broadcast(f"Carta Virada (Bebi): {self.format_card(self.trump_card)}\n")
        self.broadcast(f"Naipe Principal: {self.trump_suit}\n")
        print("[GAME] Mãos distribuídas:")
        print(hands_summary)

    def normal_card_value(self, value):
        """Retorna o valor numérico base da carta."""
        values = {
            'A': 14, 'K': 13, 'Q': 12, 'J': 11,
            '10': 10, '9': 9, '8': 8, '7': 7,
            '6': 6, '5': 5, '4': 4, '3': 3,
            '2': 2, '1': 1
        }
        return values.get(value, 0)

    def card_value(self, card, leading_suit):
        """Define o valor para comparação das cartas com base na hierarquia especificada."""
        value, suit = card

        # Cartas especiais
        if card == ('3', 'Espadas'):
            return (16, 0)  # Bebi
        elif suit == self.trump_suit and value == 'Q':
            return (15, 0)  # Q do naipe da virada
        elif suit == self.trump_suit and value == '2':
            return (14, 0)  # 2 do naipe da virada
        elif card == ('2', 'Espadas'):
            return (13, 0)  # 2 de Espadas
        elif card == ('3', 'Paus'):
            return (12, 0)  # 3 de Paus
        elif card == ('A', 'Ouros'):
            return (11, 0)  # Ás de Ouros
        elif card == ('2', 'Paus'):
            return (10, 0)  # 2 de Paus
        elif card == ('1', 'Paus'):
            return (9, 0)   # 1 de Paus
        elif suit == self.trump_suit:
            # Outras cartas do naipe da virada (trump_suit)
            if value == 'K':
                return (8, 13)  # K do trump
            elif value == 'J':
                return (7, 11)  # J do trump
            else:
                # Para outras cartas do trump, usa o valor normal
                normal_value = self.normal_card_value(value)
                return (6, normal_value)
        elif suit == leading_suit:
            # Cartas do naipe inicial (leading_suit)
            if value == 'K':
                return (5, 13)  # K do leading_suit
            elif value == 'J':
                return (4, 11)  # J do leading_suit
            elif value == 'Q':
                return (3, 12)  # Q do leading_suit
            else:
                normal_value = self.normal_card_value(value)
                return (2, normal_value)
        else:
            # Outras cartas
            normal_value = self.normal_card_value(value)
            return (1, normal_value)

    def register_move_multiplayer(self, player_index, chosen_card):
        """
        Registra a jogada no modo multiplayer e sincroniza as jogadas.
        Cada jogador só pode jogar quando for sua vez.
        Se for a última jogada da rodada, calcula o resultado, reinicia os controles e notifica os clientes.
        """
        card_map = {'E': 'Espadas', 'O': 'Ouros', 'C': 'Copas', 'P': 'Paus'}
        rank_map = {'K': 'K', 'Q': 'Q', 'J': 'J'}
        with self.round_condition:
            while player_index != self.current_turn:
                self.round_condition.wait()
            if chosen_card.lower() == 'auto':
                if not self.hands[player_index]:
                    raise ValueError("Sua mão está vazia!")
                chosen_card_tuple = random.choice(self.hands[player_index])
            else:
                if len(chosen_card) < 2:
                    raise ValueError("Formato inválido. Exemplo: 'Kc' para Rei de Copas.")
                raw_value = chosen_card[:-1]
                suit_letter = chosen_card[-1].upper()
                if raw_value.upper() in rank_map:
                    value = rank_map[raw_value.upper()]
                else:
                    value = raw_value
                suit = card_map.get(suit_letter)
                if not suit:
                    raise ValueError(f"Naipe inválido: {chosen_card[-1]}")
                chosen_card_tuple = (value, suit)
                if chosen_card_tuple not in self.hands[player_index]:
                    raise ValueError(f"A carta {self.format_card(chosen_card_tuple)} não está na sua mão.")
            self.hands[player_index].remove(chosen_card_tuple)
            self.current_round[player_index] = chosen_card_tuple
            self.broadcast(f"{self.player_names[player_index]} jogou {self.format_card(chosen_card_tuple)}")
            print(f"[GAME] {self.player_names[player_index]} jogou {self.format_card(chosen_card_tuple)}")
            if len(self.current_round) == len(self.players):
                round_moves = [self.current_round[i] for i in range(len(self.players))]
                # Determinar leading_suit (primeira carta não nula)
                leading_suit = None
                for card in round_moves:
                    if card is not None:
                        leading_suit = card[1]
                        break
                # Calcular valores das cartas
                card_values = []
                for card in round_moves:
                    if card is None:
                        card_values.append((0, 0))
                    else:
                        card_values.append(self.card_value(card, leading_suit))
                # Encontrar o índice do maior valor
                max_value = max(card_values)
                vencedor = card_values.index(max_value)
                self.montes[vencedor % 2] += 1
                reason = f"A carta {self.format_card(round_moves[vencedor])} foi a maior."
                win_msg = f"{self.player_names[vencedor]} venceu a rodada. Motivo: {reason}"
                self.history.append(win_msg)
                self.broadcast(win_msg)
                print(f"[GAME] {win_msg}")
                self.current_round = {}
                self.leading_suit = None  # Resetar para a próxima rodada
                self.round_result_computed = False
                self.current_turn = 0
                self.broadcast(f"Nova rodada iniciada. Agora é a vez de: {self.player_names[0]}")
                self.round_condition.notify_all()
            else:
                self.current_turn += 1
                if self.current_turn < len(self.players):
                    self.broadcast(f"Agora é a vez de: {self.player_names[self.current_turn]}")
                self.round_condition.notify_all()
        return

    def play_step(self, player_index, chosen_card):
        """
        Executa a jogada do jogador.
        Se multiplayer, utiliza register_move_multiplayer.
        Se singleplayer, o jogador humano (índice 0) joga manualmente e as jogadas da IA (índices 1-3) são simuladas.
        """
        if not self.singleplayer:
            return self.register_move_multiplayer(player_index, chosen_card)
        else:
            if player_index != 0:
                raise ValueError("No modo singleplayer, somente o jogador humano (índice 0) joga manualmente.")
            # Jogada do humano:
            card_map = {'E': 'Espadas', 'O': 'Ouros', 'C': 'Copas', 'P': 'Paus'}
            rank_map = {'K': 'K', 'Q': 'Q', 'J': 'J'}
            if chosen_card.lower() == 'auto':
                if not self.hands[0]:
                    raise ValueError("Sua mão está vazia!")
                human_card = random.choice(self.hands[0])
            else:
                if len(chosen_card) < 2:
                    raise ValueError("Formato inválido. Exemplo: 'Kc' para Rei de Copas.")
                raw_value = chosen_card[:-1]
                suit_letter = chosen_card[-1].upper()
                if raw_value.upper() in rank_map:
                    value = rank_map[raw_value.upper()]
                else:
                    value = raw_value
                suit = card_map.get(suit_letter)
                if not suit:
                    raise ValueError(f"Naipe inválido: {chosen_card[-1]}")
                human_card = (value, suit)
                if human_card not in self.hands[0]:
                    raise ValueError(f"A carta {self.format_card(human_card)} não está na sua mão.")
            self.hands[0].remove(human_card)
            self.current_round[0] = human_card
            self.broadcast(f"{self.player_names[0]} jogou {self.format_card(human_card)}")
            print(f"[GAME] {self.player_names[0]} jogou {self.format_card(human_card)}")
            # Simula as jogadas dos bots (índices 1, 2 e 3)
            for ai_index in range(1, len(self.players)):
                if self.hands[ai_index]:
                    ai_card = random.choice(self.hands[ai_index])
                    self.hands[ai_index].remove(ai_card)
                    self.current_round[ai_index] = ai_card
                    self.broadcast(f"{self.player_names[ai_index]} jogou {self.format_card(ai_card)}")
                    print(f"[GAME] {self.player_names[ai_index]} jogou {self.format_card(ai_card)}")
                else:
                    self.current_round[ai_index] = None
            valid_moves = {i: card for i, card in self.current_round.items() if card is not None}
            if not valid_moves:
                return
            # Determinar leading_suit (primeira carta não nula)
            leading_suit = None
            for card in valid_moves.values():
                if card is not None:
                    leading_suit = card[1]
                    break
            # Calcular valores das cartas
            card_values = []
            for card in valid_moves.values():
                if card is None:
                    card_values.append((0, 0))
                else:
                    card_values.append(self.card_value(card, leading_suit))
            # Encontrar o índice do maior valor
            max_value = max(card_values)
            winner_index = list(valid_moves.keys())[card_values.index(max_value)]
            self.montes[winner_index % 2] += 1
            round_moves_str = ", ".join([f"{self.player_names[i]}: {self.format_card(valid_moves[i])}" 
                                          for i in valid_moves])
            round_summary = f"Rodada: {round_moves_str}"
            self.history.append(round_summary)
            self.broadcast(round_summary)
            print(f"[GAME] {round_summary}")
            reason = f"A carta {self.format_card(valid_moves[winner_index])} foi a maior."
            win_msg = f"{self.player_names[winner_index]} venceu a rodada. Motivo: {reason}"
            self.history.append(win_msg)
            self.broadcast(win_msg)
            print(f"[GAME] {win_msg}")
            self.current_round = {}
            self.leading_suit = None  # Resetar para a próxima rodada
            self.current_turn = 0
            self.broadcast(f"Nova rodada iniciada. Agora é a vez de: {self.player_names[0]}")
            # Se todas as mãos estiverem vazias, encerra a partida
            if all(len(hand) == 0 for hand in self.hands):
                self.end_game()

    def end_game(self):
        """Finaliza a partida, mostra a dupla vencedora, atualiza ranking e salva os dados em CSV."""
        self.game_end_time = datetime.now()
        winner_team = 1 if self.montes[0] > self.montes[1] else 2
        final_msg = f"Dupla {winner_team} venceu a partida com placar {self.montes}"
        self.history.append(final_msg)
        atualizar_ranking(self, winner_team)
        msg_final = "Partida terminada!\n" + "\n".join(self.history) + "\n" + obter_ranking_formatado()
        self.broadcast(msg_final)
        print(f"[GAME] {msg_final}")
        self.save_game_data()
        self.finished = True

    def save_game_data(self):
        """
        Salva os dados da partida em 'game_data.csv'.
        Os dados incluem: Modo, Jogadores, Histórico, Vencedor, Placar, Naipe Principal, Carta Virada, Início e Término.
        """
        filename = "game_data.csv"
        file_exists = os.path.isfile(filename)
        
        with open(filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow([
                    "Modo", "Jogadores", "Histórico", "Vencedor", "Placar", "Naipe Principal", 
                    "Carta Virada", "Início da Partida", "Término da Partida"
                ])
            
            modo = "Singleplayer" if self.singleplayer else "Multiplayer"
            jogadores = ", ".join(self.player_names)
            historico = " || ".join(self.history)
            vencedor_texto = "Dupla 1" if self.montes[0] > self.montes[1] else "Dupla 2"
            placar = f"[{self.montes[0]}, {self.montes[1]}]"
            
            # Certificando que naipe_principal e carta_virada existem
            naipe_principal = self.trump_suit if self.trump_suit else ""
            carta_virada = self.trump_card if self.trump_card else ""
            
            inicio = self.game_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.game_start_time else ""
            fim = self.game_end_time.strftime("%Y-%m-%d %H:%M:%S") if self.game_end_time else ""
            
            writer.writerow([modo, jogadores, historico, vencedor_texto, placar, naipe_principal, carta_virada, inicio, fim])
            print(f"[GAME] Dados salvos em {filename}")

    def reset_game(self):
        """Reinicializa os dados internos para uma nova partida (mantendo os sockets conectados)."""
        with self.lock:
            self.deck = []
            self.trump_card = None
            self.trump_suit = None
            self.history = []
            self.hands = []
            self.montes = [0, 0]
            self.game_start_time = None
            self.game_end_time = None
            self.played_cards = []
            self.cards_played = {}
            self.finished = False
            self.current_round = {}
            self.round_result_computed = False
            self.current_turn = 0

# ------------------------------------------
# Gerenciamento de Salas (para multiplayer)
# ------------------------------------------
game_rooms = {}  # {room_id: {"game": DouradoGame, "clients": [socket, ...]}}
room_lock = threading.Lock()

def assign_room(client_socket, player_name, singleplayer_choice):
    global game_rooms
    with room_lock:
        if singleplayer_choice:
            # Cria uma sala exclusiva para o jogador e adiciona 3 bots
            room_id = f"SP_{player_name}_{int(time.time())}"
            new_game = DouradoGame(mode=20, singleplayer=True)
            new_game.player_names.append(player_name)
            new_game.players.append(client_socket)
            # Adiciona bots (todos usarão o mesmo socket para broadcast)
            for bot in ["Bot1", "Bot2", "Bot3"]:
                new_game.player_names.append(bot)
                new_game.players.append(client_socket)
            game_rooms[room_id] = {"game": new_game, "clients": [client_socket]}
            print(f"[ROOM] Sala {room_id} criada para singleplayer com bots: {new_game.player_names}")
            return room_id, new_game
        else:
            # Procura uma sala multiplayer que ainda não esteja completa
            for room_id, room in game_rooms.items():
                if not room["game"].singleplayer and len(room["clients"]) < 4:
                    room["clients"].append(client_socket)
                    room["game"].player_names.append(player_name)
                    room["game"].players.append(client_socket)
                    print(f"[ROOM] Jogador {player_name} adicionado à sala {room_id}")
                    return room_id, room["game"]
            # Se nenhuma sala disponível, cria uma nova
            room_id = f"M_{len(game_rooms)+1}"
            new_game = DouradoGame(mode=20, singleplayer=False)
            new_game.player_names.append(player_name)
            new_game.players.append(client_socket)
            game_rooms[room_id] = {"game": new_game, "clients": [client_socket]}
            print(f"[ROOM] Sala {room_id} criada para multiplayer.")
            return room_id, new_game

def send_message(clients, message):
    for client in clients:
        try:
            client.send(message.encode())
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")

# ------------------------------------------
# Função para lidar com cada cliente
# ------------------------------------------
def handle_client(client_socket):
    try:
        client_socket.send("Digite seu nome: ".encode())
        player_name = client_socket.recv(1024).decode().strip()
        print(f"[SERVER] Novo jogador conectado: {player_name}")
        menu_inicial = ("Escolha o modo de jogo:\n"
                        "1. Jogar contra a máquina (Singleplayer)\n"
                        "2. Jogar multiplayer\n")
        client_socket.send(menu_inicial.encode())
        try:
            modo = int(client_socket.recv(1024).decode().strip())
        except:
            client_socket.send("Entrada inválida. Encerrando conexão.\n".encode())
            return
        singleplayer_choice = True if modo == 1 else False
        
        client_socket.send("Escolha a modalidade (digite 20 ou 52): ".encode())
        try:
            modalidade = int(client_socket.recv(1024).decode().strip())
        except:
            client_socket.send("Entrada inválida. Encerrando conexão.\n".encode())
            return
        if modalidade not in [20, 52]:
            client_socket.send("Modalidade inválida. Encerrando conexão.\n".encode())
            return
        
        room_id, game = assign_room(client_socket, player_name, singleplayer_choice)
        client_socket.send(f"Você foi atribuído à sala {room_id}.\n".encode())
        print(f"[SERVER] Jogador {player_name} atribuído à sala {room_id}.")
        
        if singleplayer_choice:
            game.start_game()
            game.deal_cards()
            game.reveal_hands()
            game.started = True
        else:
            with room_lock:
                if len(game_rooms[room_id]["clients"]) == 4:
                    print(f"[GAME] Sala {room_id} completa. Iniciando partida multiplayer...")
                    send_message(game_rooms[room_id]["clients"], "Todos os jogadores conectados. Iniciando partida...")
                    game.started = True
                    game.start_game()
                    game.deal_cards()
                    game.reveal_hands()
        
        while not game.started:
            time.sleep(0.1)
        
        idx = game.players.index(client_socket)
        while len(game.hands) <= idx:
            time.sleep(0.1)
        client_socket.send(f"Sua mão: {game.get_hand(idx)}\n".encode())
        
        # Loop de interação com o cliente
        while True:
            if game.finished:
                menu = ("\nA partida acabou!\n"
                        "6. Jogar novamente (desconecte e reconecte para nova partida)\n"
                        "7. Mostrar Ranking\n"
                        "5. Sair\n"
                        "Digite sua opção: ")
            else:
                menu = ("\nEscolha uma opção:\n"
                        "1. Jogar próxima rodada\n"
                        "2. Ver histórico\n"
                        "3. Ver minha mão\n"
                        "4. Jogar automaticamente\n"
                        "7. Mostrar Ranking\n"
                        "5. Sair\n"
                        "Digite sua opção: ")
            
            # Envia o menu somente para o jogador cuja vez é
            if idx == game.current_turn:
                client_socket.send(menu.encode())
            else:
                client_socket.send(f"Agora é a vez de: {game.player_names[game.current_turn]}\n".encode())
                # Lê o input para evitar bloqueio, mas ignora-o
                _ = client_socket.recv(1024).decode().strip()
                client_socket.send("Aguarde, não é sua vez.\n".encode())
                continue

            opcao_str = client_socket.recv(1024).decode().strip()
            if not opcao_str:
                break
            try:
                opcao = int(opcao_str)
            except:
                client_socket.send("Opção inválida!\n".encode())
                continue

            if game.finished:
                if opcao == 6:
                    client_socket.send("Para jogar novamente, desconecte e reconecte.\n".encode())
                    break
                elif opcao == 7:
                    ranking_msg = obter_ranking_formatado()
                    client_socket.send((ranking_msg + "\n").encode())
                    continue
                elif opcao == 5:
                    client_socket.send("Saindo...\n".encode())
                    break
                else:
                    client_socket.send("Opção inválida!\n".encode())
                    continue
            else:
                if opcao == 1:
                    if not game.hands[idx]:
                        client_socket.send("Você não tem mais cartas para jogar!\n".encode())
                        continue
                    client_socket.send("Digite a carta (ex: Kc para Rei de Copas ou 'auto'): ".encode())
                    carta = client_socket.recv(1024).decode().strip()
                    try:
                        game.play_step(idx, carta)
                        for player in game_rooms[room_id]["clients"]:
                            p_idx = game.players.index(player)
                            player.send(f"Sua mão: {game.get_hand(p_idx)}\n".encode())
                    except Exception as e:
                        client_socket.send(f"Erro: {str(e)}\n".encode())
                elif opcao == 2:
                    client_socket.send(("Histórico:\n" + "\n".join(game.history[-10:]) + "\n").encode())
                elif opcao == 3:
                    client_socket.send(f"Sua mão: {game.get_hand(idx)}\n".encode())
                elif opcao == 4:
                    if not game.hands[idx]:
                        client_socket.send("Você não tem mais cartas para jogar!\n".encode())
                        continue
                    try:
                        game.play_step(idx, "auto")
                        for player in game_rooms[room_id]["clients"]:
                            p_idx = game.players.index(player)
                            player.send(f"Sua mão: {game.get_hand(p_idx)}\n".encode())
                    except Exception as e:
                        client_socket.send(f"Erro: {str(e)}\n".encode())
                elif opcao == 7:
                    ranking_msg = obter_ranking_formatado()
                    client_socket.send((ranking_msg + "\n").encode())
                elif opcao == 5:
                    client_socket.send("Saindo...\n".encode())
                    break
                else:
                    client_socket.send("Opção inválida!\n".encode())
                    continue

            with game.lock:
                if game.hands and all(len(hand) == 0 for hand in game.hands):
                    game.end_game()
        print(f"[SERVER] Cliente {player_name} desconectado.")
    except Exception as e:
        print(f"Erro no handle_client: {str(e)}")
    finally:
        client_socket.close()

# ------------------------------------------
# Função Principal do Servidor
# ------------------------------------------
def server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', TCP_PORT))
    server_socket.listen(10)
    print("Servidor TCP iniciado na porta", TCP_PORT)
    while True:
        try:
            client_socket, addr = server_socket.accept()
            print(f"[TCP] Conexão estabelecida com {addr}")
            threading.Thread(target=handle_client, args=(client_socket,), daemon=True).start()
        except KeyboardInterrupt:
            print("Servidor encerrado.")
            break

if __name__ == "__main__":
    threading.Thread(target=udp_discovery, daemon=True).start()
    server()