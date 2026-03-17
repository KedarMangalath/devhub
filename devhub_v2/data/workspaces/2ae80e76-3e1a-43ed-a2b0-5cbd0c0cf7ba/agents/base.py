import os
import json
from google import genai
from google.genai import types

class BaseAgent:
    """Base class for DevHub agents wrapping google-genai for the gemini-3.1-pro model."""
    
    def __init__(self, role: str, system_instruction: str, model: str = "gemini-3.1-pro"):
        self.role = role
        self.system_instruction = system_instruction
        self.model = model
        
        # We assume GOOGLE_API_KEY environment variable is set
        api_key = os.environ.get("GOOGLE_API_KEY")
        
        self.client = genai.Client(api_key=api_key)
        self.chat = None

    def _get_config(self, tools=None, response_schema=None) -> types.GenerateContentConfig:
        config_args = {
            "system_instruction": self.system_instruction,
            "temperature": 0.2, # Low temp for coding consistency
        }
        
        if tools:
            config_args["tools"] = tools
            
        if response_schema:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = response_schema
            
        return types.GenerateContentConfig(**config_args)

    def generate(self, prompt: str, tools=None, response_schema=None) -> str:
        """Single-turn generation."""
        config = self._get_config(tools, response_schema)
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return response.text

    def start_chat(self, history=None):
        """Starts a multi-turn chat session."""
        config = self._get_config()
        self.chat = self.client.chats.create(
            model=self.model,
            config=config,
            history=history if history else []
        )
        return self.chat

    def send_message(self, message: str) -> str:
        """Sends a message in an existing chat."""
        if not self.chat:
            self.start_chat()
            
        # The genai Chat object has send_message method
        response = self.chat.send_message(message)
        return response.text

    def parse_json(self, response_text: str) -> dict:
        """Utility to safely parse JSON from markdown code blocks in GenAI responses."""
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            inner: list[str] = []
            skip_first = True
            for line in lines:
                if skip_first and line.startswith("```"):
                    skip_first = False
                    continue
                if line.strip() == "```":
                    break
                inner.append(line)
            text = "\n".join(inner)
            
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nRaw text: {text}")
