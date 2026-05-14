# 🛡️ Perth Gatekeeper Bot

Telegram gatekeeper bot — controls access to the private White Channel by cross-referencing the Black Channel membership, managing join requests, and running reputation checks against the legacy database.

**Bot ID (token prefix):** `8502950869` — this uniquely identifies the Gatekeeper bot from the Vouch/Rep bot.

## Features

- **Join Request Gate** — auto-approves/declines Black Channel join requests; blocks flagged users
- **Membership Sync** — daily sweep revokes verification for users who leave the Black Channel
- **Health Check** — monitors the White Channel every 5 minutes; enters Emergency Mode if it goes down and broadcasts alert to all verified users
- **Reputation Integration** — cross-references the legacy `reputation.db` and the Vouch Bot's database
- **Emergency Mode** — gracefully handles White Channel takedowns with user notifications
- **Admin Panel** — full inline admin panel via `/admin` in DMs
- **Editable Messages** — change any user-facing message via the admin panel without touching code
- **Vouch Passthrough** — `/vouch`, `/unvouch`, `/link` commands for verified members

## Bot Tokens (Separation of Concerns)

| Bot | Token Prefix | Purpose |
|-----|-------------|---------|
| **Gatekeeper** | `8502950869:AAGb...` | Access control, join requests, White Channel management |
| **Vouch/Rep Bot** | `8581140481:AAE_...` | Reputation tracking, vouch history, admin panel |

Each bot runs as a separate systemd service (`gatekeeper.service` vs `repbot.service`) on the same OCI instance.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Gatekeeper bot token (prefix `8502950869`) |

All other settings (White Channel ID, invite link, message templates, etc.) are configured via the live admin panel and stored in `gatekeeper.db`.

## File Structure

```
gatekeeper_bot/
├── main.py              # Entry point — scheduler, polling, join request handler
├── config.py            # Constants & env vars
├── database.py          # aiosqlite models + DB helpers
├── migrate.py           # DB migration utility
├── import_legacy.py     # Import legacy reputation.db entries
├── rescue.py            # Emergency recovery utility
├── requirements.txt     # Python dependencies
├── handlers/
│   ├── admin.py         # /admin panel (inline keyboard)
│   ├── common.py        # /start /vouch /unvouch /link
│   ├── reputation.py    # Reputation query helpers
│   └── logger.py        # Audit logging handler
└── utils/
    ├── helpers.py       # Black channel membership check, broadcast
    └── reputation.py    # Score fetchers
```

## Admin Commands

| Command | Description |
|---|---|
| `/admin` | Full admin panel (DM only) |
| `/vouch <id> [comment]` | Vouch for a user (verified members) |
| `/unvouch <id> [comment]` | Revoke vouch (verified members) |
| `/link` | Get White Channel invite link (verified only) |
| `/start` | Show verification status |

---

## 🚀 Deploy on OCI — Full Instructions

### Prerequisites (Windows)

Your SSH key is at: `C:\Users\defak\Downloads\botcurrentpriv.key`

---

### Step 1 — SSH into the Server

Open **PowerShell** and run:

```powershell
ssh -i "C:\Users\defak\Downloads\botcurrentpriv.key" ubuntu@<YOUR_OCI_PUBLIC_IP>
```

> If you get a permissions warning, fix it first:
> ```powershell
> icacls "C:\Users\defak\Downloads\botcurrentpriv.key" /inheritance:r /grant:r "$($env:USERNAME):(R)"
> ```

---

### Step 2 — Server Preparation (run on server)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git sqlite3
```

---

### Step 3 — Clone & Set Up the Gatekeeper Bot

```bash
# Clone into /home/ubuntu/gatekeeper
git clone https://github.com/dfaktzl/telebot.git /home/ubuntu/gatekeeper
cd /home/ubuntu/gatekeeper

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 4 — Configure Environment

```bash
nano /home/ubuntu/gatekeeper/.env
```

Paste **exactly** this (token is pre-filled — this is the Gatekeeper-specific token):

```env
BOT_TOKEN=8502950869:AAGbNWY86HLNvA54o16rS1PSkqv2hTppmIU
```

Save: `Ctrl+O` → Enter → `Ctrl+X`

---

### Step 5 — Systemd Service (24/7 Uptime)

```bash
sudo nano /etc/systemd/system/gatekeeper.service
```

Paste:

```ini
[Unit]
Description=Perth Gatekeeper Bot (8502950869)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/gatekeeper
ExecStart=/home/ubuntu/gatekeeper/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=gatekeeper
EnvironmentFile=/home/ubuntu/gatekeeper/.env
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/ubuntu/gatekeeper
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Save: `Ctrl+O` → Enter → `Ctrl+X`

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gatekeeper
sudo systemctl start gatekeeper
sudo journalctl -u gatekeeper -f   # watch live logs
```

---

### Step 6 — Verify Both Bots Are Running

```bash
sudo systemctl status gatekeeper   # Gatekeeper (token: 8502950869)
sudo systemctl status repbot       # Vouch/Rep bot (token: 8581140481)
```

---

### Future Updates (2 commands)

```bash
cd /home/ubuntu/gatekeeper
git pull
sudo systemctl restart gatekeeper
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied (publickey)` | Fix key permissions: `icacls "C:\Users\defak\Downloads\botcurrentpriv.key" /inheritance:r /grant:r "$($env:USERNAME):(R)"` |
| Bot not responding | `sudo journalctl -u gatekeeper -f` to see errors |
| DB locked error | Check only one instance is running: `ps aux | grep python` |
| Emergency mode stuck | Use `/admin` panel → Settings → Clear Emergency Mode |
