import socket
import threading

def receive_messages(client_socket):
    while True:
        try:
            message = client_socket.recv(1024).decode()
            if message:
                print(f"\n{message}\n")
            else:
                break
        except:
            client_socket.close()
            break

def choose_game_mode():
    print("Escolha o modo de jogo:")
    print("1. Jogar contra a máquina")
    print("2. Jogar multiplayer")
    choice = input("Escolha 1 ou 2: ").strip()
    return int(choice)

def client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 12345))
    
    # Envia a escolha do modo para o servidor
    game_mode = choose_game_mode()
    client_socket.send(str(game_mode).encode())
    
    # Inicia uma thread para receber mensagens do servidor
    threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()
    
    # Loop principal: envia as entradas do usuário para o servidor
    while True:
        try:
            user_input = input()  # Aguarda o usuário digitar
            if user_input.strip().lower() == "sair":
                client_socket.send("3".encode())  # Envia opção de sair
                break
            else:
                client_socket.send(user_input.encode())
        except KeyboardInterrupt:
            break
    
    client_socket.close()

if __name__ == "__main__":
    client()
import socket
import threading

def receive_messages(client_socket):
    while True:
        try:
            message = client_socket.recv(1024).decode()
            if message:
                print(f"\n{message}\n")
            else:
                break
        except:
            client_socket.close()
            break

def choose_game_mode():
    print("Escolha o modo de jogo:")
    print("1. Jogar contra a máquina")
    print("2. Jogar multiplayer")
    choice = input("Escolha 1 ou 2: ").strip()
    return int(choice)

def client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 12345))
    
    # Envia a escolha do modo para o servidor
    game_mode = choose_game_mode()
    client_socket.send(str(game_mode).encode())
    
    # Inicia uma thread para receber mensagens do servidor
    threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()
    
    # Loop principal: envia as entradas do usuário para o servidor
    while True:
        try:
            user_input = input()  # Aguarda o usuário digitar
            if user_input.strip().lower() == "sair":
                client_socket.send("3".encode())  # Envia opção de sair
                break
            else:
                client_socket.send(user_input.encode())
        except KeyboardInterrupt:
            break
    
    client_socket.close()

if __name__ == "__main__":
    client()
