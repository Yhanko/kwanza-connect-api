"""
Controllers do módulo rates.
"""
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from app.exceptions import success_response
from ..services.use_cases import GetLiveRateUseCase, ConvertAmountUseCase, GetPlatformStatsUseCase
from ..infra.repositories import DjangoRatesRepository


class ExchangeRateListView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'rates_public'

    @extend_schema(tags=['Câmbios'])
    def get(self, request):
        repo = DjangoRatesRepository()
        rates = repo.list_all_rates()
        # For simple listing, we can return the result directly or serialize
        return success_response(data=rates, message='Taxas de câmbio actuais.')


class ConvertCurrencyView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'rates_public'

    @extend_schema(
        tags=['Câmbios'],
        parameters=[
            OpenApiParameter('from', str, required=True),
            OpenApiParameter('to', str, required=True),
            OpenApiParameter('amount', float, required=True),
        ]
    )
    def get(self, request):
        from_code = request.query_params.get('from')
        to_code   = request.query_params.get('to')
        amount    = request.query_params.get('amount')

        if not from_code or not to_code or not amount:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('from, to e amount são parâmetros obrigatórios.')

        from decimal import Decimal, InvalidOperation
        try:
            amount_decimal = Decimal(str(amount))
        except (ValueError, InvalidOperation):
            from rest_framework.exceptions import ValidationError
            raise ValidationError('amount inválido.')

        repo = DjangoRatesRepository()
        result = ConvertAmountUseCase(repo).execute(from_code, to_code, amount_decimal)
        return success_response(data=result)


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Estatísticas'])
    def get(self, request):
        repo = DjangoRatesRepository()
        stats = GetPlatformStatsUseCase(repo).execute()
        return success_response(data=stats)
