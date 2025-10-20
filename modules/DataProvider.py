"""
Data Provider - Handle The Data's come from server
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from .CoreConfig import (
    DEVICE_STATUS,
    STEP_ICONS,
    STEP_PROGRESS,
    WORKFLOW_STEPS,
    BotConfig,
    Validators,
    get_step_info,
)

logger = logging.getLogger(__name__)


@dataclass
class OrderInfo:
    """Order information with proper field mapping"""

    # --- Core identifiers ---
    order_number: str
    customer_name: str
    nationalId: str
    phone_number: str
    city: str
    # --- Order-level workflow status ---
    steps: int  # numeric workflow stage
    current_step: str  # text (from WORKFLOW_STEPS)
    status_icon: str  # icon for current step
    progress: int  # percentage (from STEP_PROGRESS)
    progress_bar: str  # text block visual
    # --- Device-level info ---
    device_model: str
    serial_number: str
    device_status: str
    registration_date: str
    pre_reception_date: str
    # --- Dates and details ---
    registration_date: str
    pre_reception_date: str
    repair_description: Optional[str] = None
    tracking_code: Optional[str] = None
    total_cost: Optional[int] = None
    payment_link: Optional[str] = None
    factor_payment: Optional[Dict[str, Any]] = None
    devices: Optional[List[Dict[str, Any]]] = None

    def to_display_dict(self) -> Dict[str, Any]:
        """Convert to display format consumable by MessageHandler"""
        return {
            "order_number": self.order_number,
            "customer_name": self.customer_name,
            "phone_number": self.phone_number,
            "city": self.city,
            # Global status (already precomputed)
            "steps": self.steps,
            "current_step": self.current_step,
            "status_icon": self.status_icon,
            "progress": self.progress,
            "progress_bar": self.progress_bar,
            # Device info
            "device_model": self.device_model,
            "serial_number": self.serial_number,
            "device_status": self.device_status,
            # Dates
            "registration_date": self.registration_date,
            "pre_reception_date": self.pre_reception_date,
            # Other optional fields
            "tracking_code": self.tracking_code or "---",
            "repair_description": self.repair_description or "---",
            "payment_link": self.payment_link,
            "total_cost": self.total_cost,
            "factor_payment": self.factor_payment,
            "devices": self.devices or [],
        }

    def _format_date(self, date_str: str) -> str:
        """Format date for display (remove time part)"""
        if not date_str or date_str == "---":
            return "---"
        # Split by space and take only date part
        if " " in date_str:
            return date_str.split(" ")[0]
        return date_str


# =====================================================
# Main DataProvider Class
# =====================================================


class DataProvider:
    """API communication manager with caching"""

    def __init__(self, config: BotConfig, redis_client=None):
        self.config = config
        self.redis = redis_client
        self.session: Optional[ClientSession] = None
        self._lock = asyncio.Lock()
        self._session_lock = asyncio.Lock()

        self.cache_prefix = "bot:cache:"
        self.auth_token = os.getenv("AUTH_TOKEN", "")
        self.cache_ttl = 300  # 5 minutes
        self.timeout = ClientTimeout(total=30, connect=10, sock_read=20)

    async def __aenter__(self):
        """Async context manager entry"""
        await self.ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()

    async def _cache_get(self, key: str) -> Optional[Dict]:
        if not self.redis:
            return None
        try:
            data = await self.redis.get(f"{self.cache_prefix}{key}")
            return json.loads(data) if data else None
        except:
            return None

    async def _cache_set(self, key: str, value: Dict, ttl: int = 300) -> None:
        if not self.redis:
            return
        try:
            await self.redis.setex(
                f"{self.cache_prefix}{key}", ttl, json.dumps(value, ensure_ascii=False)
            )
        except:
            pass  # Silent fail for caching

    async def ensure_session(self):
        async with self._session_lock:
            if not self.session or self.session.closed:
                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    ttl_dns_cache=300,
                    enable_cleanup_closed=True,
                )

                self.session = aiohttp.ClientSession(
                    timeout=self.timeout,
                    connector=connector,
                    headers={
                        "User-Agent": "HamoonBot/1.0",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                logger.debug("HTTP session created")

    async def close_session(self):
        async with self._session_lock:
            if self.session and not self.session.closed:
                await self.session.close()
                await asyncio.sleep(0.1)  # Allow cleanup
                self.session = None
                logger.debug("HTTP session closed")

    async def _make_request(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry_count: int = 2,
    ) -> Optional[Dict]:
        """Make HTTP request with retry and error handling"""
        await self.ensure_session()

        # Prepare headers
        request_headers = {"auth-token": self.auth_token} if self.auth_token else {}
        if headers:
            request_headers.update(headers)

        last_error = None

        for attempt in range(retry_count):
            try:
                async with self.session.request(
                    method, url, json=json_data, headers=request_headers
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        return data
                    elif response.status == 404:
                        logger.debug(f"Not found: {url}")
                        return None
                    elif response.status >= 500:
                        last_error = f"Server error {response.status}"
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2**attempt)
                            continue
                    # Client error - don't retry
                    else:
                        text = await response.text()
                        logger.error(f"API error {response.status}: {text[:200]}")
                        return None

            except asyncio.TimeoutError:
                last_error = "Timeout"
                if attempt < retry_count - 1:
                    await asyncio.sleep(2**attempt)
                    continue
            except aiohttp.ClientError as e:
                last_error = str(e)
                if attempt < retry_count - 1:
                    await asyncio.sleep(2**attempt)
                    continue
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return None

        # All retries failed
        logger.error(f"Request failed after {retry_count} attempts: {last_error}")
        return None

    async def get_order(
        self, identifier: str, id_type: str = "number", force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Unified order fetching by different identifier types"""

        logger.info(f"Getting order by {id_type}: {identifier}")

        # Route to appropriate method based on id_type
        if id_type == "national_id" or id_type == "nationalId":
            # For National ID lookup
            cache_key = f"order:nid:{identifier}"

            if not force_refresh:
                cached = await self._cache_get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for National ID {identifier}")
                    return cached

            # Use the National ID endpoint
            endpoint = self.config.server_urls.get(
                "national_id"
            ) or self.config.server_urls.get("nationalId")
            if not endpoint:
                logger.error("National ID endpoint not configured")
                return None
            logger.info(f"Fetching National ID {identifier} from API: {endpoint}")

            json_data = {"nationalId": identifier}
            response = await self._make_request("POST", endpoint, json_data=json_data)

            if response:
                logger.info(
                    f"🔍 RAW RESPONSE: {json.dumps(response, ensure_ascii=False)[:500]}"
                )

                if not response.get("success", True):
                    logger.error(f"API error: {response.get('message')}")
                    return None

                order_info = self._parse_order_response(response)
                if order_info:
                    logger.info(
                        f"✅ Successfully parsed order for National ID {identifier}"
                    )
                    result = order_info.to_display_dict()
                    await self._cache_set(cache_key, result, ttl=self.cache_ttl)
                    return result
                else:
                    logger.error(f"❌ Failed to parse: {response}")

            logger.warning(f"No order found for National ID {identifier}")
            return None

        elif id_type == "number":
            return await self.get_order_by_number(identifier, force_refresh)
        elif id_type == "serial":
            return await self.get_order_by_serial(identifier, force_refresh)
        else:
            logger.error(f"Invalid id_type: {id_type}")
            return None

    async def get_user_orders(self, national_id: str) -> list:
        """Get user's orders by national ID"""
        try:
            response = await self._make_request(
                "GET",
                self.config.server_urls.get("user_orders"),
                params={"nationalId": national_id},
            )

            if response and response.get("success", True):
                orders_data = response.get("data", [])
                # Convert to OrderInfo objects
                orders = []
                for order_data in orders_data:
                    order = self._parse_order_response(order_data)
                    if order:
                        orders.append(order)
                return orders
            return []
        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return []

    async def get_order_by_number(
        self, order_number: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get order by tracking number"""
        if not order_number:
            return None

        cache_key = f"order:number:{order_number}"

        if not force_refresh:
            cached = await self._cache_get(cache_key)
            if cached:
                logger.debug(f"Cache hit for order {order_number}")
                return cached

        endpoint = self.config.server_urls.get("number")
        if not endpoint:
            logger.error("Order tracking endpoint not configured")
            return None

        logger.info(f"Fetching order {order_number} from API")

        json_data = {"number": order_number}
        response = await self._make_request("POST", endpoint, json_data=json_data)

        if not response:
            logger.warning(f"No response for order {order_number}")
            return None

        order_info = self._parse_order_response(response)
        if order_info:
            result = order_info.to_display_dict()
            await self._cache_set(cache_key, result, ttl=self.cache_ttl)
            return result

        logger.warning(f"Failed to parse order {order_number}")
        return None

    async def get_order_by_serial(
        self, serial: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get order by device serial"""
        if not serial:
            return None

        is_valid, error_msg = Validators.validate_serial(serial)
        if not is_valid:
            logger.warning(f"Invalid serial format: {error_msg}")
            return None

        cache_key = f"order:serial:{serial}"

        if not force_refresh:
            cached = await self._cache_get(cache_key)
            if cached:
                logger.debug(f"Cache hit for serial {serial}")
                return cached

        endpoint = self.config.server_urls.get("serial")
        if not endpoint:
            logger.error("Serial tracking endpoint not configured")
            return None

        logger.info(f"Fetching serial {serial} from API")

        json_data = {"serial": serial}
        response = await self._make_request("POST", endpoint, json_data=json_data)

        if not response:
            logger.warning(f"No response for serial {serial}")
            return None

        order_info = self._parse_order_response(response)
        if order_info:
            result = order_info.to_display_dict()
            await self._cache_set(cache_key, result, ttl=self.cache_ttl)
            return result

        logger.warning(f"Failed to parse serial {serial}")
        return None

    async def authenticate_user(self, national_id: str) -> Optional[Dict]:
        """Authenticate user by national ID"""
        if not national_id:
            return None

        cache_key = f"user:nid:{national_id}"
        cached = await self._cache_get(cache_key)
        if cached:
            return cached

        endpoint = self.config.server_urls.get("national_id")
        if not endpoint:
            logger.warning("Auth endpoint not configured - using mock")
            return {
                "name": "کاربر آزمایشی",
                "phone": "09121234567",
                "national_id": national_id,
                "authenticated": True,
            }

        response = await self._make_request(
            "POST", endpoint, json_data={"nationalId": national_id}
        )

        if response:
            # Check if it's an error response
            if not response.get("success", True):
                logger.warning(f"Auth failed: {response.get('message')}")
                return None

            # The National ID endpoint returns order data, extract user info from it
            data = response.get("data", response)
            if data:
                user_data = {
                    "name": data.get("$$_contactId", "نامشخص"),
                    "phone_number": data.get("contactId_phone", "نامشخص"),
                    "city": data.get("contactId_cityId", "نامشخص"),
                    "national_id": (
                        data.get("contactId_nationalCode")
                        or data.get("contactId_nationalId")
                        or national_id
                    ),
                    "authenticated": True,
                }
                await self._cache_set(cache_key, user_data, ttl=1800)
                return user_data

        return None

    async def submit_complaint(
        self,
        national_id: str,
        complaint_type: str,
        description: str,
        user_name: str,
        phone_number: str,
    ) -> Optional[str]:
        """Submit complaint to API with validation and error handling"""

        if not all([national_id, complaint_type, description]):
            logger.error("Missing required complaint fields")
            return None

        if len(description.strip()) < 10:
            logger.error("Complaint description too short")
            return None

        if self.redis:
            rate_key = f"complaint:rate:{national_id}"
            count = await self.redis.incr(rate_key)
            if count == 1:
                await self.redis.expire(rate_key, 3600)
            if count > 5:
                logger.warning(f"Rate limit exceeded for {national_id}")
                return None

        endpoint = self.config.server_urls.get("submit_complaint")
        if not endpoint:
            logger.warning("Complaint endpoint not configured")
            import time

            return f"TKT-MOCK-{int(time.time())}"

        json_data = {
            "nationalId": national_id.strip(),
            "complaintType": complaint_type.strip(),
            "description": description.strip(),
            "userName": user_name or "",
            "phoneNumber": phone_number or "",
        }

        response = await self._make_request("POST", endpoint, json_data=json_data)

        if response:
            if response.get("success", True):
                ticket = (
                    response.get("ticket_number")
                    or response.get("ticketNumber")
                    or response.get("id")
                    or response.get("ticketId")
                )

                if ticket:
                    logger.info(f"✅ Complaint submitted: {ticket}")
                    await self._cache_set(
                        f"complaint:{ticket}", json_data, ttl=86400
                    )  # Cache for 24h
                    return ticket
                else:
                    logger.warning("API success but no ticket returned")
            else:
                error_msg = response.get("message", "Unknown API error")
                logger.error(f"❌ Complaint failed: {error_msg}")

        logger.error("❌ No response from complaint API")
        return None

    async def submit_repair_request(
        self, nationalId: str, description: str, contact: str
    ) -> Optional[str]:
        """Submit repair request"""
        return await self.submit_data(
            "repair", nationalId, description=description, contact=contact
        )

    def _parse_order_response(self, response: Dict) -> Optional[OrderInfo]:
        """Parse order API response - preserving all server fields"""
        try:
            data = response.get("data", response)
            if isinstance(data, list):
                data = data[0] if data else {}

            # --- Device normalization ---
            devices_raw = data.get("items", []) or []
            normalized_devices = []
            for d in devices_raw:
                status_raw = d.get("status", 0)
                if isinstance(status_raw, str):
                    rev_device_status = {v: k for k, v in DEVICE_STATUS.items()}
                    status_code = rev_device_status.get(status_raw.strip(), 0)
                else:
                    status_code = int(status_raw) if isinstance(status_raw, int) else 0
                normalized_devices.append(
                    {
                        "model": d.get("$$_deviceId", "نامشخص"),
                        "serial": d.get("serialNumber", "---"),
                        "status": DEVICE_STATUS.get(status_code, "نامشخص"),
                        "status_code": status_code,
                    }
                )
            first_device = normalized_devices[0] if normalized_devices else {}

            # --- Order-level status (steps) ---
            steps_raw = data.get("steps", data.get("status", 0))
            if isinstance(steps_raw, str):
                rev_steps = {
                    v: k for k, v in {**WORKFLOW_STEPS, **DEVICE_STATUS}.items()
                }
                steps_int = rev_steps.get(steps_raw.strip(), 0)
            else:
                steps_int = steps_raw if isinstance(steps_raw, int) else 0

            # --- Pre-calc progress metadata ---
            step_info = get_step_info(steps_int)

            return OrderInfo(
                order_number=str(data.get("number", data.get("processNumber", ""))),
                customer_name=data.get("$$_contactId", "نامشخص"),
                phone_number=data.get("contactId_phone", ""),
                nationalId=data.get("contactId_nationalCode")
                or data.get("contactId_nationalId"),
                city=data.get("contactId_cityId", ""),
                steps=steps_int,
                current_step=step_info["text"],
                status_icon=step_info["icon"],
                progress=step_info["progress"],
                progress_bar=f"[{step_info['bar']}]",
                device_model=first_device.get("model", "نامشخص"),
                serial_number=first_device.get("serial", "---"),
                device_status=first_device.get("status", "نامشخص"),
                registration_date=data.get(
                    "warehouseRecieptId_createdOn", data.get("createdOn", "")
                ),
                pre_reception_date=data.get("preReceptionId_createdOn", ""),
                repair_description=first_device.get("passDescription", ""),
                tracking_code=(
                    str(data.get("preReceptionId_number", ""))
                    if data.get("preReceptionId_number")
                    else None
                ),
                total_cost=data.get("factorId_totalPriceWithTax"),
                payment_link=data.get("factorId_paymentLink"),
                factor_payment=data.get("factorPayment"),
                devices=normalized_devices,
            )
        except Exception as e:
            logger.error(f"Error parsing order response: {e}", exc_info=True)
            return None

    def _parse_user_response(self, response: Dict) -> Optional[Dict]:
        """Parse user authentication response"""
        try:
            # Handle both wrapped and unwrapped responses
            data = response.get("data", response)

            # For National ID lookups, the user info is in the main data
            return {
                "name": data.get("$$_contactId", data.get("name", "نامشخص")),
                "phone": data.get("contactId_phone", data.get("phone", "")),
                "national_id": data.get(
                    "contactId_nationalCode", "contactId_nationalId"
                ),
                "authenticated": True,
            }
        except Exception as e:
            logger.error(f"Error parsing user response: {e}")
            return None

    async def submit_data(
        self, submission_type: str, national_id: str, **kwargs
    ) -> Optional[str]:
        """Unified submission method for complaints and repairs"""
        endpoint = self.config.server_urls.get(f"submit_{submission_type}")

        if not endpoint:
            # Return mock data for testing
            return f"MOCK-{datetime.now().timestamp():.0f}"

        # Build request data
        json_data = {
            "nationalId": national_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }

        response = await self._make_request("POST", endpoint, json_data=json_data)

        # For complaints and repairs, return ticket number
        if response:
            return response.get(
                "ticketNumber",
                response.get("id", f"REF-{datetime.now().timestamp():.0f}"),
            )
        return None


async def create_data_provider(config: BotConfig, redis_client=None) -> DataProvider:
    """Factory initializer for DataProvider."""
    provider = DataProvider(config, redis_client)
    await provider.ensure_session()
    logger.info("✅ DataProvider ready")
    return provider
