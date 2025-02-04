import socket
import threading
import random
import csv
import time
from datetime import datetime

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

    def create_deck(self):
        suits = ['Ouros', 'Espadas', 'Copas', 'Paus']
        values = ['4', '5', '6', '7', 'Q', 'J', 'K', 'A', '2', '3']
        if self.mode == 20:
            # Para 20 cartas: usa somente K, J, Q, A (16 cartas) + extras:
            # 3 de Espadas, 3 de Paus, 2 de Paus e 2 de Espadas
            deck = [card for card in [(value, suit) for suit in suits for value in values]
                    if card[0] in ['K', 'J', 'Q', 'A']]
            extras = [('3', 'Espadas'), ('3', 'Paus'), ('2', 'Paus'), ('2', 'Espadas')]
            deck += extras
        else:
            deck = [(value, suit) for suit in suits for value in values]
        random.shuffle(deck)
        self.deck = deck

    def start_game(self):
        self.create_deck()
        if not self.deck:
            raise ValueError("O baralho está vazio.")
        self.trump_card = self.deck.pop()
        self.trump_suit = self.trump_card[1]
        self.history.append(f"Carta virada (Bebi): {self.trump_card}")
        self.history.append(f"Naipe principal: {self.trump_suit}")
        self.game_start_time = datetime.now()

    def deal_cards(self):
        num_cards = 3 if self.mode == 20 else 9
        self.hands = []
        if len(self.deck) < num_cards * 4:
            raise ValueError("Cartas insuficientes no baralho para distribuir.")
        for _ in range(4):
            hand = [self.deck.pop() for _ in range(num_cards)]
            self.hands.append(hand)
        return self.hands

    def add_player(self, player_socket, player_name):
        self.players.append(player_socket)
        self.player_names.append(player_name)

    def broadcast(self, message):
        for player in self.players:
            try:
                player.send(message.encode())
            except:
                pass

    def reveal_hands(self):
        hands_summary = "\n".join([f"Jogador {i+1}: {hand}" for i, hand in enumerate(self.hands)])
        self.broadcast(f"Cartas Distribuídas:\n{hands_summary}\n")
        self.history.append(f"Cartas distribuídas:\n{hands_summary}")
        self.broadcast(f"Carta Virada (Bebi): {self.trump_card}\n")
        self.broadcast(f"Naipe Principal: {self.trump_suit}\n")

    def card_value(self, card):
        # Define os valores para comparação das cartas
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
        Executa uma rodada. O jogador que enviar sua jogada manualmente informa sua carta
        no formato, por exemplo, 'Qe' para Q de Espadas.
        Se singleplayer, os demais jogadores jogam automaticamente.
        Em multiplayer, cada cliente deverá enviar sua jogada.
        """
        card_map = {'O': 'Ouros', 'E': 'Espadas', 'C': 'Copas', 'P': 'Paus'}
        if len(chosen_card) < 2:
            raise ValueError("Formato de carta inválido.")
        chosen_card_tuple = (chosen_card[0].upper(), card_map.get(chosen_card[1].upper()))
        if not chosen_card_tuple[1]:
            raise ValueError(f"Naipe inválido: {chosen_card[1]}")
        if chosen_card_tuple not in self.hands[player_index]:
            raise ValueError(f"A carta {chosen_card_tuple} não está na sua mão.")
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
        round_summary = "Rodada: " + ", ".join([f"Jogador {i+1}: {card}" for i, card in enumerate(current_round)])
        self.history.append(round_summary)
        self.broadcast(round_summary)
        try:
            winner = current_round.index(max(current_round, key=self.card_value))
        except Exception as e:
            winner = 0
        self.starting_player = winner
        self.montes[winner % 2] += 1
        reason = f"A carta {current_round[winner]} foi a maior."
        self.history.append(f"Dupla {winner % 2 + 1} venceu a rodada. Motivo: {reason}")
        self.broadcast(f"{round_summary}\nDupla {winner % 2 + 1} venceu. Motivo: {reason}\n")

    def end_game(self):
        self.game_end_time = datetime.now()
        winner_team = 1 if self.montes[0] > self.montes[1] else 2
        self.history.append(f"Dupla {winner_team} venceu a partida com placar {self.montes}")
        self.broadcast("Partida terminada!\n" + "\n".join(self.history))
        self.save_game_data()

    def save_game_data(self):
        filename = "game_data.csv"
        with open(filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(["Nome do Jogador", "Cartas Jogadas", "Início da Partida", "Término da Partida"])
            for i, name in enumerate(self.player_names):
                played_cards = " | ".join([str(card) for card in self.hands[i]])
                writer.writerow([
                    name,
                    played_cards,
                    self.game_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    self.game_end_time.strftime("%Y-%m-%d %H:%M:%S")
                ])

def handle_client(client_socket, game):
    try:
        # Primeiro: solicita o nome do jogador
        client_socket.send("Digite seu nome: ".encode())
        player_name = client_socket.recv(1024).decode().strip()
        game.add_player(client_socket, player_name)
        
        # Se for o primeiro cliente, exibe o menu para definir modo e modalidade
        if len(game.players) == 1:
            # Solicita o modo de jogo
            menu = ("Escolha o modo de jogo:\n"
                    "1. Jogar contra a máquina\n"
                    "2. Jogar multiplayer\n")
            client_socket.send(menu.encode())
            modo = int(client_socket.recv(1024).decode().strip())
            game.singleplayer = True if modo == 1 else False
            
            # Solicita a modalidade
            client_socket.send("Escolha a modalidade (digite 20 ou 52): ".encode())
            modalidade = int(client_socket.recv(1024).decode().strip())
            if modalidade not in [20, 52]:
                client_socket.send("Modalidade inválida. Encerrando conexão.".encode())
                client_socket.close()
                return
            game.mode = modalidade
        else:
            # Se for multiplayer e não for o primeiro cliente, apenas informa para aguardar
            if not game.singleplayer:
                client_socket.send("Aguardando início da partida...\n".encode())
                while len(game.players) < 4:
                    time.sleep(0.5)
        
        # Inicia o jogo quando o número necessário de jogadores for atingido
        if len(game.players) == (1 if game.singleplayer else 4) and game.game_start_time is None:
            game.start_game()
            hands = game.deal_cards()
            game.reveal_hands()
            for i, player in enumerate(game.players):
                player.send(f"Sua mão: {hands[i]}\n".encode())
                game.history.append(f"Jogador {i+1}: {hands[i]}")
        
        # Loop principal do jogo
        while True:
            # Para singleplayer, se a mão do jogador humano (índice 0) estiver vazia, encerra o jogo
            if game.singleplayer and not game.hands[0]:
                game.end_game()
                break
            client_socket.send("Escolha uma opção:\n1. Jogar próxima rodada\n2. Ver histórico\n3. Sair\n".encode())
            opcao = int(client_socket.recv(1024).decode().strip())
            if opcao == 1:
                # Solicita a carta do jogador
                client_socket.send("Digite a carta que deseja jogar (ex: Qe): ".encode())
                carta = client_socket.recv(1024).decode().strip().upper()
                idx = game.players.index(client_socket)
                try:
                    game.play_step(idx, carta)
                except Exception as err:
                    client_socket.send(f"Erro: {err}\nSua mão: {game.hands[idx]}\n".encode())
                    continue
            elif opcao == 2:
                client_socket.send(("Histórico da partida:\n" + "\n".join(game.history)).encode())
            elif opcao == 3:
                client_socket.send("Saindo...\n".encode())
                client_socket.close()
                break
    except Exception as e:
        try:
            client_socket.send(f"Erro: {e}".encode())
        except:
            pass
        client_socket.close()

def server():
    game = DouradoGame()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 12345))
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
    server()
