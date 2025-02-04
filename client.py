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

def discover_server():
    # Exibe o IP do computador para conexão manual
    hostname = socket.getfqdn()
    local_ips = socket.gethostbyname_ex(hostname)[2]
    print(f"Seu IP: {local_ips}")
    print("Caso a descoberta automática falhe, use um desses IPs no cliente remoto.")
    
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.settimeout(5)  # Timeout de 5 segundos
    server_ip = None
    try:
        udp_socket.sendto(b"DISCOVER", ('<broadcast>', 12346))
        data, addr = udp_socket.recvfrom(1024)
        server_ip = data.decode().strip()
    except socket.timeout:
        print("Não foi possível encontrar o servidor automaticamente.")
        server_ip = input("Digite o IP do servidor manualmente: ").strip()
    finally:
        udp_socket.close()
    return server_ip

def client():
    server_ip = discover_server()
    print(f"Conectando ao servidor em {server_ip}...")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, 12345))

    game_mode = choose_game_mode()
    client_socket.send(str(game_mode).encode())

    threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()

    while True:
        try:
            user_input = input()
            if user_input.strip().lower() == "sair":
                client_socket.send("3".encode())
                break
            else:
                client_socket.send(user_input.encode())
        except KeyboardInterrupt:
            break

    client_socket.close()

if __name__ == "__main__":
    client()