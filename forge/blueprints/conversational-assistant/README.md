# Conversational Assistant Blueprint

**Difficulty:** Beginner
**Category:** Conversational
**Estimated Time:** 2-4 hours

---

## Intent

Build a multi-turn conversational agent that maintains context, responds naturally, and can be customized for specific domains. This is the foundational pattern for chat-based applications.

---

## When to Use This Blueprint

✅ **Good fit:**
- Customer support chatbots
- Personal assistants
- Interactive tutors
- FAQ bots
- Domain-specific advisors

❌ **Consider another blueprint:**
- Heavy document processing → Document Processor
- Autonomous task completion → Agent blueprints
- Code assistance → Code Review Agent

---

## Capability Map

```
Required Skills                 Recommended Skills
─────────────────               ──────────────────
[first-message]      ─────────► [context-management]
       │                              │
       ▼                              ▼
[message-structure]            [error-handling]
       │
       ▼
[streaming] ────► [multi-turn]
       │               │
       ▼               ▼
[system-prompts]──────┘
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Your Application                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────┐    ┌──────────────┐               │
│  │   User       │    │  Assistant   │               │
│  │   Interface  │◄──►│   Core       │               │
│  └──────────────┘    └──────┬───────┘               │
│                             │                        │
│  ┌──────────────────────────┴───────────────────┐   │
│  │              Conversation Manager             │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │   │
│  │  │ History │  │ System  │  │   Context   │  │   │
│  │  │ Store   │  │ Prompt  │  │   Window    │  │   │
│  │  └─────────┘  └─────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────┘   │
│                             │                        │
│                             ▼                        │
│                    ┌────────────────┐               │
│                    │  Claude SDK    │               │
│                    │  (Streaming)   │               │
│                    └────────────────┘               │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Components

1. **User Interface**: Where users input messages (CLI, web, mobile)
2. **Assistant Core**: Main logic orchestrating the conversation
3. **Conversation Manager**: Handles history, system prompt, and context
4. **Claude SDK**: Streaming API integration

---

## Decision Points

When instantiating this blueprint, you'll need to decide:

| Decision | Options | Considerations |
|----------|---------|----------------|
| **Interface Type** | CLI, Web, API | CLI for prototypes, Web for users, API for integration |
| **Persistence** | In-memory, File, Database | In-memory for demos, persistent for production |
| **Streaming** | Yes / No | Yes for chat UX, No for background processing |
| **Context Strategy** | Full history, Sliding window, Summary | Trade-off between context and cost |
| **System Prompt** | Static, Dynamic, Hybrid | Static is simpler, dynamic for personalization |

---

## Validation Criteria

Your implementation is complete when:

- [ ] User can send messages and receive responses
- [ ] Conversation maintains context across turns
- [ ] System prompt shapes assistant behavior
- [ ] Streaming displays responses in real-time (if chosen)
- [ ] History persists across sessions (if persistence chosen)
- [ ] Graceful error handling for API failures
- [ ] Clean shutdown with conversation save

---

## Publication Targets

This blueprint can be published to:

- **npm/PyPI**: As a reusable library
- **Docker**: As a containerized service
- **CLI**: As a command-line tool
- **API**: As a REST/GraphQL endpoint

---

## File Structure

```
my-assistant/
├── src/
│   ├── main.py              # Entry point
│   ├── assistant.py         # Core assistant logic
│   ├── conversation.py      # Conversation management
│   ├── config.py            # Configuration
│   └── prompts/
│       └── system.txt       # System prompt
├── tests/
│   ├── test_assistant.py
│   └── test_conversation.py
├── requirements.txt
└── README.md
```

---

## Quick Start

1. Complete required curriculum nodes
2. Run: `claude` (in this directory)
3. Tell Claude Code: "Instantiate the conversational-assistant blueprint"
4. Answer the decision point questions
5. Review generated code
6. Customize for your use case

---

## Examples

See the `examples/` directory for:
- `simple_cli.py`: Basic command-line chat
- `web_api.py`: FastAPI-based web chat
- `persistent_chat.py`: Chat with file-based persistence
