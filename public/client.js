const socket = io();
let myState = { code: null, sid: null, selectingNext: false };

const $ = id => document.getElementById(id);

// URL auto-join
const urlCode = new URLSearchParams(location.search).get("room");
if (urlCode) $("code-input").value = urlCode.toUpperCase();

$("btn-create").onclick = () => {
  const name = $("name-input").value.trim();
  if (!name) return showError("Inserisci il tuo nome");
  socket.emit("create_room", { name });
};
$("btn-join").onclick = () => {
  const name = $("name-input").value.trim();
  const code = $("code-input").value.trim().toUpperCase();
  if (!name) return showError("Inserisci il tuo nome");
  if (!code) return showError("Inserisci il codice stanza");
  socket.emit("join_room", { name, code });
};
function showError(msg) { $("home-error").textContent = msg; }

socket.on("joined", ({ code, sid }) => {
  myState.code = code; myState.sid = sid;
  $("screen-home").classList.add("hidden");
  $("screen-game").classList.remove("hidden");
  $("room-code").textContent = code;
  history.replaceState(null, "", `?room=${code}`);
});

socket.on("error_msg", ({ msg }) => showError(msg));

$("btn-copy").onclick = () => {
  const url = `${location.origin}${location.pathname}?room=${myState.code}`;
  navigator.clipboard.writeText(url).then(() => {
    $("btn-copy").textContent = "Copiato!";
    setTimeout(() => $("btn-copy").textContent = "Copia link", 2000);
  });
};

$("btn-start").onclick = () => socket.emit("start_game", { code: myState.code });
$("btn-reset").onclick = () => {
  if (confirm("Ricominciare con un nuovo mazzo?")) socket.emit("reset_room", { code: myState.code });
};

$("btn-reaction").onclick = sendReaction;
$("reaction-input").addEventListener("keypress", e => { if (e.key === "Enter") sendReaction(); });
function sendReaction() {
  const text = $("reaction-input").value.trim();
  if (!text) return;
  socket.emit("send_reaction", { code: myState.code, text });
  $("reaction-input").value = "";
}

let timerInterval = null;

socket.on("state", s => {
  renderPlayers(s);
  renderCard(s);
  renderActions(s);
  renderTimer(s);
  renderLog(s);
  $("deck-left").textContent = s.deck_left;
  $("phase-label").textContent = phaseLabel(s.phase);
  const me = s.players.find(p => p.sid === myState.sid);
  if (me && me.is_host) $("host-controls").classList.remove("hidden");
  else $("host-controls").classList.add("hidden");
  if (s.phase !== "lobby") $("btn-start").classList.add("hidden");
  else $("btn-start").classList.remove("hidden");
});

function phaseLabel(p) {
  return { lobby: "Lobby", playing: "In gioco", final: "Carta finale", ended: "Chiuso" }[p] || p;
}

function renderPlayers(s) {
  const ul = $("players-list");
  ul.innerHTML = "";
  s.players.forEach(p => {
    const li = document.createElement("li");
    if (p.sid === s.current_sid) li.classList.add("current");
    if (myState.selectingNext && p.sid !== myState.sid) {
      li.classList.add("selectable");
      li.onclick = () => {
        socket.emit("pass_turn", { code: myState.code, next_sid: p.sid });
        myState.selectingNext = false;
      };
    }
    li.innerHTML = `<span>${escapeHtml(p.name)} <small>(${p.played})</small></span>
      <span>${p.is_host ? '<span class="badge host">host</span>' : ''}</span>`;
    ul.appendChild(li);
  });
}

function renderCard(s) {
  const box = $("card-box");
  box.className = "card-box";
  if (!s.current_card) {
    box.classList.add("empty");
    const msg = s.phase === "lobby" ? "Aspettiamo che l'animatore dia il via…"
      : s.phase === "ended" ? "🌿 Il cerchio si chiude. Grazie."
      : s.current_sid === myState.sid ? "Tocca a te: pesca una carta."
      : `Turno di ${nameOf(s, s.current_sid)}…`;
    box.innerHTML = `<div class="empty-msg">${msg}</div>`;
    return;
  }
  const c = s.current_card;
  if (c.fase === "TERRENI COMUNI") box.classList.add("terreni");
  if (c.fase === "CARTA FINALE") box.classList.add("finale");
  box.innerHTML = `
    <div class="card-number">#${c.id === 999 ? "FINAL" : c.id}</div>
    <div class="card-fase">${escapeHtml(c.fase)}</div>
    <div class="card-titolo">${escapeHtml(c.titolo)}</div>
    <div class="card-domanda">${escapeHtml(c.domanda)}</div>
    ${c.extra ? `<div class="card-extra">✨ ${escapeHtml(c.extra)}</div>` : ""}
  `;
}

function renderActions(s) {
  const bar = $("action-bar");
  bar.innerHTML = "";
  const isMyTurn = s.current_sid === myState.sid;

  if (s.phase === "playing") {
    if (isMyTurn && !s.current_card) {
      const btn = document.createElement("button");
      btn.className = "primary"; btn.textContent = "🎴 Pesca carta";
      btn.onclick = () => socket.emit("draw_card", { code: myState.code });
      bar.appendChild(btn);
    } else if (isMyTurn && s.current_card) {
      const btn = document.createElement("button");
      btn.className = "primary";
      btn.textContent = myState.selectingNext ? "Scegli un giocatore nel cerchio →" : "✋ Passa il testimone";
      btn.onclick = () => { myState.selectingNext = !myState.selectingNext; renderPlayers(s); };
      bar.appendChild(btn);
    }
  } else if (s.phase === "final") {
    const alreadyDone = s.final_done.includes(myState.sid);
    if (!alreadyDone) {
      const btn = document.createElement("button");
      btn.className = "primary";
      btn.textContent = "✅ Ho concluso il mio giro";
      btn.onclick = () => socket.emit("final_answer", { code: myState.code });
      bar.appendChild(btn);
    } else {
      const span = document.createElement("span");
      span.textContent = `In attesa degli altri (${s.final_done.length}/${s.players.length})`;
      span.style.color = "#c8b9f0";
      bar.appendChild(span);
    }
  }
}

function renderTimer(s) {
  clearInterval(timerInterval);
  const el = $("timer");
  if (!s.timer_end) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  const update = () => {
    const left = Math.max(0, Math.floor(s.timer_end - Date.now()/1000));
    const m = Math.floor(left/60), sec = left%60;
    $("timer-text").textContent = `${m}:${String(sec).padStart(2,"0")}`;
    if (left <= 30) el.classList.add("warning"); else el.classList.remove("warning");
    if (left <= 0) clearInterval(timerInterval);
  };
  update();
  timerInterval = setInterval(update, 500);
}

function renderLog(s) {
  const ul = $("log-list");
  ul.innerHTML = "";
  s.log.slice().reverse().forEach(entry => {
    const li = document.createElement("li");
    li.textContent = entry.msg;
    ul.appendChild(li);
  });
}

function nameOf(s, sid) {
  const p = s.players.find(x => x.sid === sid);
  return p ? p.name : "…";
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c =>
    ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}
