import socket
import json
import struct
import time

HOST = "127.0.0.1"
PORT = 4444

# load card deck
with open("deck_list.json", "r") as f:
    cards = json.load(f)

# temporary deck for player
deck_list = list(cards.keys())[:50]

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

player_id = input("Enter player ID (player_1 or player_2): ")
player_ready = {
    "type": "PLAYER_READY",
    "seq_num": 1,
    "player_id": player_id,
    "deck_list": deck_list
}

# send PLAYER_READY
send_pdu(client_socket, player_ready)

# receive the lobby update
while True:
    reply = recv_pdu(client_socket)

    if reply is None:
        print("[C] Server disconnected.")
        break

    msg_type = reply.get("type")

    if msg_type == "GAME_STATE_UPDATE":
        state = reply.get("state", {})

        print(f"\n=== {state.get('phase')} ===")

        if state.get("phase") == "LOBBY":
            print(f"Players Ready: {state['players_ready']}")
            print(f"Waiting For: {state['waiting_for']}")

        elif state.get("phase") == "MULLIGAN":
            print(f"Turn: {state['turn']}")
            print(f"Active Player: {state['active_player']}")
            print(f"Life Totals: {state['life_totals']}")
            print(f"My Hand: {state['hand']}")
            print(f"Hand Counts: {state['hand_counts']}")
            print(f"Library Counts: {state['library_count']}")
            print(f"Battlefield: {state['battlefield']}")
            print(f"Graveyard: {state['graveyard']}")
            print(f"Stack: {state['stack']}")

    elif msg_type == "PONG":
        print("[C] Received PONG")

    elif msg_type == "ERROR":
        print(f"[ERROR] {reply['code']}: {reply['message']}")

    else:
        print(f"[C] Received: {reply}")

client_socket.close()
print("[C] Socket closed")