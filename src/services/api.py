"""API Service - Handles all external API interactions."""
import logging, asyncio, aiohttp
from pydantic import ValidationError, BaseModel
from src.config.enums import ComplaintType
from src.config.settings import Settings
from src.core.client import APIClient
from src.models.domain import Order, AuthResponse, SubmissionResponse
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

    async def _make_request(self, method: str, endpoint_key: str, model_to_validate: type[BaseModel], **kwargs) -> BaseModel:
        """Internal request handler that centralizes error handling, response processing, and validation."""
        endpoint_url = self.settings.get_endpoint(endpoint_key)
        if not endpoint_url:
            raise ConfigurationError(f"API endpoint for '{endpoint_key}' is not configured.")

        force_refresh = kwargs.pop("force_refresh", False)
        if force_refresh and hasattr(self.client, "cache"):
            await self.client.cache.invalidate(f"bot:cache:order:*{endpoint_url}*")

        try:
            response = await self.client.request(method, endpoint_url, **kwargs)
            if not response.success:
                if response.status in {401, 403}:
                    raise APIAuthenticationError(f"Authentication failed for {endpoint_url}. Detail: {response.error or 'API AUTHENTICATION ERROR'}")
                raise APIResponseError(status_code=response.status, error_detail=response.error)
            
            payload = response.data or {}

            if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
                merged = {**payload, **payload["data"]}
                payload = merged

            if isinstance(payload, dict) and payload.get("success") is False:
                msg = payload.get("message") or "عملیات ناموفق در سرور"
                raise APIResponseError(status_code=422, error_detail=msg)
            if payload is None or (isinstance(payload, (dict, list)) and not payload):
                raise APIResponseError(status_code=404, error_detail="Empty response")
            
            if isinstance(payload, dict) and "data" in payload:
                data_part = payload.get("data")
                if isinstance(data_part, dict):
                    payload = data_part
                elif isinstance(data_part, list) and len(data_part) == 1:
                    payload = data_part[0]
                else:
                    payload = data_part
            
            if model_to_validate:
                try:
                    return model_to_validate.model_validate(payload)
                except (ValidationError, TypeError) as e:
                    logger.error(f"Pydantic validation failed for {endpoint_key}: {e}\nRaw Data: {payload}")
                    raise APIValidationError(model_name=model_to_validate.__name__, validation_errors=str(e)) from e
            return payload

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"API timeout after {getattr(self.client, 'timeout', 'unknown')} to {endpoint_url}")
            else:
                logger.error(f"Network error calling endpoint {endpoint_url}: {e}")
            raise APINetworkError(original_exception=e) from e

    async def authenticate_user(self, national_id: str) -> AuthResponse:
        validated_data = await self._make_request("post", "national_id", Order, data={'nationalId': national_id})
        return AuthResponse(order=validated_data)
    
    async def get_order_by_number(self, order_number: str, force_refresh: bool = False) -> Order:
        return await self._make_request("post", "number", Order, data={'number': order_number}, force_refresh = force_refresh)
    
    async def get_order_by_serial(self, serial: str) -> Order:
        return await self._make_request("post", "serial", Order, data={'serial': serial})

    async def submit_complaint(
        self,
        complaint_type_id: int,
        text: str,
        chat_id: str = None,
        user_name: str = None,
        phone_number: str = None,
        device_serial: str = None,
    ) -> SubmissionResponse:
        """Submits a user complaint."""
        ctype_map = ComplaintType.map_to_server(complaint_type_id)
        description_with_chat = (
            f"{text.strip()}\n\nfrom telegram - chat-id: {chat_id}"
            if chat_id else text.strip()
        )
        payload = {
            "SubjectId": ctype_map["subject_guid"],  
            "Description": description_with_chat,
            "Unit": ctype_map["unit"],
            "Name": user_name,
            "Phone": phone_number,
            "DeviceSerial": device_serial,
        }
        raw_data = await self._make_request("post", "submit_complaint", SubmissionResponse, data=payload)
        if isinstance(raw_data, dict):
            success = raw_data.get("success", True)
            msg = raw_data.get("message", "عملیات ناموفق در سرور")
        else:  
            success = getattr(raw_data, "success", True)
            msg = getattr(raw_data, "message", "عملیات ناموفق در سرور")

        if not success:
            raise APIResponseError(status_code=400, error_detail=msg)
        return raw_data

    async def submit_repair_request(
        self,
        description: str,
        device_serial: str ,
        device_model: str = None,
        chat_id: str = None,
        user_name: str = None,
        phone_number: str = None,
    ) -> SubmissionResponse:
        """Submits a repair request."""
        payload = {
            "Description": description,
            "DeviceSerial":device_serial,
            "DeviceModel":device_model,
            "ChatId":chat_id,
            "Name": user_name,
            "Phone": phone_number
        }
        raw_data = await self._make_request("post", "submit_repair", SubmissionResponse, data=payload)
        if isinstance(raw_data, dict):
            success = raw_data.get("success", True)
            msg = raw_data.get("message", "عملیات ناموفق در سرور")
        else:  
            success = getattr(raw_data, "success", True)
            msg = getattr(raw_data, "message", "عملیات ناموفق در سرور")

        if not success:
            raise APIResponseError(status_code=400, error_detail=msg)
        return raw_data
