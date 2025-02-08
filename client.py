import socket
import threading
import sys
import time

# Configurações de conexão
TCP_PORT = 12345
UDP_PORT = 54321
BROADCAST_MSG = "DISCOVER_SERVER"
DISCOVERY_TIMEOUT = 5  # tempo máximo para descoberta via UDP (em segundos)

def discover_server():
    """
    Realiza descoberta via UDP para encontrar o servidor.
    Envia uma mensagem broadcast e aguarda a resposta.
    Retorna uma tupla (server_ip, server_port) se encontrado ou (None, None) caso contrário.
    """
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.settimeout(DISCOVERY_TIMEOUT)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        udp_sock.sendto(BROADCAST_MSG.encode(), ('<broadcast>', UDP_PORT))
        data, addr = udp_sock.recvfrom(1024)
        response = data.decode()
        if response.startswith("SERVER_FOUND:"):
            tcp_port = int(response.split(":")[1])
            print(f"[DISCOVERY] Servidor encontrado em {addr[0]}:{tcp_port}")
            return addr[0], tcp_port
    except Exception as e:
        print(f"[DISCOVERY] Erro na descoberta UDP: {e}")
    finally:
        udp_sock.close()
    return None, None

def receive_messages(sock):
    """
    Thread responsável por receber mensagens do servidor e exibi-las.
    Caso o servidor encerre a conexão, informa o usuário e finaliza o programa.
    """
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                print("[SERVER] Conexão encerrada pelo servidor.")
                break
            # Exibe a mensagem recebida (pode conter instruções do jogo, histórico, etc.)
            print("\n" + data.decode() + "\n> ", end="", flush=True)
        except Exception as e:
            print(f"[RECEIVER] Erro ao receber dados: {e}")
            break
    print("[RECEIVER] Encerrando thread de recebimento.")
    sock.close()
    sys.exit()

def send_user_input(sock):
    """
    Thread responsável por ler a entrada do usuário e enviar os comandos para o servidor.
    Caso o usuário digite 'sair' ou 'exit', encerra a conexão.
    """
    print("\n[CLIENTE] Digite seus comandos conforme as instruções do jogo.")
    while True:
        try:
            # Exibe um prompt para o usuário
            message = input("> ").strip()
            if message.lower() in ["exit", "sair"]:
                print("[CLIENTE] Encerrando conexão...")
                sock.send(message.encode())
                break
            # Envia a mensagem digitada ao servidor
            sock.send(message.encode())
        except Exception as e:
            print(f"[SENDER] Erro ao enviar mensagem: {e}")
            break
    sock.close()
    sys.exit()

def main():
    # Tenta descobrir o servidor via UDP
    server_ip, server_port = discover_server()
    if server_ip is None:
        # Se não for possível a descoberta automática, solicita o IP manualmente.
        server_ip = input("Servidor não encontrado automaticamente. Digite o IP do servidor: ").strip()
        server_port = TCP_PORT

    print(f"[CLIENTE] Tentando conectar ao servidor em {server_ip}:{server_port}...")
    try:
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((server_ip, server_port))
        print("[CLIENTE] Conectado com sucesso!")
    except Exception as e:
        print(f"[CLIENTE] Erro ao conectar ao servidor: {e}")
        sys.exit(1)

    # Inicia a thread de recebimento de mensagens do servidor
    receiver_thread = threading.Thread(target=receive_messages, args=(tcp_sock,), daemon=True)
    receiver_thread.start()

    # A thread principal (ou uma separada) fica responsável por enviar as mensagens
    send_user_input(tcp_sock)

if __name__ == "__main__":
    main()
