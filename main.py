from fastapi import FastAPI, Request
import requests

app = FastAPI()

# ===============================
# Telegram bot configuration
# ===============================
TOKEN = "8273691312:AAGY4a8YidXubM5C1s2Q6PuZdGsUk4iYmvM"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"

# ===============================
# C# API configuration
# ===============================
SERVER_URL = "http://192.168.41.41:8010/api/v1/ass-process/GetByNumber"
AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6ImEuamFtc2hpZGkiLCJpZCI6Ijc5ZDc3NTllLTkxOGItNGIzZS05MmI2LTlkMzIxNjFiYzIzMiIsIm5hbWUiOiLYp9mF24zYsSDYrNmF2LTbjNiv24wiLCJuYmYiOjE3NTkwNjAxMjYsImV4cCI6MTc2NzcwMDEyNiwiaWF0IjoxNzU5MDYwMTI2LCJpc3MiOiJodHRwOi8vd3d3LlZpZGEubmV0In0.pCRTWccku_NIWKtYeTjHBYOL4DhHuYTnDlUBRw86-wM"


@app.get("/")
def root():
    return {"message": "hello from Hamon Electronic commerce"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates."""
    try:
        data = await request.json()
    except Exception:
        return {"ok": False}

    # --------------------------------
    # Handle normal text messages
    # --------------------------------
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").strip()

        if text == "/start":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "پیگیری پذیرش (شماره)", "callback_data": "order_number"}],
                    [{"text": "پیگیری پذیرش (سریال)", "callback_data": "order_serial"}],
                    [{"text": "پشتیبانی", "callback_data": "support"}],
                ]
            }
            send_message(chat_id, "خوش آمدید 🙌\nلطفا یکی از گزینه‌ها را انتخاب کنید:", reply_markup=keyboard)

        elif text.startswith("ID:"):
            customer_id = text.replace("ID:", "").strip()
            result = forward_to_server(customer_id)
            if result:
                send_message(chat_id, f"نتیجه دریافت شد:\n{result}")
            else:
                send_message(chat_id, "⚠️ خطا در دریافت اطلاعات از سرور")

        elif text == "/support":
            send_message(
                chat_id,
                "برای ارتباط با پشتیبانی لطفا موضوع خود را مطرح کرده و شماره تماس خود را بنویسید.\n"
                "همچنین می‌توانید مستقیم تماس بگیرید (08:00 - 17:00):\n+031 1111 333"
            )

    # --------------------------------
    # Handle button clicks (callbacks)
    # --------------------------------
    elif "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        choice = query["data"]

        if choice == "order_number":
            send_message(chat_id, "لطفا شماره پذیرش خود را به این صورت ارسال کنید:\n\nID:12345")

        elif choice == "order_serial":
            send_message(chat_id, "لطفا شماره سریال خود را به این صورت ارسال کنید:\n\nID:12HEC345678")

        elif choice == "support":
            send_message(
                chat_id,
                "برای ارتباط با پشتیبانی لطفا موضوع خود را مطرح کرده و شماره تماس خود را بنویسید.\n"
                "همچنین می‌توانید مستقیم تماس بگیرید (08:00 - 17:00):\n+031 1111 333"
            )

    return {"ok": True}


# ===============================
# Helper: Forward to C# API
# ===============================
def forward_to_server(customer_id: str):
    payload = {"number": customer_id}
    headers = {
        "auth-token": AUTH_TOKEN,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(SERVER_URL, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.exceptions.RequestException:
        return None


# ===============================
# Helper: Send Telegram messages
# ===============================
def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=5)
    except requests.exceptions.RequestException:
        pass
