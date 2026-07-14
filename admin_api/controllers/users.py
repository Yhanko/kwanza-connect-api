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
