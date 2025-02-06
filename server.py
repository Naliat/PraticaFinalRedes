import socket
import threading
import random
import csv
import time
from datetime import datetime

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
    if winning_team == 1:
        indices = [0, 2]
    else:
        indices = [1, 3]
    for i in indices:
        if i < len(game.player_names):
            nome = game.player_names[i]
            RANKING[nome] = RANKING.get(nome, 0) + 1

def obter_ranking_formatado():
    if not RANKING:
        return "Ranking vazio."
    ranking_str = "Ranking em Tempo Real:\n"
    for nome, pontos in sorted(RANKING.items(), key=lambda x: x[1], reverse=True):
        ranking_str += f"{nome}: {pontos} vitória(s)\n"
    return ranking_str

# ------------------------------------------
# Classe do Jogo
# ------------------------------------------
class DouradoGame:
    def __init__(self, mode=20, singleplayer=False):
        self.players = []             # Sockets dos jogadores
        self.deck = []                # Baralho de cartas
        self.trump_card = None        # Carta virada (Bebi)
        self.trump_suit = None        # Naipe principal
        self.history = []             # Histórico da partida (rounds)
        self.mode = mode              # Modalidade: 20 ou 52 cartas
        self.hands = []               # Mãos dos jogadores (lista de listas)
        self.montes = [0, 0]          # Pontuação por dupla
        self.starting_player = 0      # Índice do jogador vencedor da rodada
        self.game_start_time = None
        self.game_end_time = None
        self.player_names = []        # Lista com os nomes dos jogadores
        self.played_cards = []        # Lista de rounds (cada round: lista de 4 cartas)
        self.cards_played = {}        # Dicionário: {nome: [cartas jogadas]}
        self.singleplayer = singleplayer
        self.finished = False         # Flag para indicar fim de partida
        self.lock = threading.Lock()  # Lock para sincronização

    def create_deck(self):
        """Cria o baralho conforme a modalidade."""
        suits = ['Ouros', 'Espadas', 'Copas', 'Paus']
        # Aqui usamos um conjunto de valores para todas as cartas.
        values = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'Q', 'J', 'K', 'A']
        if self.mode == 20:
            # Exemplo: usar apenas figuras (K, J, Q, A) + extras
            deck = [card for card in [(value, suit) for suit in suits for value in values]
                    if card[0] in ['K', 'J', 'Q', 'A']]
            extras = [('3', 'Espadas'), ('3', 'Paus'), ('2', 'Paus'), ('2', 'Espadas')]
            deck += extras
        else:
            deck = [(value, suit) for suit in suits for value in values]
        random.shuffle(deck)
        self.deck = deck

    def start_game(self):
        """Inicializa o jogo: cria o baralho, define a carta virada e registra o início."""
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
        """Distribui as cartas para os 4 jogadores."""
        num_cards = 3 if self.mode == 20 else 9
        self.hands = []
        if len(self.deck) < num_cards * 4:
            raise ValueError("Cartas insuficientes para distribuir.")
        for _ in range(4):
            hand = [self.deck.pop() for _ in range(num_cards)]
            self.hands.append(hand)
        return self.hands

    def add_player(self, player_socket, player_name):
        """Adiciona um jogador e inicializa seu registro de cartas jogadas."""
        with self.lock:
            self.players.append(player_socket)
            self.player_names.append(player_name)
            self.cards_played[player_name] = []

    def broadcast(self, message):
        """Envia mensagem para todos os jogadores."""
        for player in self.players:
            try:
                player.send(message.encode())
            except Exception:
                pass

    def format_card(self, card):
        """Formata a carta para exibição: <valor> de <naipe>."""
        value, suit = card
        value_map = {
            '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
            '6': '6', '7': '7', '8': '8', '9': '9', '10': '10',
            'Q': 'Dama', 'J': 'Valete', 'K': 'Rei', 'A': 'Ás'
        }
        return f"{value_map.get(value, value)} de {suit}"

    def reveal_hands(self):
        """Envia a todos os jogadores as mãos distribuídas."""
        hands_summary = "\n".join(
            [f"Jogador {i+1}: {', '.join([self.format_card(c) for c in hand])}"
             for i, hand in enumerate(self.hands)]
        )
        self.broadcast(f"Cartas Distribuídas:\n{hands_summary}\n")
        self.history.append(f"Cartas distribuídas:\n{hands_summary}")
        self.broadcast(f"Carta Virada (Bebi): {self.format_card(self.trump_card)}\n")
        self.broadcast(f"Naipe Principal: {self.trump_suit}\n")
        # Imprime no terminal do servidor:
        print("[GAME] Mãos distribuídas:")
        print(hands_summary)

    def card_value(self, card):
        """Define o valor para comparação das cartas."""
        values = {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
                  '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
                  'Q': 11, 'J': 12, 'K': 13, 'A': 14}
        # Se for o "3 de Espadas", ele vale 100.
        if card == ('3', 'Espadas'):
            return 100
        # Se a carta for do naipe principal (trump), adiciona bônus.
        value, suit = card
        if suit == self.trump_suit:
            return 90 + values.get(value, 0)
        return values.get(value, 0)

    def play_step(self, player_index, chosen_card):
        """
        Executa uma jogada. O jogador deve informar a carta no formato <valor><inicial do naipe>.
        Exemplos:
          - "1e" → 1 de Espadas  
          - "Ae" → Ás de Espadas  
          - "Ve" → Valete de Espadas (V é convertido para J)  
          - "Rc" → Rei de Copas (R é convertido para K)  
          - "auto" → jogada automática
        """
        # Mapeamento para naipes (E: Espadas, O: Ouros, C: Copas, P: Paus)
        card_map = {'E': 'Espadas', 'O': 'Ouros', 'C': 'Copas', 'P': 'Paus'}
        # Mapeamento para valores abreviados (figuras):
        rank_map = {'R': 'K', 'D': 'Q', 'V': 'J'}
        if chosen_card.lower() == 'auto':
            if not self.hands[player_index]:
                raise ValueError("Sua mão está vazia!")
            chosen_card_tuple = random.choice(self.hands[player_index])
        else:
            if len(chosen_card) < 2:
                raise ValueError("Formato inválido. Exemplo: 'Rc' para Rei de Copas.")
            # O valor pode ter mais de um dígito, então pegamos todos os caracteres, exceto o último.
            raw_value = chosen_card[:-1]
            suit_letter = chosen_card[-1].upper()
            # Converte se for atalho de figura:
            if raw_value.upper() in rank_map:
                value = rank_map[raw_value.upper()]
            else:
                value = raw_value  # mantém o que foi digitado (ex: "1", "2", etc.)
            suit = card_map.get(suit_letter)
            if not suit:
                raise ValueError(f"Naipe inválido: {chosen_card[-1]}")
            chosen_card_tuple = (value, suit)
            if chosen_card_tuple not in self.hands[player_index]:
                raise ValueError(f"A carta {self.format_card(chosen_card_tuple)} não está na sua mão.")
        # Remove a carta da mão do jogador
        self.hands[player_index].remove(chosen_card_tuple)
        # Registra a jogada
        nome = self.player_names[player_index]
        self.cards_played[nome].append(chosen_card_tuple)
        # Prepara a rodada (lista com 4 posições)
        current_round = [None] * 4
        current_round[player_index] = chosen_card_tuple
        # Para os demais jogadores, se tiverem cartas, executa jogada simulada/aleatória
        for i in range(4):
            if i != player_index:
                if not self.hands[i]:
                    continue
                if self.singleplayer:
                    card_i = self.hands[i].pop(random.randrange(len(self.hands[i])))
                else:
                    card_i = self.hands[i].pop()  # Jogada simulada
                current_round[i] = card_i
                nome_i = self.player_names[i]
                self.cards_played[nome_i].append(card_i)
        self.played_cards.append(current_round)
        # Monta o resumo da rodada (somente para jogadores que jogaram)
        round_summary = "Rodada: " + ", ".join(
            [f"Jogador {i+1}: {self.format_card(card)}" 
             for i, card in enumerate(current_round) if card is not None]
        )
        self.history.append(round_summary)
        self.broadcast(round_summary)
        # Também imprime no terminal do servidor:
        print("[GAME] " + round_summary)
        # Determina o vencedor da rodada
        try:
            cartas_validas = [card for card in current_round if card is not None]
            vencedor = current_round.index(max(cartas_validas, key=self.card_value))
        except Exception:
            vencedor = 0
        self.starting_player = vencedor
        self.montes[vencedor % 2] += 1
        reason = f"A carta {self.format_card(current_round[vencedor])} foi a maior."
        win_msg = f"Dupla {vencedor % 2 + 1} venceu a rodada. Motivo: {reason}"
        self.history.append(win_msg)
        self.broadcast(win_msg)
        print("[GAME] " + win_msg)

    def end_game(self):
        """Finaliza a partida, atualiza ranking, salva dados e notifica os jogadores."""
        self.game_end_time = datetime.now()
        winner_team = 1 if self.montes[0] > self.montes[1] else 2
        final_msg = f"Dupla {winner_team} venceu a partida com placar {self.montes}"
        self.history.append(final_msg)
        atualizar_ranking(self, winner_team)
        msg_final = "Partida terminada!\n" + "\n".join(self.history) + "\n" + obter_ranking_formatado()
        self.broadcast(msg_final)
        # Imprime o resumo final no terminal do servidor:
        print("[GAME] " + msg_final)
        self.save_game_data()
        self.finished = True

    def save_game_data(self):
        """Salva os dados da partida em 'game_data.csv' (nome, cartas jogadas, início e término)."""
        filename = "game_data.csv"
        with open(filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(["Nome do Jogador", "Cartas Jogadas", "Início da Partida", "Término da Partida"])
            for nome in self.player_names:
                jogadas = " | ".join([self.format_card(card) for card in self.cards_played.get(nome, [])])
                inicio = self.game_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.game_start_time else ""
                fim = self.game_end_time.strftime("%Y-%m-%d %H:%M:%S") if self.game_end_time else ""
                writer.writerow([nome, jogadas, inicio, fim])

    def reset_game(self):
        """Reinicializa os dados internos para uma nova partida (mantendo os sockets conectados)."""
        with self.lock:
            self.deck = []
            self.trump_card = None
            self.trump_suit = None
            self.history = []
            self.hands = []
            self.montes = [0, 0]
            self.starting_player = 0
            self.game_start_time = None
            self.game_end_time = None
            self.played_cards = []
            self.cards_played = {}
            self.finished = False
            # Os nomes dos jogadores e os sockets permanecem.

# Método auxiliar para obter a mão do jogador de forma legível.
def get_hand(self, player_index):
    return ', '.join([self.format_card(card) for card in self.hands[player_index]])
DouradoGame.get_hand = get_hand

# ------------------------------------------
# Função para lidar com cada cliente
# ------------------------------------------
def handle_client(client_socket, game):
    try:
        # Solicita e registra o nome do jogador
        client_socket.send("Digite seu nome: ".encode())
        player_name = client_socket.recv(1024).decode().strip()
        game.add_player(client_socket, player_name)
        
        # Se for o primeiro jogador, define modo e modalidade
        if len(game.players) == 1:
            menu_inicial = ("Escolha o modo de jogo:\n"
                            "1. Jogar contra a máquina\n"
                            "2. Jogar multiplayer\n")
            client_socket.send(menu_inicial.encode())
            try:
                modo = int(client_socket.recv(1024).decode().strip())
            except:
                client_socket.send("Entrada inválida. Encerrando conexão.\n".encode())
                return
            game.singleplayer = True if modo == 1 else False
            client_socket.send("Escolha a modalidade (digite 20 ou 52): ".encode())
            try:
                modalidade = int(client_socket.recv(1024).decode().strip())
            except:
                client_socket.send("Entrada inválida. Encerrando conexão.\n".encode())
                return
            if modalidade not in [20, 52]:
                client_socket.send("Modalidade inválida. Encerrando conexão.\n".encode())
                return
            game.mode = modalidade
            game.start_game()
            game.deal_cards()
            game.reveal_hands()
        else:
            # Para os demais jogadores:
            if game.singleplayer:
                client_socket.send("Aguardando início da partida...\n".encode())
            else:
                client_socket.send(f"Você entrou na partida como Jogador {len(game.players)}.\n".encode())
                if len(game.players) == 4:
                    game.start_game()
                    game.deal_cards()
                    game.reveal_hands()
        
        # Aguarda que a mão esteja pronta e a envia
        idx = game.players.index(client_socket)
        while len(game.hands) <= idx:
            time.sleep(0.1)
        client_socket.send(f"Sua mão: {game.get_hand(idx)}\n".encode())
        
        # Loop principal de interação com o cliente
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
            client_socket.send(menu.encode())
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
                    client_socket.send("Digite a carta (ex: Rc para Rei de Copas ou 'auto'): ".encode())
                    carta = client_socket.recv(1024).decode().strip()
                    try:
                        game.play_step(idx, carta)
                        # Atualiza a mão de todos os jogadores
                        for player in game.players:
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
                        for player in game.players:
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
        # Fim do loop de interação
    except Exception as e:
        print(f"Erro no handle_client: {str(e)}")
    finally:
        client_socket.close()

# ------------------------------------------
# Função Principal do Servidor
# ------------------------------------------
def server():
    game = DouradoGame()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', TCP_PORT))
    server_socket.listen(4)
    print("Servidor TCP iniciado na porta", TCP_PORT)
    while True:
        try:
            client_socket, addr = server_socket.accept()
            with game.lock:
                if game.finished:
                    # Se o jogo terminou, cria um novo objeto para uma nova partida.
                    game = DouradoGame()
            print(f"[TCP] Conexão estabelecida com {addr}")
            threading.Thread(target=handle_client, args=(client_socket, game), daemon=True).start()
        except KeyboardInterrupt:
            print("Servidor encerrado.")
            break

if __name__ == "__main__":
    threading.Thread(target=udp_discovery, daemon=True).start()
    server()
