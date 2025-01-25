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

def client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 12345))

    threading.Thread(target=receive_messages, args=(client_socket,)).start()

    while True:
        msg = input("Digite sua escolha: ")
        if msg.lower() == 'sair':
            break
        client_socket.send(msg.encode())

    client_socket.close()

if __name__ == "__main__":
    client()
