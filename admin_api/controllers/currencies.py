from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from app.permissions import IsAdminUser
from offers.models import Currency
from app.exceptions import success_response
from audit.infra.models import AuditLog

class AdminCurrenciesView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Currencies'])
    def get(self, request):
        currencies = Currency.objects.all().order_by('sort_order', 'code')
        data = [{
            'id': str(c.id),
            'code': c.code,
            'name': c.name,
            'symbol': c.symbol,
            'flag_emoji': c.flag_emoji,
            'is_active': c.is_active,
            'sort_order': c.sort_order
        } for c in currencies]
        return success_response(data=data)


class AdminSeedCurrenciesView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Currencies'])
    def post(self, request):
        currencies_data = [
            {'code': 'AOA', 'name': 'Kwanza', 'symbol': 'Kz', 'flag_emoji': '🇦🇴', 'sort_order': 1},
            {'code': 'USD', 'name': 'Dólar Americano', 'symbol': '$', 'flag_emoji': '🇺🇸', 'sort_order': 2},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'flag_emoji': '🇪🇺', 'sort_order': 3},
            {'code': 'GBP', 'name': 'Libra Esterlina', 'symbol': '£', 'flag_emoji': '🇬🇧', 'sort_order': 4},
            {'code': 'ZAR', 'name': 'Rand Sul-Africano', 'symbol': 'R', 'flag_emoji': '🇿🇦', 'sort_order': 5},
            {'code': 'BRL', 'name': 'Real Brasileiro', 'symbol': 'R$', 'flag_emoji': '🇧🇷', 'sort_order': 6},
            {'code': 'CAD', 'name': 'Dólar Canadiano', 'symbol': 'C$', 'flag_emoji': '🇨🇦', 'sort_order': 7},
            {'code': 'AED', 'name': 'Dirham', 'symbol': 'د.إ', 'flag_emoji': '🇦🇪', 'sort_order': 8},
        ]

        count = 0
        for curr in currencies_data:
            obj, created = Currency.objects.update_or_create(
                code=curr['code'],
                defaults={
                    'name': curr['name'],
                    'symbol': curr['symbol'],
                    'flag_emoji': curr['flag_emoji'],
                    'sort_order': curr['sort_order'],
                    'is_active': True
                }
            )
            if created:
                count += 1

        AuditLog.objects.create(
            action='create',
            resource='Currency',
            resource_id='batch_seed',
            user_id=str(request.user.id),
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return success_response(message=f'{count} moedas inseridas ou atualizadas com sucesso.')
