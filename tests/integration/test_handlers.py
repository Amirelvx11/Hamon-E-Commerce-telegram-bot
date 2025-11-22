import os, sys
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Factory Utilities
# ---------------------------------------------------------------------------

def message_mock(text="/start", user_id=99, chat_id=77):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        bot=AsyncMock(),
        answer=AsyncMock(),
        edit_text=AsyncMock(),
        delete=AsyncMock(),
    )


def callback_mock(data="callback_data", user_id=99, chat_id=77):
    return SimpleNamespace(
        data=data,
        message=SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            edit_text=AsyncMock(),
            delete=AsyncMock(),
            answer=AsyncMock(),
            bot=AsyncMock(),
        ),
        from_user=SimpleNamespace(id=user_id),
        answer=AsyncMock(),
    )


@pytest.fixture
def mock_session_manager():
    m = MagicMock()
    m.cleanup_messages = AsyncMock()
    m.track_message = AsyncMock()
    m.get_session = AsyncMock()
    
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=SimpleNamespace(
        is_authenticated=True,
        temp_data={},
        last_orders=[],
        order_number="123",
        user_name="Test User",
        phone_number="09120000000"
    ))
    cm.__aexit__ = AsyncMock(return_value=False)

    m.get_session = MagicMock(return_value=cm)
    m.get_stats = AsyncMock(return_value={
        "total_sessions": 5,
        "authenticated_sessions": 2,
        "cached_sessions": 1,
        "total_requests": 9,
    })
    return m


@pytest.fixture
def mock_api_service():
    from src.models.domain import Order, AuthResponse, SubmissionResponse
    
    svc = MagicMock()

    test_order = Order(
        number="456",  # Maps to order_number via alias
        **{
            '$$_contactId': 'علی محمدی',  # customer_name
            'contactId_nationalCode': '0012345678',  # national_id
            'contactId_phone': '09123456789',
            'contactId_cityId': 'تهران تهران',
            'steps': 2,  # status_code
            '$$_steps': 'در حال بررسی',  # status_text
            'warehouseRecieptId_number': '123456',  # tracking_code
            'warehouseRecieptId_createdOn': '1404/09/01 12:23',  # registration_date_raw
            'items': [  # devices
                {
                    '$$_deviceId': 'ANFU AF 85',
                    'serialNumber': '00HEC123456',
                    '$$_status': 'در انتظار تعمیر',
                    'status': 1,
                    'passDescription': 'شکستگی صفحه نمایش'
                }
            ],
            'factorId_number': '123456',  # invoice_number
            'factorId_paymentLink': 'https://example.com/payment/456',  # payment_link
            'factorPayment': {  # payment
                'id': '27561483',
                'factorId_paymentLink': 'https://example.com/payment/456',
                'referenceCode': '10000',
                '$$_invoiceId': '123456'
            }
        }
    )

    svc.get_order_by_number = AsyncMock(return_value=test_order)
    
    serial_order = Order(
        number="789",
        **{
            '$$_contactId': 'محمد رضایی',
            'contactId_nationalCode': '0087654321',
            'contactId_phone': '09121111111',
            'contactId_cityId': 'اصفهان کاشان',
            'steps': 5,
            '$$_steps': 'تکمیل شده',
            'warehouseRecieptId_number': '98765',
            'items': [],
            'factorId_paymentLink': 'https://example.com/payment/789'
        }
    )
    svc.get_order_by_serial = AsyncMock(return_value=serial_order)
    
    auth_response = AuthResponse(order=test_order)
    svc.authenticate_user = AsyncMock(return_value=auth_response)
    
    submission_response = SubmissionResponse(
        success=True,
        message="درخواست شما با موفقیت ثبت شد",
        ticketNumber="15123",
        recordId="ID3456-789-101112-131415"
    )
    svc.submit_repair_request = AsyncMock(return_value=submission_response)
    return svc

@pytest.fixture
def mock_state():
    """Create a fully mocked FSMContext for testing"""
    state = MagicMock(spec=FSMContext)
    
    state.set_state = AsyncMock()
    state.get_state = AsyncMock(return_value=None)
    state.set_data = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock(return_value={})
    state.clear = AsyncMock()
    
    return state

# ---------------------------------------------------------------------------
# COMMON ROUTER
# ---------------------------------------------------------------------------

async def test_common_handle_start_invokes_menu(monkeypatch, mock_session_manager):
    from src.handlers import common_routers

    fake_settings = MagicMock()
    fake_dynamic = MagicMock()
    fake_cache = MagicMock()
    msg = message_mock("/start")

    router = common_routers.prepare_router(fake_settings, mock_session_manager, fake_dynamic, fake_cache)
    # extract first handler (CommandStart)
    handler = list(router.observers["message"].handlers)[0].callback

    storage = MemoryStorage()
    fsm_ctx = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=100, user_id =200))
    await handler(msg, fsm_ctx)

    mock_session_manager.cleanup_messages.assert_awaited()
    msg.answer.assert_awaited()
    msg.delete.assert_awaited()


