from fastapi import FastAPI, Request
import requests,time

app = FastAPI()

# --- Config ---
TOKEN = "8273691312:AAGY4a8YidXubM5C1s2Q6PuZdGsUk4iYmvM"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"
SERVER_URLS = {
    "number": "http://192.168.41.41:8010/api/v1/ass-process/GetByNumber",
    "serial": "http://192.168.41.41:8010/api/v1/ass-process/GetBySerial",
}
AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6ImEuamFtc2hpZGkiLCJpZCI6Ijc5ZDc3NTllLTkxOGItNGIzZS05MmI2LTlkMzIxNjFiYzIzMiIsIm5hbWUiOiLYp9mF24zYsSDYrNmF2LTbjNiv24wiLCJuYmYiOjE3NTkwNjAxMjYsImV4cCI6MTc2NzcwMDEyNiwiaWF0IjoxNzU5MDYwMTI2LCJpc3MiOiJodHRwOi8vd3d3LlZpZGEubmV0In0.pCRTWccku_NIWKtYeTjHBYOL4DhHuYTnDlUBRw86-wM"

# Track user states: chat_id -> state
user_states = {}


@app.get("/")
def root():
    return {"message": "Hamon Electronic Commerce, to contact us please visit our website https://hamoonpay.com/"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates"""
    try:
        update = await request.json()
    except Exception:
        return {"ok": False}

    if "message" in update:
        await handle_message(update["message"])
    elif "callback_query" in update:
        await handle_callback(update["callback_query"])

    return {"ok": True}


# --- Telegram Handlers ---
async def handle_message(message: dict):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    state_data = user_states.get(chat_id, {})
    state = state_data.get("state")

    if text == "/start":
        show_main_menu(chat_id)

    elif text == "/support":
        send_support_info(chat_id)

    elif state == "waiting_for_subject":
        # check expiration
        if time.time() > state_data.get("expires", 0):
            user_states.pop(chat_id, None)
            send_message(chat_id, "⏰ زمان ارسال تمام شد !!")
            show_main_menu(chat_id)
        else:
            # save message (for now just log)
            save_subject(chat_id, text)
            send_message(chat_id, "✅ موضوع شما با موفقیت ثبت شد.")
            user_states.pop(chat_id, None)
            show_main_menu(chat_id)
        return

    elif state == "waiting_for_number":
        handle_order_number(chat_id, text)

    elif state == "waiting_for_serial":
        handle_serial(chat_id, text)

    else:
        show_main_menu(chat_id, error=True)



async def handle_callback(query: dict):
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]
    choice = query["data"]

    if choice == "order_number":
        user_states[chat_id] = {"state": "waiting_for_number", "expires": time.time() + 300}
        edit_message(chat_id, message_id, "لطفا شماره پذیرش  خود را وارد کنید.(فقط عدد)")

    elif choice == "order_serial":
        user_states[chat_id] = {"state": "waiting_for_serial", "expires": time.time() + 300}
        edit_message(chat_id, message_id, "لطفا شماره سریال دستگاه خود را وارد کنید (کامل یا ۶ رقم آخر):\nمثال: 12HEC345678")


    elif choice == "support":
        send_support_info(chat_id, message_id=message_id)

    elif choice == "send_subject":
        user_states[chat_id] = {"state": "waiting_for_subject", "expires": time.time() + 300}
        edit_message(chat_id, message_id, "❔ لطفا متن خود را با رعایت نکات اخلاقی بنویسید:")

    elif choice == "main_menu":
        user_states.pop(chat_id, None)
        show_main_menu(chat_id, message_id=message_id)


# --- Order Handlers ---
def handle_order_number(chat_id: int, text: str):
    if text.isdigit() and len(text) < 10:
        result = request_server("number", {"number": text})
        send_result(chat_id, result, "سفارش")
        user_states.pop(chat_id, None)
    else:
        # invalid input → reset state
        user_states.pop(chat_id, None)
        edit_message(chat_id, None, "❌ شماره پذیرش نامعتبر", reply_markup=get_back_keyboard())


def handle_serial(chat_id: int, text: str):
    if len(text) >= 6:
        result = request_server("serial", {"serial": text})
        send_result(chat_id, result, "دستگاه")
        user_states.pop(chat_id, None)
    else:
        # invalid input → reset state
        user_states.pop(chat_id, None)
        edit_message(chat_id, None, "❌ شماره سریال معتبر نیست. حداقل ۶ کاراکتر وارد کنید.", reply_markup=get_back_keyboard())


# --- API & Data Processing ---
def request_server(mode: str, payload: dict):
    """Send request to backend server"""
    url = SERVER_URLS[mode]
    headers = {"auth-token": AUTH_TOKEN, "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")
        return None


def send_result(chat_id: int, result: dict, label: str):
    """Format and send result to user"""
    if not result:
        edit_message(chat_id, None, "⚠️ خطا در دریافت اطلاعات از سرور", reply_markup=get_back_keyboard())
        return

    if result.get("success") is False:
        edit_message(chat_id, None, f"❌ {label} شما در سیستم یافت نشد. لطفا دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.", reply_markup=get_back_keyboard())
        return

    data = result.get("data", {})
    status = data.get("$$_steps", "نامشخص")

    # Base info
    msg = f"✅ وضعیت {label} شما:\n\n📌 وضعیت کلی: {status}\n"

    # Extra fields
    if data.get("warehouseIssueId_referenceNumber"):
        msg += f"🚚 کد رهگیری پستی: {data['warehouseIssueId_referenceNumber']}\n"
    if data.get("warehouseRecieptId_createdOn"):
        msg += f"📦 تاریخ رسید انبار: {data['warehouseRecieptId_createdOn'].split(' ')[0]}\n"
    if data.get("factorId_number"):
        msg += f"🧾 شماره فاکتور: {data['factorId_number']}\n"
    if data.get("factorId_totalPriceWithTax"):
        try:
            price_int = int(float(data['factorId_totalPriceWithTax']))
            msg += f"💰 مبلغ فاکتور (با مالیات): {price_int:,} ریال\n"
        except Exception:
            msg += f"💰 مبلغ فاکتور (با مالیات): {data['factorId_totalPriceWithTax']} ریال\n"
        if data.get("factorId_paymentLink"):
            msg += f"💳 لینک پرداخت صورتحساب: {data['factorId_paymentLink']} \n"

    # Items
    items = data.get("items", [])
    if items:
        msg += f"\n📱 تعداد دستگاه‌ها: {len(items)}\n"
        for i, item in enumerate(items[:8], start=1):
            msg += (
                f"\n🔹 دستگاه {i}:\n"
                f"   • مدل: {item.get('$$_deviceId', 'نامشخص')}\n"
                f"   • شماره سریال: {item.get('serialNumber', 'ثبت نشده')}\n"
                f"   • وضعیت: {item.get('$$_status', 'نامشخص')}\n"
            )

    more_url = None
    if len(items) > 8:
        more_url = "https://hamoonpay.com/"

    keyboard = get_back_keyboard(view_more_url=more_url)
    edit_message(chat_id, None, msg, reply_markup=keyboard)


# --- UI & Support ---
def show_main_menu(chat_id: int, message_id: int = None, error=False):
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔢 پیگیری سفارش از طریق شماره پذیرش", "callback_data": "order_number"}],
            [{"text": "#️⃣ پیگیری سفارش از طریق سریال پذیرش", "callback_data": "order_serial"}],
            [{"text": "👥ارتباط با واحد پشتیبانی ", "callback_data": "support"}],
        ]
    }
    msg = "❌ لطفا فقط از منوی زیر استفاده کنید ❌" if error else "خوش آمدید 🙌\nلطفا یکی از گزینه‌ها را انتخاب کنید:"

    edit_message(chat_id, message_id, msg, reply_markup=keyboard)


def send_support_info(chat_id: int, message_id: int = None):
    keyboard = get_back_keyboard()
    keyboard["inline_keyboard"].insert(
        0,
        [
            {"text": "👥 ارتباط با ما", "url": "https://hamoonpay.com/contact-us/"},
            {"text": "❔ ارسال موضوع", "callback_data": "send_subject"},
        ],
    )

    text = (
        "برای ارتباط با پشتیبانی لطفا موضوع خود را مطرح کرده و شماره تماس خود را بنویسید.\n"
        "همکاران ما در اسرع وقت موضوع شما را پیگیری خواهند کرد.\n"
        "همچنین می‌توانید به صورت تلفنی با ما در ارتباط باشید:\n"
        "📞 03133127 (08:00 - 17:00)"
    )

    edit_message(chat_id, message_id, text, reply_markup=keyboard)


def get_back_keyboard(view_more_url: str = None):
    keyboard = {"inline_keyboard": []}
    if view_more_url:
        keyboard["inline_keyboard"].append([{"text": "📂 مشاهده موارد بیشتر", "url": view_more_url}])
    keyboard["inline_keyboard"].append([{"text": "🔙 بازگشت به منو", "callback_data": "main_menu"}])
    return keyboard


def save_subject(chat_id: int, text: str):
    # url = "http://192.168.41.41:8010/api/v1/support/save"  # edit this link
    # payload = {"chat_id": chat_id, "message": text}
    # headers = {"auth-token": AUTH_TOKEN, "Content-Type": "application/json"}
    # try:
    #     requests.post(url, json=payload, headers=headers, timeout=10)
    # except requests.exceptions.RequestException as e:
    #     print(f"[ERROR] Failed to save subject: {e}")
    print(f"[SUPPORT] Subject received from {chat_id}: {text}")




# --- Telegram API Helpers ---
def send_message(chat_id: int, text: str, reply_markup=None):
    """Send a fresh message (used only when we don't want to edit)."""
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=8)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send message: {e}")


def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None):
    """Edit an existing message if message_id provided, otherwise send a new one."""
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if message_id:
        payload["message_id"] = message_id
        method = "editMessageText"
    else:
        method = "sendMessage"
    try:
        requests.post(f"{TELEGRAM_API_URL}/{method}", json=payload, timeout=8)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to edit/send message: {e}")
