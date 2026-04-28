from .base_tool import BaseTool, ToolContext, ToolResult


class NarrateTool(BaseTool):
    name = "narrate"
    description = (
        "Share your current reasoning or observation with the user before taking action. "
        "Call this to explain what you're about to do or what you found. "
        "The thought is shown live as you work — use it to think out loud."
    )
    read_only = True

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Your current reasoning, observation, or plan.",
                },
            },
            "required": ["thought"],
        }

    def call(self, input_data: dict, context: ToolContext) -> ToolResult:
        return ToolResult(output=input_data.get("thought", ""))
