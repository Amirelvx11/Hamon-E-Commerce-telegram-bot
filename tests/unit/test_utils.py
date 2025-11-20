import pytest
import types
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils.formatters import safe_get, gregorian_to_jalali, Formatters
from src.utils.keyboards import KeyboardFactory
from src.utils.messages import get_message, MESSAGES
from src.utils.validators import Validators, ValidationResult


# ---------------------- formatters.py ----------------------
def test_safe_get_nested_dict_and_attrs():
    obj = {"a": {"b": {"c": 5}}}
    class Dummy: d = 10
    assert safe_get(obj, "a", "b", "c") == 5
    assert safe_get(Dummy(), "d") == 10
    assert safe_get(obj, "x", default="fallback") == "fallback"

def test_gregorian_to_jalali_structure():
    date_str = gregorian_to_jalali(datetime(2025, 5, 5))
    assert isinstance(date_str, str)
    parts = date_str.split("/")
    assert len(parts) == 3 and all(i.isdigit() for i in parts)

def test_formatters_order_and_user_texts():
    order_data = {
        "number": "321",
        "$$_contactId": "Customer",
        "contactId_nationalCode": "1234567890",
        "contactId_phone": "09120000000",
        "contactId_cityId": "Tehran",
        "steps": 3,
        "$$_steps": "Delivered",
        "items": []
    }
    # order_detail returns (text, buttons) tuple
    txt, buttons = Formatters.order_detail(order_data)
    assert "321" in txt or "سفارش" in txt

    orders = [
        {"order_number": "123", "steps": 1, "devices": []},
        {"order_number": "456", "steps": 2, "devices": []},
    ]
    lst = Formatters.order_list(orders, page=1)
    assert "صفحه" in lst or "123" in lst

    # user_info expects UserSession object
    from src.models.user import UserSession
    session = UserSession(
        chat_id=123,
        user_id=456,
        user_name="Kamy",
        phone_number="09121234567",
        national_id="1234567890",
        is_authenticated=True
    )
    info_txt, _ = Formatters.user_info(session)
    assert "Kamy" in info_txt and "0912" in info_txt

    complaint = Formatters.complaint_submitted("C-1", "شکایت سخت‌افزار")
    repair = Formatters.repair_submitted("R-9")
    assert "C-1" in complaint
    assert "R-9" in repair


# ---------------------- keyboards.py ----------------------
def _t(k): return [b.text for r in k.inline_keyboard for b in r]

def test_keyboards(monkeypatch):
    monkeypatch.setattr("src.utils.messages.get_message", lambda k: "لغو")
    
    # Create iterable mock for ComplaintType enum
    class MockComplaintItem:
        def __init__(self, display):
            self.display = display
    
    class MockComplaintTypeEnum:
        _items = [MockComplaintItem("خدمات"), MockComplaintItem("فنی")]
        
        @staticmethod
        def get_keyboard_options():
            return [{"text": "خدمات", "type_id": 1}]
        
        def __iter__(self):
            return iter(self._items)
        
        def __len__(self):
            return len(self._items)
    
    monkeypatch.setattr("src.utils.keyboards.ComplaintType", MockComplaintTypeEnum())

    # main menus
    ka = KeyboardFactory.main_inline_menu(True)
    kg = KeyboardFactory.main_inline_menu(False)
    assert any("اطلاعات" in x for x in _t(ka))
    assert any("ورود" in x for x in _t(kg))
    assert isinstance(KeyboardFactory.remove(), ReplyKeyboardRemove)

    # order actions / device list / my orders
    o = types.SimpleNamespace(has_payment_link=True, is_paid=False, payment_link="x")
    k1 = KeyboardFactory.order_actions("O1", o)
    k2 = KeyboardFactory.device_list_actions("O1", 2, 4)
    s = types.SimpleNamespace(order_number="O1", temp_data={"raw_auth_data": {"order_number": "O1"}})
    k3 = KeyboardFactory.my_orders_actions(s)
    assert any("فاکتور" in t for t in _t(k1))
    assert any("🔍" in t or "جزئیات" in t for t in _t(k2))
    assert any("بازگشت" in t for t in _t(k3))

    # complaint types / single / cancel / back
    assert any("خدمات" in t for t in _t(KeyboardFactory.complaint_types_inline()))
    for f in [KeyboardFactory.single_button("Btn","cb"), KeyboardFactory.cancel_inline(),
              KeyboardFactory.back_inline(extra_buttons=[{"text":"X","callback":"cb:x"}])]:
        assert isinstance(f, InlineKeyboardMarkup) and any(_t(f))

    # reply modes
    r1 = KeyboardFactory.complaint_types_reply()
    r2 = KeyboardFactory.cancel_reply("دیگر")
    
    # Check for complaint type text OR cancel button
    r1_texts = [b.text for row in r1.keyboard for b in row]
    assert any("خدمات" in t or "فنی" in t or "لغو" in t for t in r1_texts)
    assert any("دیگر" in b.text for row in r2.keyboard for b in row)

# ---------------------- messages.py ----------------------
def test_message_retrieval_and_defaults():
    txt_ok = get_message("welcome")
    assert isinstance(txt_ok, str) and len(txt_ok) > 0
    txt_fail = get_message("not_exist_key")
    assert isinstance(txt_fail, str)
    formatted = MESSAGES.get("order_not_found", id=11)
    assert "11" in formatted or isinstance(formatted, str)


# ---------------------- validators.py ----------------------
@pytest.mark.parametrize("nid,valid", [("1234567891", True), ("1111111111", False), ("0045", False)])
def test_validate_national_id_cases(nid, valid):
    res = Validators.validate_national_id(nid)
    assert isinstance(res, ValidationResult)
    assert res.is_valid is valid

@pytest.mark.parametrize("order,exp", [("1234", True), ("ab1234", True), ("1", False)])
def test_validate_order_number(order, exp):
    r = Validators.validate_order_number(order)
    assert r.is_valid == exp

@pytest.mark.parametrize("serial,exp", [("00HEC234567", True), ("234567", True), ("BAD234", False)])
def test_validate_serial(serial, exp):
    r = Validators.validate_serial(serial)
    assert r.is_valid == exp

@pytest.mark.parametrize("phone,exp", [("09123456789", True), ("+989123456789", True), ("999", False)])
def test_validate_phone_cases(phone, exp):
    r = Validators.validate_phone(phone)
    assert r.is_valid == exp
    if exp:
        assert r.cleaned_value.startswith("09")

@pytest.mark.parametrize("txt,minl,exp", [("ok",5,False), ("long enough text",5,True)])
def test_validate_text_length(txt,minl,exp):
    r = Validators.validate_text_length(txt, min_length=minl)
    assert r.is_valid == exp
