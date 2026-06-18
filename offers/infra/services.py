import uuid
from ..services.use_cases import IChatService, INotificationService
from app.services.websocket_service import ChannelsWebSocketService

class DjangoChatService(IChatService):
    def create_offer_room(self, offer_id: uuid.UUID, owner_id: uuid.UUID, buyer_id: uuid.UUID) -> uuid.UUID:
        from chat.models import Room, RoomMember, RoomEvent
        
        # Procura uma sala existente (direct ou offer) entre estes dois utilizadores
        # Evitamos criar múltiplas salas para o mesmo par de pessoas
        existing_room = Room.objects.filter(
            members__user_id=owner_id
        ).filter(
            members__user_id=buyer_id
        ).first()



        if existing_room:
            # Reutiliza a sala existente e reactiva-a se estava fechada
            existing_room.offer_id = offer_id
            existing_room.status = 'active'
            existing_room.save(update_fields=['offer_id', 'status'])
            
            # Regista o novo interesse na sala existente
            RoomEvent.objects.create(
                room=existing_room,
                actor_id=buyer_id,
                event_type='deal_proposed',
                payload={'offer_id': str(offer_id), 'reused': True}
            )
            return existing_room.id

        # Se não existir, cria uma nova
        room = Room.objects.create(
            offer_id=offer_id,
            room_type='offer',
            status='active',
        )
        RoomMember.objects.create(room=room, user_id=owner_id, is_admin=True)
        RoomMember.objects.create(room=room, user_id=buyer_id)
        
        RoomEvent.objects.create(
            room=room,
            actor_id=owner_id,
            event_type='room_created',
            payload={'offer_id': str(offer_id)}
        )
        return room.id


class DjangoNotificationService(INotificationService):
    def notify_interest_accepted(self, buyer_id: uuid.UUID, offer_id: uuid.UUID, room_id: uuid.UUID) -> None:
        from notifications.services.notification_service import NotificationService
        from notifications.models import NotificationType
        from users.models import User
        
        try:
            buyer = User.objects.get(id=buyer_id)
            NotificationService.send(
                recipient=buyer,
                notification_type=NotificationType.INTEREST_ACCEPTED,
                payload={
                    'offer_id': str(offer_id),
                    'room_id':  str(room_id),
                    'redirect': f'/chat/{room_id}'
                }
            )
        except User.DoesNotExist:
            pass

    def notify_interest_rejected(self, buyer_id: uuid.UUID, offer_id: uuid.UUID) -> None:
        from notifications.services.notification_service import NotificationService
        from notifications.models import NotificationType
        from users.models import User
        
        try:
            buyer = User.objects.get(id=buyer_id)
            NotificationService.send(
                recipient=buyer,
                notification_type=NotificationType.INTEREST_REJECTED,
                payload={
                    'offer_id': str(offer_id),
                    'redirect': '/offers'
                }
            )
        except User.DoesNotExist:
            pass

