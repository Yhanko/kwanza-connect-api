"""
Use cases do módulo de transações.
Orquestra repositórios e lógica de negócio operando sobre Entidades.
"""
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from ..domain.entities import TransactionEntity, TransactionReviewEntity
from ..domain.interfaces import ITransactionRepository

class IOfferService(ABC):
    @abstractmethod
    def close_offer(self, offer_id: uuid.UUID) -> None:
        pass
    
    @abstractmethod
    def get_offer_details(self, offer_id: uuid.UUID) -> dict:
        pass

class IChatService(ABC):
    @abstractmethod
    def close_room(self, room_id: uuid.UUID) -> None:
        pass
    
    @abstractmethod
    def get_other_participant(self, room_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
        pass

    @abstractmethod
    def verify_room_offer(self, room_id: uuid.UUID, offer_id: uuid.UUID) -> bool:
        pass

class INotificationService(ABC):
    @abstractmethod
    def notify_transaction_completed(self, recipient_id: uuid.UUID, actor_id: uuid.UUID, tx_id: uuid.UUID) -> None:
        pass
    
    @abstractmethod
    def notify_new_review(self, recipient_id: uuid.UUID, actor_id: uuid.UUID, rating: int) -> None:
        pass

class ConfirmDealUseCase:
    def __init__(self, repository: ITransactionRepository, offer_service: IOfferService, chat_service: IChatService, notification_service: INotificationService):
        self.repository = repository
        self.offer_service = offer_service
        self.chat_service = chat_service
        self.notification_service = notification_service

    def execute(self, user_id: uuid.UUID, offer_id: uuid.UUID, room_id: uuid.UUID, notes: str = '') -> TransactionEntity:
        with transaction.atomic():
            # 1. Busca detalhes da oferta
            offer_data = self.offer_service.get_offer_details(offer_id)
            if not offer_data or offer_data['owner_id'] != user_id:
                raise NotFound('Oferta não encontrada ou não pertence ao utilizador.')

            # 2. Identifica o outro participante e valida a sala
            if not self.chat_service.verify_room_offer(room_id, offer_id):
                raise ValidationError('Esta sala de chat não está associada a esta oferta.')

            buyer_id = self.chat_service.get_other_participant(room_id, user_id)
            if not buyer_id:
                raise ValidationError('Não foi possível identificar o comprador nesta sala.')

            # Validação de conformidade PCBC/FT para o comprador
            try:
                from security.services.aml_engine import AMLEngine
                from django.contrib.auth import get_user_model
                User = get_user_model()
                buyer_obj = User.objects.filter(id=buyer_id).first()
                if buyer_obj:
                    want_amount_dec = Decimal(str(offer_data['want_amount']))
                    amount_aoa = AMLEngine.convert_to_aoa(want_amount_dec, 'AOA')
                    aml_buyer = AMLEngine.evaluate_transaction_risk(
                        user=buyer_obj,
                        amount_aoa=amount_aoa,
                        currency_code='AOA'
                    )
                    if aml_buyer.is_blocked:
                        raise ValidationError({'detail': f'Operação não permitida pelo compliance BNA: {aml_buyer.block_reason}'})
            except ValidationError:
                raise
            except Exception:
                pass

            # 3. Cria a transação
            tx = TransactionEntity(
                id=uuid.uuid4(),
                offer_id=offer_id,
                room_id=room_id,
                seller_id=user_id,
                buyer_id=buyer_id,
                give_currency_id=offer_data['give_currency_id'],
                give_amount=offer_data['give_amount'],
                want_currency_id=offer_data['want_currency_id'],
                want_amount=offer_data['want_amount'],
                rate=offer_data['exchange_rate_snapshot'],
                notes=notes,
                status='completed'
            )
            saved_tx = self.repository.save_transaction(tx)

            # 4. Encerra oferta e sala
            self.offer_service.close_offer(offer_id)
            self.chat_service.close_room(room_id)

            # 5. Notifica
            self.notification_service.notify_transaction_completed(buyer_id, user_id, saved_tx.id)

            return saved_tx

class ListUserTransactionsUseCase:
    def __init__(self, repository: ITransactionRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID) -> List[TransactionEntity]:
        return self.repository.list_user_transactions(user_id)

class RateTransactionUseCase:
    def __init__(self, repository: ITransactionRepository, notification_service: INotificationService):
        self.repository = repository
        self.notification_service = notification_service

    def execute(self, reviewer_id: uuid.UUID, transaction_id: uuid.UUID, rating: int, comment: str = '') -> TransactionReviewEntity:
        tx = self.repository.get_transaction_by_id(transaction_id)
        if not tx:
            raise NotFound('Transação não encontrada.')

        # Valida participantes
        if reviewer_id == tx.seller_id:
            reviewed_id = tx.buyer_id
        elif reviewer_id == tx.buyer_id:
            reviewed_id = tx.seller_id
        else:
            raise PermissionDenied('Apenas os participantes da transação podem avaliá-la.')

        existing = self.repository.get_review_by_transaction_and_user(transaction_id, reviewer_id)
        if existing:
             raise ValidationError('Já avaliou esta transação.')

        review = TransactionReviewEntity(
            id=uuid.uuid4(),
            transaction_id=transaction_id,
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            comment=comment
        )
        saved_review = self.repository.save_review(review)

        # Notifica receptor
        self.notification_service.notify_new_review(reviewed_id, reviewer_id, rating)

        return saved_review

class ListUserReviewsUseCase:
    def __init__(self, repository: ITransactionRepository):
        self.repository = repository

    def execute(self, user_id: uuid.UUID) -> List[TransactionReviewEntity]:
        return self.repository.list_user_reviews_received(user_id)
