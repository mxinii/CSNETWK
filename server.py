import socket
import json
import struct
import threading
import random

HOST = "127.0.0.1"
PORT = 4444

# global game_phase
game_phase = "LOBBY"
# server seq num
server_seq_num = 0

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
print(f"[S] Listening on {HOST}:{PORT}")

# load card deck
with open("deck_list.json", "r") as f:
    cards = json.load(f)

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
    global server_seq_num
    """Send every ready player an updated GAME_STATE_UPDATE (lobby variant)."""
    ready_ids = [p["player_id"] for p in players.values()] 
    all_ids = ["player_1", "player_2"]  
    waiting_for = [pid for pid in all_ids if pid not in ready_ids]

    for conn in players:
        server_seq_num += 1

        send_pdu(conn, {
            "type": "GAME_STATE_UPDATE",
            "seq_num": server_seq_num,
            "state": {
                "phase": "LOBBY",
                "players_ready": len(players),
                "waiting_for": waiting_for
            }
        })

def handle_player_ready(conn, pdu):
    global game_phase

    if game_phase != "LOBBY":
        send_pdu(conn, {
            "type": "ERROR",
            "seq_num": pdu.get("seq_num", 1),
            "code": "INVALID_STATE",
            "message": "PLAYER_READY is only allowed while in the LOBBY."
        })
        return
    
    player_id = pdu.get("player_id")
    deck_list = pdu.get("deck_list")

    # validate deck
    if not isinstance(deck_list, list):
        send_pdu(conn, {
            "type": "ERROR",
            "seq_num": pdu.get("seq_num", 1),
            "code": "ILLEGAL_DECK",
            "message": "Deck list is missing or invalid."
        })
        return

    # validate deck size
    if len(deck_list) < 1 or len(deck_list) > 50:
        send_pdu(conn, {
        "type": "ERROR",
        "seq_num": pdu.get("seq_num", 1),
        "code": "ILLEGAL_DECK",
        "message": f"Deck contains {len(deck_list)} cards; must be 1-50."
    })
        return

    # validate every card ID
    illegal_cards = [
        card_id
        for card_id in deck_list
        if card_id not in cards
    ]

    if illegal_cards:
        send_pdu(conn, {
        "type": "ERROR",
        "seq_num": pdu.get("seq_num", 1),
        "code": "ILLEGAL_DECK",
        "message": f"Unknown card IDs: {', '.join(illegal_cards)}"
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

        players[conn] = {
            "player_id": player_id, 
            "deck_list": deck_list,
            "library": [],
            "hand": [],
            "life": 20
            }
        print(f"[S] {player_id} is ready with {len(deck_list)} cards ({len(players)}/2)")

    broadcast_lobby_status()

    if len(players) == 2:
        game_phase = "GAME_SETUP"
        print("[S] Both players ready — would transition to GAME_SETUP here")
        start_game_setup()

def start_game_setup():
    global game_phase
    global server_seq_num

    game_phase = "GAME_SETUP"
    print("[S] Starting GAME_SETUP")

    #initialize player life to 20
    for player in players.values():
        player["life"] = 20

    # shuffle deck
    for player in players.values():
        player["library"] = player["deck_list"][:]
        random.shuffle(player["library"])

    # draw seven cards
    for player in players.values():
        player["hand"] = []

        while player["library"] and len(player["hand"]) < 7:
            player["hand"].append(player["library"].pop())

    # choose player to start
    starting_conn = random.choice(list(players.keys()))

    for conn, player in players.items():
        player["is_starting_player"] = (conn == starting_conn)

    # send game state update
    for conn, player in players.items():
        server_seq_num += 1

        send_pdu(conn,{
            "type":"GAME_STATE_UPDATE",
            "seq_num":server_seq_num,
            "state": {
                # setup complete, transitioned to MULLIGAN
                "turn": 0,
                "phase": "MULLIGAN",

                # starting player / player inplay
                "active_player": players[starting_conn]["player_id"],

                "life_totals": {
                    info["player_id"]: info["life"]
                    for info in players.values()
                },
            # personalized player's hand
            "hand":player["hand"],
            
            "hand_counts": {
                info["player_id"]: len(info["hand"])
                for info in players.values()
            },
            "library_count":{
                info["player_id"]: len(info["library"])
                for info in players.values()
            },
            "battlefield": {
                info["player_id"]: []
                for info in players.values()
            },
            "graveyard": {
                info["player_id"]: []
                for info in players.values()
            },
            "stack": []
            }
        })

    game_phase = "MULLIGAN"
    print("[S] Transitioned to MULLIGAN")

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

            if len(players) == 1:
                send_pdu(conn, {
                    "type":      "GAME_OVER",
                    "seq_num":   pdu.get("seq_num", 0),
                    "winner_id": "player_1",
                    "loser_id":  "player_2",
                    "reason":    "DISCONNECT"
                    })

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