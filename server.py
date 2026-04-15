"""
Server per il gioco online "La Linea del Tempo".
Flask + Flask-SocketIO. Stanze create via link condivisibile.
"""
import os, random, string, time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

from cards import MAIN_CARDS, COMMON_CARDS, FINAL_CARD, ALL_CARDS

app = Flask(__name__, static_folder="public", template_folder="public")
app.config["SECRET_KEY"] = "linea-del-tempo-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

rooms = {}  # code -> stato stanza

def new_code():
    while True:
        c = "".join(random.choices(string.ascii_uppercase, k=4))
        if c not in rooms:
            return c

def make_room(host_sid, host_name):
    code = new_code()
    deck = [c["id"] for c in ALL_CARDS]
    random.shuffle(deck)
    rooms[code] = {
        "code": code,
        "host": host_sid,
        "players": {},  # sid -> {name, played, is_host}
        "order": [],    # ordine di ingresso
        "deck": deck,
        "drawn": [],
        "current_sid": None,
        "current_card": None,
        "phase": "lobby",  # lobby | playing | final | ended
        "final_done": [],
        "timer_end": None,
        "log": [],
    }
    return code

def state_for_client(room):
    def card_by_id(cid):
        for c in ALL_CARDS:
            if c["id"] == cid:
                return c
        if cid == FINAL_CARD["id"]:
            return FINAL_CARD
        return None
    return {
        "code": room["code"],
        "phase": room["phase"],
        "players": [
            {"sid": sid, "name": p["name"], "played": p["played"], "is_host": p["is_host"]}
            for sid, p in room["players"].items()
        ],
        "current_sid": room["current_sid"],
        "current_card": card_by_id(room["current_card"]) if room["current_card"] else None,
        "deck_left": len(room["deck"]),
        "timer_end": room["timer_end"],
        "final_done": room["final_done"],
        "log": room["log"][-30:],
    }

def broadcast(code):
    if code in rooms:
        socketio.emit("state", state_for_client(rooms[code]), room=code)

def log(room, msg):
    room["log"].append({"t": time.time(), "msg": msg})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return {"ok": True, "rooms": len(rooms)}

@socketio.on("create_room")
def on_create(data):
    name = (data.get("name") or "Animatore").strip()[:30]
    code = make_room(request.sid, name)
    room = rooms[code]
    room["players"][request.sid] = {"name": name, "played": 0, "is_host": True}
    room["order"].append(request.sid)
    join_room(code)
    log(room, f"{name} ha creato la stanza")
    emit("joined", {"code": code, "sid": request.sid})
    broadcast(code)

@socketio.on("join_room")
def on_join(data):
    code = (data.get("code") or "").upper().strip()
    name = (data.get("name") or "Ospite").strip()[:30]
    if code not in rooms:
        emit("error_msg", {"msg": "Codice stanza non valido"})
        return
    room = rooms[code]
    if len(room["players"]) >= 12:
        emit("error_msg", {"msg": "Stanza piena"})
        return
    room["players"][request.sid] = {"name": name, "played": 0, "is_host": False}
    room["order"].append(request.sid)
    join_room(code)
    log(room, f"{name} è entrato nel cerchio")
    emit("joined", {"code": code, "sid": request.sid})
    broadcast(code)

@socketio.on("start_game")
def on_start(data):
    code = data.get("code")
    room = rooms.get(code)
    if not room or request.sid != room["host"]:
        return
    if len(room["players"]) < 2:
        emit("error_msg", {"msg": "Servono almeno 2 giocatori"})
        return
    # Taglio del mazzo + sorteggio primo giocatore
    cut = random.randint(1, max(1, len(room["deck"]) - 1))
    room["deck"] = room["deck"][cut:] + room["deck"][:cut]
    first = random.choice(list(room["players"].keys()))
    room["current_sid"] = first
    room["phase"] = "playing"
    log(room, f"Inizia {room['players'][first]['name']} (sorteggiato)")
    broadcast(code)

