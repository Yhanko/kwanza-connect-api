import pytest
import uuid
from unittest.mock import Mock, patch
from rest_framework.exceptions import ValidationError

from users.services.use_cases import ForgotPasswordUseCase, ResetPasswordUseCase
from users.domain.entities import UserEntity, UserSecurityEntity
from users.domain.interfaces import IUserRepository

def test_forgot_password_success():
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    user_id = uuid.uuid4()
    user = UserEntity(id=user_id, email="test@example.com", full_name="Test User")
    mock_repo.get_by_email.return_value = user
    
    use_case = ForgotPasswordUseCase(mock_repo)
    
    # Act & Assert
    try:
        use_case.execute("test@example.com")
    except Exception as e:
        pytest.fail(f"execute() raised {type(e).__name__} unexpectedly!")

def test_forgot_password_user_not_found():
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    mock_repo.get_by_email.return_value = None
    
    use_case = ForgotPasswordUseCase(mock_repo)
    
    # Act & Assert
    with pytest.raises(ValidationError):
        use_case.execute("notfound@example.com")


def test_reset_password_success():
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    user_id = uuid.uuid4()
    user = UserEntity(id=user_id, email="test@example.com", full_name="Test User")
    
    mock_repo.get_by_email.return_value = user
    security = UserSecurityEntity(id=uuid.uuid4(), user_id=user_id)
    mock_repo.get_security_by_user_id.return_value = security
    
    use_case = ResetPasswordUseCase(mock_repo)
    
    # Act
    with patch('users.models.User.objects.get') as mock_get:
        mock_django_user = Mock()
        mock_get.return_value = mock_django_user
        
        use_case.execute("test@example.com", "new_password_123")
        
        # Assert
        mock_django_user.set_password.assert_called_once_with("new_password_123")
        mock_django_user.save.assert_called_once_with(update_fields=['password'])
        mock_repo.update_security.assert_called_once_with(security)
        assert security.password_changed_at is not None

def test_reset_password_user_not_found():
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    mock_repo.get_by_email.return_value = None
    
    use_case = ResetPasswordUseCase(mock_repo)
    
    # Act & Assert
    with pytest.raises(ValidationError):
        use_case.execute("notfound@example.com", "new_password_123")
