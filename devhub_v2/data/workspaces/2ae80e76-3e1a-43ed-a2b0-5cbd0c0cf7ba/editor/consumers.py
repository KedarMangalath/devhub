import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from agents.workspace import workspace_manager

class EditorConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.workspace_id = self.scope['url_route']['kwargs']['workspace_id']
        self.room_group_name = f'workspace_{self.workspace_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive_json(self, content):
        action = content.get('action')
        file_path = content.get('path')
        
        if action == 'edit':
            file_content = content.get('content')
            
            # Send message to room group so other clients update
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'editor_message',
                    'action': 'edit',
                    'path': file_path,
                    'content': file_content,
                    'sender': self.channel_name
                }
            )

    # Receive message from room group
    async def editor_message(self, event):
        # Don't echo back to sender
        if event.get('sender') == self.channel_name:
            return
            
        # Send message to WebSocket
        await self.send_json({
            'action': event['action'],
            'path': event['path'],
            'content': event.get('content')
        })
