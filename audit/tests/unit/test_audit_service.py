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
    """Testa o helper global mockando o use case interno."""
    mock_request = MagicMock()
    mock_request.META = {
        'REMOTE_ADDR': '192.168.1.1',
        'HTTP_USER_AGENT': 'Mozilla/5.0'
    }
    mock_request.user.is_authenticated = True
    mock_request.user.id = uuid.uuid4()
    
    audit_log(
        action='LOGIN_TEST',
        resource='auth',
        request=mock_request
    )
    
    # Verifica se o use case foi chamado com os dados extraídos do request
    mock_execute.assert_called_once()
    kwargs = mock_execute.call_args[1]
    assert kwargs['action'] == 'LOGIN_TEST'
    assert kwargs['ip_address'] == '192.168.1.1'
    assert kwargs['user_agent'] == 'Mozilla/5.0'
    assert kwargs['user_id'] == mock_request.user.id
