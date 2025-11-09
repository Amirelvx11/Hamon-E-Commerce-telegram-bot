"""Input validators with standardized result format(return bool for validation result)."""
import re
from dataclasses import dataclass
from typing import Optional, Union, Any

@dataclass
class ValidationResult:
    """Standardized result for all validation operations."""
    is_valid: bool
    cleaned_value: Optional[Any] = None  
    error_message: Optional[str] = None

class Validators:
    """
    Centralized static methods for all business logic validation.
    Each method returns a `ValidationResult` object for consistent handling.
    """
    MIN_TEXT_LENGTH = 10
    MAX_TEXT_LENGTH = 1000

    @staticmethod
    def _clean_numeric(value: Union[str, int]) -> str:
        """Remove all non-numeric characters"""
        return re.sub(r'\D', '', str(value))
    
    @staticmethod
    def validate_national_id(nid: Union[str, int]) -> ValidationResult:
        """Validate Iranian national or legal entity ID (10 or 11 digits)"""
        cleaned = Validators._clean_numeric(nid)
        
        if not cleaned.isdigit() or len(cleaned) not in (10, 11):
            return ValidationResult(False, None, "❌ کد/شناسه ملی باید فقط شامل ۱۰ یا ۱۱ رقم باشد.")
        
        # 11-digit: legal entity
        if len(cleaned) == 11:
            return ValidationResult(True, cleaned)

        # 10-digit: personal national ID checksum validation
        if len(cleaned) == 10:
            # Avoid invalid sequences like 0000000000, 1111111111, etc.
            if len(set(cleaned)) == 1:
                return ValidationResult(False, None, "❌ کد ملی نامعتبر است.")
        
            check = sum(int(cleaned[i]) * (10 - i) for i in range(9)) % 11
            valid = (check < 2 and int(cleaned[9]) == check) or (check >= 2 and int(cleaned[9]) == 11 - check)

            return ValidationResult(valid, cleaned if valid else None, None if valid else "❌ کد ملی نامعتبر است.")

        # (future formats, reserved for expansion)
        return ValidationResult(False, None, "❌ فرمت کد/شناسه ملی نامعتبر است.")
    
    @staticmethod
    def validate_order_number(order_num: Union[str, int]) -> ValidationResult:
        """Validate order tracking number"""
        cleaned = Validators._clean_numeric(order_num)
        
        if not cleaned:
            return ValidationResult(
                is_valid=False,
                error_message="❌ شماره پذیرش باید فقط عدد باشد و همچنین نمی‌تواند خالی باشد!"
            )
        if len(cleaned) < 3 or len(cleaned) > 8:
            return ValidationResult(
                is_valid=False,
                error_message="❌ تعداد ارقام شماره پذیرش نامعتبر!"
            )
        
        return ValidationResult(is_valid=True,cleaned_value=cleaned)
    
    @staticmethod
    def validate_serial(serial: Optional[str]) -> ValidationResult:
        """Validate device serial"""
        if not serial or not serial.strip():
            return ValidationResult(
                is_valid=False,
                error_message="❌ سریال دستگاه خالی است!"
            )
        
        cleaned = re.sub(r'[\s\-_]', '', serial.strip().upper())

        if len(cleaned) == 11 and (
            cleaned.startswith("00HEC") or cleaned.startswith("05HEC")
        ) and cleaned[5:].isdigit():
            return ValidationResult(True, cleaned_value=cleaned)

        if cleaned.isdigit() and len(cleaned) == 6 and cleaned != "000000":
            return ValidationResult(is_valid=True, cleaned_value=cleaned)
        
        return ValidationResult(
            is_valid=False,
            error_message=(
                "❌ فرمت سریال نامعتبر است!\n"
                "شماره سریال باید یکی از موارد زیر باشد:\n"
                "• ۶ رقم آخر مثل: 234567\n"
                "• یا کامل آن مثل: 00HEC234567 یا 05HEC234567"
            )
        )
    
    @staticmethod
    def validate_phone(phone: str) -> ValidationResult:
        """Validate Iranian mobile"""
        if not phone:
            return ValidationResult(
                is_valid=False,
                error_message="❌ شماره همراه خالی است"
            )
        
        cleaned = re.sub(r'[\s\-\(\)]', '', phone.strip())
        
        if not re.match(r'^(\+98|0098|0)?9\d{9}$', cleaned):
            return ValidationResult(
                is_valid=False,
                error_message="❌ شماره همراه نامعتبر (مثال: 09121234567)"
            )
        
        # Normalize to 09XX... format
        if cleaned.startswith('+98'):
            cleaned = '0' + cleaned[3:]
        elif cleaned.startswith('0098'):
            cleaned = '0' + cleaned[4:]
        elif not cleaned.startswith('0'):
            cleaned = '0' + cleaned
        
        return ValidationResult(
            is_valid=True,
            cleaned_value=cleaned
        )
    
    @classmethod
    def validate_text_length(cls, text: str, 
                            min_length: Optional[int] = None,
                            max_length: Optional[int] = None,
                            context: str = "متن") -> ValidationResult:
        """Validate text length for complaint text's, repair description & ..."""
        if not text or not text.strip():
            return ValidationResult(
                is_valid=False,
                error_message=f"⚠️ لطفاً {context} را وارد کنید"
            )
        
        cleaned = text.strip()
        min_len = min_length or cls.MIN_TEXT_LENGTH
        max_len = max_length or cls.MAX_TEXT_LENGTH
        
        if len(cleaned) < min_len:
            return ValidationResult(
                is_valid=False,
                error_message=f"⚠️ {context} باید حداقل {min_len} کاراکتر باشد"
            )
        
        if len(cleaned) > max_len:
            return ValidationResult(
                is_valid=False,
                error_message=f"⚠️ {context} حداکثر {max_len} کاراکتر مجاز است"
            )
        
        return ValidationResult(
            is_valid=True,
            cleaned_value=cleaned
        )
