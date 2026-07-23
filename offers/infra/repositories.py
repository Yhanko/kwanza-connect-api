from typing import Optional, List
import uuid
from decimal import Decimal
from django.db import transaction, models
from django.utils import timezone
from ..models import (
    Currency as DjangoCurrency, 
    ExchangeRate as DjangoExchangeRate, 
    Offer as DjangoOffer, 
    OfferInterest as DjangoOfferInterest,
    OfferView as DjangoOfferView
)
from ..domain.entities import OfferEntity, OfferInterestEntity, CurrencyEntity, ExchangeRateEntity
from ..domain.interfaces import IOfferRepository

class DjangoOfferRepository(IOfferRepository):
    
    def _currency_to_entity(self, django_currency: DjangoCurrency) -> CurrencyEntity:
        return CurrencyEntity(
            id=django_currency.id,
            code=django_currency.code,
            name=django_currency.name,
            symbol=django_currency.symbol,
            flag_emoji=django_currency.flag_emoji,
            is_active=django_currency.is_active,
            sort_order=django_currency.sort_order
        )

    def _exchange_rate_to_entity(self, django_rate: DjangoExchangeRate) -> ExchangeRateEntity:
        return ExchangeRateEntity(
            id=django_rate.id,
            from_currency_id=django_rate.from_currency_id,
            to_currency_id=django_rate.to_currency_id,
            rate=django_rate.rate,
            source=django_rate.source,
            fetched_at=django_rate.fetched_at
        )

    def _offer_to_entity(self, django_offer: DjangoOffer) -> OfferEntity:
        from users.domain.entities import UserEntity

        owner_entity = None
        if hasattr(django_offer, 'owner') and django_offer.owner:
            owner_entity = UserEntity(
                id=django_offer.owner.id,
                email=django_offer.owner.email,
                full_name=django_offer.owner.full_name,
                is_active=django_offer.owner.is_active,
                is_verified=django_offer.owner.is_verified,
                is_available=django_offer.owner.is_available,
                verification_status=django_offer.owner.verification_status,
                phone=django_offer.owner.phone,
                country_code=django_offer.owner.country_code,
                city=django_offer.owner.city,
                address=django_offer.owner.address,
                province=django_offer.owner.province,
                municipality=django_offer.owner.municipality,
                neighborhood=django_offer.owner.neighborhood,
                occupation=django_offer.owner.occupation,
                bio=django_offer.owner.bio,
                avatar=django_offer.owner.avatar,
                date_joined=django_offer.owner.date_joined,
                preferred_give_currency=django_offer.owner.preferred_give_currency,
                preferred_want_currency=django_offer.owner.preferred_want_currency,
            )

        give_currency_entity = None
        if hasattr(django_offer, 'give_currency') and django_offer.give_currency:
            give_currency_entity = self._currency_to_entity(django_offer.give_currency)

        want_currency_entity = None
        if hasattr(django_offer, 'want_currency') and django_offer.want_currency:
            want_currency_entity = self._currency_to_entity(django_offer.want_currency)

        return OfferEntity(
            id=django_offer.id,
            owner_id=django_offer.owner_id,
            give_currency_id=django_offer.give_currency_id,
            give_amount=django_offer.give_amount,
            want_currency_id=django_offer.want_currency_id,
            want_amount=django_offer.want_amount,
            exchange_rate_snapshot=django_offer.exchange_rate_snapshot,
            offer_type=django_offer.offer_type,
            status=django_offer.status,
            notes=django_offer.notes,
            views_count=django_offer.views_count,
            city=django_offer.city,
            country_code=django_offer.country_code,
            latitude=django_offer.latitude,
            longitude=django_offer.longitude,
            implied_rate=django_offer.implied_rate,
            expires_at=django_offer.expires_at,
            created_at=django_offer.created_at,
            updated_at=django_offer.updated_at,
            owner=owner_entity,
            give_currency=give_currency_entity,
            want_currency=want_currency_entity,
        )

    def _interest_to_entity(self, django_interest: DjangoOfferInterest) -> OfferInterestEntity:
        from users.domain.entities import UserEntity

        buyer_entity = None
        if hasattr(django_interest, 'buyer') and django_interest.buyer:
            buyer_entity = UserEntity(
                id=django_interest.buyer.id,
                email=django_interest.buyer.email,
                full_name=django_interest.buyer.full_name,
                is_active=django_interest.buyer.is_active,
                is_verified=django_interest.buyer.is_verified,
                is_available=django_interest.buyer.is_available,
                verification_status=django_interest.buyer.verification_status,
                phone=django_interest.buyer.phone,
                country_code=django_interest.buyer.country_code,
                city=django_interest.buyer.city,
                address=django_interest.buyer.address,
                province=django_interest.buyer.province,
                municipality=django_interest.buyer.municipality,
                neighborhood=django_interest.buyer.neighborhood,
                occupation=django_interest.buyer.occupation,
                bio=django_interest.buyer.bio,
                avatar=django_interest.buyer.avatar,
                date_joined=django_interest.buyer.date_joined,
                preferred_give_currency=django_interest.buyer.preferred_give_currency,
                preferred_want_currency=django_interest.buyer.preferred_want_currency,
            )

        room_entity = None
        if hasattr(django_interest, 'room') and django_interest.room:
            # Simplificamos para evitar circularidade profunda ou retornar apenas ID se necessário
            # Aqui podemos colocar a lógica de conversão de Room para Entity se disponível
            room_entity = django_interest.room # Passamos o objecto por agora

        return OfferInterestEntity(
            id=django_interest.id,
            offer_id=django_interest.offer_id,
            buyer_id=django_interest.buyer_id,
            status=django_interest.status,
            message=django_interest.message,
            room_id=django_interest.room_id,
            created_at=django_interest.created_at,
            responded_at=django_interest.responded_at,
            buyer=buyer_entity,
            room=room_entity,
        )


    def get_currency_by_code(self, code: str) -> Optional[CurrencyEntity]:
        try:
            return self._currency_to_entity(DjangoCurrency.objects.get(code__iexact=code))

        except DjangoCurrency.DoesNotExist:
            return None

    def get_currency_by_id(self, currency_id: uuid.UUID) -> Optional[CurrencyEntity]:
        try:
            return self._currency_to_entity(DjangoCurrency.objects.get(id=currency_id))
        except DjangoCurrency.DoesNotExist:
            return None

    def get_exchange_rate(self, from_id: uuid.UUID, to_id: uuid.UUID) -> Optional[ExchangeRateEntity]:
        try:
            rate = DjangoExchangeRate.objects.get(from_currency_id=from_id, to_currency_id=to_id)
            return self._exchange_rate_to_entity(rate)
        except DjangoExchangeRate.DoesNotExist:
            return None

    def save_offer(self, offer: OfferEntity) -> OfferEntity:
        with transaction.atomic():
            django_offer, created = DjangoOffer.objects.update_or_create(
                id=offer.id,
                defaults={
                    'owner_id': offer.owner_id,
                    'give_currency_id': offer.give_currency_id,
                    'give_amount': offer.give_amount,
                    'want_currency_id': offer.want_currency_id,
                    'want_amount': offer.want_amount,
                    'exchange_rate_snapshot': offer.exchange_rate_snapshot,
                    'offer_type': offer.offer_type,
                    'status': offer.status,
                    'notes': offer.notes,
                    'views_count': offer.views_count,
                    'city': offer.city,
                    'country_code': offer.country_code,
                    'latitude': offer.latitude,
                    'longitude': offer.longitude,
                    'expires_at': offer.expires_at,
                }
            )
            # Recarrega com relações para garantir que owner, give_currency e
            # want_currency estão disponíveis na entidade retornada
            django_offer = DjangoOffer.objects.select_related(
                'owner', 'give_currency', 'want_currency'
            ).get(id=django_offer.id)
            return self._offer_to_entity(django_offer)

    def get_offer_by_id(self, offer_id: uuid.UUID) -> Optional[OfferEntity]:
        try:
            return self._offer_to_entity(
                DjangoOffer.objects.select_related('owner', 'give_currency', 'want_currency').get(id=offer_id)
            )
        except DjangoOffer.DoesNotExist:
            return None

    def get_offer_by_id_for_update(self, offer_id: uuid.UUID) -> Optional[OfferEntity]:
        try:
            # Bloqueio de base de dados para evitar condições de corrida (select_for_update)
            return self._offer_to_entity(
                DjangoOffer.objects.select_related('owner', 'give_currency', 'want_currency')
                .select_for_update().get(id=offer_id)
            )
        except DjangoOffer.DoesNotExist:
            return None

    def list_offers(self, filters: dict) -> List[OfferEntity]:
        qs = DjangoOffer.objects.filter(status='active').select_related('owner', 'give_currency', 'want_currency')
        
        from django.db.models import Q
        
        if search := filters.get('search'):
            # Pesquisa por nome do publicador ou código das moedas
            qs = qs.filter(
                Q(owner__full_name__icontains=search) |
                Q(give_currency__code__icontains=search) |
                Q(want_currency__code__icontains=search) |
                Q(owner__province__icontains=search) |
                Q(owner__municipality__icontains=search) |
                Q(city__icontains=search)
            )
            
        if give := filters.get('give_currency'):
            qs = qs.filter(give_currency__code__iexact=give)
        if want := filters.get('want_currency'):
            qs = qs.filter(want_currency__code__iexact=want)
        if city := filters.get('city'):
            qs = qs.filter(city__icontains=city)
        if province := filters.get('province'):
            qs = qs.filter(owner__province__iexact=province)
        if municipality := filters.get('municipality'):
            qs = qs.filter(owner__municipality__iexact=municipality)
        if min_amount := filters.get('min_amount'):
            qs = qs.filter(give_amount__gte=min_amount)
        if max_amount := filters.get('max_amount'):
            qs = qs.filter(give_amount__lte=max_amount)
        
        # Ordenação (os mais recentes por defeito)
        order = filters.get('order', '-created_at')
        if order in ['created_at', '-created_at', 'give_amount', '-give_amount']:
            qs = qs.order_by(order)
        else:
            qs = qs.order_by('-created_at')
        
        # Só mostra ofertas não expiradas (expires_at=None OU ainda no futuro)
        final_qs = qs.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        )
        return [self._offer_to_entity(o) for o in final_qs]

    def save_interest(self, interest: OfferInterestEntity) -> OfferInterestEntity:
        django_interest, created = DjangoOfferInterest.objects.update_or_create(
            id=interest.id,
            defaults={
                'offer_id': interest.offer_id,
                'buyer_id': interest.buyer_id,
                'status': interest.status,
                'message': interest.message,
                'room_id': interest.room_id,
                'responded_at': interest.responded_at,
            }
        )
        return self._interest_to_entity(django_interest)

    def get_interest_by_id(self, interest_id: uuid.UUID) -> Optional[OfferInterestEntity]:
        try:
            return self._interest_to_entity(DjangoOfferInterest.objects.get(id=interest_id))
        except DjangoOfferInterest.DoesNotExist:
            return None

    def get_interest_by_id_for_update(self, interest_id: uuid.UUID) -> Optional[OfferInterestEntity]:
        try:
            # Bloqueio de base de dados para evitar condições de corrida (select_for_update)
            return self._interest_to_entity(DjangoOfferInterest.objects.select_for_update().get(id=interest_id))
        except DjangoOfferInterest.DoesNotExist:
            return None

    def get_interest_by_offer_and_buyer(self, offer_id: uuid.UUID, buyer_id: uuid.UUID) -> Optional[OfferInterestEntity]:
        try:
            return self._interest_to_entity(DjangoOfferInterest.objects.get(offer_id=offer_id, buyer_id=buyer_id))
        except DjangoOfferInterest.DoesNotExist:
            return None

    def increment_offer_views(self, offer_id: uuid.UUID) -> None:
        DjangoOffer.objects.filter(id=offer_id).update(views_count=models.F('views_count') + 1)

    def register_offer_view(self, offer_id: uuid.UUID, user_id: Optional[uuid.UUID]) -> None:
        DjangoOfferView.objects.create(offer_id=offer_id, user_id=user_id)
