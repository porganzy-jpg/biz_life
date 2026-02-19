import httpx, os, sys
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
msg = sys.argv[1] if len(sys.argv) > 1 else "test"

resp = httpx.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": msg}
)
print(resp.status_code, resp.json().get("ok"))
