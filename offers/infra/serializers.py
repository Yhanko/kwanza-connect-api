"""
Serializers do módulo offers.
"""
from rest_framework import serializers
from ..models import Currency, ExchangeRate, Offer, OfferInterest, OfferView
from users.infra.serializers import PublicUserSerializer


class CurrencySerializer(serializers.Serializer):
    """Funciona com CurrencyEntity (dataclass) e com objetos Django ORM."""
    id         = serializers.UUIDField()
    code       = serializers.CharField()
    name       = serializers.CharField()
    symbol     = serializers.CharField()
    flag_emoji = serializers.CharField()
    is_active  = serializers.BooleanField()


class ExchangeRateSerializer(serializers.ModelSerializer):
    from_currency = CurrencySerializer(read_only=True)
    to_currency   = CurrencySerializer(read_only=True)

    class Meta:
        model  = ExchangeRate
        fields = ['from_currency', 'to_currency', 'rate', 'fetched_at']


class OfferCreateSerializer(serializers.Serializer):
    give_currency_code  = serializers.CharField(max_length=10)
    give_amount         = serializers.DecimalField(max_digits=24, decimal_places=2)
    want_currency_code  = serializers.CharField(max_length=10)
    want_amount         = serializers.DecimalField(max_digits=24, decimal_places=2)
    offer_type          = serializers.ChoiceField(choices=Offer.OFFER_TYPE, default='sell')
    notes               = serializers.CharField(max_length=500, required=False, allow_blank=True)
    city                = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country_code        = serializers.CharField(max_length=5, required=False, allow_blank=True)
    latitude            = serializers.DecimalField(max_digits=10, decimal_places=8, required=False, allow_null=True)
    longitude           = serializers.DecimalField(max_digits=11, decimal_places=8, required=False, allow_null=True)
    expires_at          = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        if data.get('give_currency_code') == data.get('want_currency_code'):
            raise serializers.ValidationError('As moedas de origem e destino não podem ser iguais.')
        if data.get('give_amount', 0) <= 0 or data.get('want_amount', 0) <= 0:
            raise serializers.ValidationError('Os valores têm de ser positivos.')
        return data



class OfferSerializer(serializers.Serializer):
    """
    Serializer que funciona com OfferEntity (dataclass) e com objetos Django ORM.
    """
    id                      = serializers.UUIDField()
    give_amount             = serializers.DecimalField(max_digits=24, decimal_places=2)
    want_amount             = serializers.DecimalField(max_digits=24, decimal_places=2)
    exchange_rate_snapshot  = serializers.DecimalField(max_digits=24, decimal_places=8)
    implied_rate            = serializers.DecimalField(max_digits=24, decimal_places=8, allow_null=True)
    spread_percentage       = serializers.SerializerMethodField()
    offer_type              = serializers.CharField()
    status                  = serializers.CharField()
    is_active               = serializers.BooleanField()
    notes                   = serializers.CharField()
    city                    = serializers.CharField()
    country_code            = serializers.CharField()
    latitude                = serializers.DecimalField(max_digits=10, decimal_places=8, allow_null=True, required=False)
    longitude               = serializers.DecimalField(max_digits=11, decimal_places=8, allow_null=True, required=False)
    views_count             = serializers.IntegerField()
    expires_at              = serializers.DateTimeField(allow_null=True)
    created_at              = serializers.DateTimeField(allow_null=True)
    updated_at              = serializers.DateTimeField(allow_null=True)
    owner                   = serializers.SerializerMethodField()
    give_currency           = serializers.SerializerMethodField()
    want_currency           = serializers.SerializerMethodField()

    def get_spread_percentage(self, obj):
        try:
            return obj.spread_percentage
        except Exception:
            return None

    def get_owner(self, obj):
        owner = getattr(obj, 'owner', None)
        if owner is None:
            return None
        from users.infra.serializers import PublicUserSerializer
        # Suporta tanto entidade como objeto ORM
        if hasattr(owner, '__dict__') or hasattr(owner, 'id'):
            try:
                return PublicUserSerializer(owner).data
            except Exception:
                return None
        return None

    def get_give_currency(self, obj):
        currency = getattr(obj, 'give_currency', None)
        if currency is None:
            return None
        try:
            return CurrencySerializer(currency).data
        except Exception:
            return None

    def get_want_currency(self, obj):
        currency = getattr(obj, 'want_currency', None)
        if currency is None:
            return None
        try:
            return CurrencySerializer(currency).data
        except Exception:
            return None


class OfferInterestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OfferInterest
        fields = ['message']


class OfferInterestSerializer(serializers.ModelSerializer):
    buyer = PublicUserSerializer(read_only=True)

    class Meta:
        model  = OfferInterest
        fields = [
            'id', 'buyer', 'status', 'message',
            'room', 'created_at', 'responded_at',
        ]
