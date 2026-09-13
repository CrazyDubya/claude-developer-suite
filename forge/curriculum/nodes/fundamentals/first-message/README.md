# Your First Message

**Category:** Fundamentals
**Difficulty:** 1/5
**Estimated Time:** 15 minutes
**Prerequisites:** [SDK Setup](../sdk-setup/), [API Key Management](../api-keys/)

---

## Learning Objectives

By the end of this node, you will:
- Send a message to Claude and receive a response
- Understand the basic message structure
- Handle the response object

---

## Concept Overview

The core interaction with Claude is the **messages API**. You send a list of messages, and Claude responds with a new message. This is the foundation of all Claude applications.

### Basic Message Flow

```
Your App → Messages API → Claude → Response → Your App
```

Every request needs:
1. **Model**: Which Claude model to use
2. **Max Tokens**: Maximum response length
3. **Messages**: The conversation so far

---

## Key Patterns

### Python: Simple Message

```python
from anthropic import Anthropic

client = Anthropic()

message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello, Claude! What's your name?"}
    ]
)

# Access the response text
print(message.content[0].text)
```

### TypeScript: Simple Message

```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

const message = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1024,
    messages: [
        { role: 'user', content: 'Hello, Claude! What\'s your name?' }
    ]
});

// Access the response text
console.log(message.content[0].text);
```

---

## Response Structure

The response object contains:

```python
message.id          # Unique message ID
message.type        # Always "message"
message.role        # Always "assistant" for responses
message.content     # List of content blocks
message.model       # Model that generated the response
message.stop_reason # Why generation stopped ("end_turn", "max_tokens", etc.)
message.usage       # Token usage information
```

### Content Blocks

The `content` field is a list because Claude can return multiple types of content:

```python
for block in message.content:
    if block.type == "text":
        print(block.text)
    elif block.type == "tool_use":
        # Handle tool calls (covered in Tools section)
        pass
```

---

## Common Pitfalls

1. **Forgetting max_tokens**: This parameter is required
2. **Accessing content incorrectly**: It's `message.content[0].text`, not `message.content`
3. **Wrong role**: User messages must have `role: "user"`

---

## Exercises

1. **Hello Claude** (`exercises/01_hello_claude.py`): Send your first message
2. **Token Counting** (`exercises/02_token_counting.py`): Examine the usage field
3. **Multiple Questions** (`exercises/03_multiple_questions.py`): Send several independent questions

---

## Next Steps

After completing this node, proceed to:
- [Message Structure](../../messaging/message-structure/) - Deep dive into message formatting
- [Streaming Responses](../../messaging/streaming/) - Real-time response handling
