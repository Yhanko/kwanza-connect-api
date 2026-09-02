"""
Serializers do módulo de notificações.
"""
from rest_framework import serializers
from ..models import Notification, NotificationPreference, PushDevice
from users.infra.serializers import PublicUserSerializer


class NotificationSerializer(serializers.ModelSerializer):
    actor = PublicUserSerializer(read_only=True)
    message = serializers.CharField(source='body', read_only=True)
    notif_type = serializers.CharField(source='type', read_only=True)

    class Meta:
        model  = Notification
        fields = [
            'id', 'recipient', 'actor', 'type', 'notif_type',
            'title', 'body', 'message', 'payload', 'is_read',
            'read_at', 'created_at'
        ]
        read_only_fields = fields



class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NotificationPreference
        fields = [
            'channel', 'new_interest', 'interest_accepted',
            'interest_rejected', 'interest_cancelled', 'offer_expired',
            'new_message', 'deal_accepted', 'deal_cancelled',
            'rate_alert', 'account_verified', 'system'
        ]


class PushDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PushDevice
        fields = ['id', 'platform', 'token', 'device_name', 'is_active', 'registered_at']
        read_only_fields = ['id', 'registered_at']
