import socket
import json
import struct
import threading
import random
import argparse
import datetime

HOST = "127.0.0.1"
PORT = 4444

# --- verbose mode setup ---
# Parse --verbose / -v at startup. VERBOSE is a module-level flag that every
# send_pdu/recv_pdu call checks before printing. Toggled only via the CLI flag
# for now (RFC just requires it be toggleable at runtime via startup argument).
parser = argparse.ArgumentParser(description="MTGNP Game Server")
parser.add_argument("-v", "--verbose", action="store_true",
                     help="Print every PDU sent/received to the console")
args = parser.parse_args()
VERBOSE = args.verbose

def log_pdu(direction: str, peer_label: str, pdu: dict):
    """Print a clearly-labelled, readable line for every PDU when verbose mode is on.
    direction: 'SEND' or 'RECV'
    peer_label: human-readable identifier for the other end (e.g. 'player_1' or address tuple)
    """
    if not VERBOSE:
        return
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    label = f"S->{peer_label}" if direction == "SEND" else f"{peer_label}->S"
    print(f"[VERBOSE {timestamp}] [{label}] {json.dumps(pdu)}")

# global game_phase
game_phase = "LOBBY"
# server seq num
server_seq_num = 0

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
print(f"[S] Listening on {HOST}:{PORT}")

# load card deck
with open("deck_list.json", "r") as f:
    cards = json.load(f)

connected_clients = []       
players = {}                 
lock = threading.Lock()  # to protect shared state

def get_peer_label(sock):
    """Prefer the player_id if this connection has registered one; fall back to address."""
    info = players.get(sock)
    if info and info.get("player_id"):
        return info["player_id"]
    try:
        addr = sock.getpeername()
        return f"{addr[0]}:{addr[1]}"
    except OSError:
        return "unknown"

def send_pdu(sock, pdu: dict): #to send a PDU to the socket
    log_pdu("SEND", get_peer_label(sock), pdu)
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
    pdu = json.loads(payload.decode("utf-8"))
    log_pdu("RECV", get_peer_label(sock), pdu)
    return pdu

def broadcast_lobby_status():
    global server_seq_num
    """Send every ready player an updated GAME_STATE_UPDATE (lobby variant)."""
    with lock:
        ready_ids = [p["player_id"] for p in players.values()]
        snapshot_conns = list(players.keys())
    all_ids = ["player_1", "player_2"]
    waiting_for = [pid for pid in all_ids if pid not in ready_ids]

    for conn in snapshot_conns:
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

    should_start_setup = False
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
            "life": 20,
            "mulligan_count": 0,
            "kept": False,
            "last_state_seq_num": None
            }
        print(f"[S] {player_id} is ready with {len(deck_list)} cards ({len(players)}/2)")

        # Decide the LOBBY -> GAME_SETUP transition while still holding the lock so
        # exactly one of the two client threads (whichever inserts the 2nd player)
        # triggers start_game_setup(), never both concurrently.
        if len(players) == 2 and game_phase == "LOBBY":
            game_phase = "GAME_SETUP"
            should_start_setup = True

    broadcast_lobby_status()

    if should_start_setup:
        print("[S] Both players ready — transitioning to GAME_SETUP")
        start_game_setup()

def get_starting_player_id():
    """Look up which player was chosen to go first (set once in start_game_setup)."""
    for info in players.values():
        if info.get("is_starting_player"):
            return info["player_id"]
    return None

