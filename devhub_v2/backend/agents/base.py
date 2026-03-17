import os
import json
from openai import OpenAI
from pydantic import BaseModel

class BaseAgent:
    """Base class for DevHub agents wrapping openai for the gpt-4o-mini model."""
    
    def __init__(self, role: str, system_instruction: str, model: str = "gpt-4o-mini"):
        self.role = role
        self.system_instruction = system_instruction
        self.model = model
        
        # We assume OPENAI_API_KEY environment variable is set
        api_key = os.environ.get("OPENAI_API_KEY")
        
        self.client = OpenAI(api_key=api_key)
        self.chat_history = []

    def generate(self, prompt: str, tools=None, response_schema=None) -> str:
        """Single-turn generation."""
        messages = [
            {"role": "system", "content": self.system_instruction},
            {"role": "user", "content": prompt}
        ]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

        if response_schema:
            kwargs["response_format"] = { "type": "json_object" }

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def start_chat(self, history=None):
        """Starts a multi-turn chat session."""
        self.chat_history = history if history else []
        return self

    def send_message(self, message: str) -> str:
        """Sends a message in an existing chat."""
        messages = [
            {"role": "system", "content": self.system_instruction}
        ]
        
        # Add history
        for msg in self.chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
        messages.append({"role": "user", "content": message})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        
        reply = response.choices[0].message.content
        self.chat_history.append({"role": "user", "content": message})
        self.chat_history.append({"role": "assistant", "content": reply})
        
        return reply

    def parse_json(self, response_text: str) -> dict:
        """Utility to safely parse JSON from markdown code blocks in GenAI responses."""
        if not response_text:
            return {}
            
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            inner = []
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
