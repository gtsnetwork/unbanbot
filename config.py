import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8886222574:AAGWXDfP3EvQSFAXTAPv8Nfa17yKyDoiqiU").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "8480522053"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/appeals.sqlite3")
SUPPORT_TEXT = os.getenv(
    "SUPPORT_TEXT",
    "For support, contact the GTS NETWORK team through the official group administrators."
)
GUIDELINES_TEXT = os.getenv(
    "GUIDELINES_TEXT",
    "Submit truthful and complete information. Be respectful. Do not submit repeated "
    "appeals while an earlier appeal for the same group is pending. Submitting an appeal "
    "does not guarantee that a ban will be removed."
)
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "3"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required. Set it in the deployment environment.")
