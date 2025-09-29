from fastapi import FastAPI, Request
import requests

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
    state = user_states.get(chat_id)

    if text == "/start":
        show_main_menu(chat_id)

    elif state == "waiting_for_number":
        handle_order_number(chat_id, text)

    elif state == "waiting_for_serial":
        handle_serial(chat_id, text)

    elif text == "/support":
        send_support_info(chat_id)

    else:
        show_main_menu(chat_id, error=True)


async def handle_callback(query: dict):
    chat_id = query["message"]["chat"]["id"]
    choice = query["data"]

    if choice == "order_number":
        user_states[chat_id] = "waiting_for_number"
        send_message(chat_id, "لطفا شماره پذیرش  خود را وارد کنید.(فقط عدد)")

    elif choice == "order_serial":
        user_states[chat_id] = "waiting_for_serial"
        send_message(chat_id, "لطفا شماره سریال دستگاه خود را وارد کنید (کامل یا ۶ رقم آخر):\nمثال: 12HEC345678")

    elif choice == "support":
        send_support_info(chat_id)

    elif choice == "main_menu":
        # show main menu on back button press
        show_main_menu(chat_id)


# --- Order Handlers ---
def handle_order_number(chat_id: int, text: str):
    if text.isdigit() and len(text) < 10:
        result = request_server("number", {"number": text})
        send_result(chat_id, result, "سفارش")
        user_states.pop(chat_id, None)
    else:
        # invalid input → include back-to-menu button
        send_message(chat_id, "❌ شماره پذیرش نامعتبر", reply_markup=get_back_keyboard())


def handle_serial(chat_id: int, text: str):
    if len(text) >= 6:
        result = request_server("serial", {"serial": text})
        send_result(chat_id, result, "دستگاه")
        user_states.pop(chat_id, None)
    else:
        send_message(chat_id, "❌ شماره سریال معتبر نیست. حداقل ۶ کاراکتر وارد کنید.", reply_markup=get_back_keyboard())


# --- API & Data Processing ---
def request_server(mode: str, payload: dict):
    """Send request to backend server"""
    url = SERVER_URLS[mode]
    headers = {"auth-token": AUTH_TOKEN, "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


def send_result(chat_id: int, result: dict, label: str):
    """Format and send result to user"""
    if not result:
        send_message(chat_id, "⚠️ خطا در دریافت اطلاعات از سرور", reply_markup=get_back_keyboard())
        return

    if result.get("success") is False:
        send_message(chat_id, f"❌ {label} شما در سیستم یافت نشد. لطفا دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.", reply_markup=get_back_keyboard())
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
        # try to display price with thousands separator and 'ریال'
        try:
            price_int = int(float(data['factorId_totalPriceWithTax']))
            msg += f"💰 مبلغ فاکتور (با مالیات): {price_int:,} ریال\n"
        except Exception:
            msg += f"💰 مبلغ فاکتور (با مالیات): {data['factorId_totalPriceWithTax']} ریال\n"

    # Items
    items = data.get("items", [])
    if items:
        msg += f"\n📱 تعداد دستگاه‌ها: {len(items)}\n"

        # Show only first 8 devices (preview)
        for i, item in enumerate(items[:8], start=1):
            msg += (
                f"\n🔹 دستگاه {i}:\n"
                f"   • مدل: {item.get('$$_deviceId', 'نامشخص')}\n"
                f"   • شماره سریال: {item.get('serialNumber', 'ثبت نشده')}\n"
                f"   • وضعیت: {item.get('$$_status', 'نامشخص')}\n"
            )

    # If more than 8 → prepare keyboard with view-more url + back button
    more_url = None
    if len(items) > 8:
        more_url = "https://hamoonpay.com/"  # replace with your real URL later

    # Build back + maybe view-more keyboard
    keyboard = get_back_keyboard(view_more_url=more_url)

    # Send final message with keyboard (keyboard attached to last chunk)
    send_message(chat_id, msg, reply_markup=keyboard)


# --- UI & Support ---
def show_main_menu(chat_id: int, error=False):
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔢 پیگیری پذیرش (شماره)", "callback_data": "order_number"}],
            [{"text": "#️⃣ پیگیری پذیرش (سریال)", "callback_data": "order_serial"}],
            [{"text": "👥 پشتیبانی", "callback_data": "support"}],
        ]
    }
    msg = "❌ لطفا فقط از منوی زیر استفاده کنید ❌" if error else "خوش آمدید 🙌\nلطفا یکی از گزینه‌ها را انتخاب کنید:"
    send_message(chat_id, msg, reply_markup=keyboard)


def send_support_info(chat_id: int):
    # keyboard = get_back_keyboard() 
    # keyboard["inline_keyboard"].insert(
    #     0,
    #     [{"text":" 📞 تماس با ما ","url":"tel:03133127"}]
    # )
    send_message(
        chat_id,
        "برای ارتباط با پشتیبانی لطفا موضوع خود را مطرح کرده و شماره تماس خود را بنویسید.\n"
        "همکاران ما در اسرع وقت موضوع شما را پیگیری خواهند کرد.\n"
        "همچنین می‌توانید به صورت تلفنی با ما در ارتباط باشید:\n📞 03133127 (08:00 - 17:00)",
        reply_markup=get_back_keyboard()
    )


# --- Helpers: keyboards & Telegram API ---
def get_back_keyboard(view_more_url: str = None):
    """Return keyboard with optional 'view more' url and always a 'back to menu' callback."""
    keyboard = {"inline_keyboard": []}
    if view_more_url:
        keyboard["inline_keyboard"].append([{"text": "📂 مشاهده موارد بیشتر", "url": view_more_url}])
    # back button (callback handled by handle_callback)
    keyboard["inline_keyboard"].append([{"text": "🔙 بازگشت به منو", "callback_data": "main_menu"}])
    return keyboard


def send_message(chat_id: int, text: str, reply_markup=None):
    """Send a message to Telegram; attach keyboard on the final chunk."""
    max_len = 4000  # safe margin under 4096
    parts = [text[i:i + max_len] for i in range(0, len(text), max_len)]
    total = len(parts)

    for idx, part in enumerate(parts):
        payload = {"chat_id": chat_id, "text": part}
        # attach reply_markup on the last part so button appears under final content
        if reply_markup and idx == total - 1:
            payload["reply_markup"] = reply_markup
        try:
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=8)
        except requests.exceptions.RequestException:
            # keep silent (consistent with existing behavior)
            pass
