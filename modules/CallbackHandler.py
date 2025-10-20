"""
Callback Handler - Handles all inline keyboard interactions
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest

from .CoreConfig import (
    COMPLAINT_TYPE_MAP,
    MAIN_INLINE_KEYBOARD,
    MESSAGES,
    STEP_ICONS,
    WORKFLOW_STEPS,
    CallbackFormats,
    ComplaintType,
    UserState,
    get_step_display,
    get_step_info,
)
from .DataProvider import DataProvider, OrderInfo
from .SessionManager import RedisSessionManager

if TYPE_CHECKING:
    from .MessageHandler import MessageHandler

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Handles all callback queries from inline keyboards - COMPLETE IMPLEMENTATION"""

    def __init__(
        self,
        message_handler: "MessageHandler",
        session_manager: RedisSessionManager,
        data_provider: DataProvider,
    ):
        self.msg = message_handler
        self.sessions = session_manager
        self.data = data_provider
        self.ORDERS_PER_PAGE = 5

    async def handle_callback(self, update: Update):
        """Main callback router - handles all button clicks"""
        query: Optional[CallbackQuery] = update.callback_query
        if not query or not query.data:
            return

        # Answer callback immediately
        try:
            await query.answer()
        except BadRequest as e:
            if "query is too old" in str(e).lower():
                logger.debug("Ignoring old callback query")
                return
            raise e

        user_id = query.from_user.id
        chat_id = query.message.chat.id
        message_id = query.message.message_id
        data = query.data

        logger.info(f"Callback '{data}' from user {user_id} in chat {chat_id}")

        try:
            async with self.sessions.session(chat_id) as session:
                session.temp_data["last_bot_message_id"] = message_id

                # Route to specific handlers
                await self._route_callback(query, chat_id, message_id, data, session)

        except Exception as e:
            logger.error(f"Callback error [{data}]: {e}", exc_info=True)
            try:
                await query.answer("❌ خطایی رخ داد", show_alert=True)
                await self._show_error(chat_id, message_id)
            except:
                pass

    async def _route_callback(
        self, query: CallbackQuery, chat_id: int, message_id: int, data: str, session
    ):
        """Route callbacks to appropriate handlers"""

        if data in [CallbackFormats.MAIN_MENU, "main_menu"]:
            await self.handle_main_menu(chat_id, message_id, session)
        elif data in [CallbackFormats.BACK, "back"]:
            await self.handle_back(chat_id, message_id, session)
        elif data in [CallbackFormats.CANCEL, "cancel"]:
            await self.handle_cancel(chat_id, message_id, session)
        elif data in [CallbackFormats.AUTHENTICATE, "authenticate"]:
            await self.handle_authenticate(chat_id, message_id, session)
        elif data in [CallbackFormats.LOGOUT, "logout"]:
            await self.handle_logout(chat_id, message_id, session)
        elif data in [CallbackFormats.MY_INFO, "my_info"]:
            await self.handle_my_info(chat_id, message_id, session)
        elif data in [CallbackFormats.MY_ORDERS, "my_orders"]:
            await self.handle_my_orders(chat_id, message_id, session, page=1)
        elif data in [CallbackFormats.TRACK_BY_NUMBER, "track_by_number"]:
            await self.handle_track_by_number(chat_id, message_id, session)
        elif data in [CallbackFormats.TRACK_BY_SERIAL, "track_by_serial"]:
            await self.handle_track_by_serial(chat_id, message_id, session)
        elif data in [CallbackFormats.REPAIR_REQUEST, "repair_request"]:
            await self.handle_repair_request(chat_id, message_id, session)
        elif data in [CallbackFormats.SUBMIT_COMPLAINT, "submit_complaint"]:
            await self.handle_submit_complaint(chat_id, message_id, session)
        elif data.startswith("complaint_"):
            await self.handle_complaint_type(chat_id, message_id, data, session)
        elif data.startswith("my_orders_page_"):
            page = self._extract_page_number(data)
            await self.handle_my_orders(chat_id, message_id, session, page)
        elif data.startswith("order_"):
            order_number = self._extract_order_number(data)
            await self.handle_order_details(chat_id, message_id, order_number, session)
        elif data.startswith("refresh_order:"):
            order_number = data.split(":", 1)[1]
            await self.handle_refresh_order(chat_id, message_id, order_number, session)
        elif data.startswith("devices_"):
            order_number = self._extract_order_number(data)
            await self.handle_devices_list(
                chat_id, message_id, order_number, session, page=1
            )
        elif data.startswith("page_") and "devices" in data:
            page, order_number = self._extract_device_page(data)
            await self.handle_devices_list(
                chat_id, message_id, order_number, session, page
            )
        elif data in [CallbackFormats.HELP, "help"]:
            await self.handle_help(chat_id, message_id, session)
        elif data in [CallbackFormats.NOOP, "noop"]:
            pass
        else:
            logger.warning(f"Unhandled callback data: {data}")
            await self._show_error(chat_id, message_id, "عملیات نامشخص")

    # ========== UTILITY METHODS ==========
    def _extract_page_number(self, data: str) -> int:
        """Extract page number from callback data"""
        try:
            return int(data.replace("my_orders_page_", ""))
        except ValueError:
            return 1

    def _extract_order_number(self, data: str) -> str:
        """Extract order number from callback data"""
        try:
            return data.replace("order_", "").replace("devices_", "")
        except:
            return ""

    def _extract_device_page(self, data: str) -> tuple:
        """Extract page and order number from device pagination"""
        parts = data.split("_")
        try:
            page = int(parts[1])
            order_number = parts[3]
            return page, order_number
        except:
            return 1, ""

    async def _show_error(self, chat_id: int, message_id: int, error_msg: str = None):
        """Show error with back button"""
        text = error_msg or "❌ خطایی رخ داد"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            ]
        )

        try:
            await self.msg.edit_message(
                chat_id, message_id, text, reply_markup=keyboard, activate_keyboard=True
            )
        except Exception as e:
            logger.error(f"Error showing error: {e}")

    async def _require_auth(self, chat_id: int, message_id: int, session):
        """Show authentication required"""
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔐 ورود", callback_data=CallbackFormats.AUTHENTICATE
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                    )
                ],
            ]
        )

        await self.msg.edit_message(
            chat_id,
            message_id,
            "⚠️ ابتدا وارد حساب کاربری شوید",
            reply_markup=keyboard,
            activate_keyboard=True,
        )

    # ========== NAVIGATION HANDLERS ==========
    async def handle_main_menu(self, chat_id: int, message_id: int, session):
        """Show appropriate main menu based on authentication"""
        try:
            session.temp_data.pop("last_menu_type", None)

            if session.is_authenticated and session.nationalId:
                session.state = UserState.AUTHENTICATED
                await self._show_authenticated_menu(
                    chat_id, message_id, session.user_name
                )
            else:
                session.state = UserState.IDLE
                await self._show_main_menu(chat_id, message_id)

        except Exception as e:
            logger.error(f"Main menu error: {e}")
            await self._show_error(chat_id, message_id)

    async def handle_back(self, chat_id: int, message_id: int, session):
        """Go back to main menu"""
        await self.handle_main_menu(chat_id, message_id, session)

    async def handle_cancel(self, chat_id: int, message_id: int, session):
        """Cancel current operation and return to menu"""
        try:
            # Reset operation state
            session.state = (
                UserState.IDLE
                if not session.is_authenticated
                else UserState.AUTHENTICATED
            )
            session.temp_data.pop("last_menu_type", None)
            session.temp_data.pop("complaint_type", None)
            session.temp_data.pop("lookup_type", None)
            session.temp_data.pop("lookup_value", None)

            # Show cancel message briefly
            try:
                await self.msg.edit_message(
                    chat_id,
                    message_id,
                    "❌ عملیات لغو شد",
                    reply_markup=None,
                    activate_keyboard=False,
                )
                await asyncio.sleep(1)
            except:
                pass

            # Return to main menu
            await self.handle_main_menu(chat_id, message_id, session)

        except Exception as e:
            logger.error(f"Cancel error: {e}")
            await self.handle_main_menu(chat_id, message_id, session)

    # ========== AUTHENTICATION HANDLERS ==========
    async def handle_authenticate(self, chat_id: int, message_id: int, session):
        """Start authentication flow"""
        session.state = UserState.WAITING_nationalId
        session.temp_data.pop("last_menu_type", None)

        text = MESSAGES["auth_request"]
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            ]
        )

        await self.msg.edit_message(
            chat_id, message_id, text, reply_markup=keyboard, activate_keyboard=True
        )

    async def handle_logout(self, chat_id: int, message_id: int, session):
        """Handle user logout"""
        try:
            await self.sessions.logout(session.user_id)
            await self.msg.edit_message(
                chat_id,
                message_id,
                "✅ با موفقیت خارج شدید",
                reply_markup=None,
                activate_keyboard=True,
            )
            await asyncio.sleep(1)
            await self._show_main_menu(chat_id, message_id)
        except Exception as e:
            logger.error(f"Logout error: {e}")
            await self._show_error(chat_id, message_id)

    # ========== USER INFO HANDLERS ==========
    async def handle_my_info(self, chat_id: int, message_id: int, session):
        """Display user profile information"""
        if not session.is_authenticated:
            await self._show_main_menu(chat_id, message_id)
            return

        # Get user data from session
        name = session.user_name or "ثبت نشده"
        national_id = session.nationalId or "نامشخص"
        phone = session.phone_number or "ثبت نشده"
        city = session.city or "ثبت نشده"

        info_text = f"""👤 **اطلاعات کاربری**

👤 نام: {name}
🆔 کد ملی: `{national_id}`
📱 تلفن: {phone}
🏙️ شهر: {city}

📊 **وضعیت حساب**: فعال ✅"""

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            ]
        )

        await self.msg.edit_message(
            chat_id,
            message_id,
            info_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
            activate_keyboard=True,
        )

    async def handle_my_orders(
        self, chat_id: int, message_id: int, session, page: int = 1
    ):
        """Show user's orders with pagination"""
        if not session.is_authenticated:
            await self._require_auth(chat_id, message_id, session)
            return

        try:
            await self.msg.edit_message(
                chat_id,
                message_id,
                "⏳ در حال دریافت سفارشات...",
                activate_keyboard=False,
            )

            orders_result = await self.data.get_user_orders(session.nationalId)

            if isinstance(orders_result, list):
                if orders_result and isinstance(orders_result[0], dict):
                    orders = []
                    for order_data in orders_result:
                        parsed_order = self.data._parse_order_response(order_data)
                        if parsed_order:
                            orders.append(parsed_order)
                else:
                    orders = orders_result
            elif isinstance(orders_result, dict) and orders_result.get("success"):
                orders_data = orders_result.get("data", orders_result.get("orders", []))
                orders = []
                for order_data in orders_data:
                    if isinstance(order_data, dict):
                        parsed_order = self.data._parse_order_response(order_data)
                        if parsed_order:
                            orders.append(parsed_order)
            else:
                orders = []

            if not orders:
                text = "📭 **سفارش فعالی یافت نشد**\n\nبرای مشاهده سفارشات گذشته، با پشتیبانی تماس بگیرید."
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                            )
                        ]
                    ]
                )

                await self.msg.edit_message(
                    chat_id,
                    message_id,
                    text,
                    reply_markup=keyboard,
                    activate_keyboard=True,
                )
                return

            # Pagination
            total_pages = (
                len(orders) + self.ORDERS_PER_PAGE - 1
            ) // self.ORDERS_PER_PAGE
            page = max(1, min(page, total_pages))
            start_idx = (page - 1) * self.ORDERS_PER_PAGE
            end_idx = min(start_idx + self.ORDERS_PER_PAGE, len(orders))
            page_orders = orders[start_idx:end_idx]

            # Build display
            text = f"📦 **سفارشات شما** (صفحه {page} از {total_pages})\n\n"

            buttons = []
            for i, order in enumerate(page_orders, start_idx + 1):
                order_num = order.order_number
                step = order.steps
                status_icon = STEP_ICONS.get(step, "📍")
                status_text = get_step_display(step)

                text += f"{i}. {status_icon} `{order_num}`\n"
                text += f"   📱 {order.device_model}\n"
                text += f"   📅 {order.registration_date or 'نامشخص'}\n"
                text += f"   📍 {status_text}\n\n"

                # Add order button
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"{status_icon} {order_num}",
                            callback_data=f"order_{order_num}",
                        )
                    ]
                )

            text += f"📊 نمایش {start_idx + 1}-{end_idx} از {len(orders)} سفارش"

            # Navigation buttons
            nav_row = []
            if page > 1:
                nav_row.append(
                    InlineKeyboardButton(
                        "⬅️ قبلی", callback_data=f"my_orders_page_{page-1}"
                    )
                )
            nav_row.append(
                InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")
            )
            if page < total_pages:
                nav_row.append(
                    InlineKeyboardButton(
                        "➡️ بعدی", callback_data=f"my_orders_page_{page+1}"
                    )
                )

            if nav_row:
                buttons.append(nav_row)

            # Quick navigation for many pages
            if total_pages > 3:
                quick_nav = []
                if page > 2:
                    quick_nav.append(
                        InlineKeyboardButton("⏮ اول", callback_data="my_orders_page_1")
                    )
                if page < total_pages - 1:
                    quick_nav.append(
                        InlineKeyboardButton(
                            "⏭ آخر", callback_data=f"my_orders_page_{total_pages}"
                        )
                    )
                if quick_nav:
                    buttons.append(quick_nav)

            buttons.append(
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            )

            await self.msg.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
                activate_keyboard=True,
            )

        except Exception as e:
            logger.error(f"My orders error: {e}")
            await self._show_error(chat_id, message_id)

    # ========== TRACKING HANDLERS ==========
    async def handle_track_by_number(self, chat_id: int, message_id: int, session):
        """Start order number tracking"""
        session.state = UserState.WAITING_ORDER_NUMBER
        session.temp_data.pop("last_menu_type", None)

        text = "🔢 **پیگیری با شماره پذیرش**\n\nلطفاً شماره 6 رقمی پذیرش را وارد کنید:\n\nمثال: `123456`"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 انصراف", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            ]
        )

        await self.msg.edit_message(
            chat_id,
            message_id,
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
            activate_keyboard=True,
        )

    async def handle_track_by_serial(self, chat_id: int, message_id: int, session):
        """Start serial number tracking"""
        session.state = UserState.WAITING_SERIAL
        session.temp_data.pop("last_menu_type", None)

        text = "#️⃣ **پیگیری با سریال دستگاه**\n\nلطفاً شماره سریال 12 رقمی دستگاه را وارد کنید:\n\nمثال: `01HEC2345678`"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 انصراف", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            ]
        )

        await self.msg.edit_message(
            chat_id,
            message_id,
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
            activate_keyboard=True,
        )

    # ========== ORDER DETAIL HANDLERS ==========
    async def handle_order_details(
        self, chat_id: int, message_id: int, order_number: str, session
    ):
        """Show detailed order information"""
        try:
            # Show loading
            await self.msg.edit_message(
                chat_id,
                message_id,
                "⏳ دریافت جزئیات سفارش...",
                activate_keyboard=False,
            )

            # Fetch order
            order_info = await self.data.get_order_by_number(order_number)
            if not order_info:
                await self._show_error(chat_id, message_id, "❌ سفارش یافت نشد")
                return

            # Format detailed view
            text = self._format_order_details(order_info)

            # Build action buttons
            buttons = []

            # Payment button if needed
            if order_info.payment_link and not order_info.factor_payment:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            "💳 پرداخت فاکتور", url=order_info.payment_link
                        )
                    ]
                )

            # Action buttons
            if order_info.devices and len(order_info.devices) > 1:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            "📱 دستگاه‌ها", callback_data=f"devices_{order_number}"
                        )
                    ]
                )

            buttons.extend(
                [
                    [
                        InlineKeyboardButton(
                            "🔄 بروزرسانی",
                            callback_data=f"refresh_order:{order_number}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                        )
                    ],
                ]
            )

            await self.msg.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
                activate_keyboard=True,
            )

        except Exception as e:
            logger.error(f"Order details error: {e}")
            await self._show_error(chat_id, message_id)

    def _format_order_details(self, order_info: OrderInfo) -> str:
        """Format complete order details"""
        step_info = get_step_info(order_info.steps)

        # Progress bar
        progress_text = f"{step_info['icon']} {step_info['text']}"
        progress_bar = f"[{step_info['bar']}] {step_info['progress']}%"

        # Basic info
        basic_info = f"""🔢 **سفارش #{order_info.order_number}**

👤 {order_info.customer_name}
📱 {order_info.device_model}
🔢 {order_info.serial_number}
🏙️ {order_info.city or 'نامشخص'}

📊 **وضعیت:**
{progress_bar}
📍 {progress_text}"""

        # Dates
        dates_section = f"""📅 **زمان‌بندی:**
• ثبت: {order_info.registration_date or 'نامشخص'}
• پیش‌پذیرش: {order_info.pre_reception_date or 'نامشخص'}"""

        # Financial info
        financial_section = ""
        if order_info.total_cost:
            financial_section = f"""💰 **مالی:**
• کل هزینه: {order_info.total_cost:,} تومان"""

            if order_info.payment_link and not order_info.factor_payment:
                financial_section += "\n• وضعیت پرداخت: ⏳ منتظر پرداخت"
            elif order_info.factor_payment:
                financial_section += f"\n• وضعیت پرداخت: ✅ پرداخت شده\n  کد مرجع: {order_info.factor_payment.get('reference_code', '---')}"
            else:
                financial_section += "\n• وضعیت پرداخت: ---"

        # Tracking
        tracking_section = ""
        if order_info.tracking_code:
            tracking_section = f"📦 **ردیابی:** {order_info.tracking_code}"

        # Repair info
        repair_section = ""
        if order_info.repair_description:
            repair_section = f"🔧 **توضیحات تعمیر:**\n{order_info.repair_description}"

        return f"{basic_info}\n\n{dates_section}\n\n{financial_section}\n\n{tracking_section}\n\n{repair_section}"

    async def handle_refresh_order(
        self, chat_id: int, message_id: int, order_number: str, session
    ):
        """Refresh order status"""
        try:
            # Show loading
            await self.msg.edit_message(
                chat_id, message_id, "🔄 در حال بروزرسانی...", activate_keyboard=False
            )

            # Fetch fresh data (force refresh)
            fresh_order = await self.data.get_order(
                order_number, "number", force_refresh=True
            )

            if not fresh_order:
                await self._show_error(chat_id, message_id, "❌ سفارش یافت نشد")
                return

            # Update display
            text = self._format_order_details(fresh_order)

            buttons = [
                [
                    InlineKeyboardButton(
                        "🔄 بروزرسانی مجدد",
                        callback_data=f"refresh_order:{order_number}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU
                    )
                ],
            ]

            # Add payment button if needed
            if fresh_order.payment_link and not fresh_order.factor_payment:
                buttons.insert(
                    0,
                    [
                        InlineKeyboardButton(
                            "💳 پرداخت فاکتور", url=fresh_order.payment_link
                        )
                    ],
                )

            await self.msg.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
                activate_keyboard=True,
            )

        except Exception as e:
            logger.error(f"Refresh error: {e}")
            await self._show_error(chat_id, message_id)

    # ========== DEVICE HANDLERS (for multi-device orders) ==========
    async def handle_devices_list(
        self, chat_id: int, message_id: int, order_number: str, session, page: int = 1
    ):
        """Show list of devices for an order"""
        try:
            # Fetch order to get devices
            order_info = await self.data.get_order_by_number(order_number)
            if not order_info or not order_info.devices:
                await self._show_error(
                    chat_id, message_id, "❌ اطلاعات دستگاه یافت نشد"
                )
                return

            devices = order_info.devices
            total_pages = (len(devices) + 3 - 1) // 3  # 3 devices per page
            page = max(1, min(page, total_pages))
            start_idx = (page - 1) * 3
            end_idx = min(start_idx + 3, len(devices))
            page_devices = devices[start_idx:end_idx]

            # Build display
            text = f"📱 **دستگاه‌های سفارش {order_number}**\n\n"

            buttons = []
            for i, device in enumerate(page_devices, start_idx + 1):
                model = device.get("model", "نامشخص")
                serial = device.get("serial", "---")
                status_code = device.get("status_code", 0)
                status = device.get("status", "نامشخص")
                status_icon = STEP_ICONS.get(status_code, "📍")

                text += f"{i}. {status_icon} **{model}**\n"
                text += f"   🔢 سریال: `{serial}`\n"
                text += f"   📍 وضعیت: {status}\n\n"

                # Device detail button (if needed)
                buttons.append(
                    [
                        InlineKeyboardButton(
                            f"{status_icon} {model[:20]}...",
                            callback_data=f"device_detail_{serial}",
                        )
                    ]
                )

            text += f"📊 نمایش {start_idx + 1}-{end_idx} از {len(devices)} دستگاه"

            # Navigation
            if total_pages > 1:
                nav_row = []
                if page > 1:
                    nav_row.append(
                        InlineKeyboardButton(
                            "⬅️ قبلی",
                            callback_data=f"page_{page-1}_devices_{order_number}",
                        )
                    )
                nav_row.append(
                    InlineKeyboardButton(
                        f"📱 {page}/{total_pages}", callback_data="noop"
                    )
                )
                if page < total_pages:
                    nav_row.append(
                        InlineKeyboardButton(
                            "➡️ بعدی",
                            callback_data=f"page_{page+1}_devices_{order_number}",
                        )
                    )
                buttons.append(nav_row)

            buttons.append(
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت", callback_data=f"order_{order_number}"
                    )
                ]
            )

            await self.msg.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
                activate_keyboard=True,
            )

        except Exception as e:
            logger.error(f"Devices list error: {e}")
            await self._show_error(chat_id, message_id)

    # ========== SERVICE HANDLERS ==========
    async def handle_repair_request(self, chat_id: int, message_id: int, session):
        """Start repair request flow"""
        if not session.is_authenticated:
            await self._require_auth(chat_id, message_id, session)
            return

        session.state = UserState.WAITING_REPAIR_DESC
        session.temp_data.pop("last_menu_type", None)

        text = """🔧 **درخواست تعمیر**

لطفاً مشکل دستگاه خود را با جزئیات شرح دهید:

💡 **نکات مهم:**
• نوع دستگاه و مدل
• مشکل اصلی (نرم‌افزاری/سخت‌افزاری)
• زمان وقوع مشکل
• اقدامات انجام شده

حداقل 20 کاراکتر"""

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ انصراف", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            ]
        )

        await self.msg.edit_message(
            chat_id,
            message_id,
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
            activate_keyboard=True,
        )

    async def handle_submit_complaint(self, chat_id: int, message_id: int, session):
        """Start complaint submission flow"""
        if not session.is_authenticated:
            await self._require_auth(chat_id, message_id, session)
            return

        session.state = UserState.WAITING_COMPLAINT_TYPE
        session.temp_data.pop("last_menu_type", None)

        text = """📝 **ثبت شکایت/پیشنهاد**

لطفاً نوع موضوع را انتخاب کنید تا بتوانیم بهتر به شما کمک کنیم:"""

        # Complaint type keyboard
        complaint_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔧 مشکل فنی", callback_data="complaint_technical"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💰 مسائل مالی", callback_data="complaint_payment"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📦 ارسال/تحویل", callback_data="complaint_shipping"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🎧 پشتیبانی", callback_data="complaint_service"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📝 سایر موارد", callback_data="complaint_other"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ انصراف", callback_data=CallbackFormats.MAIN_MENU
                    )
                ],
            ]
        )

        await self.msg.edit_message(
            chat_id,
            message_id,
            text,
            reply_markup=complaint_keyboard,
            parse_mode=ParseMode.MARKDOWN,
            activate_keyboard=True,
        )

    async def handle_complaint_type(
        self, chat_id: int, message_id: int, data: str, session
    ):
        """Handle complaint type selection"""
        # Map callback data to ComplaintType
        complaint_mapping = {
            "complaint_technical": ComplaintType.TECHNICAL,
            "complaint_payment": ComplaintType.PAYMENT,
            "complaint_shipping": ComplaintType.SHIPPING,
            "complaint_service": ComplaintType.SERVICE,
            "complaint_other": ComplaintType.OTHER,
        }

        complaint_type = complaint_mapping.get(data)
        if not complaint_type:
            await self._show_error(chat_id, message_id, "نوع شکایت نامعتبر")
            return

        # Set session state
        session.state = UserState.WAITING_COMPLAINT_TEXT
        session.temp_data["complaint_type"] = complaint_type
        session.temp_data.pop("last_menu_type", None)

        # Show type confirmation and text input prompt
        type_display = COMPLAINT_TYPE_MAP.get(complaint_type, "سایر")
        text = f"""📝 **{type_display}**

حالا لطفاً جزئیات شکایت/پیشنهاد خود را بنویسید:

💡 **نکات:**
• شرح کامل مشکل
• تاریخ وقوع
• اطلاعات تماس (در صورت نیاز)
• مدارک/تصاویر (در صورت وجود)

حداقل 30 کاراکتر"""

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ انصراف", callback_data=CallbackFormats.MAIN_MENU
                    )
                ]
            ]
        )

        await self.msg.edit_message(
            chat_id,
            message_id,
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
            activate_keyboard=True,
        )

    # ========== HELP & INFO ==========
    async def handle_help(self, chat_id: int, message_id: int, session):
        """Show comprehensive help information"""
        try:
            help_text = MESSAGES["help"].format(
                support_phone=self.msg.config.support_phone,
                website_url=self.msg.config.website_url,
                support_email=self.msg.config.support_email,
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 منوی اصلی", callback_data=CallbackFormats.MAIN_MENU
                        )
                    ]
                ]
            )

            if message_id:
                await self.msg.edit_message(
                    chat_id,
                    message_id,
                    help_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                    activate_keyboard=True,
                )
            else:
                await self.msg.send_message(
                    chat_id,
                    help_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                    activate_keyboard=True,
                )

        except Exception as e:
            logger.error(f"Help error: {e}")
            await self.handle_main_menu(chat_id, message_id, session)

    async def show_main_menu(
        self, chat_id: int, message_id: int = None, is_authenticated: bool = False
    ):
        """Show main menu - called from MessageHandler"""
        try:
            async with self.sessions.session(chat_id) as session:
                if not is_authenticated:
                    is_authenticated = session.is_authenticated

                if message_id:
                    session.temp_data["last_bot_message_id"] = message_id

                if is_authenticated:
                    await self._show_authenticated_menu(chat_id, message_id)
                else:
                    await self._show_welcome_menu(chat_id, message_id)

        except Exception as e:
            logger.error(f"Error in show_main_menu: {e}")
            await self._show_error(chat_id, message_id)

    async def show_help(self, chat_id: int, message_id: int = None):
        """Show help menu - called from MessageHandler"""
        try:
            async with self.sessions.session(chat_id) as session:
                if message_id:
                    session.temp_data["last_bot_message_id"] = message_id

            help_text = MESSAGES.get("help", "راهنما در دسترس نیست")
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 منوی اصلی", callback_data=CallbackFormats.MAIN_MENU
                        )
                    ]
                ]
            )

            if message_id:
                await self.msg.edit_message(
                    chat_id, message_id, help_text, reply_markup=keyboard
                )
            else:
                await self.msg.send_message(chat_id, help_text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in show_help: {e}")
            await self._show_error(chat_id, message_id)

    async def show_authenticated_menu(self, chat_id: int, message_id: int = None):
        """Show authenticated user menu - called from MessageHandler"""
        try:
            async with self.sessions.session(chat_id) as session:
                if message_id:
                    session.temp_data["last_bot_message_id"] = message_id

                await self._show_authenticated_menu(chat_id, message_id)

        except Exception as e:
            logger.error(f"Error in show_authenticated_menu: {e}")
            await self._show_error(chat_id, message_id)

    # ========== PRIVATE DISPLAY METHODS ==========
    async def _show_main_menu(self, chat_id: int, message_id: int):
        """Show main menu for non-authenticated users"""
        keyboard = InlineKeyboardMarkup(MAIN_INLINE_KEYBOARD)
        text = "🏠 **منوی اصلی**\n\nلطفاً یک گزینه را انتخاب کنید:"

        try:
            await self.msg.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
                activate_keyboard=True,
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Main menu error: {e}")

    async def _show_welcome_menu(self, chat_id: int, message_id: int = None):
        """Show welcome menu for new/unauthenticated users"""
        keyboard = InlineKeyboardMarkup(MAIN_INLINE_KEYBOARD)
        text = MESSAGES.get(
            "welcome", "🌟 به ربات هامون خوش آمدید!\n\nلطفاً یک گزینه را انتخاب کنید:"
        )

        try:
            if message_id:
                await self.msg.edit_message(
                    chat_id,
                    message_id,
                    text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    activate_keyboard=True,
                )
            else:
                await self.msg.send_message(
                    chat_id,
                    text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    activate_keyboard=True,
                )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Welcome menu error: {e}")

    async def _show_authenticated_menu(self, chat_id: int, message_id: int, name: str):
        """Show authenticated user menu"""
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👤 اطلاعات من", callback_data=CallbackFormats.MY_INFO
                    ),
                    InlineKeyboardButton(
                        "📦 سفارشات من", callback_data=CallbackFormats.MY_ORDERS
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔢 پیگیری سفارش", callback_data=CallbackFormats.TRACK_BY_NUMBER
                    ),
                    InlineKeyboardButton(
                        "#️⃣ پیگیری سریال", callback_data=CallbackFormats.TRACK_BY_SERIAL
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔧 تعمیرات", callback_data=CallbackFormats.REPAIR_REQUEST
                    ),
                    InlineKeyboardButton(
                        "📝 شکایت", callback_data=CallbackFormats.SUBMIT_COMPLAINT
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❓ راهنما", callback_data=CallbackFormats.HELP
                    ),
                    InlineKeyboardButton(
                        "🚪 خروج", callback_data=CallbackFormats.LOGOUT
                    ),
                ],
            ]
        )

        text = f"👋 سلام {name} عزیز!\n\n📋 **پنل کاربری**\nانتخاب کنید:"

        try:
            await self.msg.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
                activate_keyboard=True,
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Auth menu error: {e}")
