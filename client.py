import socket
import threading
import time

# Configurações para descoberta UDP
UDP_PORT = 54321         # Deve ser igual à porta UDP definida no servidor
DISCOVER_MSG = "DISCOVER_SERVER"
TIMEOUT = 3              # Tempo em segundos para aguardar a resposta

def discover_server():
    """
    Envia uma mensagem de broadcast para descobrir o servidor e retorna o IP e porta do servidor encontrado.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.settimeout(TIMEOUT)
    try:
        udp_socket.sendto(DISCOVER_MSG.encode(), ('<broadcast>', UDP_PORT))
        data, addr = udp_socket.recvfrom(1024)
        response = data.decode()
        if response.startswith("SERVER_FOUND:"):
            tcp_port = int(response.split(":")[1])
            print(f"Servidor encontrado em {addr[0]} na porta {tcp_port}")
            return addr[0], tcp_port
    except socket.timeout:
        print("Nenhum servidor encontrado na rede.")
    finally:
        udp_socket.close()
    return None, None

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
    # Descobre o servidor na rede
    server_ip, server_port = discover_server()
    if not server_ip:
        print("Não foi possível localizar o servidor. Verifique se o servidor está ativo e na mesma rede.")
        return

    # Conecta ao servidor via TCP
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((server_ip, server_port))
    except Exception as e:
        print(f"Erro ao conectar no servidor: {e}")
        return
    
    # Recebe e responde à solicitação de nome
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
