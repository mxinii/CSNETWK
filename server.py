import socket
import json
import struct
import threading

HOST = "127.0.0.1"
PORT = 4444

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
print(f"[S] Listening on {HOST}:{PORT}")

connected_clients = []       
players = {}                 
lock = threading.Lock()  # to protect shared state

def send_pdu(sock, pdu: dict): #to send a PDU to the socket
    payload = json.dumps(pdu).encode("utf-8")
    length_prefix = struct.pack(">I", len(payload)) 
    sock.sendall(length_prefix + payload)

def recv_exact(sock, n): #to recv exact n bytes from socket
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

def broadcast_lobby_status():
    """Send every ready player an updated GAME_STATE_UPDATE (lobby variant)."""
    ready_ids = [p["player_id"] for p in players.values()] 
    all_ids = ["player_1", "player_2"]  
    waiting_for = [pid for pid in all_ids if pid not in ready_ids]

    for conn in players:
        send_pdu(conn, {
            "type": "GAME_STATE_UPDATE",
            "seq_num": 2, #todo: this is hardcoded for now, should be incremented per message
            "state": {
                "phase": "LOBBY",
                "players_ready": len(players),
                "waiting_for": waiting_for
            }
        })

def handle_player_ready(conn, pdu):
    player_id = pdu.get("player_id")
    deck_list = pdu.get("deck_list")

    #todo: Need to add rejection if card is not part of set. RFC 6.2 also requires rejecting decks with cards not in the legal card set. 
    if not deck_list or len(deck_list) > 50:
        send_pdu(conn, {
            "type": "ERROR",
            "seq_num": pdu.get("seq_num", 1),
            "code": "ILLEGAL_DECK",
            "message": f"Deck contains {len(deck_list) if deck_list else 0} cards; must be 1-50."
        })
        return

    with lock:
        # Reject a duplicate player_id 
        for other_conn, other_info in players.items():
            if other_conn != conn and other_info["player_id"] == player_id:
                send_pdu(conn, {
                    "type": "ERROR",
                    "seq_num": pdu.get("seq_num", 1),
                    "code": "DUPLICATE_ID",
                    "message": f"player_id '{player_id}' is already taken."
                })
                return

        players[conn] = {"player_id": player_id, "deck_list": deck_list}
        print(f"[S] {player_id} is ready with {len(deck_list)} cards ({len(players)}/2)")

    broadcast_lobby_status()

    if len(players) == 2:
        print("[S] Both players ready — would transition to GAME_SETUP here")
        # todo: implement GAME_SETUP (RFC Section 6.3):
        #   1. Validate both decks (already partly done)
        #   2. Set both life totals to 20
        #   3. Shuffle each deck 
        #   4. Draw 7 cards each
        #   5. Randomly pick who goes first (coin flip)
        #   6. Send each player a personalized GAME_STATE_UPDATE (Section 6.3
        #      example) showing their own hand + opponent's hand_count only
        #      (never reveal the opponent's actual hand: RFC 12, Confidentiality)
        #   7. Transition state to MULLIGAN (Section 6.4) and start handling
        #      MULLIGAN_CHOICE PDUs

def handle_client(conn, addr):
    print(f"[S] Handling client {addr}")
    try:
        while True:
            pdu = recv_pdu(conn)
            if pdu is None:
                print(f"[S] Client {addr} disconnected")
                #todo: RFC 4.2 states disconnect during a game should trigger GAME_OVER with reason DISCONNECT, broadcast to the OTHER
                # player. atm nothing is sent to the remaining player.
                break

            print(f"[S] Received: {pdu}")
            msg_type = pdu.get("type")

            if msg_type == "PING":
                send_pdu(conn, {"type": "PONG", "seq_num": pdu.get("seq_num", 0), "timestamp": pdu.get("timestamp", 0)})
            elif msg_type == "PLAYER_READY":
                handle_player_ready(conn, pdu)
            else:
                send_pdu(conn, {
                    "type": "ERROR",
                    "seq_num": pdu.get("seq_num", 0),
                    "code": "UNKNOWN_TYPE",
                    "message": f"Unhandled type: {msg_type}"
                })
    finally:
        conn.close()
        with lock:
            if conn in connected_clients:
                connected_clients.remove(conn)
            if conn in players:
                del players[conn]

while True:
    conn, addr = server_socket.accept()

    with lock:
        if len(connected_clients) >= 2:
            print(f"[S] Refusing extra connection from {addr}")
            conn.close()
            continue
        connected_clients.append(conn)

    print(f"[S] Accepted connection from {addr} ({len(connected_clients)}/2)")
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.daemon = True
    thread.start()