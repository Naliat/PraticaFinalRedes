import socket
import threading
import random
import csv
import time
from datetime import datetime

# ------------------------------------------
# Configuração para descoberta via UDP
# ------------------------------------------
UDP_PORT = 54321       # Porta para descoberta UDP
TCP_PORT = 12345       # Porta do servidor TCP (mantida a mesma)
BROADCAST_MSG = "DISCOVER_SERVER"
RESPONSE_MSG = f"SERVER_FOUND:{TCP_PORT}"

def udp_discovery():
    """
    Função que aguarda requisições UDP de descoberta e responde com as informações do servidor.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", UDP_PORT))
    print(f"Servidor UDP de descoberta iniciado na porta {UDP_PORT}...")
    
    while True:
        try:
            data, addr = udp_socket.recvfrom(1024)
            if data.decode() == BROADCAST_MSG:
                udp_socket.sendto(RESPONSE_MSG.encode(), addr)
                print(f"Respondendo a descoberta para {addr}")
        except Exception as e:
            print(f"Erro no UDP: {e}")
            break

# ------------------------------------------
# Lógica original do jogo
# ------------------------------------------
class DouradoGame:
    def __init__(self, mode=20, singleplayer=False):
        self.players = []             # Sockets dos jogadores
        self.deck = []                # Baralho de cartas
        self.trump_card = None        # Carta virada (Bebi)
        self.trump_suit = None        # Naipe principal
        self.history = []             # Histórico da partida
        self.mode = mode              # Modalidade: 20 ou 52 cartas
        self.hands = []               # Mãos dos jogadores
        self.montes = [0, 0]          # Pontuação por duplas (ex.: jogadores 1 e 3 vs. 2 e 4)
        self.starting_player = 0      # Jogador vencedor da rodada
        self.game_start_time = None
        self.game_end_time = None
        self.player_names = []        # Nomes dos jogadores
        self.played_cards = []        # Histórico das rodadas
        self.singleplayer = singleplayer  # True se jogar contra a máquina
        self.lock = threading.Lock()  # Lock para sincronização

    def create_deck(self):
        """Cria o baralho de acordo com a modalidade."""
        suits = ['Ouros', 'Espadas', 'Copas', 'Paus']
        values = ['4', '5', '6', '7', 'Q', 'J', 'K', 'A', '2', '3']
        if self.mode == 20:
            # Para 20 cartas: usa somente K, J, Q, A + extras:
            deck = [card for card in [(value, suit) for suit in suits for value in values]
                    if card[0] in ['K', 'J', 'Q', 'A']]
            extras = [('3', 'Espadas'), ('3', 'Paus'), ('2', 'Paus'), ('2', 'Espadas')]
            deck += extras
        else:
            deck = [(value, suit) for suit in suits for value in values]
        random.shuffle(deck)
        self.deck = deck

    def start_game(self):
        """Inicia o jogo."""
        with self.lock:
            self.create_deck()
            if not self.deck:
                raise ValueError("O baralho está vazio.")
            self.trump_card = self.deck.pop()
            self.trump_suit = self.trump_card[1]
            self.history.append(f"Carta virada (Bebi): {self.format_card(self.trump_card)}")
            self.history.append(f"Naipe principal: {self.trump_suit}")
            self.game_start_time = datetime.now()

    def deal_cards(self):
        """Distribui as cartas para os jogadores."""
        num_cards = 3 if self.mode == 20 else 9
        self.hands = []
        if len(self.deck) < num_cards * 4:
            raise ValueError("Cartas insuficientes no baralho para distribuir.")
        for _ in range(4):
            hand = [self.deck.pop() for _ in range(num_cards)]
            self.hands.append(hand)
        return self.hands

    def add_player(self, player_socket, player_name):
        """Adiciona um jogador ao jogo."""
        with self.lock:
            self.players.append(player_socket)
            self.player_names.append(player_name)
            # Notifica todos sobre a nova conexão
            self.broadcast(f"{player_name} se conectou.")

    def broadcast(self, message):
        """Envia uma mensagem para todos os jogadores."""
        for player in self.players:
            try:
                player.send(message.encode())
            except:
                pass

    def format_card(self, card):
        """Formata a carta para exibição por extenso."""
        value, suit = card
        value_map = {
            '4': '4',
            '5': '5',
            '6': '6',
            '7': '7',
            'Q': 'Dama',
            'J': 'Valete',
            'K': 'Rei',
            'A': 'Ás',
            '2': '2',
            '3': '3'
        }
        return f"{value_map.get(value, value)} de {suit}"

    def reveal_hands(self):
        """Mostra as cartas distribuídas para todos os jogadores."""
        hands_summary = "\n".join([f"Jogador {i+1}: {', '.join([self.format_card(c) for c in hand])}" 
                                   for i, hand in enumerate(self.hands)])
        self.broadcast(f"Cartas Distribuídas:\n{hands_summary}\n")
        self.history.append(f"Cartas distribuídas:\n{hands_summary}")
        self.broadcast(f"Carta Virada (Bebi): {self.format_card(self.trump_card)}\n")
        self.broadcast(f"Naipe Principal: {self.trump_suit}\n")

    def card_value(self, card):
        """Retorna o valor da carta para comparação."""
        values = {'4': 1, '5': 2, '6': 3, '7': 4, 'Q': 5, 'J': 6, 'K': 7, 'A': 8, '2': 9, '3': 10}
        value, suit = card
        if card == ('3', 'Espadas'):
            return 100  # 3 de Espadas é a carta mais forte
        if value == 'Q' and suit == self.trump_suit:
            return 98   # Dama do naipe principal é a segunda mais forte
        if value == 'A' and suit == self.trump_suit:
            return 97   # Ás do naipe principal é a terceira mais forte
        if suit == self.trump_suit:
            return 90 + values[value]
        return values[value]

    def play_step(self, player_index, chosen_card):
        """
        Executa uma rodada. O jogador envia sua jogada informando a carta no formato, por exemplo, 'Qe'
        para Q de Espadas. Se o jogador digitar 'auto', a carta será escolhida aleatoriamente.
        """
        card_map = {'O': 'Ouros', 'E': 'Espadas', 'C': 'Copas', 'P': 'Paus'}
        if chosen_card.lower() == 'auto':
            chosen_card_tuple = random.choice(self.hands[player_index])
        else:
            if len(chosen_card) < 2:
                raise ValueError("Formato de carta inválido.")
            chosen_card_tuple = (chosen_card[0].upper(), card_map.get(chosen_card[1].upper()))
            if not chosen_card_tuple[1]:
                raise ValueError(f"Naipe inválido: {chosen_card[1]}")
            if chosen_card_tuple not in self.hands[player_index]:
                raise ValueError(f"A carta {self.format_card(chosen_card_tuple)} não está na sua mão.")
        self.hands[player_index].remove(chosen_card_tuple)
        current_round = [None] * 4
        current_round[player_index] = chosen_card_tuple
        for i in range(4):
            if i != player_index and self.hands[i]:
                if self.singleplayer:
                    current_round[i] = self.hands[i].pop(random.randrange(len(self.hands[i])))
                else:
                    current_round[i] = self.hands[i].pop()  # Em multiplayer, o servidor simula a jogada se não for informado
        self.played_cards.append(current_round)
        round_summary = "Rodada: " + ", ".join([f"Jogador {i+1}: {self.format_card(card)}" for i, card in enumerate(current_round)])
        self.history.append(round_summary)
        self.broadcast(round_summary)
        try:
            winner = current_round.index(max(current_round, key=self.card_value))
        except Exception as e:
            winner = 0
        self.starting_player = winner
        self.montes[winner % 2] += 1
        reason = f"A carta {self.format_card(current_round[winner])} foi a maior."
        self.history.append(f"Dupla {winner % 2 + 1} venceu a rodada. Motivo: {reason}")
        self.broadcast(f"{round_summary}\nDupla {winner % 2 + 1} venceu. Motivo: {reason}\n")

    def end_game(self):
        """Finaliza o jogo, salva os dados e envia ranking aos jogadores."""
        self.game_end_time = datetime.now()
        winner_team = 1 if self.montes[0] > self.montes[1] else 2
        self.history.append(f"Dupla {winner_team} venceu a partida com placar {self.montes}")
        self.broadcast("Partida terminada!\n" + "\n".join(self.history))
        self.save_game_data(winner_team)
        ranking = self.compute_ranking()
        self.broadcast("----- Ranking -----\n" + ranking + "\n")
        self.prompt_new_game()

    def save_game_data(self, winner_team):
        """Salva os dados da partida em um arquivo CSV."""
        filename = "game_data.csv"
        with open(filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            # Escreve o cabeçalho se o arquivo estiver vazio
            if file.tell() == 0:
                writer.writerow(["Nome do Jogador", "Cartas Restantes", "Início da Partida", "Término da Partida", "Resultado"])
            for i, name in enumerate(self.player_names):
                played_cards = " | ".join([self.format_card(card) for card in self.hands[i]]) if i < len(self.hands) else "" 
                # Define se o jogador foi vencedor: em um jogo de 4 jogadores, jogadores 1 e 3 formam a equipe 1 e 2 e 4 a equipe 2
                if (winner_team == 1 and i % 2 == 0) or (winner_team == 2 and i % 2 == 1):
                    result = "Vencedor"
                else:
                    result = "Perdedor"
                writer.writerow([
                    name,
                    played_cards,
                    self.game_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    self.game_end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    result
                ])

    def compute_ranking(self):
        """
        Lê o arquivo CSV e agrupa as partidas por nome, somando a quantidade de vitórias.
        Retorna uma string formatada com o ranking.
        """
        filename = "game_data.csv"
        ranking_dict = {}
        try:
            with open(filename, mode="r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    name = row["Nome do Jogador"]
                    result = row["Resultado"]
                    if name not in ranking_dict:
                        ranking_dict[name] = 0
                    if result == "Vencedor":
                        ranking_dict[name] += 1
        except Exception as e:
            print(f"Erro ao calcular ranking: {e}")
            return ""
        
        # Ordena o ranking do maior para o menor número de vitórias
        sorted_ranking = sorted(ranking_dict.items(), key=lambda x: x[1], reverse=True)
        ranking_str = "\n".join([f"{i+1}. {name} - {wins} vitórias" for i, (name, wins) in enumerate(sorted_ranking)])
        return ranking_str

    def prompt_new_game(self):
        """
        Solicita aos jogadores se desejam jogar novamente.
        Se todos não digitarem 'sair', a partida reinicia; caso contrário, as conexões são encerradas.
        """
        self.broadcast("Deseja jogar novamente? Digite seu nome para continuar ou 'sair' para encerrar:")
        responses = []
        for player in self.players:
            try:
                resp = player.recv(1024).decode().strip().lower()
                responses.append(resp)
            except:
                responses.append("sair")
        if any(resp == "sair" for resp in responses):
            self.broadcast("Encerrando conexão para alguns jogadores. Obrigado por jogar!")
            for player, resp in zip(self.players, responses):
                if resp == "sair":
                    try:
                        player.send("Saindo...\n".encode())
                        player.close()
                    except:
                        pass
            # Reinicia o jogo apenas com os jogadores que não saíram
            self.players = [p for p, r in zip(self.players, responses) if r != "sair"]
            self.player_names = [name for name, r in zip(self.player_names, responses) if r != "sair"]
        else:
            self.broadcast("Reiniciando partida...")
        # Reinicia as variáveis do jogo para uma nova partida
        self.deck = []
        self.trump_card = None
        self.trump_suit = None
        self.history = []
        self.hands = []
        self.montes = [0, 0]
        self.starting_player = 0
        self.game_start_time = None
        self.game_end_time = None

def handle_client(client_socket, game):
    """Função para lidar com cada cliente."""
    try:
        # Solicita o nome do jogador
        client_socket.send("Digite seu nome: ".encode())
        player_name = client_socket.recv(1024).decode().strip()
        game.add_player(client_socket, player_name)
        
        # Se for o primeiro cliente, define modo e modalidade
        if len(game.players) == 1:
            menu = ("Escolha o modo de jogo:\n"
                    "1. Jogar contra a máquina\n"
                    "2. Jogar multiplayer\n")
            client_socket.send(menu.encode())
            modo = int(client_socket.recv(1024).decode().strip())
            game.singleplayer = True if modo == 1 else False
            
            client_socket.send("Escolha a modalidade (digite 20 ou 52): ".encode())
            modalidade = int(client_socket.recv(1024).decode().strip())
            if modalidade not in [20, 52]:
                client_socket.send("Modalidade inválida. Encerrando conexão.".encode())
                client_socket.close()
                return
            game.mode = modalidade
        else:
            # Se multiplayer e não for o primeiro cliente, apenas informa para aguardar
            if not game.singleplayer:
                client_socket.send("Aguardando início da partida...\n".encode())
                while len(game.players) < 4:
                    time.sleep(0.5)
        
        # Inicia o jogo quando o número necessário de jogadores for atingido
        if len(game.players) == (1 if game.singleplayer else 4) and game.game_start_time is None:
            game.start_game()
            game.deal_cards()
            game.reveal_hands()
            for i, player in enumerate(game.players):
                player.send(f"Sua mão: {game.get_hand(i)}\n".encode())
                game.history.append(f"Jogador {i+1}: {game.get_hand(i)}")
        
        # Loop principal do jogo com o menu de opções
        while True:
            client_socket.send((
                "\nEscolha uma opção:\n"
                "1. Jogar próxima rodada\n"
                "2. Ver histórico\n"
                "3. Ver minha mão\n"
                "4. Jogar automaticamente\n"
                "5. Sair\n"
            ).encode())
            try:
                opcao = int(client_socket.recv(1024).decode().strip())
            except ValueError:
                client_socket.send("Opção inválida. Tente novamente.\n".encode())
                continue
            
            idx = game.players.index(client_socket)
            if opcao == 1:
                client_socket.send("Digite a carta que deseja jogar (ex: Qe) ou 'auto' para jogar automaticamente: ".encode())
                carta = client_socket.recv(1024).decode().strip()
                try:
                    game.play_step(idx, carta)
                except Exception as err:
                    client_socket.send(f"Erro: {err}\nSua mão: {game.get_hand(idx)}\n".encode())
                    continue
            elif opcao == 2:
                client_socket.send(("Histórico da partida:\n" + "\n".join(game.history)).encode())
            elif opcao == 3:
                client_socket.send(f"Sua mão: {game.get_hand(idx)}\n".encode())
            elif opcao == 4:
                try:
                    game.play_step(idx, "auto")
                except Exception as err:
                    client_socket.send(f"Erro: {err}\n".encode())
            elif opcao == 5:
                client_socket.send("Saindo...\n".encode())
                client_socket.close()
                break
            else:
                client_socket.send("Opção inválida. Tente novamente.\n".encode())
    except Exception as e:
        try:
            client_socket.send(f"Erro: {e}".encode())
        except:
            pass
        client_socket.close()

def server():
    """Função principal do servidor."""
    game = DouradoGame()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind para todas as interfaces para permitir conexão de outros computadores
    server_socket.bind(('0.0.0.0', TCP_PORT))
    server_socket.listen(4)
    print("Servidor iniciado e aguardando conexões...")
    
    while True:
        try:
            client_socket, addr = server_socket.accept()
            print(f"Conexão estabelecida com {addr}")
            threading.Thread(target=handle_client, args=(client_socket, game)).start()
        except KeyboardInterrupt:
            print("Servidor encerrado.")
            break

if __name__ == "__main__":
    # Inicia a thread de descoberta UDP
    threading.Thread(target=udp_discovery, daemon=True).start()
    server()
