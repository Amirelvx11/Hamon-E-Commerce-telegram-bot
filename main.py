from fastapi import FastAPI, Request
import requests

app = FastAPI()

TOKEN = "8273691312:AAGY4a8YidXubM5C1s2Q6PuZdGsUk4iYmvM"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"

@app.get("/")
def root():
    return {"message": "hello from Hamon Electronic commerce"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    print("Incoming update:", data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            # show inline buttons
            keyboard = {
                "inline_keyboard": [
                    [{"text": "پیگیری پذیرش", "callback_data": "reception"}],
                    [{"text": "پیگیری فروش", "callback_data": "sales"}],
                ]
            }
            send_message(chat_id, "وضعیت خود را مشخص کنید: ", reply_markup=keyboard)
        
        elif text == "/support":
             send_message(chat_id,"برای ارتباط با ما لطفا موضوع خود را مطرح کرده و شماره تماس خود را بنویسید، در اسرع وقت به موضوع شما رسیدگی خواهد شد. همچنین میتوانید با واحد پشتیبانی ما به صورت مستقیم تماس بگیرید(ساعت پاسخگویی 08:00 - 17:00):\n+031 1111 333 ")

    
    elif "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        data_choice = query["data"]

        if data_choice == "reception":
            send_message(chat_id, "برای پیگیری وضعیت پذیرش خود با شماره زیر در ارتباط باشید: \n +031 1111 333")
        elif data_choice == "sales":
            send_message(chat_id, "شماره مرکز واحد فروش: \n +031 1111 333")

    return {"ok": True}


def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json=payload,
            timeout=5
        )
    except requests.exceptions.RequestException as e:
        print("Error sending message:", e)
