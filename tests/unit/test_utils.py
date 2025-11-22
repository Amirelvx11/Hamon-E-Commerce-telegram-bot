import pytest, types
from datetime import datetime
from types import SimpleNamespace
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove
from src.utils.formatters import safe_get, gregorian_to_jalali, Formatters
from src.utils.keyboards import KeyboardFactory
from src.utils.messages import get_message, MESSAGES
from src.utils.validators import Validators, ValidationResult


# ---------- formatters.py ----------
def test_safe_get_and_gregorian_to_jalali(monkeypatch):
    obj = {"a": {"b": {"c": 7}}}
    class D: d = 8
    assert safe_get(obj, "a", "b", "c") == 7
    assert safe_get(D(), "d") == 8
    assert safe_get(obj, "x", default="fallback") == "fallback"
    lst = [1, 2, {"z": 5}]
    assert safe_get(lst, 2, "z") == 5
    assert safe_get(lst, 9, default="x") == "x"

    # Normal & faulty Jalali conversions
    s = gregorian_to_jalali(datetime(2025, 5, 5))
    assert isinstance(s, str) and len(s.split("/")) == 3
    assert gregorian_to_jalali("not‑date") == "نامشخص"
    monkeypatch.setattr("jdatetime.datetime.fromgregorian", lambda **k: (_ for _ in ()).throw(ValueError))
    assert gregorian_to_jalali(datetime.now()) == "نامشخص"

def test_formatters_core_paths(monkeypatch):
    txt, _ = Formatters.order_detail({"semantic_error": True})
    assert "❌" in txt
    t2, _ = Formatters.order_detail(None)
    assert "❌" in t2

    order = {
        "order_number": "O1",
        "status_code": 0,
        "devices": [],
        "$$_contactId": "C123",
        "contactId_nationalCode": "N111",
        "is_paid": True,
        "invoice_number": "INV‑1",
        "has_payment_link": True,
    }
    txt, _ = Formatters.order_detail(order)
    assert "شماره پذیرش" in txt and "فاکتور" in txt

    from src.models.user import UserSession
    s = UserSession(chat_id=1, user_id=1, user_name="U", phone_number="09", national_id="99", is_authenticated=True)
    s.temp_data = {"raw_auth_data": {}}
    t3, _ = Formatters.my_orders_summary(s)
    assert "سفارش" in t3
    assert "C1" not in t3  # no injection noise

    orders = [{"order_number": f"X{i}", "steps": 0} for i in range(3)]
    txt1 = Formatters.order_list(orders, 3)
    txt2 = Formatters.order_list(orders, 0)
    assert "سفارشات" in txt1 and "سفارشات" in txt2

    d_order = {"order_number": "O1", "devices": [{"model": "M", "serial": "S", "status_code": 1}]}
    assert "دستگاه" in Formatters.device_list_paginated(d_order)
    assert "هیچ" in Formatters.device_list_paginated({"order_number": "O1", "devices": []})

    uinfo, _ = Formatters.user_info(s)
    assert "U" in uinfo and "09" in uinfo
    assert "C-" in Formatters.complaint_submitted("C-1", "hardware")
    assert "R-" in Formatters.repair_submitted("R-1")

    # Device list multi‑page
    devs = [{"model": f"M{i}", "serial": f"S{i}", "status_code": 0} for i in range(10)]
    out = Formatters.device_list_paginated({"order_number": "O", "devices": devs}, 2)
    assert "صفحه" in out

    # Order detail with devices for button test
    dev_order = order | {"devices": [{"model": "M", "serial": "S", "status_code": 1}]}
    t, btns = Formatters.order_detail(dev_order, is_auth=True)
    assert "دستگاه" in t and any("بازگشت" in b["text"] for b in btns)


# ---------- keyboards.py ----------
def _texts(kb): 
    return [b.text for r in kb.inline_keyboard for b in r]

