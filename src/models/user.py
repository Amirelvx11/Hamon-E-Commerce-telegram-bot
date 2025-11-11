""" User domain models (sessions & base info for user)"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime,timedelta
from typing import Optional, Dict, Any, List
from src.config.settings import get_config
from src.config.enums import UserState
from src.models.domain import sanitize_text, clean_numeric_string

class UserProfile(BaseModel):
    """Represents the canonical, persistent user profile"""
    user_id: int
    national_id: str
    name: str
    phone: Optional[str] = None # Will become required when OTP is implemented
    city: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator('national_id', mode='before')
    def clean_nid(cls, v):
        return clean_numeric_string(v)

    @field_validator('name', 'city', mode='before')
    def clean_texts(cls, v):
        return sanitize_text(v)

class UserSession(BaseModel):
    """Unified user session model – cached in Redis and kept in memory."""
    chat_id: int
    user_id: int

    national_id: Optional[str] = None
    user_name: Optional[str] = None
    phone_number: Optional[str] = None  
    city: Optional[str] = None

    state: UserState = UserState.IDLE
    is_authenticated: bool = False

    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(default_factory=lambda: datetime.now() + timedelta(minutes=60))

    last_bot_messages: List[int] = Field(default_factory=list)
    temp_data: Dict[str, Any] = Field(default_factory=dict)
    request_count: int = 0
    
    order_number: Optional[str] = None
    last_orders: List[Dict] = Field(default_factory=list)

    class Config:
        use_enum_values = True 
        extra = 'ignore' 

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def refresh(self, minutes: Optional[int] = None) -> None:
        self.last_activity = datetime.now()
        if minutes:
            self.expires_at = self.last_activity + timedelta(minutes=minutes)
    
    @classmethod
    def create_with_default_expiry(cls, **kwargs) -> "UserSession":
        cfg = get_config()
        timeout_min = cfg.session_timeout_minutes
        instance = cls(**kwargs)
        instance.expires_at = datetime.now() + timedelta(minutes=timeout_min)
        return instance

    @field_validator('user_name', 'city', mode='before')
    def normalize_session_texts(cls, v):
        return sanitize_text(v)

    def to_dict(self, sanitize_temp_data: bool = True) -> Dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        if sanitize_temp_data:
            data.pop('temp_data', None)
            data.pop('last_bot_messages', None)
        return data
    