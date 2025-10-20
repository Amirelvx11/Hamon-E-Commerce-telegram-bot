"""
Core Configuration 
"""
import os
import logging
import re
from enum import Enum, auto
from telegram import (ReplyKeyboardMarkup,
 KeyboardButton, InlineKeyboardMarkup,
 InlineKeyboardButton
)
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class UserState(Enum):
    IDLE = auto()
    WAITING_nationalId = auto()
    AUTHENTICATED = auto()
    WAITING_ORDER_NUMBER = auto()
    WAITING_SERIAL = auto()
    WAITING_COMPLAINT_TEXT = auto()
    WAITING_COMPLAINT_TYPE = auto()
    WAITING_REPAIR_DESC = auto()
    RATE_LIMITED = auto()

class ComplaintType(Enum):
    TECHNICAL = "technical"
    PAYMENT = "payment"
    SHIPPING = "shipping"
    SERVICE = "service"
    OTHER = "other"


class CallbackFormats:
    """Standardized callback data formats for consistency"""
    
    # Navigation
    MAIN_MENU = "main_menu"
    BACK = "back"
    CANCEL = "cancel"
    
    # Authentication
    AUTHENTICATE = "authenticate"
    LOGOUT = "logout"
    
    # User actions
    MY_INFO = "my_info"
    MY_ORDERS = "my_orders"
    
    # Tracking
    TRACK_BY_NUMBER = "track_by_number"
    TRACK_BY_SERIAL = "track_by_serial"
    
    # Services
    REPAIR_REQUEST = "repair_request"
    SUBMIT_COMPLAINT = "submit_complaint"

    # Info pages
    CONTACT_INFO = "contact_info"
    HELP = "help"

    # Dynamic formats (with placeholders)
    ORDER_DETAILS = "order_{}"
    REFRESH_ORDER = "refresh_order:{}"
    DOWNLOAD_REPORT = "download_report:{}"
    DEVICES = "devices_{}"
    PAGE_DEVICES = "page_{}_devices_{}" 
    MY_ORDERS_PAGE = "my_orders_page_{}"
    COMPLAINT_TYPE = "complaint_{}"
    NOOP = "noop"  # For non-clickable buttons
    
    @staticmethod
    def parse_callback(callback_data: str) -> tuple:
        """Parse callback data to extract action and parameters"""
        if ":" in callback_data:
            parts = callback_data.split(":", 1)
            return parts[0], parts[1] if len(parts) > 1 else None
        elif "_" in callback_data:
            parts = callback_data.split("_", 1)
            return parts[0], parts[1] if len(parts) > 1 else None
        return callback_data, None


WORKFLOW_STEPS = {
    0: "ورود مرسوله",
    1: "پیش پذیرش",
    2: "پذیرش",
    3: "تعمیرات",
    4: "صدور صورتحساب",
    5: "خزانه داری",
    6: "خروج کالا",
    7: "ارسال",
    8: "تکمیل اطلاعات",
    9: "منتظر پرداخت",
    10: "راکد",
    50: "پایان عملیات"
}

STEP_PROGRESS = {
    0: 0,    # ورود مرسوله
    1: 10,   # پیش پذیرش
    2: 20,   # پذیرش
    3: 35,   # تعمیرات
    4: 50,   # صدور صورتحساب
    5: 60,   # خزانه داری
    6: 70,   # خروج کالا
    7: 80,   # ارسال
    8: 85,   # تکمیل اطلاعات
    9: 90,   # منتظر پرداخت
    10: 95,  # راکد
    50: 100  # پایان عملیات
}

STEP_ICONS = {
    0: "📥",   # ورود مرسوله
    1: "📝",   # پیش پذیرش
    2: "✅",   # پذیرش
    3: "🔧",   # تعمیرات
    4: "📄",   # صدور صورتحساب
    5: "💰",   # خزانه داری
    6: "📦",   # خروج کالا
    7: "🚚",   # ارسال
    8: "📋",   # تکمیل اطلاعات
    9: "⏳",   # منتظر پرداخت
    10: "⏸️",  # راکد
    50: "✔️"   # پایان عملیات
}

