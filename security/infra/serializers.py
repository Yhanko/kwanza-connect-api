from rest_framework import serializers
from ..models import SuspiciousActivityReport, UserRiskProfile


class SuspiciousActivityReportSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    rule_name = serializers.CharField(source='get_rule_code_display', read_only=True)
    severity_name = serializers.CharField(source='get_severity_display', read_only=True)
    status_name = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SuspiciousActivityReport
        fields = [
            'id',
            'user',
            'user_email',
            'user_full_name',
            'related_offer_id',
            'related_transaction_id',
            'rule_code',
            'rule_name',
            'severity',
            'severity_name',
            'risk_score',
            'amount_aoa',
            'status',
            'status_name',
            'details',
            'created_at',
            'resolved_at',
            'resolution_notes',
            'reported_to_uif_at',
        ]
        read_only_fields = fields


class ResolveSARSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[
        ('DISMISS', 'Arquivar como Falso Positivo'),
        ('INVESTIGATE', 'Marcar em Investigação Aprofundada'),
        ('BLOCK_USER', 'Bloquear Conta do Utilizador'),
        ('ESCALATE_UIF', 'Reportar Formalmente à UIF (Unidade de Informação Financeira)'),
    ])
    notes = serializers.CharField(required=True, min_length=5, max_length=1500)


class UserKYCLimitsSerializer(serializers.Serializer):
    tier = serializers.CharField()
    tier_name = serializers.CharField()
    description = serializers.CharField()
    max_per_operation_aoa = serializers.FloatField()
    max_daily_aoa = serializers.FloatField()
    max_monthly_aoa = serializers.FloatField()
    daily_used_aoa = serializers.FloatField()
    monthly_used_aoa = serializers.FloatField()
    available_daily_aoa = serializers.FloatField()
    available_monthly_aoa = serializers.FloatField()
    is_monetary_access_allowed = serializers.BooleanField()
