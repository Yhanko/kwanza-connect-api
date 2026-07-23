from abc import ABC, abstractmethod
from typing import Optional, List
from .entities import UserEntity, UserSecurityEntity, IdentityDocumentEntity
import uuid

class IUserRepository(ABC):
    
    @abstractmethod
    def get_by_id(self, user_id: uuid.UUID) -> Optional[UserEntity]:
        pass
    
    @abstractmethod
    def search_users(self, filters: dict) -> List[UserEntity]:
        pass
        
    @abstractmethod
    def save_report(self, report: 'ReportEntity') -> 'ReportEntity':
        pass

    
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[UserEntity]:
        pass
    
    @abstractmethod
    def save(self, user: UserEntity) -> UserEntity:
        pass
    
    @abstractmethod
    def exists_by_email(self, email: str) -> bool:
        pass

    @abstractmethod
    def update_security(self, security: UserSecurityEntity) -> None:
        pass

    @abstractmethod
    def get_security_by_user_id(self, user_id: uuid.UUID) -> Optional[UserSecurityEntity]:
        pass

    @abstractmethod
    def get_security_by_email_token(self, token: str) -> Optional[UserSecurityEntity]:
        pass

    @abstractmethod
    def get_security_by_reset_token(self, token: str) -> Optional[UserSecurityEntity]:
        pass

    @abstractmethod
    def save_kyc_document(self, document: IdentityDocumentEntity) -> None:
        pass
    
    @abstractmethod
    def get_kyc_document_by_user_id(self, user_id: uuid.UUID) -> Optional[IdentityDocumentEntity]:
        pass
