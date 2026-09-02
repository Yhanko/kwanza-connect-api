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

    @extend_schema(
        tags=['Admin - Dashboard'],
        description='Consulta a trilha de auditoria (Audit Trail) com suporte a filtros regulatórios de conformidade BNA.'
    )
    def get(self, request):
        from app.pagination import StandardPagination
        from django.db.models import Q
        
        qs = AuditLog.objects.all().order_by('-timestamp')
        
        # Filtros de auditoria para inspeção e relatórios regulatórios
        action = request.query_params.get('action')
        resource = request.query_params.get('resource')
        severity = request.query_params.get('severity')
        status_param = request.query_params.get('status')
        user_id = request.query_params.get('user_id')
        actor_email = request.query_params.get('actor_email')
        search = request.query_params.get('search')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if action:
            qs = qs.filter(action__iexact=action)
        if resource:
            qs = qs.filter(resource__iexact=resource)
        if severity:
            qs = qs.filter(severity__iexact=severity)
        if status_param:
            qs = qs.filter(status__iexact=status_param)
        if user_id:
            qs = qs.filter(user_id=user_id)
        if actor_email:
            qs = qs.filter(actor_email__icontains=actor_email)
        if start_date:
            qs = qs.filter(timestamp__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__lte=end_date)
        if search:
            qs = qs.filter(
                Q(action__icontains=search) |
                Q(resource__icontains=search) |
                Q(actor_email__icontains=search) |
                Q(ip_address__icontains=search) |
                Q(resource_id__icontains=search)
            )
        
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        
        # Serialização detalhada dos logs de auditoria
        data = [{
            'id': log.id,
            'action': log.action,
            'resource': log.resource,
            'resource_id': log.resource_id,
            'user_id': log.user_id,
            'actor_email': log.actor_email,
            'status': log.status,
            'severity': log.severity,
            'metadata': log.metadata,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'timestamp': log.timestamp
        } for log in page]
        
        return paginator.get_paginated_response(data)