def build_personalized_mulligan_state(player):
    """Build the MULLIGAN-phase state object personalized for one player.
    Used both for the initial post-setup broadcast and for post-redraw updates."""
    return {
        "turn": 0,
        "phase": "MULLIGAN",
        "active_player": get_starting_player_id(),
        "life_totals": {
            info["player_id"]: info["life"]
            for info in players.values()
        },
        "hand": player["hand"],
        "hand_counts": {
            info["player_id"]: len(info["hand"])
            for info in players.values()
            if info is not player
        },
        "library_counts": {
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

def start_game_setup():
    global game_phase
    global server_seq_num

    print("[S] Starting GAME_SETUP")

    with lock:
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

        # Flip to MULLIGAN before sending, since a fast client could otherwise reply
        # before the server considers itself out of GAME_SETUP.
        game_phase = "MULLIGAN"

        # send personalized game state update to each player
        for conn, player in players.items():
            server_seq_num += 1
            player["last_state_seq_num"] = server_seq_num

            send_pdu(conn, {
                "type": "GAME_STATE_UPDATE",
                "seq_num": server_seq_num,
                "state": build_personalized_mulligan_state(player)
            })

    print("[S] Transitioned to MULLIGAN")

def redraw_hand(player):
    """London Mulligan redraw: shuffle hand back into library, reshuffle, draw a fresh 7."""
    player["library"].extend(player["hand"])
    player["hand"] = []
    random.shuffle(player["library"])
    while player["library"] and len(player["hand"]) < 7:
        player["hand"].append(player["library"].pop())

def check_mulligan_complete():
    """If both players have kept, transition to IN_GAME and start Turn 1's Untap Step.
    Caller must hold `lock`."""
    global game_phase, server_seq_num

    if len(players) != 2 or not all(info.get("kept") for info in players.values()):
        return

    game_phase = "IN_GAME"
    starting_id = get_starting_player_id()
    print("[S] Both players kept — transitioning to IN_GAME (Turn 1, UNTAP)")

    for conn in list(players.keys()):
        server_seq_num += 1
        send_pdu(conn, {
            "type": "PHASE_TRANSITION",
            "seq_num": server_seq_num,
            "from_phase": "MULLIGAN",
            "to_phase": "UNTAP",
            "active_player": starting_id,
            "turn": 1
        })

def handle_mulligan_choice(conn, pdu):
    """Handle a MULLIGAN_CHOICE PDU per RFC Section 6.4."""
    global server_seq_num

    if game_phase != "MULLIGAN":
        send_pdu(conn, {
            "type": "ERROR",
            "seq_num": pdu.get("seq_num", 0),
            "code": "WRONG_PHASE",
            "message": "MULLIGAN_CHOICE is only allowed during the MULLIGAN phase.",
            "rejected_action": pdu
        })
        return

    with lock:
        player = players.get(conn)
        if player is None:
            return

        # seq_num must echo the most recently sent GAME_STATE_UPDATE for this player
        expected_seq = player.get("last_state_seq_num")
        if pdu.get("seq_num") != expected_seq:
            send_pdu(conn, {
                "type": "ERROR",
                "seq_num": pdu.get("seq_num", 0),
                "code": "STALE_ACTION",
                "message": f"Priority token mismatch. Expected seq_num {expected_seq}, got {pdu.get('seq_num')}.",
                "rejected_action": pdu
            })
            return

        keep = pdu.get("keep")
        cards_to_bottom = pdu.get("cards_to_bottom", [])

        if keep:
            mulligan_count = player["mulligan_count"]

            # cards_to_bottom must contain exactly N card IDs, all currently in hand
            if not isinstance(cards_to_bottom, list) or len(cards_to_bottom) != mulligan_count:
                send_pdu(conn, {
                    "type": "ERROR",
                    "seq_num": pdu.get("seq_num", 0),
                    "code": "ILLEGAL_ACTION",
                    "message": f"cards_to_bottom must contain exactly {mulligan_count} card ID(s); got {len(cards_to_bottom) if isinstance(cards_to_bottom, list) else 'invalid'}.",
                    "rejected_action": pdu
                })
                return

            hand_check = list(player["hand"])
            for card_id in cards_to_bottom:
                if card_id not in hand_check:
                    send_pdu(conn, {
                        "type": "ERROR",
                        "seq_num": pdu.get("seq_num", 0),
                        "code": "ILLEGAL_ACTION",
                        "message": f"Card '{card_id}' is not in hand.",
                        "rejected_action": pdu
                    })
                    return
                hand_check.remove(card_id)  # guards against listing the same card twice

            # apply: remove from hand, place on bottom of library
            for card_id in cards_to_bottom:
                player["hand"].remove(card_id)
                player["library"].insert(0, card_id)

            player["kept"] = True
            print(f"[S] {player['player_id']} kept their hand"
                  + (f", bottomed {len(cards_to_bottom)} card(s)." if cards_to_bottom else "."))

            check_mulligan_complete()

        else:
            player["mulligan_count"] += 1
            redraw_hand(player)

            server_seq_num += 1
            player["last_state_seq_num"] = server_seq_num
            send_pdu(conn, {
                "type": "GAME_STATE_UPDATE",
                "seq_num": server_seq_num,
                "state": build_personalized_mulligan_state(player)
            })
            print(f"[S] {player['player_id']} mulliganed (count={player['mulligan_count']}), redrew 7 cards.")

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

            msg_type = pdu.get("type")

            if msg_type == "PING":
                send_pdu(conn, {"type": "PONG", "seq_num": pdu.get("seq_num", 0), "timestamp": pdu.get("timestamp", 0)})
            elif msg_type == "PLAYER_READY":
                handle_player_ready(conn, pdu)
            elif msg_type == "MULLIGAN_CHOICE":
                handle_mulligan_choice(conn, pdu)
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
