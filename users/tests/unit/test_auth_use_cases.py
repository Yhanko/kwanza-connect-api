import pytest
import uuid
from unittest.mock import Mock, patch
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from users.services.use_cases import LoginUseCase, VerifyEmailUseCase, ChangePasswordUseCase
from users.domain.entities import UserEntity, UserSecurityEntity
from users.domain.interfaces import IUserRepository
from audit.domain.interfaces import IAuditRepository

def test_login_success():
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    mock_audit = Mock(spec=IAuditRepository)
    
    user_id = uuid.uuid4()
    user = UserEntity(id=user_id, email="test@example.com", full_name="Test User", is_active=True)
    security = UserSecurityEntity(id=uuid.uuid4(), user_id=user_id)
    
    mock_repo.get_by_email.return_value = user
    mock_repo.get_security_by_user_id.return_value = security
    
    use_case = LoginUseCase(repository=mock_repo, audit_repo=mock_audit)
    
    # Act & Assert
    with patch('django.contrib.auth.authenticate') as mock_auth:
        with patch('rest_framework_simplejwt.tokens.RefreshToken.for_user') as mock_token:
            mock_django_user = Mock()
            mock_auth.return_value = mock_django_user
            
            mock_refresh = Mock()
            mock_refresh.access_token = "access_token_123"
            mock_refresh.__str__ = Mock(return_value="refresh_token_123")
            mock_token.return_value = mock_refresh
            
            result = use_case.execute("test@example.com", "password123")
            
            assert result['access'] == "access_token_123"
            assert result['refresh'] == "refresh_token_123"
            
            assert security.failed_login_attempts == 0
            assert security.locked_until is None
            mock_repo.update_security.assert_called_once_with(security)
            mock_repo.save.assert_called_once_with(user)

def test_login_invalid_credentials():
    mock_repo = Mock(spec=IUserRepository)
    mock_audit = Mock(spec=IAuditRepository)
    mock_repo.get_by_email.return_value = None
    
    use_case = LoginUseCase(repository=mock_repo, audit_repo=mock_audit)
    
    with pytest.raises(AuthenticationFailed) as exc:
        use_case.execute("test@example.com", "wrong")
    assert "Credenciais inválidas" in str(exc.value)

def test_verify_email_success():
    mock_repo = Mock(spec=IUserRepository)
    
    security = UserSecurityEntity(id=uuid.uuid4(), user_id=uuid.uuid4(), email_verified=False)
    user = UserEntity(id=security.user_id, email="test@example.com", full_name="Test", is_active=False)
    
    mock_repo.get_security_by_email_token.return_value = security
    mock_repo.get_by_id.return_value = user
    
    use_case = VerifyEmailUseCase(repository=mock_repo)
    
    use_case.execute("valid_token")
    
    assert security.email_verified is True
    assert security.email_token == ''
    assert security.email_verified_at is not None
    mock_repo.update_security.assert_called_once_with(security)
    
    assert user.is_active is True
    mock_repo.save.assert_called_once_with(user)

def test_verify_email_already_verified():
    mock_repo = Mock(spec=IUserRepository)
    
    security = UserSecurityEntity(id=uuid.uuid4(), user_id=uuid.uuid4(), email_verified=True)
    mock_repo.get_security_by_email_token.return_value = security
    
    use_case = VerifyEmailUseCase(repository=mock_repo)
    
    with pytest.raises(ValidationError) as exc:
        use_case.execute("valid_token")
    assert "já foi verificado" in str(exc.value)

def test_change_password_success():
    mock_repo = Mock(spec=IUserRepository)
    user_id = uuid.uuid4()
    security = UserSecurityEntity(id=uuid.uuid4(), user_id=user_id)
    mock_repo.get_security_by_user_id.return_value = security
    
    use_case = ChangePasswordUseCase(repository=mock_repo)
    
    with patch('users.models.User.objects.get') as mock_get:
        mock_django_user = Mock()
        mock_django_user.check_password.return_value = True
        mock_get.return_value = mock_django_user
        
        use_case.execute(user_id, "old_pass", "new_pass")
        
        mock_django_user.set_password.assert_called_once_with("new_pass")
        mock_django_user.save.assert_called_once_with(update_fields=['password'])
        assert security.password_changed_at is not None
        mock_repo.update_security.assert_called_once_with(security)

def test_change_password_wrong_current():
    mock_repo = Mock(spec=IUserRepository)
    user_id = uuid.uuid4()
    
    use_case = ChangePasswordUseCase(repository=mock_repo)
    
    with patch('users.models.User.objects.get') as mock_get:
        mock_django_user = Mock()
        mock_django_user.check_password.return_value = False
        mock_get.return_value = mock_django_user
        
        with pytest.raises(ValidationError) as exc:
            use_case.execute(user_id, "wrong_pass", "new_pass")
        assert "Senha actual incorrecta" in str(exc.value)
