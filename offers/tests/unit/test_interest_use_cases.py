import pytest
import uuid
from unittest.mock import Mock, patch
from decimal import Decimal
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from offers.services.use_cases import (
    ExpressInterestUseCase, AcceptInterestUseCase, 
    RejectInterestUseCase, CancelInterestUseCase,
    IChatService, INotificationService
)
from offers.domain.entities import OfferEntity, OfferInterestEntity
from offers.domain.interfaces import IOfferRepository

@patch('django.db.transaction.atomic')
def test_express_interest_success(mock_atomic):
    mock_repo = Mock(spec=IOfferRepository)
    offer_id = uuid.uuid4()
    buyer_id = uuid.uuid4()
    
    offer = OfferEntity(
        id=offer_id, owner_id=uuid.uuid4(), give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='active'
    )
    
    mock_repo.get_offer_by_id_for_update.return_value = offer
    mock_repo.get_interest_by_offer_and_buyer.return_value = None
    mock_repo.save_interest.side_effect = lambda i: i
    
    use_case = ExpressInterestUseCase(repository=mock_repo)
    interest = use_case.execute(buyer_id, offer_id, "Hello")
    
    assert interest.offer_id == offer_id
    assert interest.buyer_id == buyer_id
    assert interest.message == "Hello"
    mock_repo.save_interest.assert_called_once()

@patch('django.db.transaction.atomic')
def test_express_interest_own_offer(mock_atomic):
    mock_repo = Mock(spec=IOfferRepository)
    user_id = uuid.uuid4()
    offer = OfferEntity(
        id=uuid.uuid4(), owner_id=user_id, give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='active'
    )
    mock_repo.get_offer_by_id_for_update.return_value = offer
    
    use_case = ExpressInterestUseCase(repository=mock_repo)
    with pytest.raises(ValidationError) as exc:
        use_case.execute(user_id, offer.id)
    assert "própria oferta" in str(exc.value)

@patch('django.db.transaction.atomic')
def test_accept_interest_success(mock_atomic):
    mock_repo = Mock(spec=IOfferRepository)
    mock_chat = Mock(spec=IChatService)
    mock_notif = Mock(spec=INotificationService)
    
    owner_id = uuid.uuid4()
    buyer_id = uuid.uuid4()
    offer_id = uuid.uuid4()
    interest_id = uuid.uuid4()
    room_id = uuid.uuid4()
    
    offer = OfferEntity(
        id=offer_id, owner_id=owner_id, give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='active'
    )
    interest = OfferInterestEntity(
        id=interest_id, offer_id=offer_id, buyer_id=buyer_id, status='pending'
    )
    
    mock_repo.get_interest_by_id_for_update.return_value = interest
    mock_repo.get_offer_by_id_for_update.return_value = offer
    mock_chat.create_offer_room.return_value = room_id
    
    use_case = AcceptInterestUseCase(mock_repo, mock_chat, mock_notif)
    returned_room_id = use_case.execute(owner_id, interest_id)
    
    assert returned_room_id == room_id
    assert interest.status == 'chat_open'
    assert interest.room_id == room_id
    assert offer.status == 'dealing'
    
    mock_repo.save_interest.assert_called_once_with(interest)
    mock_repo.save_offer.assert_called_once_with(offer)
    mock_notif.notify_interest_accepted.assert_called_once_with(buyer_id, offer_id, room_id)

def test_reject_interest_success():
    mock_repo = Mock(spec=IOfferRepository)
    mock_notif = Mock(spec=INotificationService)
    
    owner_id = uuid.uuid4()
    offer = OfferEntity(
        id=uuid.uuid4(), owner_id=owner_id, give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='active'
    )
    interest = OfferInterestEntity(
        id=uuid.uuid4(), offer_id=offer.id, buyer_id=uuid.uuid4(), status='pending'
    )
    
    mock_repo.get_interest_by_id.return_value = interest
    mock_repo.get_offer_by_id.return_value = offer
    
    use_case = RejectInterestUseCase(mock_repo, mock_notif)
    use_case.execute(owner_id, interest.id)
    
    assert interest.status == 'rejected'
    mock_repo.save_interest.assert_called_once_with(interest)
    mock_notif.notify_interest_rejected.assert_called_once_with(interest.buyer_id, offer.id)

def test_cancel_interest_success():
    mock_repo = Mock(spec=IOfferRepository)
    buyer_id = uuid.uuid4()
    interest = OfferInterestEntity(
        id=uuid.uuid4(), offer_id=uuid.uuid4(), buyer_id=buyer_id, status='pending'
    )
    
    mock_repo.get_interest_by_id.return_value = interest
    
    use_case = CancelInterestUseCase(repository=mock_repo)
    use_case.execute(buyer_id, interest.id)
    
    assert interest.status == 'cancelled'
    mock_repo.save_interest.assert_called_once_with(interest)
