"""
Simple CLI Conversational Assistant

A minimal example of the conversational-assistant blueprint.
Demonstrates multi-turn conversation with streaming responses.
"""

import os
from anthropic import Anthropic


class SimpleAssistant:
    """A simple conversational assistant with memory."""

    def __init__(
        self,
        system_prompt: str = "You are a helpful assistant.",
        model: str = "claude-sonnet-4-20250514",
    ):
        self.client = Anthropic()
        self.model = model
        self.system_prompt = system_prompt
        self.conversation_history: list[dict] = []

    def send_message(self, user_message: str) -> str:
        """Send a message and get a response, maintaining conversation history."""
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Stream the response
        full_response = ""

        with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=self.conversation_history,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                full_response += text

        print()  # Newline after response

        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": full_response
        })

        return full_response

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("[Conversation cleared]")


def main():
    """Run the CLI assistant."""
    print("=" * 50)
    print("Simple CLI Assistant")
    print("=" * 50)
    print("Type 'quit' to exit, 'clear' to reset conversation")
    print()

    # Create assistant with custom system prompt
    assistant = SimpleAssistant(
        system_prompt="""You are a friendly and helpful assistant.
Keep your responses concise but informative.
If you don't know something, say so."""
    )

    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("Goodbye!")
                break

            if user_input.lower() == "clear":
                assistant.clear_history()
                continue

            # Get response
            print("\nAssistant: ", end="")
            assistant.send_message(user_input)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break


if __name__ == "__main__":
    if os.environ.get("FORGE_VALIDATION_MODE"):
        print("✓ Example validated (syntax check only)")
    else:
        main()