DEVICE_STATUS = {
    0:"ثبت اولیه",
    2:"تست اولیه",
    3:"تعمیرات",
    4:"تست نهایی",
    5:"صورتحساب",
    50:"پایان عملیات"
}

COMPLAINT_TYPE_MAP = {
    ComplaintType.TECHNICAL: "فنی",
    ComplaintType.PAYMENT: "مالی و پرداخت",
    ComplaintType.SHIPPING: "ارسال و تحویل",
    ComplaintType.SERVICE: "خدمات و پشتیبانی",
    ComplaintType.OTHER: "سایر موارد"
}

STATE_LABELS = {
    UserState.IDLE: "غیرفعال",
    UserState.WAITING_nationalId: "در انتظار فعالسازی",
    UserState.AUTHENTICATED: "فعال",
}

def get_step_info(step: int) -> Dict[str, Any]:
    """Get complete step information"""
    progress = STEP_PROGRESS.get(step, 0)
    icon = STEP_ICONS.get(step, '📍')
    text = WORKFLOW_STEPS.get(step, 'نامشخص')
    filled = int((progress / 100) * 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    return {
        'text': text,
        'icon': icon, 
        'progress': progress,
        'display': f"{icon} {text}",
        'bar': bar
    }

MAIN_REPLY_KEYBOARD = [
    [KeyboardButton("🔐 ورود با کد/شناسه ملی"), KeyboardButton("🔢 پیگیری سفارش")],
    [KeyboardButton("#️⃣ پیگیری سریال"), KeyboardButton("📦 سفارشات من")],
    [KeyboardButton("❓ راهنما"), KeyboardButton("👤 اطلاعات من")]
]
CANCEL_REPLY_KEYBOARD = [[KeyboardButton("❌ انصراف")]]

MAIN_INLINE_KEYBOARD = [
    [InlineKeyboardButton("🔐 ورود با کد/شناسه ملی", callback_data=CallbackFormats.AUTHENTICATE)],
    [InlineKeyboardButton("🔢 پیگیری سفارش", callback_data=CallbackFormats.TRACK_BY_NUMBER),
     InlineKeyboardButton("#️⃣ پیگیری سریال", callback_data=CallbackFormats.TRACK_BY_SERIAL)],
    [InlineKeyboardButton("❓ راهنما", callback_data=CallbackFormats.HELP)]
]

REPLY_BUTTON_TO_CALLBACK = {
    "🔐 ورود با کد/شناسه ملی": CallbackFormats.AUTHENTICATE,
    "🔢 پیگیری سفارش": CallbackFormats.TRACK_BY_NUMBER,
    "#️⃣ پیگیری سریال": CallbackFormats.TRACK_BY_SERIAL,
    "📦 سفارشات من": CallbackFormats.MY_ORDERS,
    "❓ راهنما": CallbackFormats.HELP,
    "👤 اطلاعات من": CallbackFormats.MY_INFO,
    "❌ انصراف": CallbackFormats.CANCEL
}

def get_step_display(step: int) -> str:
    """Get step display text with icon"""
    step_info = get_step_info(step)
    return step_info['display']

@dataclass
class BotConfig:
    """Bot configuration"""
    telegram_token: str
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = None
    auth_token: str = ""
    server_urls: Dict[str, str] = field(default_factory=dict)
    maintenance_mode: bool = False
    max_requests_hour: int = 100
    session_timeout: int = 30

    # Constants
    support_phone: str = "03133127"
    website_url: str = "https://hamoonpay.com"
    support_email: str = "support@hamoonpay.com"
    
    def __post_init__(self):
        """Initialize configuration"""
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN required")
        
        if not self.auth_token:
            self.auth_token = os.getenv("AUTH_TOKEN", "")
        
        if not self.server_urls:
            base_url = "http://192.168.41.41:8010/api/v1"
            self.server_urls = {
                "number": os.getenv("SERVER_URL_NUMBER", f"{base_url}/ass-process/GetByNumber"),
                "serial": os.getenv("SERVER_URL_SERIAL", f"{base_url}/ass-process/GetBySerial"),
                "national_id": os.getenv("SERVER_URL_NATIONAL_ID", f"{base_url}/ass-process/GetByNationalID"),  
                "user_orders": os.getenv("SERVER_URL_USER_ORDERS", f"{base_url}/ass-process/GetByNationalID"), # Point to same endpoint
                "submit_complaint": os.getenv("SERVER_URL_COMPLAINT", ""),
                "submit_repair": os.getenv("SERVER_URL_REPAIR", ""),
            }
        
        # Check maintenance mode
        if os.getenv("MAINTENANCE_MODE", "").lower() in ["true", "1", "yes"]:
            self.maintenance_mode = True

@dataclass
class BotMetrics:
    """Metrics tracker"""
    total_sessions: int = 0
    active_sessions: int = 0
    authenticated_users: int = 0
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    
    def increment_request(self):
        self.total_requests += 1
    
    def get_cache_ratio(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

class Validators:
    """Input validators with comprehensive validation and error messages"""
    
    @staticmethod
    def validate_nationalId(nid: str) -> Tuple[bool, Optional[str]]:
        """Validate national ID - supports 10, 11, or 12 digits"""
        if not nid:
            return False, "کد ملی نمی‌تواند خالی باشد"
        nid = nid.strip()
        if not nid.isdigit():
            return False, "کد/شناسه ملی باید فقط شامل ارقام باشد"
        if len(nid) < 10 or len(nid) > 12:
            return False, "کد/شناسه ملی باید 10 تا 12 رقم باشد"
        if len(nid) == 10:
            try:
                check = sum(int(nid[i]) * (10 - i) for i in range(9)) % 11
                if check < 2:
                    valid = int(nid[9]) == check
                else:
                    valid = int(nid[9]) == 11 - check
                return valid, None if valid else "کد ملی نامعتبر است (چک‌سم نامعتبر)"
            except (ValueError, IndexError):
                return False, "فرمت کد ملی نامعتبر است"     
        # For 11-12 digits, just check it's all digits (already done above)
        return True, None

    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate phone number
        Accepts 10-12 digits (Iranian mobile numbers)
        """
        cleaned = re.sub(r'[+\s\-\(\)]', '', phone)
        
        if not cleaned or not cleaned.isdigit() or len(cleaned) != 11:
            return False, "شماره تلفن نامعتبر است"
        
        # Check if it starts with valid Iranian mobile prefix (09)
        if len(cleaned) >= 11 and not cleaned.startswith('09'):
            return False, "شماره تلفن باید با 09 شروع شود"
        
        return True, None
    
    @staticmethod
    def validate_order_number(order_num: str) -> Tuple[bool, Optional[str]]:
        """
        Validate order number
        Accepts 3-10 digits
        """
        if not order_num:
            return False, "شماره سفارش نمی‌تواند خالی باشد"
        cleaned = order_num.strip()
        if not cleaned.isdigit() or len(cleaned) < 3 or len(cleaned) > 10:
            return False, "❌ فرمت شماره سفارش نادرست است" 
        return True, None
    
    @staticmethod
    def validate_serial(serial: str) -> Tuple[bool, Optional[str]]:
        """
        Validate serial number
        Accepts full serial (like 00HEC123456) or last 6 digits (123456)
        """
        if not serial:
            return False, "سریال نامعتبر است"
        
        cleaned = re.sub(r'[ \-\_]', '', serial.upper())
        
        full_pattern = re.match(r'^[A-Z0-9]{10,12}$', cleaned)
        if full_pattern:
            return True, None

        if re.match(r'^\d{6}$', cleaned):
            return True, None
        
        return False, "فرمت سریال نامعتبر است.لطفا 6 رقم آخر سریال خود یا سریال کامل را وارد کنید ❌"
    
    @staticmethod
    def validate_text_length(text: str, min_length: int = 10, max_length: int = 1000) -> Tuple[bool, Optional[str]]:
        """
        Validate text length for complaints and descriptions
        """
        if not text or len(text.strip()) < min_length:
            return False, f"متن باید حداقل {min_length} کاراکتر باشد"
        
        if len(text.strip()) > max_length:
            return False, f"متن نباید بیش از {max_length} کاراکتر باشد"
        
        return True, None
    
    @staticmethod
    def validate_complaint_type(complaint_type: str) -> bool:
        """
        Validate complaint type against allowed types
        """
        from .CoreConfig import ComplaintType
        valid_types = [t.value for t in ComplaintType]
        return complaint_type in valid_types

MESSAGES = {
    'welcome': """🌟 سلام! خوش اومدی به ربات پشتیبانی تجارت الکترونیک هامون  
   🤖 من دستیار هوشمندت هستم و اینجام تا بهت کمک کنم   

  در موارد زیر راهنماییت میکنم:
    -🛒 ثبت سفارش  
    -🛍️ پیگیری سفارش  
    -🔧 پیگیری یا ثبت تعمیرات
    -💬 ثبت نظر یا شکایت  

    میتونی از منوی زیر وارد پنل خودت بشی 👇""",

    'order_details': """📦 جزئیات سفارش

🔢 شماره: {order_number}
👤 نام: {customer_name}
📱 دستگاه: {device_model}

{progress_bar}
📍 {status}

📅 ثبت: {registration_date}

{additional_info}""",

'help': """📚 راهنمای کامل ربات پشتیبانی

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔹 چطور شروع کنم؟

1️⃣ ورود به سیستم
   کافیه کد/شناسه ملی خودتون رو وارد کنید 🆔 
   - بعد از ورود، به تمام امکانات دسترسی دارید ✅
2️⃣ پیگیری سفارش
   دو روش دارید:
   - شماره پذیرش ( 0123456 )  🔢
   - سریال دستگاه ( 01HEC2345678 ) #️⃣

━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 امکانات ویژه برای شما

بعد از ورود می‌تونید:

📦 سفارشات من
-   مشاهده همه سفارشات فعال و گذشته(در دست تعمیر یا ارسال)
🔧 درخواست تعمیر
-   ثبت درخواست تعمیرات  برای دستگاه جدید
🛒 ثبت سفارش
-   ثبت سفارش از طریق ربات و مشاهده دستگاه‌ها در سایت شرکت هامون    
💬 ثبت شکایات
-   ثبت شکایت یا پیشنهاد به صورت فوری

━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 نکات مفید

• ⏰ جلسه و فعالیت شما بعد از 30 دقیقه بدون فعالیت بسته میشه
   برای
- انصراف از هر عملیات /cancel 🔄
- برگشت به منو اصلی /menu 🏠
- خروج از حساب /logout 🚪
   رو بزنید. ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━
❓ سوالات متداول

🤔 کد/شناسه ملیم رو فراموش کردم یا به شماره همراه ثبت شده دسترسی ندارم
↳ از طریق شماره پذیرش یا سریال از وضعیت دستگاه خود اطلاع پیدا کنید.

🤔 شماره پذیرشم رو گم کردم
↳ با سریال دستگاه پیگیری کنید.

🤔 چطور شکایت یا نظراتم رو ثبت کنم؟
↳ از منو گزینه "ثبت شکایت" رو انتخاب کنید(ابتدا باید از طریق کد/شناسه ملی خود وارد سیستم شوید)

━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 ارتباط با ما

در کنار شما هستیم. 🤝
📍 آدرس: اصفهان، خیابان توحید میانی، بعد از بانک پارسیان، بین کوچه 14 و 12 ساختمان آریا طبقه دوم واحد 201
🕐 ساعات کاری:
- شنبه تا چهارشنبه:  08:00 - 16:30
- پنجشنبه:  08:00 - 12:00 

☎️ تلفن: {support_phone}
-شنبه تا چهارشنبه: (08:00 - 16:30)
- پنجشنبه: (08:00 - 12:00)

🌐 وب‌سایت رسمی تجارت الکترونیک هامون : {website_url}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💙 ممنون که همراه ما هستید!
با آرزوی بهترین‌ها برای شما 🌹""",

    'contact_info': """📞 اطلاعات تماس

☎️ {support_phone}
🌐 {website_url}
📧 {support_email}""",

    'payment_link': """💳 لینک پرداخت
    مبلغ قابل پرداخت: {amount:,} تومان
    برای مشاهده فاکتور و پرداخت روی لینک زیر کلیک کنید:
    [🔗 مشاهده فاکتور و پرداخت]({link})

    ⚠️ این لینک شامل فاکتور کامل خدمات نیز می‌باشد.""",

    'payment_completed': """✅ پرداخت انجام شده
    شماره فاکتور: {invoice_id}
    کد مرجع: {reference_code}
    مبلغ پرداختی: {amount:,} تومان
    تاریخ پرداخت: {payment_date}""",

    'maintenance': "🔧 سیستم در حال به‌روزرسانی\n\n☎️ پشتیبانی: {support_phone}",
    'rate_limited': "⚠️ محدودیت درخواست\n\nلطفا {minutes} دقیقه صبر کنید.",
    'auth_request': "🔐 لطفا کد/شناسه ملی خود را وارد کنید:",
    'auth_success': "✅ احراز هویت موفق\n\nخوش آمدید {name} عزیز!",
    'auth_failed': "❌ کد/شناسه ملی یافت نشد",
    'order_not_found': "❌ سفارش یافت نشد\n\nلطفا شماره را بررسی کنید.",
    'validation_error': "❌ {error_message}\n\nلطفاً دوباره تلاش کنید:",
    'invalid_national_id': "❌ کد/شناسه ملی نامعتبر است",
    'invalid_phone': "❌ شماره تلفن نامعتبر است", 
    'invalid_order_number': "❌ شماره سفارش نامعتبر است",
    'invalid_serial': "❌ سریال نامعتبر است",
    'text_too_short': "⚠️ متن باید حداقل 10 کاراکتر باشد",
    'repair_submitted': "✅ درخواست تعمیر ثبت شد\n\n📋 شماره: {request_number}",
    'complaint_submitted': "✅ شکایت ثبت شد\n\n🎫 شماره: {ticket_number}",
    'invalid_input': "❌ ورودی نامعتبر",
    'session_expired': "⏱ جلسه منقضی شد\n\nدوباره /start کنید",
    'error': "❌ خطا در پردازش\n لطفا دوباره امتحان کنید.",
    'loading': "⏳ در حال جستجو...",
    'no_orders_found': "📭 سفارشی یافت نشد",
    'enter_complaint_text': "📝 متن شکایت را بنویسید:", 
    'enter_repair_description': "🔧 توضیحات تعمیر:",
    'order_tracking_prompt': "🔢 شماره پذیرش:",
    'serial_tracking_prompt': "#️⃣ سریال دستگاه:",
}


def initialize_core():
    """Initialize core components"""
    config = BotConfig(
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        redis_password=os.getenv("REDIS_PASSWORD"),
        maintenance_mode=os.getenv("MAINTENANCE_MODE", "false").lower() == "true",
        max_requests_hour=int(os.getenv("MAX_REQUESTS_HOUR", "100")),
        session_timeout=int(os.getenv("SESSION_TIMEOUT", "30")),
    )
    
    metrics = BotMetrics()
    validators = Validators()
    
    return config, validators, metrics