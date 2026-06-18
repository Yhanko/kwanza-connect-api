from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from app.permissions import IsAdminUser
from users.models import User
from offers.models import Offer
from audit.infra.models import AuditLog
from app.exceptions import success_response

class AdminDashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Dashboard'])
    def get(self, request):
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        pending_kyc = User.objects.filter(verification_status='pending').count()
        
        total_offers = Offer.objects.count()
        active_offers = Offer.objects.filter(status='active').count()
        closed_offers = Offer.objects.filter(status='closed').count()
        
        return success_response(data={
            'users': {
                'total': total_users,
                'active': active_users,
                'pending_kyc': pending_kyc
            },
            'offers': {
                'total': total_offers,
                'active': active_offers,
                'closed': closed_offers
            }
        })

class AdminAuditLogsView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Dashboard'])
    def get(self, request):
        from app.pagination import StandardPagination
        qs = AuditLog.objects.all().order_by('-timestamp')
        
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        
        # Simple serialization for audit logs
        data = [{
            'id': log.id,
            'action': log.action,
            'resource': log.resource,
            'resource_id': log.resource_id,
            'user_id': log.user_id,
            'ip_address': log.ip_address,
            'created_at': log.timestamp
        } for log in page]
        
        return paginator.get_paginated_response(data)
