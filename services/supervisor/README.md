# supervisor — faulty-part tickets + Discord supervisor agent

Closes the loop between the line's QC and a human supervisor, entirely through
governed **Soda Straw** straws (no direct DB or Discord credentials in this
service).

```
 QC/vision inserts a row              supervisor replies in Discord
 into faulty_parts (status='open')        │  "reject — dented" / "accept"
            │                             ▼
            ▼                  ┌────────────────────────────┐
  ┌──────────────────┐ ticket │ supervisor_agent.py         │
  │   monitor.py     ├───────►│ (Claude + 2 straws)         │
  │ poll faulty_parts│ embed  │ • query_db (read)           │
  │  status='open'   │        │ • set_resolution            │
  │ → post to Discord│        │   → faulty_parts.resolution  │
  │ → status=ticketed│        │   → status='resolved'        │
  └──────────────────┘        └─────────────┬──────────────┘
            ▲                                │
            └──── robot reads resolution ◄────┘
                  WHERE resolution IS NOT NULL AND robot_acked = false
```

Both loops reach Postgres and Discord through the Soda Straw MCP gateway using a
scoped agent API key (`production-line-supervisor`, assigned the `postgres` and
`discord-bot` straws). See [sodastraw.py](sodastraw.py).

## Components

| File | Role |
|---|---|
| [sodastraw.py](sodastraw.py) | Async MCP client + `sql()` / `discord()` helpers |
| [monitor.py](monitor.py) | **Loop A** — new `faulty_parts` row → Discord ticket embed |
| [supervisor_agent.py](supervisor_agent.py) | **Loop B** — read replies → Claude answers / sets resolution |
| [run.py](run.py) | Runs both loops together |
| [tools/make_test_ticket.py](tools/make_test_ticket.py) | Insert a fake faulty part to demo a ticket |

## The contract (`faulty_parts` table)

| Who | Does |
|---|---|
| Vision/QC | `INSERT INTO faulty_parts (station_pos, fault, confidence, image_url)` → `status='open'`, `resolution=NULL` |
| **monitor.py** | polls `status='open'` → posts ticket to Discord → `status='ticketed'` + `discord_message_id` |
| **supervisor_agent.py** (Claude in Discord) | supervisor says go / no-go → sets `resolution`, `resolution_note`, `resolved_by`, `resolved_at` → `status='resolved'` |
| **Robot code** (yours) | polls `resolution IS NOT NULL AND robot_acked=false` → acts → `SET robot_acked=true` |

`resolution` is **`go`** (part is fine — let it continue) or **`no_go`** (pull it off the
line for rework / repack / scrap — detail in `resolution_note`).

`image_url` holds **base64** (a camera frame). Discord can't render base64 in an
embed, so the ticket shows the text fields only; if `image_url` ever contains a
real `http(s)` URL, the monitor adds it as the embed image automatically.

## Setup

```bash
cd services/supervisor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in STRAW_API_KEY and ANTHROPIC_API_KEY
```

`DISCORD_CHANNEL_ID` / `DISCORD_BOT_USER_ID` are pre-filled for #general and the
`caffeinated-robo-ravers` bot. The bot must be in the server with Send Messages +
Read Message History, and **Message Content Intent** enabled.

## Run

```bash
python run.py                      # both loops
# or individually:
python monitor.py
python supervisor_agent.py
```

## Demo

1. `python run.py`
2. In another shell: `python tools/make_test_ticket.py`
3. A ticket embed appears in #general within ~5s.
4. **Reply** to it: *"what station is it at?"* → the assistant answers from the DB.
5. Reply *"no-go — herverpakken"* → it writes `resolution='no_go'` + note onto the
   `faulty_parts` row and closes the ticket. Your robot code picks it up on its next poll.
