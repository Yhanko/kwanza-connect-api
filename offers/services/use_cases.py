"""
Use cases do módulo offers.
Orquestra repositórios e lógica de negócio operando sobre Entidades.
"""
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied


from ..domain.entities import OfferEntity, OfferInterestEntity, CurrencyEntity
from ..domain.interfaces import IOfferRepository

class IChatService(ABC):
    @abstractmethod
    def create_offer_room(self, offer_id: uuid.UUID, owner_id: uuid.UUID, buyer_id: uuid.UUID) -> uuid.UUID:
        pass

class INotificationService(ABC):
    @abstractmethod
    def notify_interest_accepted(self, buyer_id: uuid.UUID, offer_id: uuid.UUID, room_id: uuid.UUID) -> None:
        pass
    
    @abstractmethod
    def notify_interest_rejected(self, buyer_id: uuid.UUID, offer_id: uuid.UUID) -> None:
        pass

class CreateOfferUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID, data: dict) -> OfferEntity:
        give_code = data.get('give_currency_code')
        want_code = data.get('want_currency_code')

        if not give_code or not want_code:
            raise ValidationError('Moedas de origem e destino são obrigatórias.')
        if give_code == want_code:
            raise ValidationError('As moedas de origem e destino não podem ser iguais.')

        give_currency = self.repository.get_currency_by_code(give_code)
        want_currency = self.repository.get_currency_by_code(want_code)

        if not give_currency or not want_currency:
            raise ValidationError('Moeda inválida ou não suportada.')

        # Snapshot da taxa real
        rate_obj = self.repository.get_exchange_rate(give_currency.id, want_currency.id)
        rate_snapshot = rate_obj.rate if rate_obj else Decimal('0.0')

        # Validação regulatória de Prevenção ao Branqueamento de Capitais (PCBC/FT & Tiers de KYC BNA)
        try:
            from security.services.aml_engine import AMLEngine
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_obj = User.objects.filter(id=user_id).first()
            if user_obj:
                give_amount_dec = Decimal(str(data['give_amount']))
                amount_aoa = AMLEngine.convert_to_aoa(give_amount_dec, give_code, rate_snapshot)
                aml_result = AMLEngine.evaluate_transaction_risk(
                    user=user_obj,
                    amount_aoa=amount_aoa,
                    currency_code=give_code,
                    rate_snapshot=rate_snapshot
                )
                if aml_result.is_blocked:
                    raise ValidationError({'detail': aml_result.block_reason})
        except ValidationError:
            raise
        except Exception:
            pass

        offer = OfferEntity(
            id=uuid.uuid4(),
            owner_id=user_id,
            give_currency_id=give_currency.id,
            give_amount=Decimal(str(data['give_amount'])),
            want_currency_id=want_currency.id,
            want_amount=Decimal(str(data['want_amount'])),
            exchange_rate_snapshot=rate_snapshot,
            payment_methods=data.get('payment_methods', []),
            offer_type=data.get('offer_type', 'sell'),
            notes=data.get('notes', ''),
            city=data.get('city', ''),
            country_code=data.get('country_code', ''),
            latitude=data.get('latitude', None),
            longitude=data.get('longitude', None),
            expires_at=data.get('expires_at'),
        )
        
        return self.repository.save_offer(offer)

class ListOffersUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, filters: dict) -> List[OfferEntity]:
        return self.repository.list_offers(filters)

class GetOfferUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, offer_id: uuid.UUID, viewer_id: Optional[uuid.UUID] = None) -> OfferEntity:
        offer = self.repository.get_offer_by_id(offer_id)
        if not offer:
            raise NotFound('Oferta não encontrada.')

        # Regista visualização
        if viewer_id and viewer_id != offer.owner_id:
            self.repository.register_offer_view(offer_id, viewer_id)
            self.repository.increment_offer_views(offer_id)
            offer.views_count += 1

        return offer

class PauseOfferUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID, offer_id: uuid.UUID) -> OfferEntity:
        offer = self.repository.get_offer_by_id(offer_id)
        if not offer or offer.owner_id != user_id:
            raise NotFound('Oferta não encontrada ou não pertence ao utilizador.')
            
        if offer.status != 'active':
            raise ValidationError('Só é possível pausar ofertas activas.')
            
        offer.status = 'paused'
        return self.repository.save_offer(offer)

class ResumeOfferUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID, offer_id: uuid.UUID) -> OfferEntity:
        offer = self.repository.get_offer_by_id(offer_id)
        if not offer or offer.owner_id != user_id:
            raise NotFound('Oferta não encontrada ou não pertence ao utilizador.')
            
        if offer.status != 'paused':
            raise ValidationError('Só é possível retomar ofertas pausadas.')
            
        offer.status = 'active'
        return self.repository.save_offer(offer)

class CloseOfferUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID, offer_id: uuid.UUID) -> None:
        offer = self.repository.get_offer_by_id(offer_id)
        if not offer or offer.owner_id != user_id:
            raise NotFound('Oferta não encontrada ou não pertence ao utilizador.')
        offer.status = 'closed'
        self.repository.save_offer(offer)

class AcceptInterestUseCase:
    def __init__(self, repository: IOfferRepository, chat_service: IChatService, notification_service: INotificationService):
        self.repository = repository
        self.chat_service = chat_service
        self.notification_service = notification_service

    def execute(self, user_id: uuid.UUID, interest_id: uuid.UUID) -> uuid.UUID:
        with transaction.atomic():
            interest = self.repository.get_interest_by_id_for_update(interest_id)
            if not interest:
                 raise NotFound('Interesse não encontrado.')
                 
            offer = self.repository.get_offer_by_id_for_update(interest.offer_id)
            if not offer or offer.owner_id != user_id:
                raise PermissionDenied('Apenas o dono da oferta pode aceitar interesses.')

            if interest.status != 'pending':
                raise ValidationError('Só é possível aceitar interesses pendentes.')
            
            if offer.status != 'active':
                raise ValidationError('Esta oferta já não está disponível para negociação.')

            # Orquestração
            room_id = self.chat_service.create_offer_room(offer.id, offer.owner_id, interest.buyer_id)
            
            interest.status = 'chat_open'
            interest.room_id = room_id
            interest.responded_at = timezone.now()

            self.repository.save_interest(interest)

            offer.status = 'dealing'
            self.repository.save_offer(offer)

            self.notification_service.notify_interest_accepted(interest.buyer_id, offer.id, room_id)
            
            return room_id

class RejectInterestUseCase:
    def __init__(self, repository: IOfferRepository, notification_service: INotificationService):
        self.repository = repository
        self.notification_service = notification_service

    def execute(self, user_id: uuid.UUID, interest_id: uuid.UUID) -> None:
        interest = self.repository.get_interest_by_id(interest_id)
        if not interest:
             raise NotFound('Interesse não encontrado.')

        offer = self.repository.get_offer_by_id(interest.offer_id)
        if not offer or offer.owner_id != user_id:
             raise PermissionDenied('Apenas o dono da oferta pode rejeitar interesses.')

        if interest.status != 'pending':
            raise ValidationError('Só é possível rejeitar interesses pendentes.')

        interest.status = 'rejected'
        interest.responded_at = datetime.now()
        self.repository.save_interest(interest)

        self.notification_service.notify_interest_rejected(interest.buyer_id, offer.id)

class CancelInterestUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID, interest_id: uuid.UUID) -> None:
        interest = self.repository.get_interest_by_id(interest_id)
        if not interest or interest.buyer_id != user_id:
            raise NotFound('Interesse não encontrado ou não pertence ao utilizador.')

        if interest.status != 'pending':
            raise ValidationError('Só podes cancelar um interesse pendente.')

        interest.status = 'cancelled'
        self.repository.save_interest(interest)

class ExpressInterestUseCase:
    def __init__(self, repository: IOfferRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID, offer_id: uuid.UUID, message: str = '') -> OfferInterestEntity:
        with transaction.atomic():
            # Bloqueia a oferta para verificar disponibilidade de forma segura
            offer = self.repository.get_offer_by_id_for_update(offer_id)
            if not offer:
                raise NotFound('Oferta não encontrada.')

            if offer.owner_id == user_id:
                raise ValidationError('Não pode demonstrar interesse na sua própria oferta.')
            if not offer.is_active:
                raise ValidationError('Esta oferta já não está disponível.')
            
            existing = self.repository.get_interest_by_offer_and_buyer(offer_id, user_id)
            if existing:
                raise ValidationError('Já demonstrou interesse nesta oferta.')

            interest = OfferInterestEntity(
                id=uuid.uuid4(),
                offer_id=offer_id,
                buyer_id=user_id,
                message=message,
            )
            return self.repository.save_interest(interest)
