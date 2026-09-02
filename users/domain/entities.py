from dataclasses import dataclass, field
from datetime import datetime
from django.utils import timezone
from typing import Optional, List, Any
import uuid

@dataclass
class IdentityDocumentEntity:
    id: uuid.UUID
    user_id: uuid.UUID
    doc_type: str
    doc_number: str
    doc_country: str
    status: str
    front_image: Optional[Any] = None
    back_image: Optional[Any] = None
    pdf_file: Optional[Any] = None
    rejection_reason: str = ""
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_id: Optional[uuid.UUID] = None

    def is_approved(self) -> bool:
        return self.status == 'approved'

@dataclass
class UserSecurityEntity:
    id: uuid.UUID
    user_id: uuid.UUID
    email_token: str = ""
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    phone_otp: str = ""
    phone_otp_expires_at: Optional[datetime] = None
    phone_verified: bool = False
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    two_factor_enabled: bool = False
    two_factor_secret: str = ""
    two_factor_backup_codes: List[str] = field(default_factory=list)
    password_changed_at: Optional[datetime] = None
    password_reset_token: str = ""
    password_reset_expires: Optional[datetime] = None


    def is_locked(self) -> bool:
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def generate_backup_codes(self, count: int = 8) -> List[str]:
        import secrets
        import hashlib
        plain_codes = []
        hashed_codes = []
        for _ in range(count):
            part1 = secrets.token_hex(2).upper()
            part2 = secrets.token_hex(2).upper()
            c = f"{part1}-{part2}"
            plain_codes.append(c)
            hashed_codes.append(hashlib.sha256(c.encode()).hexdigest())

        self.two_factor_backup_codes = hashed_codes
        return plain_codes

    def verify_and_consume_backup_code(self, raw_code: str) -> bool:
        import hashlib
        if not raw_code:
            return False
        normalized_code = raw_code.strip().upper()
        code_hash = hashlib.sha256(normalized_code.encode()).hexdigest()
        if self.two_factor_backup_codes and code_hash in self.two_factor_backup_codes:
            self.two_factor_backup_codes = [c for c in self.two_factor_backup_codes if c != code_hash]
            return True
        return False


@dataclass
class UserEntity:
    id: uuid.UUID
    email: str
    full_name: str
    username: Optional[str] = None
    is_active: bool = False
    is_staff: bool = False
    is_verified: bool = False
    is_available: bool = False
    verification_status: str = 'pending'
    phone: str = ""
    country_code: str = "AO"
    city: str = ""
    address: str = ""
    province: str = ""
    municipality: str = ""
    neighborhood: str = ""
    occupation: str = ""
    bio: str = ""
    avatar: Optional[Any] = None
    last_seen: Optional[datetime] = None
    date_joined: Optional[datetime] = None
    preferred_give_currency: str = ""
    preferred_want_currency: str = ""
    password: Optional[str] = None
    
    security: Optional[UserSecurityEntity] = None
    identity_document: Optional[IdentityDocumentEntity] = None

    def is_kyc_complete(self) -> bool:
        return self.verification_status == 'approved'

    def update_last_seen(self):
        self.last_seen = datetime.now()


@dataclass
class ReportEntity:
    id: uuid.UUID
    reporter_id: uuid.UUID
    reported_to_id: uuid.UUID
    room_id: Optional[uuid.UUID]
    reason: str
    status: str
    admin_notes: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

