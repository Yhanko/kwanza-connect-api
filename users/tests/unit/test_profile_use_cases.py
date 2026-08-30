import pytest
import uuid
from unittest.mock import Mock, patch
from rest_framework.exceptions import NotFound, ValidationError

from users.services.use_cases import UpdateProfileUseCase, SubmitKYCUseCase
from users.domain.entities import UserEntity, IdentityDocumentEntity
from users.domain.interfaces import IUserRepository
from app.services.storage import IStorageService

@patch('users.services.use_cases.NotificationService.notify_admins')
def test_update_profile_success(mock_notify):
    mock_repo = Mock(spec=IUserRepository)
    mock_storage = Mock(spec=IStorageService)
    
    user_id = uuid.uuid4()
    user = UserEntity(id=user_id, email="test@example.com", full_name="Old Name")
    mock_repo.get_by_id.return_value = user
    
    # Simula return no save
    mock_repo.save.side_effect = lambda u: u
    
    use_case = UpdateProfileUseCase(repository=mock_repo, storage_service=mock_storage)
    
    updated_user = use_case.execute(user_id, full_name="New Name", city="Luanda")
    
    assert updated_user.full_name == "New Name"
    assert updated_user.city == "Luanda"
    mock_repo.save.assert_called_once_with(user)
    mock_notify.assert_called_once()

def test_update_profile_user_not_found():
    mock_repo = Mock(spec=IUserRepository)
    mock_repo.get_by_id.return_value = None
    
    use_case = UpdateProfileUseCase(repository=mock_repo)
    
    with pytest.raises(NotFound) as exc:
        use_case.execute(uuid.uuid4(), full_name="New Name")
    assert "Utilizador não encontrado" in str(exc.value)

@patch('users.services.use_cases.NotificationService.notify_admins')
def test_submit_kyc_success_new_doc(mock_notify):
    mock_repo = Mock(spec=IUserRepository)
    user_id = uuid.uuid4()
    user = UserEntity(id=user_id, email="test@example.com", full_name="Test", verification_status='unverified')
    
    mock_repo.get_by_id.return_value = user
    mock_repo.get_kyc_document_by_user_id.return_value = None
    
    use_case = SubmitKYCUseCase(repository=mock_repo)
    
    doc_data = {
        'doc_type': 'bi',
        'doc_number': '002367037LA033',
        'front_image': 'url_front',
        'back_image': 'url_back'
    }
    
    use_case.execute(user_id, doc_data)
    
    mock_repo.save_kyc_document.assert_called_once()
    saved_doc = mock_repo.save_kyc_document.call_args[0][0]
    assert saved_doc.doc_type == 'bi'
    assert saved_doc.doc_number == '002367037LA033'
    assert saved_doc.status == 'pending'
    
    assert user.verification_status == 'submitted'
    mock_repo.save.assert_called_once_with(user)
    mock_notify.assert_called_once()

def test_submit_kyc_already_approved():
    mock_repo = Mock(spec=IUserRepository)
    user_id = uuid.uuid4()
    user = UserEntity(id=user_id, email="test@example.com", full_name="Test", verification_status='approved')
    
    mock_repo.get_by_id.return_value = user
    
    use_case = SubmitKYCUseCase(repository=mock_repo)
    
    with pytest.raises(ValidationError) as exc:
        use_case.execute(user_id, {'doc_type': 'bi'})
    
    assert "não podem ser reenviados" in str(exc.value)