async def test_common_admin_stats_generates_output(mock_session_manager):
    from src.handlers import common_routers

    fake_settings = MagicMock(admin_chat_id="77")
    fake_dynamic = MagicMock(
        is_admin=lambda uid: True,
        get_status=lambda: {"features_enabled": 1, "total_features": 1,
                            "maintenance_mode": False, "last_updated": "now", "admin_users": 1}
    )
    fake_cache = MagicMock(
        get_stats=lambda: {"hits": 1, "misses": 0, "hit_rate": 1.0, "connected": True}
    )
    msg = message_mock(chat_id=77)
    router = common_routers.prepare_router(fake_settings, mock_session_manager, fake_dynamic, fake_cache)
    func = next(f.callback for f in router.observers["message"].handlers if "handle_admin_stats" in f.callback.__qualname__)
    await func(msg)
    msg.answer.assert_awaited()


# ---------------------------------------------------------------------------
# AUTH ROUTER
# ---------------------------------------------------------------------------

async def test_auth_flow_sets_state(mock_api_service, mock_session_manager, mock_state):
    from src.handlers import auth
    router = auth.prepare_router(mock_api_service, mock_session_manager)

    func = list(router.observers["message"].handlers)[0].callback
    msg = message_mock("🔐 ورود با کد/شناسه ملی")
    await func(msg, mock_state)
    mock_state.set_state.assert_awaited()


async def test_auth_process_national_id_validates_user(mock_api_service, mock_session_manager, mock_state):
    from src.handlers import auth
    router = auth.prepare_router(mock_api_service, mock_session_manager)
    func = next(f.callback for f in router.observers["message"].handlers if "process_national_id" in f.callback.__qualname__)
    msg = message_mock("0012345678")
    await func(msg, mock_state)
    msg.answer.assert_awaited()


# ---------------------------------------------------------------------------
# ORDER ROUTER
# ---------------------------------------------------------------------------

async def test_order_prompt_number_starts_fsm(mock_api_service, mock_session_manager, mock_state):
    from src.handlers import order
    router = order.prepare_router(mock_api_service, mock_session_manager)
    func = next(f.callback for f in router.observers["message"].handlers if "prompt_order_number" in f.callback.__qualname__)
    msg = message_mock("🔢 پیگیری با شماره پذیرش")
    await func(msg, mock_state)
    mock_state.set_state.assert_awaited()


async def test_order_process_order_number_calls_api(mock_api_service, mock_session_manager, mock_state):
    from src.handlers import order
    router = order.prepare_router(mock_api_service, mock_session_manager)
    func = next(f.callback for f in router.observers["message"].handlers if "process_order_number" in f.callback.__qualname__)
    msg = message_mock("1234567")
    await func(msg, mock_state)
    mock_api_service.get_order_by_number.assert_awaited()
    msg.answer.assert_awaited()  # handled by _edit_or_respond


# ---------------------------------------------------------------------------
# SUPPORT ROUTER
# ---------------------------------------------------------------------------

async def test_support_start_complaint_requires_auth(monkeypatch, mock_api_service, mock_session_manager, mock_state):
    from src.handlers import support
    router = support.prepare_router(mock_api_service, mock_session_manager)

    monkeypatch.setattr("src.handlers.support._ensure_authenticated", AsyncMock(return_value=True))

    msg = message_mock("📝 ثبت شکایات")
    func = next(f.callback for f in router.observers["message"].handlers if "start_complaint" in f.callback.__qualname__)
    await func(msg, mock_state)
    mock_session_manager.track_message.assert_awaited()


async def test_support_process_repair_text_creates_ticket(mock_api_service, mock_session_manager, mock_state):
    from src.handlers import support
    router = support.prepare_router(mock_api_service, mock_session_manager)
    func = next(f.callback for f in router.observers["message"].handlers if "process_repair_text" in f.callback.__qualname__)

    msg = message_mock("توضیحات تست تعمیر")
    await func(msg, mock_state)

    mock_api_service.submit_repair_request.assert_awaited()
    msg.answer.assert_awaited()
    mock_state.clear.assert_awaited()


# ---------------------------------------------------------------------------
# HELPERS BEHAVIOR BASIC TESTS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("has_msg", [True, False])
async def test_edit_or_respond_variants(has_msg):
    from src.handlers.helpers import _edit_or_respond
    from aiogram.types import CallbackQuery, Message

    if has_msg:
        # Simulate CallbackQuery with message
        msg_mock = MagicMock()
        msg_mock.edit_text = AsyncMock(return_value=msg_mock)
        
        callback_event = MagicMock(spec=CallbackQuery)
        callback_event.message = msg_mock
        
        result = await _edit_or_respond(callback_event, "Sample", reply_markup=None)
        msg_mock.edit_text.assert_awaited_once()
    else:
        # Simulate Message directly - needs edit_text AND answer
        msg_mock = MagicMock(spec=Message)
        msg_mock.edit_text = AsyncMock(return_value=msg_mock)
        msg_mock.answer = AsyncMock(return_value=msg_mock)
        msg_mock.delete = AsyncMock()
        
        result = await _edit_or_respond(msg_mock, "Sample", reply_markup=None)
        # For Message, it should try edit_text first
        msg_mock.edit_text.assert_awaited_once()

async def test_prepare_for_processing_sends_loading():
    from src.handlers.helpers import _prepare_for_processing
    
    sm = MagicMock()
    sm.cleanup_messages = AsyncMock()
    sm.track_message = AsyncMock()

    msg = message_mock("data")
    msg.answer = AsyncMock(return_value=SimpleNamespace(message_id=1))

    await _prepare_for_processing(msg, sm, "Loading")
    sm.track_message.assert_awaited()
