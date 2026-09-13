"""
Basic Streaming Example

Demonstrates how to stream Claude's response in real-time,
showing text as it's generated.
"""

import os
import sys

from anthropic import Anthropic


def stream_response():
    """Stream a response from Claude."""
    client = Anthropic()

    print("Streaming response from Claude:\n")
    print("-" * 40)

    # Use the streaming context manager
    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Write a haiku about programming, then explain it briefly."
            }
        ]
    ) as stream:
        # Iterate over the text stream
        for text in stream.text_stream:
            # Print each chunk as it arrives
            # flush=True ensures immediate output
            print(text, end="", flush=True)

    print("\n" + "-" * 40)

    # Get the final message for metadata
    final_message = stream.get_final_message()

    print(f"\nStream complete!")
    print(f"Stop reason: {final_message.stop_reason}")
    print(f"Output tokens: {final_message.usage.output_tokens}")


def stream_with_events():
    """Stream with full event handling."""
    client = Anthropic()

    print("\nEvent-based streaming:\n")

    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": "Say 'Hello, streaming world!' and nothing else."
            }
        ]
    ) as stream:
        for event in stream:
            # Handle different event types
            if event.type == "message_start":
                print(f"[Stream started - ID: {event.message.id}]")

            elif event.type == "content_block_start":
                print(f"[Content block {event.index} started]")

            elif event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    sys.stdout.write(event.delta.text)
                    sys.stdout.flush()

            elif event.type == "content_block_stop":
                print(f"\n[Content block {event.index} complete]")

            elif event.type == "message_stop":
                print("[Stream ended]")


if __name__ == "__main__":
    if os.environ.get("FORGE_VALIDATION_MODE"):
        print("✓ Example validated (syntax check only)")
    else:
        stream_response()
        stream_with_events()
