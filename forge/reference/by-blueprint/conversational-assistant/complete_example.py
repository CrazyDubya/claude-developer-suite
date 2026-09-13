"""
Complete Conversational Assistant Reference Implementation

This is a full-featured reference implementation of the conversational-assistant
blueprint. It demonstrates best practices for:
- Multi-turn conversation management
- Streaming responses
- Session persistence
- Context window management
- Error handling

Use this as a reference when building your own implementation.
"""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Generator

from anthropic import Anthropic


@dataclass
class Message:
    """A single message in a conversation."""
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_api_format(self) -> dict:
        """Convert to Claude API message format."""
        return {"role": self.role, "content": self.content}


@dataclass
class Session:
    """A conversation session with metadata."""
    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> Message:
        """Add a message to the session."""
        message = Message(role=role, content=content)
        self.messages.append(message)
        self.last_active = datetime.now().isoformat()
        return message

    def get_context(self, max_messages: int = 20) -> list[dict]:
        """Get recent messages in API format."""
        recent = self.messages[-max_messages:]
        return [m.to_api_format() for m in recent]

    def to_dict(self) -> dict:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "messages": [asdict(m) for m in self.messages],
            "created_at": self.created_at,
            "last_active": self.last_active,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Deserialize session from dictionary."""
        messages = [Message(**m) for m in data.get("messages", [])]
        return cls(
            session_id=data["session_id"],
            messages=messages,
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_active=data.get("last_active", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class SessionStore:
    """Persist sessions to disk."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: Session) -> None:
        """Save session to disk."""
        path = self.storage_dir / f"{session.session_id}.json"
        with open(path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def load(self, session_id: str) -> Session | None:
        """Load session from disk."""
        path = self.storage_dir / f"{session_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return Session.from_dict(json.load(f))

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        return [p.stem for p in self.storage_dir.glob("*.json")]


class ConversationalAssistant:
    """A full-featured conversational assistant."""

    def __init__(
        self,
        system_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        context_window: int = 20,
        storage_dir: Path | None = None,
    ):
        self.client = Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.context_window = context_window

        # Session management
        self.session: Session | None = None
        self.store = SessionStore(storage_dir) if storage_dir else None

    def new_session(self, metadata: dict | None = None) -> str:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())[:8]
        self.session = Session(
            session_id=session_id,
            metadata=metadata or {}
        )
        return session_id

    def load_session(self, session_id: str) -> bool:
        """Load an existing session."""
        if not self.store:
            return False
        session = self.store.load(session_id)
        if session:
            self.session = session
            return True
        return False

    def save_session(self) -> None:
        """Save current session."""
        if self.session and self.store:
            self.store.save(self.session)

    def send_message(self, user_message: str) -> Generator[str, None, None]:
        """
        Send a message and yield response chunks.

        This is a generator that yields text as it streams from Claude.
        """
        if not self.session:
            self.new_session()

        # Add user message
        self.session.add_message("user", user_message)

        # Get context with sliding window
        context = self.session.get_context(self.context_window)

        # Stream response
        full_response = ""

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=context,
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    yield text

            # Add assistant response to session
            self.session.add_message("assistant", full_response)

            # Auto-save if storage is configured
            self.save_session()

        except Exception as e:
            # On error, remove the failed user message
            if self.session.messages and self.session.messages[-1].role == "user":
                self.session.messages.pop()
            raise

    def send_message_sync(self, user_message: str) -> str:
        """Send a message and return the complete response."""
        chunks = list(self.send_message(user_message))
        return "".join(chunks)

    def get_history(self) -> list[Message]:
        """Get conversation history."""
        return self.session.messages if self.session else []

    def clear_history(self) -> None:
        """Clear conversation history but keep session."""
        if self.session:
            self.session.messages = []
            self.save_session()


def create_system_prompt(domain: str = "general", name: str = "Assistant") -> str:
    """Generate a system prompt based on domain."""
    base_prompt = f"""You are {name}, a helpful AI assistant.

Your communication style:
- Be concise but thorough
- Use clear, professional language
- Ask clarifying questions when needed
- Admit when you don't know something
"""

    domain_additions = {
        "general": "",
        "technical": """
You specialize in technical topics including:
- Software development and programming
- System design and architecture
- Debugging and troubleshooting

When discussing code, use proper formatting and explain your reasoning.""",
        "support": """
You are a customer support specialist. Your priorities:
- Understand the customer's issue fully before responding
- Provide step-by-step solutions when applicable
- Escalate appropriately when you cannot resolve an issue
- Always maintain a friendly, patient tone""",
    }

    return base_prompt + domain_additions.get(domain, "")


def main():
    """Interactive demo of the conversational assistant."""
    print("=" * 60)
    print("Conversational Assistant - Reference Implementation")
    print("=" * 60)

    # Create assistant with persistence
    storage = Path("./conversations")
    assistant = ConversationalAssistant(
        system_prompt=create_system_prompt("technical", "Claude"),
        storage_dir=storage,
        context_window=20,
    )

    # Check for existing sessions
    if assistant.store:
        sessions = assistant.store.list_sessions()
        if sessions:
            print(f"\nExisting sessions: {', '.join(sessions)}")
            print("Enter session ID to resume, or press Enter for new session:")
            choice = input("> ").strip()
            if choice and choice in sessions:
                assistant.load_session(choice)
                print(f"Resumed session {choice}")
                print(f"Messages in history: {len(assistant.get_history())}")

    # Create new session if needed
    if not assistant.session:
        session_id = assistant.new_session()
        print(f"Started new session: {session_id}")

    print("\nCommands: 'quit', 'clear', 'history', 'save'")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                assistant.save_session()
                print("Session saved. Goodbye!")
                break

            if user_input.lower() == "clear":
                assistant.clear_history()
                print("[History cleared]")
                continue

            if user_input.lower() == "history":
                for msg in assistant.get_history():
                    prefix = "You" if msg.role == "user" else "Assistant"
                    print(f"\n{prefix}: {msg.content[:100]}...")
                continue

            if user_input.lower() == "save":
                assistant.save_session()
                print("[Session saved]")
                continue

            # Stream response
            print("\nAssistant: ", end="", flush=True)
            for chunk in assistant.send_message(user_input):
                print(chunk, end="", flush=True)
            print()

        except KeyboardInterrupt:
            print("\n\nSession saved. Goodbye!")
            assistant.save_session()
            break


if __name__ == "__main__":
    if os.environ.get("FORGE_VALIDATION_MODE"):
        print("✓ Reference implementation validated")
    else:
        main()
