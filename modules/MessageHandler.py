"""
Message Handler - Handles all user message interactions for the Telegram bot
"""
import logging
import asyncio
from typing import Optional,Any
from telegram import Update, CallbackQuery, Message as TelegramMessage
from telegram import Bot, Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from datetime import datetime
from functools import wraps

from .CoreConfig import (
    UserState, BotConfig, Validators, ComplaintType, CallbackFormats,
    MESSAGES, MAIN_INLINE_KEYBOARD, MAIN_REPLY_KEYBOARD, REPLY_BUTTON_TO_CALLBACK,
    CANCEL_REPLY_KEYBOARD, get_step_info
)
from .SessionManager import RedisSessionManager
from .DataProvider import DataProvider
from .CallbackHandler import CallbackHandler

logger = logging.getLogger(__name__)

def with_error_handling(func):
    """Error handling decorator"""
    @wraps(func)
    async def wrapper(self, chat_id: int, *args, **kwargs):
        try:
            return await func(self, chat_id, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            await self.send_message(chat_id, MESSAGES.get('error', '❌ خطا'))
            return None
    return wrapper

class MessageHandler:
    """Handles all message processing and state management - MINIMAL VERSION"""
    
    def __init__(self, bot: Bot, config: BotConfig, session_manager: RedisSessionManager, 
                data_provider: DataProvider, callback_handler=None):
        self.bot = bot
        self.config = config
        self.sessions = session_manager
        self.data = data_provider
        self.callback_handler = callback_handler
        self.validators = Validators()
        self._in_callback_context = False

        # State handlers mapping
        self.state_handlers = {
            UserState.WAITING_nationalId: self.handle_nationalId,
            UserState.WAITING_ORDER_NUMBER: self.handle_order_number,
            UserState.WAITING_SERIAL: self.handle_serial,
            UserState.WAITING_COMPLAINT_TEXT: self.handle_complaint_text,
            UserState.WAITING_REPAIR_DESC: self.handle_repair_description,
        }

    # ========== KEYBOARD MANAGEMENT - CENTRALIZED & MINIMAL ==========
    async def _activate_keyboard(self, chat_id: int, keyboard_layout, placeholder: str = "", is_main: bool = True):
        """Activate Reply keyboard cleanly without visible text"""
        try:
            msg = await self.bot.send_message(
                chat_id=chat_id,
                text=" ",  # Invisible character
                reply_markup=ReplyKeyboardMarkup(
                    keyboard_layout,
                    resize_keyboard=True,
                    one_time_keyboard=False,
                    input_field_placeholder=placeholder
                )
            )
            await asyncio.sleep(0.1)
            await self.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
            
            if is_main:
                async with self.sessions.session(chat_id) as session:
                    session.temp_data['main_keyboard_active'] = True
                
            logger.debug(f"Keyboard activated for {chat_id}: {placeholder}")
        except Exception as e:
            logger.debug(f"Failed to activate keyboard for {chat_id}: {e}")

    async def activate_main_keyboard(self, chat_id: int):
        """Activate main Reply keyboard"""
        await self._activate_keyboard(chat_id, MAIN_REPLY_KEYBOARD, "از منوی زیر انتخاب کنید...", is_main=True)

    async def activate_cancel_keyboard(self, chat_id: int):
        """Activate cancel-only keyboard during operations"""
        await self._activate_keyboard(chat_id, CANCEL_REPLY_KEYBOARD, "برای لغو، انصراف بزنید", is_main=False)

    async def restore_main_keyboard(self, chat_id: int):
        """Restore main keyboard after operations"""
        await self.activate_main_keyboard(chat_id)

    # ========== MESSAGE METHODS - CLEAN & NO AUTOMATIC KEYBOARD ==========
    async def send_message(self, chat_id: int, text: str, reply_markup=None, parse_mode=None, activate_keyboard: bool = False):
        """Send message - keyboard activation is explicit"""
        try:
            msg = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode or ParseMode.HTML
            )
            
            if activate_keyboard:
                await self.activate_main_keyboard(chat_id)
                
            return msg
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return None

    async def edit_message(self, chat_id: int, message_id: int, text: str, 
                        reply_markup=None, parse_mode=None, activate_keyboard=False):
        """Edit existing message with error handling"""
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            if activate_keyboard:
                await self.activate_main_keyboard(chat_id)
        except Exception as e:
            logger.error(f"Edit message error: {e}")
            await self.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)

    async def delete_message(self, chat_id: int, message_id: int):
        """Delete message"""
        try:
            return await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.debug(f"Failed to delete message {message_id}: {e}")
            return None

    # ========== CORE MESSAGE PROCESSING - MINIMAL ==========
    @with_error_handling
    async def process_message(self, chat_id: int, text: str, message: Message = None):
        """Process text messages - DIRECT METHOD CALLS"""
        if message:
            await self.delete_message(chat_id, message.message_id)

        if self.config.maintenance_mode:
            await self.send_message(chat_id, MESSAGES['maintenance'], activate_keyboard=True)
            return

        async with self.sessions.session(chat_id, chat_id) as session:
            last_bot_message_id = session.temp_data.get('last_bot_message_id')

            # Handle rate limiting
            if session.state == UserState.RATE_LIMITED:
                remaining = session.temp_data.get('rate_limit_expires', 0) - datetime.now().timestamp()
                if remaining > 0:
                    if last_bot_message_id:
                        await self.edit_message(
                            chat_id, last_bot_message_id,
                            MESSAGES['rate_limited'].format(minutes=int(remaining/60)),
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]),
                            activate_keyboard=True
                        )
                    else:
                        await self.send_message(chat_id, MESSAGES['rate_limited'].format(minutes=int(remaining/60)))
                    return
                session.state = UserState.IDLE

            session.request_count += 1
            session.last_activity = datetime.now()

            # DIRECT ROUTING
            callback_data = REPLY_BUTTON_TO_CALLBACK.get(text.strip())
            if callback_data:
                # Direct method call instead of fake update
                await self._route_reply_button(chat_id, callback_data, last_bot_message_id)
                return

            # Handle state-based input
            handler = self.state_handlers.get(session.state)
            if handler:
                await handler(chat_id, text, last_bot_message_id)
            else:
                # Default: show menu
                await self.show_menu(chat_id, message_id=last_bot_message_id)

    async def _route_reply_button(self, chat_id: int, callback_data: str, message_id: int = None):
        """Route Reply button to appropriate callback handler method"""
        async with self.sessions.session(chat_id) as session:
            session.temp_data['last_bot_message_id'] = message_id

        # Direct method calls based on callback data
        routes = {
            CallbackFormats.MAIN_MENU: self.show_menu,
            CallbackFormats.AUTHENTICATE: lambda: self.callback_handler.handle_authenticate(chat_id, message_id, MESSAGES['auth_request']),
            CallbackFormats.TRACK_BY_NUMBER: lambda: self.callback_handler.handle_track_by_number(chat_id, message_id, "🔢 لطفاً شماره پذیرش را وارد کنید:"),
            CallbackFormats.TRACK_BY_SERIAL: lambda: self.callback_handler.handle_track_by_serial(chat_id, message_id, "#️⃣ لطفاً شماره سریال دستگاه را وارد کنید:"),
            CallbackFormats.SUBMIT_COMPLAINT: self.callback_handler.handle_submit_complaint,
            CallbackFormats.HELP: self.show_help,
            CallbackFormats.LOGOUT: self.handle_logout_direct,
        }

        handler = routes.get(callback_data)
        if handler:
            try:
                if callable(handler) and handler.__code__.co_argcount == 1:  # Lambda
                    await handler(chat_id)
                else:
                    await handler(chat_id, message_id)
            except Exception as e:
                logger.error(f"Reply button routing error: {e}")
                await self.show_menu(chat_id, message_id=message_id)
        else:
            logger.warning(f"Unknown reply button callback: {callback_data}")
            await self.show_menu(chat_id, message_id=message_id)

    async def handle_logout_direct(self, chat_id: int, message_id: int = None):
        """Direct logout without fake update"""
        async with self.sessions.session(chat_id) as session:
            session.is_authenticated = False
            session.nationalId = None
            session.user_name = None
            session.state = UserState.IDLE
            session.temp_data.clear()

        await self.send_message(chat_id, "✅ با موفقیت خارج شدید", activate_keyboard=True)
        await self.show_menu(chat_id, message_id=message_id)


    # ========= COMMAND HANDLERS ==========
    async def handle_start(self, chat_id: int):
        """Handle /start - show welcome + keyboards"""
        async with self.sessions.session(chat_id) as session:
            session.state = UserState.IDLE
            session.temp_data.clear()
        
        keyboard = InlineKeyboardMarkup(MAIN_INLINE_KEYBOARD)
        await self.send_message(
            chat_id=chat_id,
            text=MESSAGES['welcome'],
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            activate_keyboard=True
        )

    async def show_menu(self, chat_id: int, message_id: int = None):
        """Show main menu - get auth status from session"""
        try:
            async with self.sessions.session(chat_id) as session:
                is_authenticated = session.is_authenticated
                if message_id:
                    session.temp_data['last_bot_message_id'] = message_id
            
            await self.callback_handler.show_main_menu(chat_id, message_id, is_authenticated)
            
        except Exception as e:
            logger.error(f"Error showing menu for {chat_id}: {e}")
            await self.send_message(chat_id, "❌ خطا در نمایش منو")

    async def show_help(self, chat_id: int, message_id: int = None):
        """Show help menu - simplified version"""
        try:
            async with self.sessions.session(chat_id) as session:
                if message_id:
                    session.temp_data['last_bot_message_id'] = message_id
            
            await self.callback_handler.show_help(chat_id, message_id)
            
        except Exception as e:
            logger.error(f"Error showing help for {chat_id}: {e}")
            await self.send_message(chat_id, "❌ خطا در نمایش راهنما")

    async def show_authenticated_menu(self, chat_id: int, message_id: int = None):
        """Show authenticated user menu - simplified version"""
        try:
            async with self.sessions.session(chat_id) as session:
                if message_id:
                    session.temp_data['last_bot_message_id'] = message_id
            
            await self.callback_handler.show_authenticated_menu(chat_id, message_id)
            
        except Exception as e:
            logger.error(f"Error showing authenticated menu for {chat_id}: {e}")
            await self.send_message(chat_id, "❌ خطا در نمایش منوی کاربری")

    # ========== STATE HANDLERS - TEXT INPUT ONLY ==========
    @with_error_handling
    async def handle_nationalId(self, chat_id: int, nationalId: str, message_id: int = None):
        """Handle national ID verification using centralized validation"""
        nationalId = nationalId.strip()
        # Use centralized validation
        is_valid, error_msg = self.validators.validate_nationalId(nationalId)
        if not is_valid:
            error_text = MESSAGES.get('validation_error', "❌ خطا در اعتبارسنجی").format(error_message=error_msg or "ورودی نامعتبر")
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")
            ]])

            if message_id:
                await self.edit_message(chat_id, message_id, error_text, reply_markup=keyboard)
            else:
                await self.send_message(chat_id, error_text, reply_markup=keyboard)

            # Reset state
            async with self.sessions.session(chat_id) as session:
                session.state = UserState.IDLE
            return
        
        # Validation passed - proceed with authentication
        if message_id:
            await self.edit_message(chat_id, message_id, "🔄 در حال بررسی...")
        else:
            loading_msg = await self.send_message(chat_id, "🔄 در حال بررسی...")
            message_id = loading_msg.message_id if loading_msg else None

        try:
            user_data = await self.data.authenticate_user(nationalId)
            
            if user_data and user_data.get('authenticated', False):
                user_name = user_data.get('name', 'کاربر')
                phone_number = user_data.get('phone', 'نامشخص') or user_data.get('phone_number', 'نامشخص')
                city = user_data.get('city', 'نامشخص')

                async with self.sessions.session(chat_id) as session:
                    session.is_authenticated = True
                    session.nationalId = nationalId
                    session.user_name = user_name
                    session.phone_number = phone_number
                    session.city = city
                    session.state = UserState.AUTHENTICATED
                    session.extend(60)

                    auth_key = f"{self.sessions.AUTH_PREFIX}{nationalId}"
                    await self.sessions.redis.setex(auth_key, self.sessions.AUTH_TTL, chat_id)

                    session.temp_data['last_bot_message_id'] = message_id

                success_text = f"✅ احراز هویت با موفقیت انجام شد\n\n👤 {user_name} عزیز، خوش آمدید!"
                
                if message_id:
                    await self.edit_message(chat_id, message_id, success_text, parse_mode=ParseMode.HTML)
                    await asyncio.sleep(1.5)
                    await self.show_authenticated_menu(chat_id, message_id)
                else:
                    await self.send_message(chat_id, success_text, parse_mode=ParseMode.HTML)
                    await self.show_authenticated_menu(chat_id)

            else:
                error_text = "❌ کد ملی یافت نشد\n\nلطفاً از صحت کد/شناسه ملی اطمینان حاصل کنید و مجددا امتحان کنید."
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 تلاش مجدد", callback_data="authenticate")],
                    [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
                ])
                
                if message_id:
                    await self.edit_message(chat_id, message_id, error_text, reply_markup=keyboard)
                
                async with self.sessions.session(chat_id) as session:
                    session.state = UserState.IDLE

        except Exception as e:
            logger.error(f"Error in handle_nationalId: {e}")
            error_text = "❌ خطا در احراز هویت. لطفاً دوباره تلاش کنید."
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")
            ]])
            
            if message_id:
                await self.edit_message(chat_id, message_id, error_text, reply_markup=keyboard)
            
            async with self.sessions.session(chat_id) as session:
                session.state = UserState.IDLE


    @with_error_handling
    async def handle_order_number(self, chat_id: int, order_number: str, message_id: int = None):
        """Handle order number input with centralized validation"""
        order_number = order_number.strip()
        
        # Validate using centralized validator
        is_valid, error_msg = self.validators.validate_order_number(order_number)
        if not is_valid:
            error_text = MESSAGES.get('validation_error', "❌ خطا در اعتبارسنجی").format(error_message=error_msg or "ورودی نامعتبر")
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")
            ]])
            
            if message_id:
                await self.edit_message(chat_id, message_id, error_text, reply_markup=keyboard)
            else:
                await self.send_message(chat_id, error_text, reply_markup=keyboard)
            
            async with self.sessions.session(chat_id) as session:
                session.state = UserState.IDLE
            return
        
        # Validation passed - proceed with lookup
        await self.handle_order_lookup(chat_id, order_number, "number", message_id)

    @with_error_handling
    async def handle_serial(self, chat_id: int, serial: str, message_id: int = None):
        """Handle serial number input with centralized validation"""
        serial = serial.strip()
        
        # Validate using centralized validator
        is_valid, error_msg = self.validators.validate_serial(serial)
        if not is_valid:
            error_text = MESSAGES.get('validation_error', "❌ خطا در اعتبارسنجی").format(error_message=error_msg or "ورودی نامعتبر")
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")
            ]])
            
            if message_id:
                await self.edit_message(chat_id, message_id, error_text, reply_markup=keyboard)
            else:
                await self.send_message(chat_id, error_text, reply_markup=keyboard)
            
            async with self.sessions.session(chat_id) as session:
                session.state = UserState.IDLE
            return
        
        # Validation passed - proceed with lookup
        await self.handle_order_lookup(chat_id, serial, "serial", message_id)


    async def handle_order_lookup(self, chat_id: int, value: str, lookup_type: str, message_id: int = None):
        """Unified order lookup processing"""
        value = value.strip()
        
        async with self.sessions.session(chat_id) as session:
            session.temp_data['lookup_type'] = lookup_type
            session.temp_data['lookup_value'] = value

        # Show loading
        if message_id:
            await self.edit_message(chat_id, message_id, "🔄 در حال جستجو...", activate_keyboard=False)
        else:
            loading_msg = await self.send_message(chat_id, "🔄 در حال جستجو...", activate_keyboard=False)
            message_id = loading_msg.message_id if loading_msg else None

        try:
            # Fetch order data
            if lookup_type == "number":
                order_info = await self.data.get_order_by_number(value)
            else:
                order_info = await self.data.get_order_by_serial(value)

            if order_info:
                # Format display
                text = self._format_order_summary(order_info)
                
                # Create inline keyboard for actions
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"refresh_order:{order_info.order_number}")],
                    [InlineKeyboardButton("📋 جزئیات کامل", callback_data=f"order_{order_info.order_number}")],
                    [InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]
                ])
                
                if message_id:
                    await self.edit_message(chat_id, message_id, text, reply_markup=keyboard, activate_keyboard=True)
                else:
                    await self.send_message(chat_id, text, reply_markup=keyboard, activate_keyboard=True)
                    
                async with self.sessions.session(chat_id) as session:
                    session.state = UserState.IDLE

            else:
                error_text = MESSAGES['order_not_found']
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")]])
                
                if message_id:
                    await self.edit_message(chat_id, message_id, error_text, reply_markup=keyboard, activate_keyboard=True)
                else:
                    await self.send_message(chat_id, error_text, reply_markup=keyboard, activate_keyboard=True)
                    
                async with self.sessions.session(chat_id) as session:
                    session.state = UserState.IDLE

        except Exception as e:
            logger.error(f"Order lookup error: {e}")
            error_text = "❌ خطا در جستجو"
            if message_id:
                await self.edit_message(chat_id, message_id, error_text, activate_keyboard=True)
            else:
                await self.send_message(chat_id, error_text, activate_keyboard=True)
            async with self.sessions.session(chat_id) as session:
                session.state = UserState.IDLE

    def _format_order_summary(self, order_info) -> str:
        """Format order summary for display"""
        step_info = get_step_info(order_info.steps)
        
        return f"""📦 **سفارش {order_info.order_number}**

👤 {order_info.customer_name}
📱 {order_info.device_model}
🔢 {order_info.serial_number}

{step_info['bar']}
📍 {step_info['display']}

📅 {order_info.registration_date or 'نامشخص'}"""

    @with_error_handling
    async def handle_complaint_text(self, chat_id: int, text: str, message_id: int = None):
        """Process complaint text with validation"""
        text = text.strip()
        
        async with self.sessions.session(chat_id) as session:
            # Authentication check
            if not session.is_authenticated:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 ورود", callback_data=CallbackFormats.AUTHENTICATE)],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU)]
                ])
                await self._show_message(chat_id, message_id, "⚠️ ابتدا وارد حساب کاربری خود شوید", keyboard)
                session.state = UserState.IDLE
                return
            
            # Validate complaint type
            complaint_type = session.temp_data.get('complaint_type')
            if not complaint_type or not isinstance(complaint_type, ComplaintType):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU)]])
                await self._show_message(chat_id, message_id, "❌ خطا در فرآیند ثبت شکایت", keyboard)
                session.state = UserState.IDLE
                return
            
            # Validate text length
            is_valid, error_msg = self.validators.validate_text_length(text, min_length=10, max_length=1000)
            if not is_valid:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 ویرایش متن", callback_data=CallbackFormats.SUBMIT_COMPLAINT)],
                    [InlineKeyboardButton("🔙 انصراف", callback_data=CallbackFormats.MAIN_MENU)]
                ])
                await self._show_message(chat_id, message_id, error_msg, keyboard)
                return
            
            # Show loading
            await self._show_message(chat_id, message_id, "⏳ در حال ثبت شکایت...")
            
            try:
                # Submit complaint
                ticket_number = await self.data.submit_complaint(
                    national_id=session.nationalId,
                    complaint_type=complaint_type.value,
                    description=text,
                    user_name=session.user_name,
                    phone_number=session.phone_number or ''
                )
                
                # Success response
                success_text = f"✅ شکایت ثبت شد\n\n🎫 شماره: {ticket_number or 'درخواست-XXX'}\n📞 تیم پشتیبانی با شما تماس خواهد گرفت"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 منوی اصلی", callback_data=CallbackFormats.MAIN_MENU)]
                ])
                
                await self._show_message(chat_id, message_id, success_text, keyboard)
                
                # Cleanup session
                session.state = UserState.IDLE
                session.temp_data.pop('complaint_type', None)
                session.extend(60)
                
                logger.info(f"Complaint submitted: {session.user_name} (ticket: {ticket_number})")
                
            except Exception as e:
                logger.error(f"Complaint submission failed for {chat_id}: {e}")
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 تلاش مجدد", callback_data=CallbackFormats.SUBMIT_COMPLAINT)],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data=CallbackFormats.MAIN_MENU)]
                ])
                await self._show_message(chat_id, message_id, "❌ خطا در ثبت شکایت", keyboard)
                session.state = UserState.WAITING_COMPLAINT_TEXT
            
            # Restore main keyboard
            await self.restore_main_keyboard(chat_id)

    def _show_message(self, chat_id: int, message_id: int, text: str, reply_markup=None):
        """Helper: Send or edit message"""
        if message_id:
            return self.edit_message(chat_id, message_id, text, reply_markup=reply_markup)
        else:
            return self.send_message(chat_id, text, reply_markup=reply_markup)

    @with_error_handling
    async def handle_repair_description(self, chat_id: int, text: str, message_id: int = None):
        """Process repair description"""
        async with self.sessions.session(chat_id) as session:
            if not session.is_authenticated:
                await self.show_menu(chat_id, message_id=message_id)
                return

            request_number = await self.data.submit_repair_request(
                session.nationalId,
                text.strip(),
                session.phone_number or ""
            )

            success_msg = MESSAGES['repair_submitted'].format(request_number=request_number or "درخواست ثبت شد")
            await self.send_message(chat_id, success_msg, activate_keyboard=True)
            
            session.state = UserState.IDLE
            await self.show_menu(chat_id, message_id=message_id)

    # ========== CALLBACK ROUTING ==========
    async def handle_callback(self, update: Update):
        """Route callbacks to CallbackHandler"""
        if not self.callback_handler:
            logger.error("CallbackHandler not initialized")
            return
        
        await self.callback_handler.handle_callback(update)
