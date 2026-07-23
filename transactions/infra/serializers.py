"""
Serializers do módulo de transações.
"""
from rest_framework import serializers
from ..models import Transaction, TransactionReview
from users.infra.serializers import PublicUserSerializer
from offers.infra.serializers import CurrencySerializer


class TransactionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    offer = serializers.UUIDField(source='offer_id', allow_null=True)
    room = serializers.UUIDField(source='room_id', allow_null=True)
    seller = serializers.SerializerMethodField()
    buyer = serializers.SerializerMethodField()
    give_currency = serializers.SerializerMethodField()
    give_amount = serializers.DecimalField(max_digits=24, decimal_places=2)
    want_currency = serializers.SerializerMethodField()
    want_amount = serializers.DecimalField(max_digits=24, decimal_places=2)
    rate = serializers.DecimalField(max_digits=24, decimal_places=8)
    status = serializers.CharField()
    notes = serializers.CharField(allow_blank=True)
    has_review = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_seller(self, obj):
        from users.models import User
        user = User.objects.filter(id=obj.seller_id).first()
        return PublicUserSerializer(user).data if user else None

    def get_buyer(self, obj):
        from users.models import User
        user = User.objects.filter(id=obj.buyer_id).first()
        return PublicUserSerializer(user).data if user else None

    def get_give_currency(self, obj):
        from offers.models import Currency
        curr = Currency.objects.filter(id=obj.give_currency_id).first()
        return CurrencySerializer(curr).data if curr else None

    def get_want_currency(self, obj):
        from offers.models import Currency
        curr = Currency.objects.filter(id=obj.want_currency_id).first()
        return CurrencySerializer(curr).data if curr else None

    def get_has_review(self, obj):
        request = self.context.get('request')
        if not request:
            return False
            
        from ..infra.repositories import DjangoTransactionRepository
        repo = DjangoTransactionRepository()
        review = repo.get_review_by_transaction_and_user(obj.id, request.user.id)
        return bool(review)


class TransactionReviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    transaction = serializers.UUIDField(source='transaction_id')
    reviewer = serializers.SerializerMethodField()
    reviewed = serializers.SerializerMethodField()
    rating = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField(required=False)

    def get_reviewer(self, obj):
        from users.models import User
        user_id = getattr(obj, 'reviewer_id', None)
        user = User.objects.filter(id=user_id).first() if user_id else None
        return PublicUserSerializer(user).data if user else None

    def get_reviewed(self, obj):
        from users.models import User
        user_id = getattr(obj, 'reviewed_id', None)
        user = User.objects.filter(id=user_id).first() if user_id else None
        return PublicUserSerializer(user).data if user else None


class TransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Transaction
        fields = ['offer', 'room', 'status', 'notes']
