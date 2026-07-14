"""
Controllers do módulo de transações.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from app.exceptions import success_response, created_response
from app.pagination import StandardPagination
from ..infra.serializers import TransactionSerializer, TransactionReviewSerializer, TransactionCreateSerializer
from ..services.use_cases import ConfirmDealUseCase, ListUserTransactionsUseCase, RateTransactionUseCase, ListUserReviewsUseCase
from ..infra.repositories import DjangoTransactionRepository
from ..infra.services import DjangoOfferService, DjangoChatService, DjangoNotificationService
import uuid
from app.audit_service import audit_log
from rest_framework.exceptions import NotFound, ValidationError


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Transações'])
    def get(self, request):
        repo = DjangoTransactionRepository()
        limit  = int(request.query_params.get('limit', 20))
        
        # We'll use a simplified list for now, as use case currently doesn't support limit
        txs    = ListUserTransactionsUseCase(repo).execute(user_id=request.user.id)
        
        paginator  = StandardPagination()
        page       = paginator.paginate_queryset(txs, request)
        serializer = TransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class TransactionConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TransactionCreateSerializer, tags=['Transações'])
    def post(self, request):
        """Dono da oferta confirma que a troca foi concluída."""
        offer_id = request.data.get('offer')
        room_id  = request.data.get('room')
        notes    = request.data.get('notes', '')
        
        if not offer_id or not room_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'offer': 'ID da oferta é obrigatório.', 'room': 'ID da sala é obrigatório.'})

        repo = DjangoTransactionRepository()
        offer_service = DjangoOfferService()
        chat_service = DjangoChatService()
        notif_service = DjangoNotificationService()
        
        use_case = ConfirmDealUseCase(repo, offer_service, chat_service, notif_service)
        trans = use_case.execute(
            user_id=request.user.id, 
            offer_id=uuid.UUID(offer_id), 
            room_id=uuid.UUID(room_id), 
            notes=notes
        )
        
        # Auditoria
        audit_log(
            action='TRANSACTION_CONFIRM', 
            resource='transactions', 
            resource_id=trans.id, 
            metadata={'offer_id': offer_id, 'room_id': room_id},
            request=request
        )
        
        return created_response(
            data=TransactionSerializer(trans).data,
            message='Transação confirmada e registada com sucesso.'
        )


class TransactionReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TransactionReviewSerializer, tags=['Transações'])
    def post(self, request, transaction_id: str):
        """Avaliar um participante de uma transação concluída."""
        rating = request.data.get('rating')
        comment = request.data.get('comment', '')

        if rating is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'rating': 'A nota (rating) é obrigatória.'})

        repo = DjangoTransactionRepository()
        notif_service = DjangoNotificationService()
        
        review = RateTransactionUseCase(repo, notif_service).execute(
            reviewer_id=request.user.id,
            transaction_id=uuid.UUID(transaction_id),
            rating=rating,
            comment=comment
        )
        
        # Auditoria
        audit_log(
            action='TRANSACTION_REVIEW', 
            resource='transactions', 
            resource_id=transaction_id, 
            metadata={'rating': rating},
            request=request
        )
        
        return created_response(
            data=TransactionReviewSerializer(review).data,
            message='Avaliação registada com sucesso.'
        )


class TransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Transações'])
    def get(self, request, transaction_id: str):
        repo = DjangoTransactionRepository()
        trans = repo.get_transaction_by_id(uuid.UUID(transaction_id))
        
        if not trans or (trans.seller_id != request.user.id and trans.buyer_id != request.user.id):
            raise NotFound('Transação não encontrada ou não pertence ao utilizador.')
        
        serializer = TransactionSerializer(trans)
        return success_response(data=serializer.data)


class ReviewListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Transações'])
    def get(self, request, user_id: str):
        repo = DjangoTransactionRepository()
        use_case = ListUserReviewsUseCase(repo)
        
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise ValidationError('ID de utilizador inválido.')

        reviews = use_case.execute(user_id=user_uuid)
        serializer = TransactionReviewSerializer(reviews, many=True)
        return success_response(data=serializer.data)


class TopLocationsMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Métricas'])
    def get(self, request):
        from django.db.models import Count
        from ..models import Transaction
        
        # Filtrar apenas transacções concluídas
        qs = Transaction.objects.filter(status='completed')
        
        # Agrupar pela cidade da oferta e contar
        metrics = qs.exclude(offer__city__isnull=True).exclude(offer__city='').values('offer__city').annotate(
            exchanges=Count('id')
        ).order_by('-exchanges')[:10]
        
        data = [
            {
                "city": item['offer__city'],
                "exchanges": item['exchanges']
            } for item in metrics
        ]
        
        return success_response(data=data, message='Métricas de localizações de topo.')


class TopPaymentMethodsMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Métricas'])
    def get(self, request):
        import re
        from collections import Counter
        from offers.models import Offer

        # Palavras-chave de plataformas/bancos com alias
        # A chave é o padrão Regex, o valor é o nome oficial
        platforms_map = {
            'PayPal': 'PayPal',
            'Wise': 'Wise',
            'Revolut': 'Revolut',
            'Binance': 'Binance',
            'Biance': 'Binance',  # erro comum
            'Unitel Money': 'Unitel Money',
            'M-Pesa': 'M-Pesa',
            'Transferência Bancária': 'Transferência Bancária',
            'BAI': 'BAI',
            'BFA': 'BFA',
            'BIC': 'BIC',
            'Keve': 'Keve',
            'PayPay': 'PayPay',
            'AfriMoney': 'AfriMoney',
            'Multicaixa': 'Multicaixa',
            'Express': 'Multicaixa Express',
            'BPA': 'BPA',
            'Atlantico': 'Atlantico',
            'Bybit': 'Bybit'
        }

        # Expressões regulares pre-compiladas, ignorando maiúsculas/minúsculas
        patterns = {p: re.compile(re.escape(p), re.IGNORECASE) for p in platforms_map.keys()}
        counter = Counter()

        # Obter todas as notas das ofertas publicadas
        qs = Offer.objects.exclude(notes__isnull=True).exclude(notes='')
        
        # Iterar e extrair menções
        for offer in qs:
            notes = offer.notes
            if not notes:
                continue
            for pattern_name, regex in patterns.items():
                if regex.search(notes):
                    official_name = platforms_map[pattern_name]
                    counter[official_name] += 1

        # Formatar para o gráfico: lista de dicionários ordenada
        data = [
            {"method": method, "count": count} 
            for method, count in counter.most_common(10)
        ]

        return success_response(data=data, message='Métricas de métodos de pagamento de topo.')
