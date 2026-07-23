from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from app.permissions import IsAdminUser
from users.models import User, IdentityDocument
from users.infra.serializers import UserProfileSerializer as UserSerializer, IdentityDocumentSerializer
from app.pagination import StandardPagination
from app.exceptions import success_response
from rest_framework.exceptions import NotFound, ValidationError
from app.audit_service import audit_log
from django.db.models import Q
from rest_framework import serializers

class AdminUserListSerializer(UserSerializer):
    identity_document = IdentityDocumentSerializer(read_only=True)
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['is_active', 'is_staff', 'verification_status', 'identity_document']

class AdminUsersView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Users'])
    def get(self, request):
        qs = User.objects.all().select_related('identity_document', 'security')
        
        search = request.query_params.get('search')
        status = request.query_params.get('status') # active, blocked
        kyc = request.query_params.get('kyc') # pending, approved, rejected, submitted
        
        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search))
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'blocked':
            qs = qs.filter(is_active=False)
        if kyc:
            qs = qs.filter(verification_status=kyc)
            
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminUserListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class AdminUserDetailsView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Users'])
    def get(self, request, user_id):
        try:
            user = User.objects.select_related('identity_document', 'security').get(id=user_id)
        except User.DoesNotExist:
            raise NotFound('Utilizador não encontrado.')
            
        return success_response(data=AdminUserListSerializer(user).data)

class AdminUserKYCView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Users'])
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound('Utilizador não encontrado.')
            
        action = request.data.get('action') # 'approve' or 'reject'
        reason = request.data.get('reason', '')
        
        if action not in ['approve', 'reject']:
            raise ValidationError('Ação inválida. Use "approve" ou "reject".')
            
        doc = getattr(user, 'identity_document', None)
        if not doc:
            raise ValidationError('Utilizador não submeteu documentos de identidade.')
            
        if action == 'approve':
            doc.status = 'approved'
            doc.reviewed_by = request.user
            user.verification_status = 'approved'
            user.is_verified = True
        else:
            doc.status = 'rejected'
            doc.rejection_reason = reason
            doc.reviewed_by = request.user
            user.verification_status = 'pending' # Volta para pendente para permitir novo envio
            user.is_verified = False
            
        doc.save()
        user.save()
        
        audit_log(
            action=f'KYC_{action.upper()}', 
            resource='users', 
            resource_id=user.id, 
            metadata={'reason': reason},
            request=request
        )
        
        return success_response(message=f'KYC do utilizador foi {"aprovado" if action == "approve" else "rejeitado"}.')

class AdminUserStatusView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Users'])
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound('Utilizador não encontrado.')
            
        if user.is_superuser and not request.user.is_superuser:
            raise ValidationError('Não pode alterar o estado de um superuser.')
            
        action = request.data.get('action') # 'block', 'unblock'
        
        if action == 'block':
            user.is_active = False
            msg = 'Utilizador bloqueado com sucesso.'
        elif action == 'unblock':
            user.is_active = True
            msg = 'Utilizador desbloqueado com sucesso.'
        else:
            raise ValidationError('Ação inválida.')
            
        user.save()
        
        audit_log(
            action=f'USER_{action.upper()}', 
            resource='users', 
            resource_id=user.id, 
            request=request
        )
        
        return success_response(message=msg)


class AdminUserSanctionView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Restrições'])
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound('Utilizador não encontrado.')
            
        if user.is_superuser and not request.user.is_superuser:
            raise ValidationError('Não pode sancionar um superuser.')
            
        from django.utils import timezone
        
        # Payload esperado: {'suspended_until': '2025-01-01T00:00:00Z', 'restricted_pages': ['/offers', '/chat']}
        suspended_until = request.data.get('suspended_until')
        restricted_pages = request.data.get('restricted_pages')
        
        if suspended_until is not None:
            user.suspended_until = suspended_until
        
        if restricted_pages is not None:
            if not isinstance(restricted_pages, list):
                raise ValidationError('restricted_pages deve ser uma lista de strings.')
            user.restricted_pages = restricted_pages
            
        user.save(update_fields=['suspended_until', 'restricted_pages'])
        
        audit_log(
            action='USER_SANCTIONED', 
            resource='users', 
            resource_id=user.id, 
            metadata={'suspended_until': suspended_until, 'restricted_pages': restricted_pages},
            request=request
        )
        
        return success_response(message='Sanções aplicadas com sucesso.')


class MiniUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'avatar']


class AdminReportListSerializer(serializers.ModelSerializer):
    reporter = MiniUserSerializer(read_only=True)
    reported_to = MiniUserSerializer(read_only=True)

    class Meta:
        from users.models import Report
        model = Report
        fields = ['id', 'reporter', 'reported_to', 'reason', 'status', 'admin_notes', 'room_id', 'created_at']



class AdminReportListView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Denúncias'])
    def get(self, request):
        from users.models import Report
        qs = Report.objects.all().select_related('reporter', 'reported_to').order_by('-created_at')
        
        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
            
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminReportListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminReportActionView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Denúncias'])
    def post(self, request, report_id):
        from users.models import Report
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            raise NotFound('Denúncia não encontrada.')
            
        action = request.data.get('action') # 'review', 'dismiss'
        admin_notes = request.data.get('admin_notes', '')
        
        if action == 'review':
            report.status = 'reviewed'
        elif action == 'dismiss':
            report.status = 'dismissed'
        else:
            raise ValidationError('Ação inválida. Use "review" ou "dismiss".')
            
        report.admin_notes = admin_notes
        report.save(update_fields=['status', 'admin_notes'])
        
        audit_log(
            action=f'REPORT_{action.upper()}', 
            resource='reports', 
            resource_id=report.id, 
            metadata={'admin_notes': admin_notes},
            request=request
        )
        
        return success_response(message=f'Denúncia marcada como {report.status}.')


class AdminUserDeleteView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin - Users'])
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound('Utilizador não encontrado.')

        if user.is_superuser:
            raise ValidationError('Não é possível eliminar um superuser.')
        if user.id == request.user.id:
            raise ValidationError('Não pode eliminar a sua própria conta.')

        import uuid as _uuid
        original_email = user.email
        # Soft-delete: deactivate + anonymize so unique constraint is freed
        user.is_active = False
        user.email = f'deleted_{_uuid.uuid4().hex[:8]}@removed.kwanza'
        user.full_name = 'Conta Eliminada'
        user.save(update_fields=['is_active', 'email', 'full_name'])

        audit_log(
            action='USER_DELETED',
            resource='users',
            resource_id=user_id,
            metadata={'original_email': original_email},
            request=request
        )

        return success_response(message='Conta de utilizador eliminada com sucesso.')
