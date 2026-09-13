"""
Your First Message to Claude

This example demonstrates the simplest possible interaction with Claude:
sending a single message and printing the response.
"""

import os

from anthropic import Anthropic


def send_first_message():
    """Send a simple greeting to Claude."""
    # Create the client (reads API key from environment)
    client = Anthropic()

    # Send a message
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Hello! Please introduce yourself in one sentence."
            }
        ]
    )

    # Print the response
    print("Claude says:")
    print(message.content[0].text)

    # Show some metadata
    print(f"\n--- Metadata ---")
    print(f"Model: {message.model}")
    print(f"Stop reason: {message.stop_reason}")
    print(f"Input tokens: {message.usage.input_tokens}")
    print(f"Output tokens: {message.usage.output_tokens}")


if __name__ == "__main__":
    # For validation mode, just verify the code is syntactically correct
    if os.environ.get("FORGE_VALIDATION_MODE"):
        print("✓ Example validated (syntax check only)")
    else:
        send_first_message()
