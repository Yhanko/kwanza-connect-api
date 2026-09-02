import pytest
import uuid
from unittest.mock import Mock, patch
from users.services.use_cases import RegisterUserUseCase
from users.domain.entities import UserEntity
from users.domain.interfaces import IUserRepository

@patch('users.services.use_cases.NotificationService.notify_admins')
def test_register_user_success(mock_notify):
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    mock_repo.exists_by_email.return_value = False
    mock_repo.exists_by_username.return_value = False
    
    def side_effect_save(user):
        return user
    mock_repo.save.side_effect = side_effect_save
    mock_repo.get_security_by_user_id.return_value = None
    mock_audit_repo = Mock()
    
    use_case = RegisterUserUseCase(repository=mock_repo, audit_repo=mock_audit_repo)
    email = "test@example.com"
    password = "KwanzaPass@2026Secure"
    full_name = "Test User"

    
    # Act
    result = use_case.execute(email=email, password=password, full_name=full_name)
    
    # Assert
    assert result['email'] == email
    assert 'id' in result
    mock_repo.exists_by_email.assert_called_once_with(email)
    mock_repo.save.assert_called()
    mock_repo.update_security.assert_called_once()
    mock_notify.assert_called_once()

def test_register_user_already_exists():
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    mock_repo.exists_by_email.return_value = True
    
    mock_audit_repo = Mock()
    use_case = RegisterUserUseCase(repository=mock_repo, audit_repo=mock_audit_repo)
    
    # Act & Assert
    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError):
        use_case.execute(email="existing@example.com", password="pwd", full_name="Name")
