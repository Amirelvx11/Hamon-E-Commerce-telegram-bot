"""API Service - Handles all external API interactions."""
import logging, asyncio, aiohttp
from datetime import datetime
from typing import Any
from pydantic import ValidationError
from src.config.enums import ComplaintType
from src.config.settings import Settings
from src.core.client import APIClient
from src.models.api import AuthResponse, SubmissionResponse
from src.models.order import Order
from src.services.exceptions import (
    ConfigurationError,
    APINetworkError,
    APIResponseError,
    APIValidationError,
    APIAuthenticationError
)

logger = logging.getLogger(__name__)

class APIService:
    """Centralized service for validated, exception-driven external data operations."""
    
    def __init__(self, api_client: APIClient , settings: Settings):
        self.client = api_client
        self.settings = settings

    async def _make_request(self, method: str, endpoint_key: str, **kwargs) -> Any:
        """Internal request handler that centralizes error handling and response processing."""
        endpoint_url = self.settings.get_endpoint(endpoint_key)
        if not endpoint_url:
            raise ConfigurationError(f"API endpoint for '{endpoint_key}' is not configured.")

        force_refresh = kwargs.pop("force_refresh", False)
        cache_ttl = kwargs.pop("cache_ttl", None)
        if force_refresh and hasattr(self.client, "cache"):
            await self.client.cache.invalidate(f"bot:cache:order:*{endpoint_url}*")

        try:
            response = await self.client.request(method, endpoint_url, **kwargs)
            if not response.success:
                status = response.status
                error_detail = response.error or response.data
                if status in {401, 403}:
                    raise APIAuthenticationError(f"Authentication failed for {endpoint_url}. Detail: {error_detail}")
                raise APIResponseError(status_code=status, error_detail=error_detail)
            
            payload = response.data
            if isinstance(payload, dict) and payload.get("success") is False:
                msg = payload.get("message") or "عملیات ناموفق در سرور"
                logger.warning(f"Semantic API failure ({endpoint_url}): {msg}")
                return {"semantic_error": True, "message": msg, "data": None}
            
            if isinstance(payload, dict) and "data" in payload:
                data_part = payload.get("data")
                if isinstance(data_part, dict):
                    payload = data_part
                elif isinstance(data_part, list) and len(data_part) == 1:
                    payload = data_part[0]
                else:
                    payload = data_part

            if payload is None or (isinstance(payload, (dict, list)) and len(payload) == 0):
                logger.warning(f"API endpoint {endpoint_url} returned success but empty payload.")
                return None
            
            return payload

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error calling endpoint {endpoint_url}: {e}")
            raise APINetworkError(original_exception=e) from e

    async def get_order_by_number(self, order_number: str, force_refresh: bool = False) -> Order:
        payload = {'number': order_number}
        raw_data = await self._make_request(
            "post", "number",
            data=payload, cache_ttl=60,
            force_refresh=force_refresh
        )
        if isinstance(raw_data, dict) and "data" in raw_data:
            raw_data = raw_data["data"]
        if not raw_data:
            raise APIResponseError(status_code=404, error_detail=f"Order '{order_number}' not found.")
        try:
            return Order.model_validate(raw_data)
        except (ValidationError, TypeError) as e:
            logger.error(f"Pydantic validation failed for order '{order_number}': {e}\nRaw Data: {raw_data}")
            raise APIValidationError(model_name="Order", validation_errors=str(e)) from e
    
    async def get_order_by_serial(self, serial: str) -> Order:
        payload = {'serial': serial}
        raw_data = await self._make_request("post", "serial", data=payload, cache_ttl=60)
        if isinstance(raw_data, dict) and "data" in raw_data:
            raw_data = raw_data["data"]
        if not raw_data:
            raise APIResponseError(status_code=404, error_detail=f"Order with serial '{serial}' not found.")
        try:
            return Order.model_validate(raw_data)
        except (ValidationError, TypeError) as e:
            logger.error(f"Pydantic validation failed for order by serial '{serial}': {e}\nRaw Data: {raw_data}")
            raise APIValidationError(model_name="Order", validation_errors=str(e)) from e

    async def authenticate_user(self, national_id: str) -> AuthResponse:
        """Authenticates user and returns the complete, validated data structure."""
        payload = {'nationalId': national_id}
        raw_response = await self._make_request("post", "national_id", data=payload, cache_ttl=300)

        if not raw_response or not raw_response.get("success", True):
            raise APIResponseError(status_code=404, error_detail=f"Auth failed for NID: '{national_id}'")
        if not isinstance(raw_response, dict):
            raise APIResponseError(status_code=500, error_detail="Invalid API format")
        
        data = raw_response

        try:
            validated_response = AuthResponse.model_validate(data)
            validated_response.raw_data = data
            return validated_response
        except (ValidationError, TypeError) as e:
            logger.error(f"Pydantic validation failed for auth {national_id}: {e}\nRaw={data}")
            raise APIValidationError(model_name="AuthResponse", validation_errors=str(e)) from e

    async def submit_complaint(
        self,
        national_id: str,
        phone_number: str,
        complaint_type_id: int,
        complaint_type_text: str,
        text: str,
        chat_id: str = None,
    ) -> SubmissionResponse:
        """Submits a user complaint."""
        ctype_map = ComplaintType.map_to_server(complaint_type_id)
        description_with_chat = (
            f"{text.strip()}\n\nfrom telegram - chat-id: {chat_id}"
            if chat_id else text.strip()
        )
        payload = {
            "description": description_with_chat,
            "phoneNumber": phone_number or "نامشخص",
            "nationalId": national_id,
            "chatId": str(chat_id or ""),
            "unit": ctype_map["unit"],
            "subjectId": ctype_map["subject_guid"],  
        }
        raw_data = await self._make_request("post", "submit_complaint", data=payload)
        logger.warning(f"📡 RAW SUBMIT RESPONSE: {raw_data!r}")

        if not raw_data:
            raise APIResponseError(status_code=500, error_detail="Empty API response")

        if not isinstance(raw_data, dict):
            raw_data = {"raw": str(raw_data)}

        raw_data.setdefault("ticketNumber", f"COMP-{int(datetime.now().timestamp())}")
        raw_data.setdefault("timestamp", datetime.now().isoformat())

        return SubmissionResponse.model_validate(raw_data)

    async def submit_repair_request(
        self,
        national_id: str,
        phone_number: str,
        description: str
    ) -> SubmissionResponse:
        """Submits a repair request."""
        payload = {
            "nationalId": national_id,
            "phoneNumber": phone_number,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }
        raw_data = await self._make_request("post", "submit_repair", data=payload)

        if not raw_data:
            raise APIResponseError(status_code=500, error_detail="Submission failed, API returned no data.")
        try:
            if "ticketNumber" not in raw_data:
                raw_data["ticketNumber"] = f"REP-{int(datetime.now().timestamp())}"
            if "timestamp" not in raw_data:
                raw_data["timestamp"] = datetime.now().isoformat()

            return SubmissionResponse.model_validate(raw_data)
        except (ValidationError, TypeError) as e:
            raise APIValidationError(model_name="SubmissionResponse", validation_errors=str(e))
        