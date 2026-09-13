# Streaming Techniques Reference

This directory contains reference implementations for streaming patterns with the Claude SDK.

## Overview

Streaming allows you to receive Claude's response as it's generated, improving user experience and enabling real-time processing.

## Files

- `basic_stream.py` - Simple streaming to console
- `event_handling.py` - Full event-based streaming with all event types
- `async_streaming.py` - Async/await streaming patterns
- `stream_to_ui.py` - Streaming to web UIs (SSE pattern)

## Key Patterns

### Basic Streaming

```python
with client.messages.stream(...) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

### Event-Based Streaming

```python
with client.messages.stream(...) as stream:
    for event in stream:
        match event.type:
            case "message_start":
                # Initialize
            case "content_block_delta":
                # Process chunk
            case "message_stop":
                # Finalize
```

### Async Streaming

```python
async with client.messages.stream(...) as stream:
    async for text in stream.text_stream:
        yield text
```

## Best Practices

1. Always use `flush=True` when printing streamed text
2. Handle all event types, even if just to ignore them
3. Get the final message for accurate usage stats
4. Consider connection timeouts for long streams
