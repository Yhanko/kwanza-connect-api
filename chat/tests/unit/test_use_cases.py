import pytest
import uuid
from unittest.mock import Mock
from datetime import datetime
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from chat.services.use_cases import (
    GetUserRoomsUseCase, GetRoomMessagesUseCase, SendMessageUseCase,
    DeleteMessageUseCase, MarkRoomAsReadUseCase
)
from chat.domain.entities import RoomEntity, RoomMemberEntity, MessageEntity
from chat.domain.interfaces import IChatRepository
from app.services.websocket_service import IWebSocketService
from app.services.storage import IStorageService

def test_get_user_rooms():
    mock_repo = Mock(spec=IChatRepository)
    use_case = GetUserRoomsUseCase(repository=mock_repo)
    user_id = uuid.uuid4()
    
    use_case.execute(user_id)
    mock_repo.list_user_rooms.assert_called_once_with(user_id)

def test_get_room_messages_success():
    mock_repo = Mock(spec=IChatRepository)
    user_id = uuid.uuid4()
    room_id = uuid.uuid4()
    
    mock_repo.get_member_by_room_and_user.return_value = Mock(spec=RoomMemberEntity)
    
    use_case = GetRoomMessagesUseCase(repository=mock_repo)
    use_case.execute(user_id, room_id)
    
    mock_repo.list_room_messages.assert_called_once_with(room_id, 50, None)

def test_get_room_messages_forbidden():
    mock_repo = Mock(spec=IChatRepository)
    mock_repo.get_member_by_room_and_user.return_value = None
    
    use_case = GetRoomMessagesUseCase(repository=mock_repo)
    with pytest.raises(PermissionDenied):
        use_case.execute(uuid.uuid4(), uuid.uuid4())

def test_send_message_success():
    mock_repo = Mock(spec=IChatRepository)
    mock_ws = Mock(spec=IWebSocketService)
    
    user_id = uuid.uuid4()
    room_id = uuid.uuid4()
    
    room = Mock(spec=RoomEntity)
    room.is_active.return_value = True
    
    mock_repo.get_room_by_id.return_value = room
    mock_repo.get_member_by_room_and_user.return_value = Mock(spec=RoomMemberEntity)
    mock_repo.save_message.side_effect = lambda m: m
    
    use_case = SendMessageUseCase(repository=mock_repo, ws_service=mock_ws)
    message = use_case.execute(user_id, room_id, {'content': 'Hello!'})
    
    assert message.room_id == room_id
    assert message.content == 'Hello!'
    assert message.sender_id == user_id
    mock_repo.save_message.assert_called_once()
    mock_ws.send_to_room.assert_called_once()

def test_send_message_room_closed():
    mock_repo = Mock(spec=IChatRepository)
    
    room = Mock(spec=RoomEntity)
    room.is_active.return_value = False
    
    mock_repo.get_room_by_id.return_value = room
    mock_repo.get_member_by_room_and_user.return_value = Mock(spec=RoomMemberEntity)
    
    use_case = SendMessageUseCase(repository=mock_repo)
    with pytest.raises(ValidationError) as exc:
        use_case.execute(uuid.uuid4(), uuid.uuid4(), {'content': 'Hello!'})
    
    assert "encerrada" in str(exc.value)

def test_send_message_not_member():
    mock_repo = Mock(spec=IChatRepository)
    room_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    room = Mock(spec=RoomEntity)
    room.is_active.return_value = True
    mock_repo.get_room_by_id.return_value = room
    mock_repo.get_member_by_room_and_user.return_value = None
    
    use_case = SendMessageUseCase(repository=mock_repo)
    
    with pytest.raises(PermissionDenied):
        use_case.execute(user_id, room_id, {'content': 'hi'})


def test_delete_message_success():
    mock_repo = Mock(spec=IChatRepository)
    user_id = uuid.uuid4()
    message = MessageEntity(
        id=uuid.uuid4(), room_id=uuid.uuid4(), sender_id=user_id, 
        content="Hello", msg_type="text"
    )
    mock_repo.get_message_by_id.return_value = message
    
    use_case = DeleteMessageUseCase(repository=mock_repo)
    use_case.execute(user_id, message.id)
    
    assert message.is_deleted is True
    assert message.content == ""
    mock_repo.save_message.assert_called_once_with(message)

def test_delete_message_forbidden():
    mock_repo = Mock(spec=IChatRepository)
    message = MessageEntity(
        id=uuid.uuid4(), room_id=uuid.uuid4(), sender_id=uuid.uuid4(), 
        content="Hello", msg_type="text"
    )
    mock_repo.get_message_by_id.return_value = message
    
    use_case = DeleteMessageUseCase(repository=mock_repo)
    with pytest.raises(PermissionDenied):
        use_case.execute(uuid.uuid4(), message.id)

def test_mark_room_as_read_success():
    mock_repo = Mock(spec=IChatRepository)
    mock_ws = Mock(spec=IWebSocketService)
    user_id = uuid.uuid4()
    room_id = uuid.uuid4()
    
    member = RoomMemberEntity(id=uuid.uuid4(), room_id=room_id, user_id=user_id)
    mock_repo.get_member_by_room_and_user.return_value = member
    
    use_case = MarkRoomAsReadUseCase(repository=mock_repo, ws_service=mock_ws)
    use_case.execute(user_id, room_id)
    
    assert member.last_read_at is not None
    mock_repo.save_member.assert_called_once_with(member)
    mock_ws.send_to_user.assert_called_once()
