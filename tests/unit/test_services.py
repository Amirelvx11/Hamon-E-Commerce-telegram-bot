import os, sys
import pytest
import asyncio
from types import SimpleNamespace
from pydantic import BaseModel
from src.services.api import APIService
from src.services.exceptions import (
    ConfigurationError,
    APIResponseError,
    APIValidationError,
    APINetworkError,
    APIAuthenticationError,
)
from src.services.notifications import NotificationService

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ---------------------- fixtures ----------------------
@pytest.fixture
def dummy_settings(mocker):
    s = mocker.Mock()
    s.get_endpoint.side_effect = lambda k: f"https://t/api/{k}" if "bad" not in k else None
    return s

@pytest.fixture
def dummy_client(mocker):
    c = mocker.AsyncMock()
    resp = SimpleNamespace(success=True, status=200, data={"id": 1})
    c.request.return_value = resp
    return c

@pytest.fixture
def service(dummy_client, dummy_settings):
    return APIService(dummy_client, dummy_settings)


# ---------------------- APIService._make_request ----------------------
@pytest.mark.asyncio
async def test_make_request_success(service):
    r = await service._make_request("get", "ok", model_to_validate=None)
    assert r == {"id": 1}  

@pytest.mark.asyncio
async def test_make_request_no_endpoint(service):
    with pytest.raises(ConfigurationError):
        r = await service._make_request("get", "bad_key", model_to_validate=None)

@pytest.mark.asyncio
async def test_response_error_and_autherror(service, dummy_client):
    dummy_client.request.side_effect = None
    dummy_client.request.return_value = SimpleNamespace(success=False, status=401, error="unauth", data=None)
    with pytest.raises(APIAuthenticationError):
        await service._make_request("post", "x", model_to_validate=None)
    
    dummy_client.request.return_value = SimpleNamespace(success=False, status=500, error="err", data=None)
    with pytest.raises(APIResponseError):
        await service._make_request("post", "x", model_to_validate=None)

@pytest.mark.asyncio
async def test_validation_error(service, dummy_client):
    dummy_client.request.return_value = SimpleNamespace(success=True, status=200, data={"invalid": "x"})
    class M(BaseModel): 
        id: int
    with pytest.raises(APIValidationError):
        await service._make_request("get", "x", M)

@pytest.mark.asyncio
async def test_network_error(service, dummy_client):
    dummy_client.request.side_effect = asyncio.TimeoutError()
    with pytest.raises(APINetworkError):
        await service._make_request("get", "x",model_to_validate=None)


# ---------------------- APIService public ----------------------
@pytest.mark.asyncio
async def test_authenticate_and_get_orders(service, mocker):
    # Match ACTUAL API response structure for NID lookup
    auth_response_data = {
        "data": {
            "number": 70231,
            "$$_contactId": "رامین اسدبیگی",
            "contactId_nationalCode": "3970165857",
            "contactId_phone": "09368501337",
            "contactId_cityId": "همدان تویسرکان",
            "steps": 50,
            "$$_steps": "پایان عملیات",
            "items": [
                {
                    "$$_deviceId": "ANFU AF75",
                    "serialNumber": "05HEC020895",
                    "status": "50"  # STRING not int
                }
            ],
            "factorId_paymentLink": "https://cms.hamoonpay.com/l/e6vQF",
            "factorPayment": None
        },
        "success": True
    }
    
    # Mock _make_request to return Order (since it validates with Order model)
    from src.models.domain import Order
    mocker.patch.object(
        service, 
        "_make_request", 
        return_value=Order.model_validate(auth_response_data["data"])
    )
    
    auth_result = await service.authenticate_user("3970165857")
    
    # AuthResponse wraps the Order
    assert auth_result.authenticated is True
    assert auth_result.order.order_number == "70231"
    assert auth_result.name == "رامین اسدبیگی"
    
    # Test get_order_by_number with typical response
    order_response = {
        "data": {
            "number": 72530,
            "$$_contactId": "عاطفه بحریپور",
            "contactId_nationalCode": "1362405728",
            "contactId_phone": "09924081915",
            "contactId_cityId": "آذربایجان شرقی تبریز",
            "steps": 0,
            "$$_steps": "ورود مرسوله",
            "items": [
                {
                    "$$_deviceId": "ANFU AF75",
                    "serialNumber": "05HEC034461",
                    "status": "0"
                }
            ],
            "factorId_paymentLink": ""
        }
    }
    
    mocker.patch.object(
        service, 
        "_make_request", 
        return_value=Order.model_validate(order_response["data"])
    )
    
    order_result = await service.get_order_by_number("72530")
    assert order_result.order_number == "72530"
    assert order_result.customer_name == "عاطفه بحریپور"
    
    # Test get_order_by_serial
    serial_result = await service.get_order_by_serial("05HEC034461")
    assert serial_result.order_number == "72530"

