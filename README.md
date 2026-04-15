# 🕰️ La Linea del Tempo — Gioco online

Gioco-intervista multigiocatore basato sulle carte "La Linea del Tempo" (GenerAction).

## Avvio locale

```bash
cd linea-del-tempo
pip install -r requirements.txt
python server.py
```

Apri http://localhost:5000 — crea una stanza, copia il link e condividilo.

## Uso in rete locale (LAN)

Dal browser di un altro PC/telefono sulla stessa rete:
`http://<IP-del-tuo-PC>:5000/?room=CODE`

Se il firewall Windows chiede, consenti l'accesso alla rete privata.

## Pubblicare online (link condivisibile in internet)

**Opzione rapida — ngrok** (senza deploy):
```bash
ngrok http 5000
```
Copia l'URL `https://xxxx.ngrok-free.app` e condividilo.

**Opzione stabile — Render / Railway / Fly**:
- crea un nuovo Web Service dal repo
- Start command: `python server.py`
- Python 3.11+
- le env `PORT` è gestita automaticamente

## Flusso di gioco (riproduce le regole ufficiali)

1. L'animatore crea la stanza e condivide il link.
2. I partecipanti entrano (2–10 consigliati).
3. L'animatore preme **Inizia**: mazzo mescolato, taglio, primo giocatore sorteggiato.
4. Il giocatore di turno **pesca** → legge la carta, risponde (timer 3 min, non bloccante).
5. Ascolto attivo: gli altri inviano una reazione breve (parola/grazie/risonanza/domanda).
6. Chi ha parlato **passa il testimone** scegliendo il prossimo.
7. Le carte **Terreni Comuni** invitano più persone a rispondere brevemente.
8. Quando tutti hanno giocato almeno una carta **e** il mazzo è esaurito → si apre la **Carta Finale**: ogni partecipante conclude.
