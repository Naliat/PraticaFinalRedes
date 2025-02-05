import socket
import threading
import time

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
    
    # Recebe e responde a solicitação de nome
    name_prompt = client_socket.recv(1024).decode()
    print(name_prompt)
    name = input()
    client_socket.send(name.encode())
    
    # Se for o primeiro cliente, o servidor solicitará o modo e a modalidade
    try:
        mode_menu = client_socket.recv(1024).decode()
        if mode_menu.strip():
            print(mode_menu)
            mode = input()
            client_socket.send(mode.encode())
            
            modality_prompt = client_socket.recv(1024).decode()
            print(modality_prompt)
            modality = input()
            client_socket.send(modality.encode())
    except Exception as e:
        pass

    # Inicia a thread para receber mensagens do servidor
    threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()
    
    # Aguarda um instante para garantir que o servidor envie as cartas
    time.sleep(1)
    # Solicita automaticamente para ver a mão (opção 3)
    client_socket.send("3".encode())
    
    # Loop principal para enviar comandos ao servidor
    while True:
        try:
            # O usuário pode digitar diretamente as opções do menu que o servidor envia:
            # 1. Jogar próxima rodada
            # 2. Ver histórico
            # 3. Ver minha mão
            # 4. Jogar automaticamente
            # 5. Sair
            user_input = input()
            if user_input.strip().lower() == "sair":
                client_socket.send("5".encode())  # Envia opção 5 para sair
                break
            else:
                client_socket.send(user_input.encode())
        except KeyboardInterrupt:
            break
    
    client_socket.close()

if __name__ == "__main__":
    client()
