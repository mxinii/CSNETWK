import socket
import json
import struct
import time

HOST = "127.0.0.1"
PORT = 4444

def send_pdu(sock, pdu: dict):
    payload = json.dumps(pdu).encode("utf-8")
    length_prefix = struct.pack(">I", len(payload))
    sock.sendall(length_prefix + payload)

def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def recv_pdu(sock):
    length_bytes = recv_exact(sock, 4)
    if length_bytes is None:
        return None
    length = struct.unpack(">I", length_bytes)[0]
    payload = recv_exact(sock, length)
    if payload is None:
        return None
    return json.loads(payload.decode("utf-8"))

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))
print(f"[C] Connected to server at {HOST}:{PORT}")

# for testing ping pong
ping = {"type": "PING", "seq_num": 1, "timestamp": int(time.time() * 1000)}
send_pdu(client_socket, ping)
print(f"[C] Sent: {ping}")

reply = recv_pdu(client_socket)
print(f"[C] Received: {reply}")

client_socket.close()
print(f"[C] Socket closed")