from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Permite acesso apenas ao dono do objecto.
    O objecto deve ter um campo 'owner' ou 'user'.
    """
    message = 'Acesso negado. Apenas o proprietário pode realizar esta acção.'

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, 'owner', None) or getattr(obj, 'user', None)
        return owner == request.user


class IsSelf(BasePermission):
    """Utilizado nos endpoints de perfil — apenas o próprio utilizador."""
    message = 'Só pode aceder ao seu próprio perfil.'

    def has_object_permission(self, request, view, obj):
        return obj == request.user


class IsVerified(BasePermission):
    """Apenas utilizadores com KYC aprovado."""
    message = 'A sua conta ainda não foi verificada. Envie os documentos de identidade.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_verified
        )


class IsRoomMember(BasePermission):
    """Permite acesso apenas a membros da sala de chat."""
    message = 'Não é membro desta sala de conversa.'

    def has_object_permission(self, request, view, obj):
        # obj é um Room
        return obj.members.filter(user=request.user).exists()


class IsAdminUser(BasePermission):
    """Apenas administradores (staff ou superuser)."""
    message = 'Acesso negado. Apenas administradores podem realizar esta acção.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )
