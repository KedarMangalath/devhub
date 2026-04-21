import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from agents.core.workspace import workspace_manager

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

import asyncio
from sandbox.executor import sandbox

class ProcessConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.workspace_id = self.scope['url_route']['kwargs']['workspace_id']
        self.process_id = self.scope['url_route']['kwargs']['process_id']
        self.room_group_name = f'process_{self.process_id}'
        
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        # Start background task to poll process output
        self.poll_task = asyncio.create_task(self.poll_process_output())

    async def disconnect(self, close_code):
        if hasattr(self, 'poll_task'):
            self.poll_task.cancel()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content):
        # Client sending input to the process (e.g. typing in terminal)
        input_data = content.get('input')
        if input_data:
            sandbox.send_input(self.process_id, input_data)

    async def poll_process_output(self):
        """Continuously polls the sandbox for output and sends it to the client"""
        try:
            while True:
                status = sandbox.get_status(self.process_id)
                output = sandbox.get_output(self.process_id)
                
                if output or not status.get('running', False):
                    await self.send_json({
                        'output': ''.join(output),
                        'status': status
                    })
                
                # If process died, send final status then stop polling
                if not status.get('running', False):
                    break
                    
                await asyncio.sleep(0.1) # 100ms poll loop (only inside async worker, no HTTP overhead)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"WebSocket process poll error: {e}")
