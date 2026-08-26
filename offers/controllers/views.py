"""
Controllers do módulo offers.
"""
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, OpenApiParameter

from app.exceptions import success_response, created_response, no_content_response
from app.permissions import IsOwner, IsVerified
from app.pagination import StandardPagination
from ..models import Currency, Offer, OfferInterest
from ..infra.serializers import (
    CurrencySerializer, OfferSerializer, OfferCreateSerializer,
    OfferInterestSerializer, OfferInterestCreateSerializer,
)
from ..services.use_cases import (
    CreateOfferUseCase, ListOffersUseCase, GetOfferUseCase,
    PauseOfferUseCase, ResumeOfferUseCase, CloseOfferUseCase,
    ExpressInterestUseCase, AcceptInterestUseCase,
    RejectInterestUseCase, CancelInterestUseCase,
)
from ..infra.repositories import DjangoOfferRepository
from ..infra.services import DjangoChatService, DjangoNotificationService
from app.services.location_service import LocationService
from django.conf import settings
import uuid
from app.audit_service import audit_log


# ─────────────────────────────────────────────
#  Moedas
# ─────────────────────────────────────────────

class CurrencyListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=['Moedas'])
    def get(self, request):
        currencies = Currency.objects.filter(is_active=True)
        serializer = CurrencySerializer(currencies, many=True)
        return success_response(data=serializer.data, message='Lista de moedas disponíveis.')


# ─────────────────────────────────────────────
#  Ofertas
# ─────────────────────────────────────────────

class OfferListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsVerified()]
        return [IsAuthenticated()]

    @extend_schema(tags=['Ofertas'])
    def get(self, request):
        repo = DjangoOfferRepository()
        filters = {
            'search':        request.query_params.get('search'),
            'give_currency': request.query_params.get('give'),
            'want_currency': request.query_params.get('want'),
            'city':          request.query_params.get('city'),
            'province':      request.query_params.get('province'),
            'municipality':  request.query_params.get('municipality'),
            'min_amount':    request.query_params.get('min_amount'),
            'max_amount':    request.query_params.get('max_amount'),
            'order':         request.query_params.get('order'),
        }
        qs         = ListOffersUseCase(repo).execute(filters=filters)
        paginator  = StandardPagination()
        page       = paginator.paginate_queryset(qs, request)
        serializer = OfferSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(request=OfferCreateSerializer, tags=['Ofertas'])
    def post(self, request):
        repo = DjangoOfferRepository()
        serializer = OfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data_to_save = serializer.validated_data.copy()

        # Tenta capturar a localização real do utilizador se as coordenadas forem enviadas e a cidade não
        lat = data_to_save.get('latitude')
        lon = data_to_save.get('longitude')
        if not data_to_save.get('city') and lat is not None and lon is not None:
            resolved_city = LocationService.reverse_geocode(
                latitude=float(lat),
                longitude=float(lon),
                timeout=getattr(settings, 'GEOLOCATION_TIMEOUT', 15)
            )
            if resolved_city:
                data_to_save['city'] = resolved_city

        # Fallback de localização se o GPS ou serviço externo falhar/estourar timeout
        if not data_to_save.get('city'):
            prov = getattr(request.user, 'province', '')
            mun = getattr(request.user, 'municipality', '')
            user_city = getattr(request.user, 'city', '')
            if prov and mun:
                data_to_save['city'] = f"{mun} - {prov}"
            elif prov:
                data_to_save['city'] = prov
            elif user_city:
                data_to_save['city'] = user_city

        offer = CreateOfferUseCase(repo).execute(user_id=request.user.id, data=data_to_save)
        
        # Auditoria
        audit_log(
            action='OFFER_CREATE', 
            resource='offers', 
            resource_id=offer.id, 
            metadata={'give': offer.give_currency.code, 'amount': float(offer.give_amount)},
            request=request
        )

        
        return created_response(
            data=OfferSerializer(offer).data,
            message='Oferta publicada com sucesso.'
        )


class MyOfferListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Ofertas'])
    def get(self, request):
        qs         = Offer.objects.filter(owner=request.user).select_related('give_currency', 'want_currency')
        paginator  = StandardPagination()
        page       = paginator.paginate_queryset(qs, request)
        serializer = OfferSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class OfferDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Ofertas'])
    def get(self, request, offer_id: str):
        repo = DjangoOfferRepository()
        offer      = GetOfferUseCase(repo).execute(
            offer_id=uuid.UUID(offer_id), 
            viewer_id=request.user.id
        )
        serializer = OfferSerializer(offer)
        return success_response(data=serializer.data)


class OfferPauseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Ofertas'])
    def post(self, request, offer_id: str):
        repo = DjangoOfferRepository()
        offer = PauseOfferUseCase(repo).execute(user_id=request.user.id, offer_id=uuid.UUID(offer_id))
        
        # Auditoria
        audit_log(action='OFFER_PAUSE', resource='offers', resource_id=offer_id, request=request)
        
        return success_response(message='Oferta pausada com sucesso.')


class OfferResumeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Ofertas'])
    def post(self, request, offer_id: str):
        repo = DjangoOfferRepository()
        offer = ResumeOfferUseCase(repo).execute(user_id=request.user.id, offer_id=uuid.UUID(offer_id))
        
        # Auditoria
        audit_log(action='OFFER_RESUME', resource='offers', resource_id=offer_id, request=request)
        
        return success_response(message='Oferta retomada com sucesso.')


class OfferCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Ofertas'])
    def post(self, request, offer_id: str):
        repo = DjangoOfferRepository()
        CloseOfferUseCase(repo).execute(user_id=request.user.id, offer_id=uuid.UUID(offer_id))
        
        # Auditoria
        audit_log(action='OFFER_CLOSE', resource='offers', resource_id=offer_id, request=request)
        
        return success_response(message='Oferta encerrada com sucesso.')


# ─────────────────────────────────────────────
#  Interesses
# ─────────────────────────────────────────────

class ExpressInterestView(APIView):
    permission_classes = [IsAuthenticated, IsVerified]

    @extend_schema(request=OfferInterestCreateSerializer, tags=['Interesses'])
    def post(self, request, offer_id: str):
        repo = DjangoOfferRepository()
        serializer = OfferInterestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        interest = ExpressInterestUseCase(repo).execute(
            user_id=request.user.id,
            offer_id=uuid.UUID(offer_id),
            message=serializer.validated_data.get('message', ''),
        )
        
        # Auditoria
        audit_log(
            action='INTEREST_EXPRESS', 
            resource='offers', 
            resource_id=offer_id, 
            metadata={'interest_id': interest.id},
            request=request
        )
        
        return created_response(
            data=OfferInterestSerializer(interest).data,
            message='Interesse registado com sucesso. O vendedor será notificado.'
        )


class OfferInterestListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Interesses'])
    def get(self, request, offer_id: str):
        """Lista os interessados na minha oferta."""
        try:
            offer = Offer.objects.get(id=offer_id, owner=request.user)
        except Offer.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Oferta não encontrada ou não pertence ao utilizador.')
        interests  = OfferInterest.objects.filter(offer=offer).select_related('buyer')
        serializer = OfferInterestSerializer(interests, many=True)
        return success_response(data=serializer.data)


class AcceptInterestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Interesses'])
    def post(self, request, interest_id: str):
        repo = DjangoOfferRepository()
        chat_service = DjangoChatService()
        notif_service = DjangoNotificationService()
        room_id = AcceptInterestUseCase(repo, chat_service, notif_service).execute(
            user_id=request.user.id, 
            interest_id=uuid.UUID(interest_id)
        )
        
        # Auditoria
        audit_log(
            action='INTEREST_ACCEPT', 
            resource='offers', 
            resource_id=interest_id, 
            metadata={'room_id': room_id},
            request=request
        )
        
        return success_response(
            data={'room_id': str(room_id)},
            message='Interesse aceite. A conversa foi iniciada.'
        )


class RejectInterestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Interesses'])
    def post(self, request, interest_id: str):
        repo = DjangoOfferRepository()
        notif_service = DjangoNotificationService()
        RejectInterestUseCase(repo, notif_service).execute(
            user_id=request.user.id, 
            interest_id=uuid.UUID(interest_id)
        )
        return success_response(message='Interesse rejeitado.')


class CancelInterestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Interesses'])
    def delete(self, request, interest_id: str):
        repo = DjangoOfferRepository()
        CancelInterestUseCase(repo).execute(
            user_id=request.user.id, 
            interest_id=uuid.UUID(interest_id)
        )
        return success_response(message='Interesse cancelado com sucesso.')


class MyInterestListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Interesses'])
    def get(self, request):
        """Lista todos os meus interesses em ofertas de outros."""
        interests = OfferInterest.objects.filter(buyer=request.user).select_related(
            'offer__give_currency', 'offer__want_currency', 'offer__owner'
        )
        paginator  = StandardPagination()
        page       = paginator.paginate_queryset(interests, request)
        serializer = OfferInterestSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