@socketio.on("draw_card")
def on_draw(data):
    code = data.get("code")
    room = rooms.get(code)
    if not room or room["phase"] != "playing":
        return
    if request.sid != room["current_sid"]:
        return
    if room["current_card"] is not None:
        return
    if not room["deck"]:
        # Passa a fase finale
        room["phase"] = "final"
        room["current_card"] = FINAL_CARD["id"]
        room["timer_end"] = None
        log(room, "Mazzo terminato — Carta Finale")
        broadcast(code)
        return
    cid = room["deck"].pop(0)
    room["current_card"] = cid
    room["drawn"].append(cid)
    room["timer_end"] = time.time() + 180  # 3 minuti
    card = next(c for c in ALL_CARDS if c["id"] == cid)
    log(room, f"{room['players'][request.sid]['name']} pesca: {card['titolo']}")
    broadcast(code)

@socketio.on("pass_turn")
def on_pass(data):
    code = data.get("code")
    next_sid = data.get("next_sid")
    room = rooms.get(code)
    if not room or room["phase"] not in ("playing",):
        return
    if request.sid != room["current_sid"]:
        return
    if next_sid not in room["players"]:
        return
    room["players"][request.sid]["played"] += 1
    prev_name = room["players"][request.sid]["name"]
    next_name = room["players"][next_sid]["name"]
    log(room, f"{prev_name} passa il testimone a {next_name}")
    room["current_sid"] = next_sid
    room["current_card"] = None
    room["timer_end"] = None
    # Tutti hanno giocato almeno una volta E mazzo vuoto → finale
    all_played = all(p["played"] >= 1 for p in room["players"].values())
    if all_played and not room["deck"]:
        room["phase"] = "final"
        room["current_card"] = FINAL_CARD["id"]
        log(room, "Tutti hanno giocato — si apre la Carta Finale")
    broadcast(code)

@socketio.on("final_answer")
def on_final(data):
    code = data.get("code")
    room = rooms.get(code)
    if not room or room["phase"] != "final":
        return
    if request.sid not in room["players"]:
        return
    if request.sid in room["final_done"]:
        return
    room["final_done"].append(request.sid)
    room["players"][request.sid]["played"] += 1
    log(room, f"{room['players'][request.sid]['name']} ha chiuso il suo giro")
    if len(room["final_done"]) >= len(room["players"]):
        room["phase"] = "ended"
        log(room, "Il cerchio si chiude. Grazie.")
    broadcast(code)

@socketio.on("send_reaction")
def on_reaction(data):
    code = data.get("code")
    text = (data.get("text") or "").strip()[:200]
    room = rooms.get(code)
    if not room or not text:
        return
    if request.sid not in room["players"]:
        return
    log(room, f"💬 {room['players'][request.sid]['name']}: {text}")
    broadcast(code)

@socketio.on("reset_room")
def on_reset(data):
    code = data.get("code")
    room = rooms.get(code)
    if not room or request.sid != room["host"]:
        return
    deck = [c["id"] for c in ALL_CARDS]
    random.shuffle(deck)
    room["deck"] = deck
    room["drawn"] = []
    room["current_sid"] = None
    room["current_card"] = None
    room["phase"] = "lobby"
    room["final_done"] = []
    room["timer_end"] = None
    for p in room["players"].values():
        p["played"] = 0
    log(room, "Nuova partita preparata")
    broadcast(code)

@socketio.on("disconnect")
def on_disconnect():
    for code, room in list(rooms.items()):
        if request.sid in room["players"]:
            name = room["players"][request.sid]["name"]
            del room["players"][request.sid]
            if request.sid in room["order"]:
                room["order"].remove(request.sid)
            if request.sid in room["final_done"]:
                room["final_done"].remove(request.sid)
            log(room, f"{name} ha lasciato il cerchio")
            if room["current_sid"] == request.sid:
                # passa automaticamente al successivo se presente
                room["current_card"] = None
                room["timer_end"] = None
                if room["order"]:
                    room["current_sid"] = room["order"][0]
                else:
                    room["current_sid"] = None
            if not room["players"]:
                del rooms[code]
            else:
                if request.sid == room["host"] and room["order"]:
                    room["host"] = room["order"][0]
                    room["players"][room["host"]]["is_host"] = True
                broadcast(code)
            break

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server on http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
