import socket
import threading
import random

class DouradoGame:
    def __init__(self):
        self.players = []
        self.deck = []
        self.current_hand = []
        self.trump_card = None
        self.trump_suit = None
        self.history = []
        self.mode = None
        self.hands = []
        self.montes = [0, 0]  # Contagem de montes por equipe
        self.starting_player = 0

    def create_deck(self, mode):
        suits = ['Ouros', 'Espadas', 'Copas', 'Paus']
        values = ['4', '5', '6', '7', 'Q', 'J', 'K', 'A', '2', '3']

        if mode == 20:
            trunfos = [
                ('3', 'Espadas'), ('Q', 'Copas'), ('2', 'Espadas'), ('3', 'Paus'), ('A', 'Ouros'),
                ('2', 'Paus'), ('A', 'Paus')
            ]
            values = ['J', 'Q', 'K']
            trunfos += [(value, suit) for suit in suits for value in values]
            self.deck = trunfos
        elif mode == 52:
            self.deck = [(value, suit) for suit in suits for value in values]
        else:
            raise ValueError("Modo de jogo inválido.")

        random.shuffle(self.deck)

    def start_game(self, mode):
        self.mode = mode
        self.create_deck(mode)
        if not self.deck:
            raise ValueError("O baralho está vazio.")
        self.trump_card = self.deck.pop()
        self.trump_suit = self.trump_card[1]
        self.history.append(f"Carta virada (Bebi): {self.trump_card}")
        self.history.append(f"Naipe principal: {self.trump_suit}")

    def deal_cards(self):
        num_cards = 3 if self.mode == 20 else 9
        self.hands = []

        if len(self.deck) < num_cards * 4:
            raise ValueError("Cartas insuficientes no baralho para distribuir.")

        for _ in range(4):
            hand = [self.deck.pop() for _ in range(num_cards)]
            self.hands.append(hand)

        return self.hands

    def add_player(self, player_socket):
        self.players.append(player_socket)

    def broadcast(self, message):
        for player in self.players:
            player.send(message.encode())

    def reveal_hands(self):
        hands_summary = "\n".join([f"Jogador {i+1}: {hand}" for i, hand in enumerate(self.hands)])
        self.broadcast(f"Cartas Distribuídas:\n{hands_summary}\n")
        self.history.append(f"Cartas distribuídas:\n{hands_summary}")
        self.broadcast(f"Carta Virada (Bebi): {self.trump_card}\n")
        self.broadcast(f"Naipe Principal: {self.trump_suit}\n")

    def play_step(self):
        if not all(self.hands):
            raise ValueError("Um dos jogadores está sem cartas para jogar.")

        current_round = [hand.pop() for hand in self.hands]
        round_summary = "Rodada: " + ", ".join([f"Jogador {i+1}: {card}" for i, card in enumerate(current_round)])
        self.history.append(round_summary)

        def card_value(card):
            values = {'4': 1, '5': 2, '6': 3, '7': 4, 'Q': 5, 'J': 6, 'K': 7, 'A': 8, '2': 9, '3': 10}
            value, suit = card

            if card == ('3', 'Espadas'):
                return 100  # 3 de Espadas é a mais forte

            if value == 'Q' and suit == self.trump_suit:
                return 98  # Dama do naipe principal é a segunda mais forte

            if value == 'A' and suit == self.trump_suit:
                return 97  # Ás do naipe principal é a terceira mais forte

            if suit == self.trump_suit:
                return 90 + values[value]  # Outras cartas do naipe principal

            return values[value]  # Cartas comuns

        winner = current_round.index(max(current_round, key=card_value))
        self.starting_player = winner
        self.montes[winner % 2] += 1

        reason = f"A carta {current_round[winner]} foi a maior."
        self.history.append(f"Dupla {winner % 2 + 1} venceu a rodada. Motivo: {reason}")
        self.broadcast(f"{round_summary}.\nDupla {winner % 2 + 1} venceu. Motivo: {reason}\n")

    def end_game(self):
        if self.montes[0] > self.montes[1]:
            winner_team = 1
        else:
            winner_team = 2

        self.history.append(f"Dupla {winner_team} venceu a partida com placar {self.montes}")
        self.broadcast("Partida terminada! Aqui está o histórico da partida:\n" + "\n".join(self.history))

def handle_client(client_socket, game):
    try:
        game.add_player(client_socket)
        client_socket.send("Escolha uma opção:\n1. Jogar normal (quatro pessoas)\n2. Jogar sozinho contra a máquina\n3. Jogar automático e aleatório\n".encode())
        game_mode = int(client_socket.recv(1024).decode().strip())

        client_socket.send("Escolha a modalidade (20 ou 52 cartas): ".encode())
        mode = int(client_socket.recv(1024).decode().strip())
        if mode not in [20, 52]:
            client_socket.send("Modalidade inválida. Tente novamente.".encode())
            return

        game.start_game(mode)
        hands = game.deal_cards()
        game.reveal_hands()

        for i, player in enumerate(game.players):
            player.send(f"Sua mão: {hands[i]}".encode())
            game.history.append(f"Jogador {i+1}: {hands[i]}")

        while game.hands[0]:
            client_socket.send("Escolha uma opção:\n1. Jogar próxima rodada\n2. Ver histórico\n3. Sair\n".encode())
            option = int(client_socket.recv(1024).decode().strip())
            if option == 1:
                game.play_step()
                if not game.hands[0]:
                    game.end_game()
            elif option == 2:
                client_socket.send("Histórico da partida:\n".encode())
                client_socket.send("\n".join(game.history).encode())
            elif option == 3:
                client_socket.close()
                break
    except Exception as e:
        client_socket.send(f"Erro: {e}".encode())
        client_socket.close()

def server():
    game = DouradoGame()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 12345))
    server_socket.listen(4)
    print("Servidor iniciado e esperando conexões...")

    while len(game.players) < 4:
        try:
            client_socket, addr = server_socket.accept()
            print(f"Conexão estabelecida com {addr}")
            threading.Thread(target=handle_client, args=(client_socket, game)).start()
        except KeyboardInterrupt:
            print("Servidor encerrado.")
            break

if __name__ == "__main__":
    server()
