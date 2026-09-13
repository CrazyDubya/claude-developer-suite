# Streaming Responses

**Category:** Messaging
**Difficulty:** 2/5
**Estimated Time:** 30 minutes
**Prerequisites:** [Message Structure](../message-structure/)

---

## Learning Objectives

By the end of this node, you will:
- Stream responses for real-time output
- Handle streaming events correctly
- Understand when to use streaming vs. non-streaming

---

## Concept Overview

Streaming allows you to receive Claude's response as it's generated, rather than waiting for the complete response. This is essential for:

- **User Experience**: Show responses appearing in real-time
- **Long Responses**: Start processing before completion
- **Timeouts**: Avoid long waits that might trigger timeouts

### Streaming Flow

```
Request → Stream Opens → Text Delta Events → Stream Closes
              ↓               ↓                  ↓
         message_start    content_block     message_stop
                          _delta
```

---

## Key Patterns

### Python: Basic Streaming

```python
from anthropic import Anthropic

client = Anthropic()

with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Tell me a short story."}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

print()  # Newline at end
```

### Python: Event-Based Streaming

For more control, handle individual events:

```python
from anthropic import Anthropic

client = Anthropic()

with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Tell me a short story."}]
) as stream:
    for event in stream:
        if event.type == "content_block_delta":
            if event.delta.type == "text_delta":
                print(event.delta.text, end="", flush=True)
        elif event.type == "message_stop":
            print("\n[Stream complete]")

# Get the final message after streaming
final_message = stream.get_final_message()
print(f"Total tokens: {final_message.usage.output_tokens}")
```

### TypeScript: Basic Streaming

```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

const stream = await client.messages.stream({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1024,
    messages: [{ role: 'user', content: 'Tell me a short story.' }]
});

for await (const chunk of stream) {
    if (chunk.type === 'content_block_delta' &&
        chunk.delta.type === 'text_delta') {
        process.stdout.write(chunk.delta.text);
    }
}

const finalMessage = await stream.finalMessage();
console.log(`\nTotal tokens: ${finalMessage.usage.output_tokens}`);
```

---

## Event Types

| Event | Description |
|-------|-------------|
| `message_start` | Stream beginning, contains message metadata |
| `content_block_start` | New content block beginning |
| `content_block_delta` | Incremental content (text or tool use) |
| `content_block_stop` | Content block complete |
| `message_delta` | Final message metadata (stop reason, usage) |
| `message_stop` | Stream complete |

---

## Common Pitfalls

1. **Forgetting flush**: Use `flush=True` to ensure immediate output
2. **Not handling all events**: Some events don't have text content
3. **Missing final message**: Call `get_final_message()` for complete usage stats

---

## When to Use Streaming

| Use Case | Streaming? | Reason |
|----------|------------|--------|
| Chat interface | ✓ Yes | Better UX |
| Background processing | ✗ No | Simpler code |
| Long-form generation | ✓ Yes | Avoid timeouts |
| Quick Q&A | ✗ No | Minimal benefit |

---

## Exercises

1. **Basic Stream** (`exercises/01_basic_stream.py`): Stream a response to console
2. **Event Inspector** (`exercises/02_event_inspector.py`): Log all event types
3. **Progress Indicator** (`exercises/03_progress.py`): Show typing indicator during generation

---

## Next Steps

After completing this node, proceed to:
- [Multi-turn Conversations](../multi-turn/) - Maintain conversation context
- [Context Management](../context-management/) - Handle long conversations
