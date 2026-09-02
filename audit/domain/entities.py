from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

@dataclass
class AuditLogEntity:
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str  # Ex: 'LOGIN', 'CREATE_OFFER', 'UPDATE_PROFILE'
    resource: str  # Ex: 'offers', 'users'
    resource_id: Optional[str] = None
    status: str = 'SUCCESS'  # 'SUCCESS', 'FAILURE', 'ATTEMPT', 'BLOCKED', 'PENDING'
    severity: str = 'INFO'  # 'INFO', 'WARNING', 'CRITICAL'
    actor_email: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.id is None:
            self.id = uuid.uuid4()
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if not self.status:
            self.status = 'SUCCESS'
        if not self.severity:
            self.severity = 'INFO'
