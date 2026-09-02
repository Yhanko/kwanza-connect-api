# pyrefly: ignore [missing-import]
import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch
from audit.domain.entities import AuditLogEntity
from audit.services.use_cases import RegisterAuditLogUseCase
from app.audit_service import audit_log

def test_audit_log_entity_creation():
    """Testa a criação da entidade de log sem dependências."""
    user_id = uuid.uuid4()
    log = AuditLogEntity(
        id=None,
        user_id=user_id,
        action='TEST_ACTION',
        resource='test_resource'
    )
    assert log.action == 'TEST_ACTION'
    assert log.user_id == user_id
    assert isinstance(log.id, uuid.UUID)

def test_register_audit_log_use_case_logic():
    """Testa a lógica do caso de uso de auditoria com mock do repositório."""
    mock_repo = MagicMock()
    use_case = RegisterAuditLogUseCase(mock_repo)
    
    action = 'LOGIN'
    resource = 'users'
    user_id = uuid.uuid4()
    
    use_case.execute(action=action, resource=resource, user_id=user_id)
    
    # Verifica se o repositório foi chamado para salvar
    assert mock_repo.save.called
    saved_entity = mock_repo.save.call_args[0][0]
    assert saved_entity.action == action
    assert saved_entity.user_id == user_id

@patch('app.audit_service._audit_use_case.execute')
def test_audit_log_helper_integration(mock_execute):
    """Testa o helper global mockando o use case interno e extraindo dados ricos."""
    mock_request = MagicMock()
    mock_request.META = {
        'HTTP_X_FORWARDED_FOR': '197.234.10.5, 10.0.0.1',
        'HTTP_USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0)'
    }
    mock_request.user.is_authenticated = True
    mock_request.user.id = uuid.uuid4()
    mock_request.user.email = 'cliente@kwanzaconnect.ao'
    
    audit_log(
        action='LOGIN_SUCCESS',
        resource='auth',
        request=mock_request
    )
    
    # Verifica se o use case foi chamado com os dados extraídos do request
    mock_execute.assert_called_once()
    kwargs = mock_execute.call_args[1]
    assert kwargs['action'] == 'LOGIN_SUCCESS'
    assert kwargs['ip_address'] == '197.234.10.5'
    assert kwargs['user_agent'] == 'Mozilla/5.0 (Windows NT 10.0)'
    assert kwargs['user_id'] == mock_request.user.id
    assert kwargs['actor_email'] == 'cliente@kwanzaconnect.ao'
    assert kwargs['status'] == 'SUCCESS'
    assert kwargs['severity'] == 'INFO'

def test_audit_log_sanitization_and_masking():
    """Testa o mascaramento rigoroso de senhas, tokens e chaves de API nos metadados."""
    mock_repo = MagicMock()
    use_case = RegisterAuditLogUseCase(mock_repo)
    
    raw_metadata = {
        'email': 'teste@kwanza.ao',
        'password': 'MinhaSenhaUltraSecreta123!',
        'token': 'jwt_access_token_xyz',
        'api_key': 'kwanza_live_key_999'
    }
    
    use_case.execute(
        action='REGISTER_ATTEMPT',
        resource='users',
        metadata=raw_metadata
    )
    
    assert mock_repo.save.called
    saved_log = mock_repo.save.call_args[0][0]
    assert saved_log.metadata['email'] == 'teste@kwanza.ao'
    assert saved_log.metadata['password'] == '********'
    assert saved_log.metadata['token'] == '********'
    assert saved_log.metadata['api_key'] == '********'


@patch('audit.tasks.AuditLog.objects.filter')
def test_cleanup_old_audit_logs_retention_6_years(mock_filter):
    """Testa se a tarefa periódica de limpeza de logs filtra registos anteriores a 6 anos."""
    from datetime import timedelta
    from django.utils import timezone
    from audit.tasks import cleanup_old_audit_logs

    mock_queryset = MagicMock()
    mock_queryset.delete.return_value = (5, {})
    mock_filter.return_value = mock_queryset

    before_call = timezone.now() - timedelta(days=6 * 365)
    result = cleanup_old_audit_logs()
    after_call = timezone.now() - timedelta(days=6 * 365)

    assert result == "Apagados 5 logs."
    assert mock_filter.called
    called_kwargs = mock_filter.call_args[1]
    assert 'timestamp__lt' in called_kwargs
    cutoff_arg = called_kwargs['timestamp__lt']
    assert before_call <= cutoff_arg <= after_call
