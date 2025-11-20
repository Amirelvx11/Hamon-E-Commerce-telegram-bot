from datetime import datetime, timedelta
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.models.domain import (
    sanitize_text, clean_numeric_string, parse_date_string,
    Order, Payment, AuthResponse, SubmissionResponse
)
from src.models.user import UserSession
from src.config.enums import UserState


def test_sanitize_text_removes_whitespace_and_tabs():
    text = "   hello\tworld  \n"
    assert sanitize_text(text) == "hello world"

def test_clean_numeric_string_only_numbers():
    raw = " 22,44a99 "
    assert clean_numeric_string(raw) == "224499"

def test_parse_date_string_valid_and_invalid():
    assert parse_date_string("2024-03-21 11:22:00") == "2024-03-21"
    assert parse_date_string(None) is None
    assert "unknown" in parse_date_string("unknown data")

def test_user_session_expiry_and_refresh(monkeypatch):
    session = UserSession(chat_id=100, user_id=200)
    monkeypatch.setattr(session, "expires_at", datetime.now() - timedelta(seconds=1))
    assert session.is_expired() is True

    session.refresh(minutes=30)
    assert session.expires_at > datetime.now()
    assert isinstance(session.last_activity, datetime)

def test_user_session_to_dict_and_defaults():
    s = UserSession(chat_id=123, user_id=456)
    data = s.to_dict()
    assert "chat_id" in data and "temp_data" not in data
    assert isinstance(s.created_at, datetime)
    assert s.state == UserState.IDLE

def test_user_session_create_with_default_expiry(monkeypatch):
    class DummyCfg:
        session_timeout_minutes = 60

    from src.config import settings
    monkeypatch.setattr(settings, "get_config", lambda: DummyCfg())

    sess = UserSession.create_with_default_expiry(chat_id=1, user_id=2)
    delta = sess.expires_at - datetime.now()
    assert 58 <= delta.total_seconds() / 60 <= 61

def test_order_and_payment_structure_parsing():
    data = {
        "number": " 00123 ",
        "$$_contactId": " Amir ",
        "contactId_nationalCode": " 1112223334 ",
        "contactId_phone": "09351234567",
        "contactId_cityId": " Tehran ",
        "steps": 1,
        "$$_steps": "Done",
        "factorId_paymentLink": "https://pay.link",
        "factorPayment": {"id": "pay_123"},
    }
    order = Order.model_validate(data)
    assert order.order_number == "00123"
    assert order.customer_name == "Amir"
    assert order.city == "Tehran"
    assert order.payment.is_completed is True
    assert order.has_payment_link
    assert order.is_paid is True

def test_payment_flags():
    pay = Payment(id="abc")
    assert pay.is_completed and pay.is_paid

def test_auth_response_wraps_and_extracts():
    order_data = {"number": "55121", "$$_contactId": "Ali", "contactId_nationalCode": "777"}
    resp = AuthResponse.model_validate(order_data)
    assert resp.order.order_number == "55121"
    assert resp.authenticated
    assert resp.name == "Ali"
    assert resp.national_id == "777"

def test_submission_response_timestamp_and_fields():
    res = SubmissionResponse(success=True, message="OK", ticketNumber="T001")
    assert res.success is True
    assert res.ticket_number == "T001"
    # timestamp must be recent ISO timestamp
    ts = datetime.fromisoformat(res.timestamp)
    assert abs(datetime.now().timestamp() - ts.timestamp()) < 5

def test_enum_and_extra_fields_ignored():
    raw = {
        "number": "123",
        "$$_contactId": "Me",
        "contactId_nationalCode": "999",
        "unexpected": "ignored_field"
    }
    parsed = Order.model_validate(raw)
    assert not hasattr(parsed, "unexpected")
