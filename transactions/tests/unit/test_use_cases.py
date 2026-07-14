import pytest
import uuid
from unittest.mock import Mock, patch
from decimal import Decimal
from rest_framework.exceptions import ValidationError, PermissionDenied

from transactions.services.use_cases import (
    ConfirmDealUseCase, ListUserTransactionsUseCase, 
    RateTransactionUseCase, ListUserReviewsUseCase,
    IOfferService, IChatService, INotificationService
)
from transactions.domain.entities import TransactionEntity, TransactionReviewEntity
from transactions.domain.interfaces import ITransactionRepository

@patch('django.db.transaction.atomic')
def test_confirm_deal_success(mock_atomic):
    # Arrange
    mock_repo = Mock(spec=ITransactionRepository)
    mock_offer_service = Mock(spec=IOfferService)
    mock_chat_service = Mock(spec=IChatService)
    mock_notif_service = Mock(spec=INotificationService)
    
    offer_id = uuid.uuid4()
    room_id = uuid.uuid4()
    user_id = uuid.uuid4()
    buyer_id = uuid.uuid4()
    
    mock_offer_service.get_offer_details.return_value = {
        'id': offer_id,
        'owner_id': user_id,
        'give_currency_id': uuid.uuid4(),
        'give_amount': Decimal("100"),
        'want_currency_id': uuid.uuid4(),
        'want_amount': Decimal("10"),
        'exchange_rate_snapshot': Decimal("0.1")
    }
    mock_chat_service.verify_room_offer.return_value = True
    mock_chat_service.get_other_participant.return_value = buyer_id
    
    mock_repo.save_transaction.side_effect = lambda tx: tx
    
    use_case = ConfirmDealUseCase(mock_repo, mock_offer_service, mock_chat_service, mock_notif_service)
    
    # Act
    tx = use_case.execute(user_id=user_id, offer_id=offer_id, room_id=room_id)
    
    # Assert
    assert tx.seller_id == user_id
    assert tx.buyer_id == buyer_id
    assert tx.status == 'completed'
    mock_repo.save_transaction.assert_called_once()
    mock_offer_service.close_offer.assert_called_once_with(offer_id)
    mock_chat_service.close_room.assert_called_once_with(room_id)
    mock_notif_service.notify_transaction_completed.assert_called_once_with(buyer_id, user_id, tx.id)

@patch('django.db.transaction.atomic')
def test_confirm_deal_invalid_room(mock_atomic):
    mock_repo = Mock(spec=ITransactionRepository)
    mock_offer = Mock(spec=IOfferService)
    mock_chat = Mock(spec=IChatService)
    mock_notif = Mock(spec=INotificationService)
    
    user_id = uuid.uuid4()
    mock_offer.get_offer_details.return_value = {'owner_id': user_id}
    mock_chat.verify_room_offer.return_value = False
    
    use_case = ConfirmDealUseCase(mock_repo, mock_offer, mock_chat, mock_notif)
    
    with pytest.raises(ValidationError) as exc:
        use_case.execute(user_id, uuid.uuid4(), uuid.uuid4())
    assert "associada a esta oferta" in str(exc.value)

def test_rate_transaction_success():
    mock_repo = Mock(spec=ITransactionRepository)
    mock_notif = Mock(spec=INotificationService)
    
    reviewer_id = uuid.uuid4()
    reviewed_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    
    tx = TransactionEntity(
        id=tx_id, offer_id=uuid.uuid4(), room_id=uuid.uuid4(),
        seller_id=reviewer_id, buyer_id=reviewed_id,
        give_currency_id=uuid.uuid4(), give_amount=Decimal('100'),
        want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        rate=Decimal('1'), status='completed'
    )
    
    mock_repo.get_transaction_by_id.return_value = tx
    mock_repo.get_review_by_transaction_and_user.return_value = None
    mock_repo.save_review.side_effect = lambda r: r
    
    use_case = RateTransactionUseCase(mock_repo, mock_notif)
    review = use_case.execute(reviewer_id, tx_id, 5, "Great")
    
    assert review.reviewer_id == reviewer_id
    assert review.reviewed_id == reviewed_id
    assert review.rating == 5
    mock_repo.save_review.assert_called_once()
    mock_notif.notify_new_review.assert_called_once_with(reviewed_id, reviewer_id, 5)

def test_rate_transaction_not_participant():
    mock_repo = Mock(spec=ITransactionRepository)
    tx = TransactionEntity(
        id=uuid.uuid4(), offer_id=uuid.uuid4(), room_id=uuid.uuid4(),
        seller_id=uuid.uuid4(), buyer_id=uuid.uuid4(),
        give_currency_id=uuid.uuid4(), give_amount=Decimal('100'),
        want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        rate=Decimal('1'), status='completed'
    )
    mock_repo.get_transaction_by_id.return_value = tx
    
    use_case = RateTransactionUseCase(mock_repo, Mock(spec=INotificationService))
    with pytest.raises(PermissionDenied):
        use_case.execute(uuid.uuid4(), tx.id, 5)

def test_list_user_transactions():
    mock_repo = Mock(spec=ITransactionRepository)
    use_case = ListUserTransactionsUseCase(mock_repo)
    user_id = uuid.uuid4()
    
    use_case.execute(user_id)
    mock_repo.list_user_transactions.assert_called_once_with(user_id)

def test_list_user_reviews():
    mock_repo = Mock(spec=ITransactionRepository)
    use_case = ListUserReviewsUseCase(mock_repo)
    user_id = uuid.uuid4()
    
    use_case.execute(user_id)
    mock_repo.list_user_reviews_received.assert_called_once_with(user_id)
