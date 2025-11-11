""" Unified formatting module for all display and text formatting needs - Combines display layouts with utility formatters """
from __future__ import annotations
import jdatetime
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Any, Tuple, Union
from src.config.enums import WorkflowSteps, DeviceStatus
from src.config.callbacks import OrderCallback
from src.models.user import UserSession
from src.models.domain import Order

def safe_get(data: Any, *keys, default: Any = None) -> Any:
    """Safely get nested attributes or dict keys."""
    current = data
    for key in keys:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(key, default)
        elif isinstance(current, (list, tuple)) and isinstance(key, int):
            try:
                current = current[key]
            except (IndexError, KeyError):
                return default
        elif hasattr(current, key):
            current = getattr(current, key, default)
        else:
            return default
    return current if current is not None else default

def gregorian_to_jalali(dt: datetime | str) -> str:
    """Convert Gregorian datetime/ISO string to Jalali date string."""
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return f"{j.year}/{j.month:02d}/{j.day:02d}"
    except Exception:
        return "نامشخص"


@dataclass
class FormatConfig:
    """Centralized formatting configuration"""
    max_items_per_page: int = 5
    max_devices_preview: int = 3
    devices_per_page: int = 8
    min_text_length: int = 10
    max_text_length: int = 1000

class Formatters:
    """Atomic + structured text formatters used throughout bot"""
    
    config = FormatConfig()

    @classmethod
    def user_info(cls, session: UserSession) -> Tuple[str, list]:
        """Handle both UserSession object and dict"""
        name = session.user_name or 'نامشخص'
        nid = session.national_id or 'نامشخص'
        phone = session.phone_number or 'ثبت نشده'
        city = session.city or 'ثبت نشده'
        is_auth = session.is_authenticated
        
        auth_status = "احراز هویت شده" if is_auth else "عدم احراز هویت"
        visit = gregorian_to_jalali(datetime.now())
        txt = (
            "👤 **اطلاعات حساب کاربری**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👨‍💼 **مشتری:** {name}\n"
            f"🌐 **کد/شناسه ملی:** `{nid}`\n"
            f"📱 **شماره همراه:** `{phone}`\n"
            f"📍 **استان/شهر:** {city}\n"
            f"🔐 **وضعیت:** {auth_status}\n\n"
            f"⏰ **آخرین بازدید:** {visit}"
        )
        return txt, []

    @classmethod
    def my_orders_summary(cls, session:UserSession) -> Tuple[str, list]:
        """Generate order summary using the cached order data."""
        raw = session.temp_data.get("raw_auth_data", {})
        orders = session.last_orders or []
        order_number = raw.get("order_number") or session.order_number or "نامشخص"
        invoice_number = raw.get("invoice_number") or ""
        payment_link = raw.get("payment_link") or ""
        factor_paid = bool(raw.get("factorPayment") or raw.get("payment"))
        
        devices = raw.get("devices", [])
        total_devices = len(devices) if devices else 0

        if payment_link:
            if factor_paid :
                payment_line = f"🧾 فاکتور پرداخت شده (شماره: `{invoice_number}`)"
            else:
                payment_line = f"💳 فاکتور آماده پرداخت (شماره: `{invoice_number}`)"
        else:
            payment_line = "⚠️ هنوز فاکتور پرداختی ثبت نشده است."

        text = (
            f"📦 **وضعیت سفارشات شما**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            "**مشخصات آخرین سفارش شما** \n"
            f"🔢 شماره پذیرش شما: `{order_number}`\n"
            f"📱 تعداد کل دستگاه‌ها: {total_devices}\n\n"
            f"{payment_line}\n"
        )
        return text.strip(), []

    @classmethod
    def order_list(cls, orders: List[Dict], page: int = 1) -> str:
        """ Format paginated orders list """
        if not orders:
            return "📦 **سفارشات شما**\n\nهیچ سفارشی یافت نشد."
        
        per_page = cls.config.max_items_per_page
        total_pages = max(1, (len(orders) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start, end = (page - 1) * per_page, min(page * per_page, len(orders))
        display_orders = orders[start:end]
        
        total_devices = sum(len(order.get('devices', [])) for order in orders)
        total_orders = len(orders)
        text = f"📦 *سفارشات شما* (مجموع: {total_orders})\nصفحه {page}/{total_pages}\n\n"
        text += f"تعداد دستگاه‌های شما: {total_devices}\n"

        for i, order in enumerate(display_orders, start=start + 1):
            order_num = order.get('order_number', '---')
            step = order.get('steps', 0)
            step_info = WorkflowSteps.get_step_info(step)
            text += f"{i}. **شماره پذیرش:**  `{order_num}`\n"
            text += f"📊 **وضعیت کلی سفارش:**\n {step_info['name']} {step_info['icon']} \n"
            text += f"{step_info['bar']} % {step_info['progress']}\n\n"
        return text
    
    @classmethod
    def order_detail(cls, order: Union[Order, dict], is_auth: bool = False) -> Tuple[str, List]:
        
        if not order or (isinstance(order, dict) and order.get("semantic_error")):
            return "❌ خطا در دریافت اطلاعات سفارش از سرور.", []

        if isinstance(order, dict):
            order = Order.model_validate(order)

        if not order:
            return "❌ اطلاعات سفارش یافت نشد", []

        step = WorkflowSteps.get_step_info(order.status_code)
        reg_date = order.registration_date or "نامشخص"
        visit = gregorian_to_jalali(datetime.now())

        devices = order.devices or []
        preview_count = cls.config.max_devices_preview
        visible = devices[:preview_count]
        dev_txt = ""

        if not devices:
            dev_txt = "📱 هیچ دستگاهی ثبت نشده است."
        elif len(devices) == 1:
            d = visible[0]
            dev_txt = (
                "**📱 مشخصات دستگاه:**\n"
                f"- مدل: {d.model}\n"
                f"- سریال: `{d.serial}`\n"
                f"- وضعیت: {DeviceStatus.get_display(d.status_code)}\n\n"
            )
        else:
            dev_txt += f"📱 تعداد کل دستگاه‌ها: {len(devices)}\n\n"
            for i, d in enumerate(visible, 1):
                dev_txt += (
                    f"**دستگاه {i}:**\n"
                    f"- مدل: {d.model}\n"
                    f"- سریال: `{d.serial}`\n"
                    f"- وضعیت: {DeviceStatus.get_display(d.status_code)}\n\n"
                )
            if len(devices) > preview_count:
                dev_txt += f"و {len(devices)-preview_count} دستگاه دیگر ...\n"

        pay_caption = ""
        if order.is_paid:
            pay_caption = f"🧾 فاکتور پرداخت شده (شماره: {order.invoice_number or 'نامشخص'})\n"
        elif order.has_payment_link:
            pay_caption = f"💳 فاکتور قابل پرداخت (شماره: {order.invoice_number or 'نامشخص'})\n"
        else:
            pay_caption = "⏳ در انتظار صدور فاکتور"
            
        txt = (
            "📋 **جزئیات سفارش**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 شماره پذیرش: `{order.order_number}`\n"
            f"🗂 کد رهگیری پذیرش (رسید انبار): `{order.tracking_code or '---'}`\n"
            f"📅 تاریخ ثبت انبار: {reg_date}\n\n"
            f"📊 **وضعیت کلی سفارش:**\n {step['name']} {step['icon']} \n"
            f"{step['bar']} % {step['progress']}\n\n"
            f"{dev_txt}\n{pay_caption}\n⏰ **آخرین بازدید:** {visit}"
        )

        buttons = []
        if len(devices) > preview_count:
            buttons.append({
                "text": "🔍 مشاهده لیست کامل دستگاه‌ها",
                "callback": OrderCallback(action="devices_list", order_number=order.order_number, page=1).pack()
            })
        if is_auth:
            buttons.append({
                "text": "🔙 بازگشت به سفارش‌های من",
                "callback": OrderCallback(action="orders_list").pack()
            })
        return txt, buttons
    
    @classmethod
    def device_list_paginated(cls, order: Dict[str, Any], page: int = 1) -> str:
        """Formats a dedicated, paginated list of devices for an order - Shows 8 devices per page."""
        order_number = safe_get(order, "order_number", default="---")
        devices = safe_get(order, "devices", default=[])
        total_devices = len(devices)

        if total_devices == 0:
            return "📱 هیچ دستگاهی برای این سفارش ثبت نشده است."

        per_page = cls.config.devices_per_page
        total_pages = max(1, (total_devices + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))

        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        visible_devices = devices[start_index:end_index]

        text = (
            f"📱 **لیست دستگاه‌های سفارش `{order_number}`**\n"
            f"صفحه {page}/{total_pages} (نمایش {start_index + 1} تا {min(end_index, total_devices)} از {total_devices})\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for i, dev in enumerate(visible_devices, start=start_index + 1):
            model = safe_get(dev, "model", default="نامشخص")
            serial = safe_get(dev, "serial", default="---")
            status_raw = safe_get(dev, "status_code") or safe_get(dev, "status", default=0)
            device_status = DeviceStatus.get_display(status_raw)

            text += (
                f"**دستگاه {i}:**\n"
                f"- مدل: {model}\n"
                f"- سریال: `{serial}`\n"
                f"- وضعیت: {device_status}\n\n"
            )
        return text

    @classmethod
    def complaint_submitted(cls, ticket_number: str, complaint_type: str) -> str:
        """Formats the complaint submission confirmation message."""
        date = gregorian_to_jalali(datetime.now())
        return (
            f"✅ **شکایت شما با موفقیت ثبت شد**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎫 **شماره پیگیری درخواست(تیکت):** `{ticket_number}`\n"
            f"📌 **نوع شکایت:** {complaint_type}\n"
            f"📅 **تاریخ ثبت:** {date}\n\n"
            f"همکاران ما در اسرع وقت به درخواست شما رسیدگی خواهند کرد."
        )

    @classmethod
    def repair_submitted(cls, ticket_number: str) -> str:
        """Formats the repair request submission confirmation message."""
        date = gregorian_to_jalali(datetime.now())
        return (
            f"✅ **درخواست تعمیر شما با موفقیت ثبت شد**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎫 **شماره پیگیری درخواست(تیکت):** `{ticket_number}`\n"
            f"📅 **تاریخ ثبت:** {date}\n\n"
            f"نتیجه بررسی و هماهنگی‌های بعدی به شما اطلاع‌رسانی خواهد شد."
        )
