import os
from dotenv import load_dotenv

load_dotenv()

# Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8502950869:AAGSp_8-dH9SKuZeHBMvRxqtZ8zLcZ5ysgE")

# Channel IDs
BLACK_CHANNEL_ID = -1003885954803

# Initial White Channel settings (can be updated via Admin Panel)
DEFAULT_WHITE_CHANNEL_ID = 0  # To be set via /admin
DEFAULT_INVITE_LINK = "https://t.me/placeholder"

# Admin Contact
ADMIN_CONTACT = "@VouchCheckerBot"
ADMIN_USERNAME = "Admin Team"

# Database
DB_PATH = "gatekeeper.db"

# Safety & Security
BROADCAST_DELAY = 0.15
  # Seconds between messages
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
SYNC_INTERVAL = 86400  # 24 hours
