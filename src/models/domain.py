from __future__ import annotations
import re
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, computed_field, AliasChoices

def clean_numeric_string(v: Any) -> Optional[str]:
    if v is None: return None
    cleaned = str(v).replace(",", "").strip()
    return re.sub(r"\D", "", cleaned)

def sanitize_text(v: str) -> str:
    if not v: return ""
    return re.sub(r"[\s\t\r\n]+", " ", str(v)).strip()

def parse_date_string(v: Any) -> Optional[str]:
    if not v or str(v).lower() in ("none", "null"): return None
    try:
        value = str(v).strip()
        date_part = value.split(" ")[0]
        return date_part
    except (ValueError, TypeError):
        return str(v) 

class Device(BaseModel):
    model: str = Field(..., alias='$$_deviceId')
    serial: str = Field(..., alias='serialNumber')
    status: str = Field("unknown", alias='$$_status')
    status_code: int = Field(0, alias='status')
    description: Optional[str] = Field(None, alias='passDescription')

    class Config:
        populate_by_name = True
        extra = 'ignore'
        frozen = True

class Payment(BaseModel):
    id: Optional[str] = None
    link: Optional[str] = Field(None, alias="factorId_paymentLink")
    reference_code: Optional[str] = Field(None, alias='referenceCode')
    invoice_id: Optional[str] = Field(None, alias='$$_invoiceId')

    @property
    def is_completed(self) -> bool:
        """Check if payment exists (has ID)"""
        return bool(self.id)
    
    @property
    def is_paid(self) -> bool:
        """Alias for is_completed"""
        return self.is_completed

    class Config:
        populate_by_name = True
        extra = 'ignore'

class Order(BaseModel):
    order_number: str = Field(..., alias='number')
    customer_name: str = Field(..., alias='$$_contactId')
    national_id: str = Field(..., validation_alias=AliasChoices('contactId_nationalCode', 'contactId_nationalId'))
    phone: Optional[str] = Field(None, alias='contactId_phone')
    city: Optional[str] = Field(None, alias='contactId_cityId')
    status_code: int = Field(0, alias='steps')
    status_text: str = Field("", alias='$$_steps')
    tracking_code: Optional[str] = Field(None, alias=AliasChoices('$$_warehouseRecieptId', 'warehouseRecieptId_number'))
    registration_date_raw: Optional[str] = Field(None, alias='warehouseRecieptId_createdOn')
    last_update: Optional[str] = Field(None, alias='modifiedOn')
    devices: List[Device] = Field(default_factory=list, alias='items')
    invoice_number: Optional[str] = Field(None, alias=AliasChoices('$$_factorId', 'factorId_number'))
    payment_link: Optional[str] = Field(None, alias='factorId_paymentLink')
    payment: Optional[Payment] = Field(None, alias='factorPayment')

    @computed_field
    @property
    def registration_date(self) -> Optional[str]:
        return parse_date_string(self.registration_date_raw)

    @field_validator('order_number', 'tracking_code', 'invoice_number', mode='before')
    @classmethod
    def normalize_numeric_ids(cls, v):
        """Only for truly numeric fields"""
        return clean_numeric_string(v) or str(v)

    @field_validator('customer_name', 'city', mode='before')
    @classmethod
    def normalize_texts(cls, v):
        return sanitize_text(v)

    @property
    def has_payment_link(self) -> bool:
        return bool(self.payment_link)
    @property
    def is_paid(self) -> bool:
        return self.payment is not None and self.payment.is_completed

    class Config:
        populate_by_name = True
        extra = 'ignore'

class AuthResponse(BaseModel):
    """Schema for successful authentication - wraps Order model"""
    order: Order
    
    @classmethod
    def model_validate(cls, obj: Any, **kwargs):
        """Handle both wrapped and unwrapped order data"""
        if isinstance(obj, dict):
            if "order" in obj:
                return super().model_validate(obj, **kwargs)
            return super().model_validate({"order": obj}, **kwargs)
        return super().model_validate(obj, **kwargs)

    @property
    def authenticated(self) -> bool:
        """Check if authentication was successful"""
        return bool(self.order and self.order.order_number)
    
    @property
    def name(self) -> str:
        return self.order.customer_name
    @property
    def national_id(self) -> str:
        return self.order.national_id
    @property
    def phone_number(self) -> Optional[str]:
        return self.order.phone
    @property
    def city(self) -> Optional[str]:
        return self.order.city
    @property
    def order_number(self) -> str:
        return self.order.order_number
    @property
    def device_count(self) -> int:
        return len(self.order.devices)
    @property
    def has_payment_link(self) -> bool:
        return self.order.has_payment_link
    @property
    def is_paid(self) -> bool:
        return self.order.is_paid

    class Config:
        populate_by_name = True

class SubmissionResponse(BaseModel):
    """Standardized response for complaint/repair submissions."""
    success: bool = True
    message: str = "Success"
    ticket_number: Optional[str] = Field(None, alias="ticketNumber")
    record_id: Optional[str] = Field(None, alias="recordId")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        populate_by_name = True
        extra = "ignore"
