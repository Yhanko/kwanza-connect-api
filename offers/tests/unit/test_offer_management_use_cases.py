import pytest
import uuid
from unittest.mock import Mock
from decimal import Decimal
from rest_framework.exceptions import ValidationError, NotFound

from offers.services.use_cases import (
    CreateOfferUseCase, ListOffersUseCase, GetOfferUseCase, 
    PauseOfferUseCase, ResumeOfferUseCase, CloseOfferUseCase
)
from offers.domain.entities import OfferEntity, CurrencyEntity
from offers.domain.interfaces import IOfferRepository

def test_create_offer_validation_error():
    mock_repo = Mock(spec=IOfferRepository)
    use_case = CreateOfferUseCase(repository=mock_repo)
    
    # Missing currencies
    with pytest.raises(ValidationError):
        use_case.execute(uuid.uuid4(), {'give_amount': 100})
        
    # Same currency
    with pytest.raises(ValidationError):
        use_case.execute(uuid.uuid4(), {'give_currency_code': 'AOA', 'want_currency_code': 'AOA'})

def test_pause_offer_success():
    mock_repo = Mock(spec=IOfferRepository)
    user_id = uuid.uuid4()
    offer = OfferEntity(
        id=uuid.uuid4(), owner_id=user_id, give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='active'
    )
    mock_repo.get_offer_by_id.return_value = offer
    mock_repo.save_offer.side_effect = lambda o: o
    
    use_case = PauseOfferUseCase(repository=mock_repo)
    paused_offer = use_case.execute(user_id, offer.id)
    
    assert paused_offer.status == 'paused'
    mock_repo.save_offer.assert_called_once_with(offer)

def test_pause_offer_not_owner():
    mock_repo = Mock(spec=IOfferRepository)
    offer = OfferEntity(
        id=uuid.uuid4(), owner_id=uuid.uuid4(), give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='active'
    )
    mock_repo.get_offer_by_id.return_value = offer
    
    use_case = PauseOfferUseCase(repository=mock_repo)
    with pytest.raises(NotFound):
        use_case.execute(uuid.uuid4(), offer.id)  # Different user id

def test_resume_offer_success():
    mock_repo = Mock(spec=IOfferRepository)
    user_id = uuid.uuid4()
    offer = OfferEntity(
        id=uuid.uuid4(), owner_id=user_id, give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='paused'
    )
    mock_repo.get_offer_by_id.return_value = offer
    mock_repo.save_offer.side_effect = lambda o: o
    
    use_case = ResumeOfferUseCase(repository=mock_repo)
    resumed_offer = use_case.execute(user_id, offer.id)
    
    assert resumed_offer.status == 'active'

def test_close_offer_success():
    mock_repo = Mock(spec=IOfferRepository)
    user_id = uuid.uuid4()
    offer = OfferEntity(
        id=uuid.uuid4(), owner_id=user_id, give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', status='active'
    )
    mock_repo.get_offer_by_id.return_value = offer
    
    use_case = CloseOfferUseCase(repository=mock_repo)
    use_case.execute(user_id, offer.id)
    
    assert offer.status == 'closed'
    mock_repo.save_offer.assert_called_once_with(offer)

def test_get_offer_with_view_increment():
    mock_repo = Mock(spec=IOfferRepository)
    owner_id = uuid.uuid4()
    viewer_id = uuid.uuid4()
    offer_id = uuid.uuid4()
    offer = OfferEntity(
        id=offer_id, owner_id=owner_id, give_currency_id=uuid.uuid4(), 
        give_amount=Decimal('100'), want_currency_id=uuid.uuid4(), want_amount=Decimal('100'),
        exchange_rate_snapshot=Decimal('1'), offer_type='sell', views_count=0
    )
    mock_repo.get_offer_by_id.return_value = offer
    
    use_case = GetOfferUseCase(repository=mock_repo)
    retrieved = use_case.execute(offer_id, viewer_id)
    
    assert retrieved.views_count == 1
    mock_repo.register_offer_view.assert_called_once_with(offer_id, viewer_id)
    mock_repo.increment_offer_views.assert_called_once_with(offer_id)
