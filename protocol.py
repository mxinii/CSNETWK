"""Shared MTGNP v1.0 wire codec and PDU envelope validation."""
import json
import struct

MAX_PDU_SIZE = 65_535
PDU_TYPES = frozenset({
    "PLAYER_READY", "GAME_STATE_UPDATE", "MULLIGAN_CHOICE", "PHASE_TRANSITION",
    "PRIORITY_GRANT", "PRIORITY_PASS", "CAST_SPELL", "ACTIVATE_ABILITY", "STACK_PUSH",
    "TRIGGER_ORDER", "TRIGGER_ORDER_RESPONSE", "TRIGGER_CHOICE", "TRIGGER_CHOICE_RESPONSE",
    "STACK_RESOLVE", "DECLARE_ATTACKERS", "DECLARE_BLOCKERS", "ASSIGN_DAMAGE_ORDER",
    "COMBAT_DAMAGE_RESULT", "PLAY_LAND", "DISCARD", "CONCEDE", "GAME_OVER", "ERROR",
    "PING", "PONG",
})

class ProtocolError(ValueError):
    pass

def validate_pdu(pdu, allow_unknown=False):
    if not isinstance(pdu, dict): raise ProtocolError("PDU must be a JSON object")
    if not isinstance(pdu.get("type"), str): raise ProtocolError("PDU type must be a string")
    if not allow_unknown and pdu["type"] not in PDU_TYPES: raise ProtocolError("UNKNOWN_TYPE")
    if not isinstance(pdu.get("seq_num"), int) or isinstance(pdu.get("seq_num"), bool) or pdu["seq_num"] < 0:
        raise ProtocolError("seq_num must be a non-negative integer")
    return pdu

def encode_pdu(pdu):
    validate_pdu(pdu, allow_unknown=True)
    payload = json.dumps(pdu, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_PDU_SIZE: raise ProtocolError("PDU exceeds 65,535 bytes")
    return struct.pack(">I", len(payload)) + payload

def recv_exact(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk: return None
        chunks.extend(chunk)
    return bytes(chunks)

def recv_pdu(sock):
    header = recv_exact(sock, 4)
    if header is None: return None
    size = struct.unpack(">I", header)[0]
    if size == 0 or size > MAX_PDU_SIZE: raise ProtocolError("INVALID_LENGTH")
    payload = recv_exact(sock, size)
    if payload is None: return None
    try: pdu = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ProtocolError("INVALID_JSON") from exc
    return validate_pdu(pdu, allow_unknown=True)
