from django.core.management.base import BaseCommand
from offers.models import Currency

class Command(BaseCommand):
    help = 'Insere as moedas iniciais (AOA, USD, EUR, etc.) na base de dados'

    def handle(self, *args, **kwargs):
        currencies = [
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
        for curr in currencies:
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
                self.stdout.write(self.style.SUCCESS(f"Moeda criada: {obj.code}"))
                count += 1
            else:
                self.stdout.write(self.style.WARNING(f"Moeda atualizada: {obj.code}"))

        self.stdout.write(self.style.SUCCESS(f"Concluído! {count} moedas inseridas."))
