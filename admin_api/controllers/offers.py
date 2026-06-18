from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from app.permissions import IsAdminUser
from offers.models import Offer, OfferInterest
from offers.infra.serializers import OfferSerializer
from app.pagination import StandardPagination
from app.exceptions import success_response
from rest_framework.exceptions import NotFound, ValidationError
from app.audit_service import audit_log
from django.db.models import Q

class AdminOffersView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Offers'])
    def get(self, request):
        qs = Offer.objects.all().select_related('owner', 'give_currency', 'want_currency').order_by('-created_at')
        
        search = request.query_params.get('search')
        status = request.query_params.get('status')
        
        if search:
            qs = qs.filter(Q(owner__full_name__icontains=search) | Q(owner__email__icontains=search))
        if status:
            qs = qs.filter(status=status)
            
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = OfferSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class AdminOfferActionView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Offers'])
    def post(self, request, offer_id):
        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            raise NotFound('Oferta não encontrada.')
            
        action = request.data.get('action') # 'close', 'pause'
        
        if action == 'close':
            offer.status = 'closed'
            msg = 'Oferta encerrada pelo administrador.'
        elif action == 'pause':
            offer.status = 'paused'
            msg = 'Oferta pausada pelo administrador.'
        else:
            raise ValidationError('Ação inválida.')
            
        offer.save(update_fields=['status'])
        
        audit_log(
            action=f'OFFER_ADMIN_{action.upper()}', 
            resource='offers', 
            resource_id=offer.id, 
            request=request
        )
        
        return success_response(message=msg)
