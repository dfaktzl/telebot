import os
from dotenv import load_dotenv

load_dotenv()

# Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8502950869:AAGbNWY86HLNvA54o16rS1PSkqv2hTppmIU")

# Admin IDs
ADMIN_IDS = frozenset()
_raw = os.getenv("ADMIN_IDS", "18281413977,7626116497,5339657191")
if _raw:
    ADMIN_IDS = frozenset(
        int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()
    )

# Log Channel
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003817851175"))

# Channel IDs
BLACK_CHANNEL_ID = -1003885954803

# Initial White Channel settings (can be updated via Admin Panel)
DEFAULT_WHITE_CHANNEL_ID = 0  # To be set via /admin
DEFAULT_INVITE_LINK = "https://t.me/placeholder"

# Admin Contact
ADMIN_CONTACT = "@GatekeeperBot"
ADMIN_USERNAME = "Admin Team"

# Database
DB_PATH = os.getenv("SHARED_DB_PATH", "gatekeeper.db")

# Safety & Security
BROADCAST_DELAY = 0.15  # Seconds between messages
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
SYNC_INTERVAL = 21600  # 6 hours (4x daily)