def test_keyboard_builder_flows(monkeypatch):
    monkeypatch.setattr("src.utils.messages.get_message", lambda _: "لغو")

    class FakeComplaintType:
        _items = [SimpleNamespace(display="خدمات", name="SUPPORT")]

        @staticmethod
        def get_keyboard_options():
            return [{"text": "خدمات", "type_id": 1}]

        def __iter__(self):
            yield from self._items

        def __len__(self):
            return len(self._items)
        
    monkeypatch.setattr("src.utils.keyboards.ComplaintType", FakeComplaintType())

    ka, kg = KeyboardFactory.main_inline_menu(True), KeyboardFactory.main_inline_menu(False)
    assert any("ورود" in t or "اطلاعات" in t for t in _texts(ka) + _texts(kg))
    assert isinstance(KeyboardFactory.remove(), ReplyKeyboardRemove)

    o = SimpleNamespace(has_payment_link=True, is_paid=False, payment_link="x")
    assert any("فاکتور" in t for t in _texts(KeyboardFactory.order_actions("O", o)))
    assert any("🔍" in t for t in _texts(KeyboardFactory.device_list_actions("O", 1, 2)))

    s = SimpleNamespace(order_number="O", temp_data={"raw_auth_data": {"order_number": "O"}})
    assert any("بازگشت" in t for t in _texts(KeyboardFactory.my_orders_actions(s)))

    assert any("خدمات" in t for t in _texts(KeyboardFactory.complaint_types_inline()))
    for f in [
        KeyboardFactory.single_button("X", "cb"),
        KeyboardFactory.cancel_inline(),
        KeyboardFactory.back_inline(extra_buttons=[{"text": "B", "callback": "c"}]),
    ]:
        assert isinstance(f, InlineKeyboardMarkup)
        assert any(_texts(f))

    r1 = KeyboardFactory.complaint_types_reply()
    r2 = KeyboardFactory.cancel_reply("لغو")
    assert any("لغو" in b.text or "بازگشت" in b.text for row in r1.keyboard for b in row)
    assert any("لغو" in b.text or "دیگر" in b.text for row in r2.keyboard for b in row)


def test_keyboard_pagination_buttons():
    from src.utils.keyboards import KeyboardFactory
    kb1 = KeyboardFactory.device_list_actions("O", 2, 3)
    kb2 = KeyboardFactory.device_list_actions("O", 1, 1)
    assert any("بعدی" in t or "قبلی" in t for t in _texts(kb1))
    assert not any("بعدی" in t or "قبلی" in t for t in _texts(kb2))


# ---------- messages.py ----------
def test_messages_core_and_error(monkeypatch):
    assert isinstance(get_message("welcome"), str)
    assert isinstance(get_message("x_does_not_exist"), str)
    assert "تماس" in MESSAGES.contact_info()
    assert "Net" in MESSAGES.error_with_retry("Net", "try")
    assert "یافت" in MESSAGES.get("order_not_found", id=11)

    for n in dir(MESSAGES):
        if n in {"get", "contact_info", "error_with_retry"}:
            continue
        f = getattr(MESSAGES, n)
        if callable(f):
            try:
                argc = f.__code__.co_argcount
            except AttributeError:
                continue
            out = f() if argc == 0 else f("x")
            assert isinstance(out, str)

    # Faulty placeholder handling
    monkeypatch.setattr("src.utils.messages.MESSAGES_DICT", {"x": "{invalid}"})
    bad = get_message("x", y=1)
    assert isinstance(bad, str)
    assert isinstance(MESSAGES.get("invalid_missing_key", z=1), str)


# ---------- validators.py ----------
@pytest.mark.parametrize("nid,ok",[("1234567891",True),("1111111111",False)])
def test_validate_nid(nid,ok):
    assert Validators.validate_national_id(nid).is_valid is ok

@pytest.mark.parametrize("o,ok",[("1234",True),("ab12",False),("1",False)])
def test_validate_order(o,ok):
    assert Validators.validate_order_number(o).is_valid == ok

@pytest.mark.parametrize("s,ok",[("00HEC234567",True),("BAD234",False)])
def test_validate_serial(s,ok):
    assert Validators.validate_serial(s).is_valid == ok

@pytest.mark.parametrize("p,ok",[("09123456789",True),("+989123456789",True),("999",False)])
def test_validate_phone(p,ok):
    r = Validators.validate_phone(p)
    assert r.is_valid == ok

@pytest.mark.parametrize("txt,minl,ok",[("ok",5,False),("long enough",5,True)])
def test_validate_text(txt,minl,ok):
    assert Validators.validate_text_length(txt,min_length=minl).is_valid == ok

def test_validator_empty_and_invalid_types():
    for val in ["", "   "]:
        for fn in [Validators.validate_serial, Validators.validate_phone, Validators.validate_text_length]:
            assert not fn(val).is_valid
    for v in [None,123,[],{},True]:
        for fn in [
            Validators.validate_order_number,
            Validators.validate_serial,
            Validators.validate_phone,
            Validators.validate_text_length,
            Validators.validate_national_id,
        ]:
            assert isinstance(fn(v), ValidationResult)

def test_validator_extreme_lengths():
    txt = "a" * (Validators.MAX_TEXT_LENGTH + 10)
    res = Validators.validate_text_length(txt)
    assert not res.is_valid
    assert "حداکثر" in res.error_message
    assert Validators._clean_numeric("a1b2") == "12"