@pytest.mark.asyncio
async def test_submit_methods_success(service, mocker):
    mocker.patch(
        "src.config.enums.ComplaintType.map_to_server",
        return_value={"subject_guid": "18141068-5b2a-47d0-b48c-797399dc7002", "unit": 2}
    )
    
    # Match ACTUAL API response for complaint
    complaint_response = {
        "data": {
            "success": True,
            "message": "شکایت موردنظر با موفقیت ثبت شد.",
            "ticketNumber": "10817",
            "recordId": "c561cbce-8498-4d3d-add9-9cbd3b3ae173"
        },
        "success": True
    }
    
    from src.models.domain import SubmissionResponse
    
    # Mock returns validated SubmissionResponse
    mocker.patch.object(
        service, 
        "_make_request", 
        return_value=SubmissionResponse.model_validate(complaint_response["data"])
    )
    
    result1 = await service.submit_complaint(1, "شکایت تست", "123456")
    
    # Now it's a SubmissionResponse object
    assert hasattr(result1, 'ticket_number')
    assert result1.ticket_number == "10817"
    assert result1.success is True
    
    # Test repair request
    result2 = await service.submit_repair_request("توضیحات تعمیر", "SN789")
    assert hasattr(result2, 'ticket_number')
    assert result2.ticket_number == "10817"

@pytest.mark.asyncio
async def test_submit_methods_fail(service, mocker):
    mocker.patch(
        "src.config.enums.ComplaintType.map_to_server",
        return_value={"subject_guid": "guid", "unit": "unit"}
    )
    
    # _make_request will raise APIResponseError for success=False
    # Mock it to raise the exception directly
    mocker.patch.object(
        service, 
        "_make_request", 
        side_effect=APIResponseError(status_code=422, error_detail="خطای اعتبارسنجی")
    )
    
    with pytest.raises(APIResponseError):
        await service.submit_complaint(1, "bad request", "cid")
    
    # Test None/empty response
    mocker.patch.object(
        service, 
        "_make_request", 
        side_effect=APIResponseError(status_code=404, error_detail="Empty response")
    )
    
    with pytest.raises(APIResponseError):
        await service.submit_repair_request("desc", "sn")


# ---------------------- NotificationService ----------------------
@pytest.mark.asyncio
async def test_notification_send_and_fail(mocker):
    bot = mocker.AsyncMock()
    sm = mocker.AsyncMock()
    n = NotificationService(bot, sm)
    bot.send_message.return_value = SimpleNamespace(message_id=10)
    ok = await n._send(123, "hi")
    assert ok
    bot.send_message.side_effect = Exception("boom")
    fail = await n._send(123, "hi")
    assert fail is False

@pytest.mark.asyncio
async def test_order_status_changed_and_expired(mocker):
    bot = mocker.AsyncMock()
    sm = mocker.AsyncMock()
    n = NotificationService(bot, sm)
    mocker.patch("src.services.notifications.WorkflowSteps.get_step_info", return_value={"icon": "📦", "name": "پردازش"})
    await n.order_status_changed(1, "ORD12", 2, "در حال بررسی")
    await n.session_expired(1)
    await n.rate_limit_exceeded(1, 120)
    await n.general_error(1, retry_callback="cb:data")
    bot.send_message.assert_called()

@pytest.mark.asyncio
async def test_broadcast(monkeypatch, mocker):
    bot = mocker.AsyncMock()
    sm = mocker.AsyncMock()
    n = NotificationService(bot, sm)
    sm.get_all_chat_ids.return_value = [1, 2]
    bot.send_message.return_value = SimpleNamespace(message_id=1)
    count = await n.broadcast("msg")
    assert count == 2
    sm.get_all_chat_ids.return_value = []
    zero = await n.broadcast("msg")
    assert zero == 0
