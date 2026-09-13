# SDK Setup

**Category:** Fundamentals
**Difficulty:** 1/5
**Estimated Time:** 15 minutes
**Prerequisites:** None

---

## Learning Objectives

By the end of this node, you will:
- Install the Claude SDK for Python or TypeScript
- Verify your installation is working
- Understand the SDK's basic structure

---

## Concept Overview

The Claude SDK provides a clean, type-safe interface to interact with Claude's API. It handles:
- Authentication and request signing
- Request/response serialization
- Streaming connections
- Error handling and retries

### Python Installation

```bash
pip install anthropic
```

### TypeScript Installation

```bash
npm install @anthropic-ai/sdk
```

---

## Key Patterns

### Python Client Initialization

```python
from anthropic import Anthropic

# The client reads ANTHROPIC_API_KEY from environment by default
client = Anthropic()

# Or pass the key explicitly
client = Anthropic(api_key="your-key-here")
```

### TypeScript Client Initialization

```typescript
import Anthropic from '@anthropic-ai/sdk';

// Reads ANTHROPIC_API_KEY from environment by default
const client = new Anthropic();

// Or pass the key explicitly
const client = new Anthropic({ apiKey: 'your-key-here' });
```

---

## Common Pitfalls

1. **Missing API Key**: The SDK will raise an error if no API key is found
2. **Wrong Python Version**: Requires Python 3.8+
3. **Network Issues**: Ensure your environment can reach `api.anthropic.com`

---

## Exercises

1. **Basic Setup** (`exercises/01_basic_setup.py`): Install the SDK and verify the version
2. **Environment Check** (`exercises/02_env_check.py`): Verify your environment is configured correctly

---

## Next Steps

After completing this node, proceed to:
- [API Key Management](../api-keys/) - Learn secure API key handling
