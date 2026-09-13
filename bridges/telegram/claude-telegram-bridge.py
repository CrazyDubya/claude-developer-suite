#!/usr/bin/env python3
"""
Claude Code <-> Telegram Bridge v10
Self-Healing Infrastructure with Graceful Shutdown, Watchdog, and Atomic Rollback

Changes in v10:
- **GRACEFUL SHUTDOWN**: Async-aware SIGTERM/SIGINT — saves checkpoint before exit
- **SELF-CONTAINED ROLLBACK**: Auto-detects previous version, falls back on startup failure
- **STARTUP RECOVERY**: Restores offset and state from checkpoint after crash/restart
- **WATCHDOG INTEGRATION**: Heartbeat file + companion echo-watchdog.sh for auto-restart
- **SHUTDOWN NOTIFICATION**: Tells Stephen via Telegram when going down and coming back up
- Inherits ALL v9 features: async architecture, vector memory, plugins, multi-model,
  dream mode, research loops, circuit breaker, health registry, atomic checkpoint

v9 features (inherited):
- Full asyncio with PriorityQueue (P0=user, P1=scheduled, P2=background)
- ChromaDB + sentence-transformers for semantic retrieval
- Plugin hot-reload with circuit breaker protection
- Multi-model orchestration (Gemini/GPT-5/Qwen) with shared context
- APScheduler + psutil for proactive health alerts
- Dream mode and autonomous research loops
- Per-conversation locks, all blocking calls in asyncio.to_thread()
"""

__all__ = [
    'BridgeConfig', 'DatabaseManager', 'TelegramClient', 'ClaudeInterface',
    'TelegramBridge', 'Session', 'Message', 'Attachment',
    'VectorMemory', 'PluginManager', 'ModelOrchestrator',
    'SchedulerManager', 'DreamEngine', 'ResearchEngine'
]

import os
import sys
import json
import time
import signal
import logging
import sqlite3
import asyncio
import subprocess
import hashlib
import mimetypes
import threading
import importlib
import inspect
import math
import uuid as uuid_module
from queue import Queue, Empty
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Protocol, runtime_checkable
from dataclasses import dataclass, asdict, field
from contextlib import contextmanager
from enum import Enum
from functools import partial
from collections import defaultdict

import aiohttp
import aiosqlite
import httpx
import psutil

# ============ CONFIGURATION ============

CONFIG_DIR = Path.home() / ".claude-bridge"
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_FILE = CONFIG_DIR / "bridge.db"
LOG_FILE = CONFIG_DIR / "bridge.log"
PID_FILE = CONFIG_DIR / "bridge.pid"
INCOMING_DIR = Path.home() / "incoming"
ATTACHMENTS_DIR = CONFIG_DIR / "attachments"
SKILLS_DIR = CONFIG_DIR / "skills"
CHROMA_DIR = CONFIG_DIR / "chroma_data"
DREAM_DIR = CONFIG_DIR / "dream_journal"
HEARTBEAT_FILE = CONFIG_DIR / "heartbeat"
CHECKPOINT_FILE = CONFIG_DIR / "checkpoint.json"
IMPORTANT_DATES_FILE = CONFIG_DIR / "important_dates.json"

for d in [CONFIG_DIR, INCOMING_DIR, ATTACHMENTS_DIR, SKILLS_DIR, CHROMA_DIR, DREAM_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============ LOGGING SETUP ============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ ENUMS ============

class AttachmentType(Enum):
    IMAGE = "image"
    DOCUMENT = "document"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"

class SessionState(Enum):
    ACTIVE = "active"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"

class Priority(Enum):
    """Message priority levels for the async queue"""
    USER = 0       # User messages — always first
    SCHEDULED = 1  # Scheduled tasks
    BACKGROUND = 2 # Background work (research, dream)

class ResearchState(Enum):
    """State machine for autonomous research"""
    PLANNING = "planning"
    SEARCHING = "searching"
    READING = "reading"
    SYNTHESIZING = "synthesizing"
    REPORTING = "reporting"
    PAUSED = "paused"
    COMPLETE = "complete"
    ABORTED = "aborted"

# ============ DATA MODELS ============

@dataclass
class BridgeConfig:
    telegram_bot_token: str
    allowed_chat_id: str
    claude_path: str = "claude"
    max_context_items: int = 15
    max_context_chars: int = 8000
    message_timeout: int = 600
    retry_attempts: int = 3
    health_check_interval: int = 60
    enable_attachments: bool = True
    max_attachment_size: int = 20 * 1024 * 1024
    # v9 additions
    memory_decay_lambda: float = 0.01  # Temporal decay rate for memories
    dream_max_clusters: int = 10
    research_max_cycles: int = 3
    research_max_urls: int = 10

    @classmethod
    def load(cls) -> 'BridgeConfig':
        config_data = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config_data = json.load(f)

        config_data['telegram_bot_token'] = os.getenv('TELEGRAM_BOT_TOKEN', config_data.get('telegram_bot_token', ''))
        config_data['allowed_chat_id'] = os.getenv('ALLOWED_CHAT_ID', config_data.get('allowed_chat_id', ''))

        if not config_data['telegram_bot_token'] or not config_data['allowed_chat_id']:
            raise ValueError("Missing required configuration: TELEGRAM_BOT_TOKEN and ALLOWED_CHAT_ID")

        return cls(**{k: v for k, v in config_data.items() if k in cls.__annotations__})

    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(asdict(self), f, indent=2)

@dataclass
class Attachment:
    attachment_id: str
    attachment_type: AttachmentType
    file_path: Path
    file_name: str
    file_size: int
    mime_type: str
    created_at: datetime

@dataclass
class Message:
    chat_id: str
    text: str
    message_id: int
    user_id: str
    timestamp: datetime
    attachments: List[Attachment] = field(default_factory=list)
    reply_to_message_id: Optional[int] = None
    thread_id: Optional[str] = None

@dataclass
class Session:
    chat_id: str
    session_id: str
    context: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    state: SessionState = SessionState.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_messages: int = 0
    total_tokens_estimate: int = 0

@dataclass
class QueueItem:
    """Item in the async priority queue"""
    priority: int
    timestamp: float
    handler: Any  # coroutine to execute
    chat_id: str
    description: str = ""

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

# ============ SKILL PROTOCOL ============

@runtime_checkable
class SkillProtocol(Protocol):
    name: str
    triggers: list

    async def execute(self, ctx: Dict[str, Any]) -> str: ...
    async def cleanup(self) -> None: ...

# ============ DATABASE MANAGER ============

class DatabaseManager:
    """Async-capable database manager"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._sync_init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _sync_init_db(self):
        """Initialize database schema (sync, called once at startup)"""
        with self.get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    chat_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    context TEXT,
                    state TEXT DEFAULT 'active',
                    metadata TEXT,
                    total_messages INTEGER DEFAULT 0,
                    total_tokens_estimate INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    user_text TEXT,
                    assistant_text TEXT,
                    reply_to_message_id INTEGER,
                    thread_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES sessions(chat_id)
                );

                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attachment_id TEXT UNIQUE NOT NULL,
                    message_id INTEGER NOT NULL,
                    attachment_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES messages(id)
                );

                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    stack_trace TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT,
                    description TEXT,
                    cron_expression TEXT,
                    task_name TEXT,
                    task_params TEXT,
                    last_run TIMESTAMP,
                    next_run TIMESTAMP,
                    active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS dream_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    themes TEXT,
                    insights TEXT,
                    memories_processed INTEGER,
                    memories_archived INTEGER DEFAULT 0,
                    user_rating TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS research_tasks (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT,
                    objective TEXT,
                    state TEXT DEFAULT 'planning',
                    findings TEXT,
                    report TEXT,
                    urls_visited TEXT,
                    cycles_completed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS memory_metadata (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    conversation_id TEXT,
                    timestamp REAL,
                    importance REAL DEFAULT 1.0,
                    tags TEXT,
                    archived BOOLEAN DEFAULT 0,
                    retrieval_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat
                ON messages(chat_id, timestamp DESC);

                CREATE INDEX IF NOT EXISTS idx_messages_thread
                ON messages(thread_id, timestamp ASC);

                CREATE INDEX IF NOT EXISTS idx_attachments_message
                ON attachments(message_id);

                CREATE INDEX IF NOT EXISTS idx_errors_timestamp
                ON errors(timestamp DESC);

                CREATE INDEX IF NOT EXISTS idx_memory_source
                ON memory_metadata(source, archived);

                CREATE INDEX IF NOT EXISTS idx_memory_timestamp
                ON memory_metadata(timestamp DESC);
            ''')

    def save_session(self, session: Session):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO sessions
                (chat_id, session_id, context, state, metadata, total_messages,
                 total_tokens_estimate, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session.chat_id, session.session_id,
                json.dumps(session.context), session.state.value,
                json.dumps(session.metadata), session.total_messages,
                session.total_tokens_estimate,
                session.created_at.isoformat(), session.updated_at.isoformat()
            ))

    def get_session(self, chat_id: str) -> Optional[Session]:
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM sessions WHERE chat_id = ?', (chat_id,)).fetchone()
            if row:
                return Session(
                    chat_id=row['chat_id'], session_id=row['session_id'],
                    context=json.loads(row['context']) if row['context'] else [],
                    state=SessionState(row['state']),
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    total_messages=row['total_messages'],
                    total_tokens_estimate=row['total_tokens_estimate'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )
            return None

    def save_message(self, chat_id: str, message_id: int, user_text: str,
                    assistant_text: str, reply_to: Optional[int] = None,
                    thread_id: Optional[str] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO messages
                (chat_id, message_id, user_text, assistant_text, reply_to_message_id, thread_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, message_id, user_text, assistant_text, reply_to, thread_id))
            return cursor.lastrowid

    def save_attachment(self, attachment: Attachment, db_message_id: int):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO attachments
                (attachment_id, message_id, attachment_type, file_path,
                 file_name, file_size, mime_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                attachment.attachment_id, db_message_id,
                attachment.attachment_type.value, str(attachment.file_path),
                attachment.file_name, attachment.file_size,
                attachment.mime_type, attachment.created_at.isoformat()
            ))

    def get_thread_messages(self, thread_id: str, limit: int = 10) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM messages WHERE thread_id = ?
                ORDER BY timestamp ASC LIMIT ?
            ''', (thread_id, limit)).fetchall()
            return [dict(row) for row in rows]

    def log_error(self, chat_id: Optional[str], error_type: str,
                 error_message: str, stack_trace: Optional[str] = None):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO errors (chat_id, error_type, error_message, stack_trace)
                VALUES (?, ?, ?, ?)
            ''', (chat_id, error_type, error_message, stack_trace))

    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM errors ORDER BY timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    def cleanup_old_attachments(self, days: int = 30):
        cutoff = datetime.now() - timedelta(days=days)
        with self.get_connection() as conn:
            rows = conn.execute(
                'SELECT file_path FROM attachments WHERE created_at < ?',
                (cutoff.isoformat(),)
            ).fetchall()
            for row in rows:
                try:
                    Path(row['file_path']).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to delete attachment: {e}")
            conn.execute('DELETE FROM attachments WHERE created_at < ?', (cutoff.isoformat(),))

    # === v9 Memory metadata methods ===

    def save_memory_metadata(self, memory_id: str, source: str, conversation_id: str = "",
                            importance: float = 1.0, tags: List[str] = None):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO memory_metadata
                (id, source, conversation_id, timestamp, importance, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (memory_id, source, conversation_id, time.time(), importance,
                  json.dumps(tags or [])))

    def get_memory_metadata(self, memory_id: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM memory_metadata WHERE id = ?', (memory_id,)).fetchone()
            return dict(row) if row else None

    def increment_retrieval_count(self, memory_ids: List[str]):
        with self.get_connection() as conn:
            for mid in memory_ids:
                conn.execute(
                    'UPDATE memory_metadata SET retrieval_count = retrieval_count + 1 WHERE id = ?',
                    (mid,)
                )

    def archive_memories(self, memory_ids: List[str]):
        with self.get_connection() as conn:
            for mid in memory_ids:
                conn.execute('UPDATE memory_metadata SET archived = 1 WHERE id = ?', (mid,))

    def get_archivable_memories(self, max_age_days: int = 30, max_results: int = 20) -> List[Dict]:
        cutoff = time.time() - (max_age_days * 86400)
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM memory_metadata
                WHERE archived = 0 AND timestamp < ? AND retrieval_count <= 1
                    AND importance <= 0.5
                ORDER BY timestamp ASC LIMIT ?
            ''', (cutoff, max_results)).fetchall()
            return [dict(row) for row in rows]

    # === Schedule methods ===

    def save_schedule(self, schedule_id: str, chat_id: str, description: str,
                     cron_expr: str, task_name: str, task_params: Dict = None):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO schedules
                (id, chat_id, description, cron_expression, task_name, task_params)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (schedule_id, chat_id, description, cron_expr, task_name,
                  json.dumps(task_params or {})))

    def get_active_schedules(self, chat_id: str = None) -> List[Dict]:
        with self.get_connection() as conn:
            if chat_id:
                rows = conn.execute(
                    'SELECT * FROM schedules WHERE active = 1 AND chat_id = ?', (chat_id,)
                ).fetchall()
            else:
                rows = conn.execute('SELECT * FROM schedules WHERE active = 1').fetchall()
            return [dict(row) for row in rows]

    def deactivate_schedule(self, schedule_id: str):
        with self.get_connection() as conn:
            conn.execute('UPDATE schedules SET active = 0 WHERE id = ?', (schedule_id,))

    # === Dream journal methods ===

    def save_dream(self, chat_id: str, themes: List[str], insights: List[str],
                  memories_processed: int, memories_archived: int = 0) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO dream_journal
                (chat_id, themes, insights, memories_processed, memories_archived)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, json.dumps(themes), json.dumps(insights),
                  memories_processed, memories_archived))
            return cursor.lastrowid

    def get_recent_dreams(self, chat_id: str, limit: int = 5) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM dream_journal WHERE chat_id = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (chat_id, limit)).fetchall()
            return [dict(row) for row in rows]

    def rate_dream(self, dream_id: int, rating: str):
        with self.get_connection() as conn:
            conn.execute('UPDATE dream_journal SET user_rating = ? WHERE id = ?', (rating, dream_id))

    # === Research task methods ===

    def save_research_task(self, task_id: str, chat_id: str, objective: str,
                          state: str = "planning", findings: List = None,
                          report: str = "", urls: List[str] = None, cycles: int = 0):
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO research_tasks
                (id, chat_id, objective, state, findings, report, urls_visited,
                 cycles_completed, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, chat_id, objective, state, json.dumps(findings or []),
                  report, json.dumps(urls or []), cycles, datetime.now().isoformat()))

    def get_research_task(self, task_id: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM research_tasks WHERE id = ?', (task_id,)).fetchone()
            return dict(row) if row else None

    def get_active_research(self, chat_id: str) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM research_tasks
                WHERE chat_id = ? AND state NOT IN ('complete', 'aborted')
                ORDER BY updated_at DESC
            ''', (chat_id,)).fetchall()
            return [dict(row) for row in rows]


# ============ VECTOR MEMORY ============

class VectorMemory:
    """
    Semantic memory using ChromaDB + sentence-transformers.
    Temporal decay ensures old memories fade unless marked important.
    """

    def __init__(self, db: DatabaseManager, decay_lambda: float = 0.01):
        self.db = db
        self.decay_lambda = decay_lambda
        self._collection = None
        self._embed_model = None
        self._available = False
        self._init_attempted = False

    async def initialize(self):
        """Initialize ChromaDB and embedding model (async-safe)"""
        if self._init_attempted:
            return self._available
        self._init_attempted = True

        try:
            result = await asyncio.to_thread(self._sync_initialize)
            return result
        except Exception as e:
            logger.error(f"Vector memory init failed: {e}")
            self._available = False
            return False

    def _sync_initialize(self) -> bool:
        """Synchronous initialization (run in thread)"""
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            # Initialize ChromaDB
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            self._collection = client.get_or_create_collection(
                name="echo_v9",
                metadata={"hnsw:space": "cosine"}
            )

            # Initialize embedding model
            self._embed_model = SentenceTransformer('all-MiniLM-L6-v2')

            self._available = True
            count = self._collection.count()
            logger.info(f"✅ Vector memory initialized ({count} memories)")
            return True

        except ImportError as e:
            logger.warning(f"Vector memory dependencies missing: {e}")
            return False
        except Exception as e:
            logger.error(f"Vector memory init error: {e}")
            return False

    @property
    def available(self) -> bool:
        return self._available

    async def store(self, text: str, source: str = "chat",
                   conversation_id: str = "", importance: float = 1.0,
                   tags: List[str] = None) -> Optional[str]:
        """Store a memory with embedding"""
        if not self._available:
            return None

        memory_id = str(uuid_module.uuid4())

        try:
            # Generate embedding in thread
            embedding = await asyncio.to_thread(
                self._embed_model.encode, text, convert_to_numpy=True
            )

            # Store in ChromaDB
            await asyncio.to_thread(
                self._collection.add,
                ids=[memory_id],
                embeddings=[embedding.tolist()],
                documents=[text],
                metadatas=[{
                    "source": source,
                    "conversation_id": conversation_id,
                    "timestamp": time.time(),
                    "importance": importance
                }]
            )

            # Store metadata in SQLite
            await asyncio.to_thread(
                self.db.save_memory_metadata,
                memory_id, source, conversation_id, importance, tags
            )

            return memory_id

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return None

    async def retrieve(self, query: str, k: int = 10,
                      source_filter: str = None,
                      include_archived: bool = False) -> List[Dict]:
        """Retrieve memories by semantic similarity with temporal decay"""
        if not self._available:
            return []

        try:
            # Generate query embedding
            query_embedding = await asyncio.to_thread(
                self._embed_model.encode, query, convert_to_numpy=True
            )

            # Query ChromaDB
            where_filter = {}
            if source_filter:
                where_filter["source"] = source_filter

            results = await asyncio.to_thread(
                self._collection.query,
                query_embeddings=[query_embedding.tolist()],
                n_results=min(k * 2, 50),  # Over-fetch for decay re-ranking
                where=where_filter if where_filter else None,
                include=["documents", "metadatas", "distances"]
            )

            if not results['ids'][0]:
                return []

            # Apply temporal decay and re-rank
            now = time.time()
            scored_results = []

            for i, memory_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                timestamp = metadata.get('timestamp', now)
                importance = metadata.get('importance', 1.0)
                distance = results['distances'][0][i]

                # Cosine similarity (ChromaDB returns distance, lower = more similar)
                similarity = max(0, 1 - distance)

                # Temporal decay
                age_days = (now - timestamp) / 86400
                decay = math.exp(-self.decay_lambda * age_days)

                # Final score
                score = similarity * decay * importance

                # Check if archived
                if not include_archived:
                    meta = await asyncio.to_thread(self.db.get_memory_metadata, memory_id)
                    if meta and meta.get('archived'):
                        continue

                scored_results.append({
                    'id': memory_id,
                    'text': results['documents'][0][i],
                    'score': score,
                    'similarity': similarity,
                    'decay': decay,
                    'importance': importance,
                    'source': metadata.get('source', 'unknown'),
                    'age_days': age_days
                })

            # Sort by score and return top k
            scored_results.sort(key=lambda x: x['score'], reverse=True)
            top_results = scored_results[:k]

            # Increment retrieval counts
            if top_results:
                await asyncio.to_thread(
                    self.db.increment_retrieval_count,
                    [r['id'] for r in top_results]
                )

            return top_results

        except Exception as e:
            logger.error(f"Memory retrieval error: {e}")
            return []

    async def compress_context(self, memories: List[Dict], query: str,
                              claude_ask_fn) -> str:
        """Compress retrieved memories into a clean context paragraph"""
        if not memories:
            return ""

        memory_texts = "\n".join([
            f"- [{m['source']}, {m['age_days']:.0f}d ago, score={m['score']:.2f}]: {m['text'][:300]}"
            for m in memories[:10]
        ])

        compress_prompt = (
            f"Synthesize these retrieved memories into a concise, relevant context "
            f"paragraph for a user asking about: {query}\n\n"
            f"Memories:\n{memory_texts}\n\n"
            f"Write a clean 2-4 sentence summary of the relevant context. "
            f"Do not explain what you're doing — just output the summary."
        )

        try:
            result, success = await claude_ask_fn(compress_prompt, timeout=30)
            if success and result:
                return f"\n[Relevant context from memory]: {result}\n"
        except Exception as e:
            logger.debug(f"Context compression failed: {e}")

        # Fallback: raw memory snippets
        return "\n[Relevant memories]:\n" + "\n".join(
            [f"- {m['text'][:200]}" for m in memories[:5]]
        ) + "\n"

    async def get_cluster_data(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """Get recent memories for clustering (used by dream mode)"""
        if not self._available:
            return []

        try:
            cutoff = time.time() - (days * 86400)
            results = await asyncio.to_thread(
                self._collection.get,
                where={"timestamp": {"$gte": cutoff}},
                include=["documents", "metadatas", "embeddings"],
                limit=limit
            )

            if not results['ids']:
                return []

            memories = []
            for i, memory_id in enumerate(results['ids']):
                memories.append({
                    'id': memory_id,
                    'text': results['documents'][i],
                    'metadata': results['metadatas'][i],
                    'embedding': results['embeddings'][i] if results.get('embeddings') else None
                })

            return memories

        except Exception as e:
            logger.error(f"Failed to get cluster data: {e}")
            return []

    async def get_stats(self) -> Dict:
        """Get memory statistics"""
        if not self._available:
            return {"available": False}

        try:
            count = await asyncio.to_thread(self._collection.count)
            return {
                "available": True,
                "total_memories": count,
                "storage_path": str(CHROMA_DIR)
            }
        except Exception as e:
            return {"available": True, "error": str(e)}


# ============ TELEGRAM CLIENT (Async) ============

class TelegramClient:
    """Async Telegram client using aiohttp"""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def create_reply_keyboard(self, buttons: List[List[str]],
                            resize: bool = True, one_time: bool = False) -> Dict:
        return {
            "keyboard": [[{"text": btn} for btn in row] for row in buttons],
            "resize_keyboard": resize,
            "one_time_keyboard": one_time
        }

    def create_inline_keyboard(self, buttons: List[List[Dict[str, str]]]) -> Dict:
        return {"inline_keyboard": buttons}

    def remove_keyboard(self) -> Dict:
        return {"remove_keyboard": True}

    async def get_updates(self, offset: int = 0, timeout: int = 30) -> List[Dict]:
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/getUpdates",
                params={"offset": offset, "timeout": timeout},
                timeout=aiohttp.ClientTimeout(total=timeout + 10)
            ) as response:
                data = await response.json()
                if data.get("ok"):
                    return data.get("result", [])
                logger.error(f"Telegram API error: {data}")
                return []
        except Exception as e:
            logger.error(f"Failed to get updates: {e}")
            return []

    async def send_message(self, chat_id: str, text: str,
                          reply_markup: Optional[Dict] = None, **kwargs) -> bool:
        max_length = 4000

        if reply_markup:
            kwargs['reply_markup'] = reply_markup

        if len(text) > max_length:
            chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            success = True
            for i, chunk in enumerate(chunks):
                chunk_kwargs = kwargs if i == len(chunks) - 1 else {
                    k: v for k, v in kwargs.items() if k != 'reply_markup'
                }
                success = success and await self._send_chunk(chat_id, chunk, **chunk_kwargs)
                await asyncio.sleep(0.5)
            return success
        else:
            return await self._send_chunk(chat_id, text, **kwargs)

    async def _send_chunk(self, chat_id: str, text: str, **kwargs) -> bool:
        try:
            session = await self._get_session()
            payload = {"chat_id": chat_id, "text": text, **kwargs}
            async with session.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_document(self, chat_id: str, file_path: Path) -> bool:
        try:
            if not file_path.exists() or file_path.stat().st_size > 50 * 1024 * 1024:
                return False

            session = await self._get_session()
            data = aiohttp.FormData()
            data.add_field('chat_id', chat_id)
            data.add_field('document', open(file_path, 'rb'), filename=file_path.name)

            async with session.post(
                f"{self.base_url}/sendDocument",
                data=data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                result = await response.json()
                return result.get("ok", False)
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False

    async def download_file(self, file_id: str, destination: Path) -> bool:
        try:
            session = await self._get_session()

            async with session.get(
                f"{self.base_url}/getFile",
                params={"file_id": file_id}
            ) as response:
                data = await response.json()
                if not data.get("ok"):
                    return False
                file_path = data["result"]["file_path"]

            file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            async with session.get(file_url) as response:
                with open(destination, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return False

    async def answer_callback(self, callback_id: str):
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/answerCallbackQuery",
                json={"callback_query_id": callback_id}
            ) as response:
                pass
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")


# ============ CLAUDE INTERFACE ============

class ClaudeState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"
    RECOVERING = "recovering"

@dataclass
class StreamMessage:
    type: str
    subtype: Optional[str] = None
    content: Optional[str] = None
    session_id: Optional[str] = None
    is_error: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)

class ClaudeInterface:
    """
    Stream-JSON Claude CLI interface with async ask method.
    The actual I/O with the subprocess uses threads (subprocess is inherently blocking),
    but the ask() method is async-compatible.
    """

    def __init__(self, claude_path: str = "claude"):
        self.claude_path = claude_path
        self.process: Optional[subprocess.Popen] = None
        self.lock = asyncio.Lock()
        self.state = ClaudeState.IDLE
        self.session_id: Optional[str] = None
        self.pending_messages: Queue = Queue()
        self.reader_thread: Optional[threading.Thread] = None
        self.reader_running = False

    async def start_session(self, resume: bool = False):
        """Start Claude CLI (runs subprocess setup in thread)"""
        await asyncio.to_thread(self._sync_start_session, resume)

    def _sync_start_session(self, resume: bool = False):
        cmd = [
            self.claude_path,
            "--permission-mode", "bypassPermissions",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose", "--print"
        ]

        if resume and self.session_id:
            cmd.extend(["--resume", self.session_id])
            logger.info(f"Resuming Claude session: {self.session_id}")
        else:
            logger.info("Starting fresh Claude session with stream-json protocol")

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_CODE_ENTRYPOINT", None)

        try:
            self.process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1, env=env
            )

            self.reader_running = True
            self.reader_thread = threading.Thread(target=self._read_stdout, daemon=True)
            self.reader_thread.start()
            self.state = ClaudeState.IDLE
            logger.info(f"Claude session ready (PID: {self.process.pid})")

        except Exception as e:
            logger.error(f"Failed to start Claude session: {e}")
            raise

    def _read_stdout(self):
        while self.reader_running and self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msg = self._parse_message(data)
                    self.pending_messages.put(msg)
                    if msg.type == "system" and msg.subtype == "init":
                        self.session_id = msg.session_id
                        logger.info(f"Session ID captured: {self.session_id}")
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON output: {line[:100]}")
            except Exception as e:
                if self.reader_running:
                    logger.error(f"Reader thread error: {e}")
        self.reader_running = False

    def _parse_message(self, data: Dict[str, Any]) -> StreamMessage:
        msg_type = data.get("type", "unknown")
        subtype = data.get("subtype")
        content = None
        session_id = data.get("session_id")
        is_error = data.get("is_error", False)

        if msg_type == "result":
            content = data.get("result", "")
        elif msg_type == "assistant":
            message = data.get("message", {})
            content_blocks = message.get("content", [])
            texts = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            content = "".join(texts)

        return StreamMessage(
            type=msg_type, subtype=subtype, content=content,
            session_id=session_id, is_error=is_error, raw=data
        )

    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    async def restart_session(self):
        logger.warning("Claude session died, attempting recovery...")
        self.state = ClaudeState.RECOVERING
        self.reader_running = False
        if self.process:
            try:
                self.process.terminate()
                await asyncio.to_thread(self.process.wait, 5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
        while not self.pending_messages.empty():
            try:
                self.pending_messages.get_nowait()
            except:
                break
        await self.start_session(resume=True)
        logger.info(f"Session recovered, new PID: {self.process.pid}")

    async def ask(self, prompt: str, system_prompt: Optional[str] = None,
                 attachments: List[Attachment] = None, session_id: Optional[str] = None,
                 timeout: int = 600) -> Tuple[str, bool]:
        """Async ask — uses lock to serialize access to the Claude process"""
        async with self.lock:
            if not self.is_alive():
                await self.start_session(resume=bool(self.session_id))

            try:
                enhanced_prompt = prompt
                if attachments:
                    attachment_paths = []
                    for att in attachments:
                        if att.attachment_type in [AttachmentType.IMAGE, AttachmentType.PHOTO]:
                            attachment_paths.append(str(att.file_path))
                        elif att.attachment_type == AttachmentType.DOCUMENT:
                            enhanced_prompt += f"\n[Attached document: {att.file_name}]"
                    if attachment_paths:
                        enhanced_prompt = " ".join(attachment_paths) + "\n\n" + enhanced_prompt

                if system_prompt:
                    enhanced_prompt = f"[SYSTEM]: {system_prompt}\n\n{enhanced_prompt}"

                input_msg = {
                    "type": "user",
                    "message": {"role": "user", "content": enhanced_prompt},
                    "uuid": str(uuid_module.uuid4())
                }

                logger.info(f"Sending to Claude session (PID: {self.process.pid})")

                # Write to stdin in thread (blocking I/O)
                await asyncio.to_thread(self._sync_write, json.dumps(input_msg) + "\n")
                self.state = ClaudeState.PROCESSING

                # Wait for result in thread
                return await asyncio.to_thread(self._sync_wait_for_result, timeout)

            except Exception as e:
                logger.error(f"Error in ask(): {e}", exc_info=True)
                self.state = ClaudeState.ERROR
                return f"Error: {str(e)}", False

    def _sync_write(self, data: str):
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def _sync_wait_for_result(self, timeout: int) -> Tuple[str, bool]:
        start_time = time.time()
        collected_content = []

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                self.state = ClaudeState.ERROR
                return f"Request timed out after {timeout}s", False

            try:
                remaining = max(0.1, timeout - elapsed)
                msg = self.pending_messages.get(timeout=min(remaining, 5.0))

                if msg.type == "result":
                    self.state = ClaudeState.COMPLETE
                    if msg.subtype == "success":
                        result = "".join(collected_content) if collected_content else (msg.content or "No response")
                        logger.info(f"Response complete ({len(result)} chars)")
                        return result, True
                    elif msg.subtype == "error_during_execution":
                        errors = msg.raw.get("errors", [])
                        error_msg = str(errors[0]) if errors else "Execution error"
                        return f"Error: {error_msg}", False
                    elif msg.subtype == "error_max_turns":
                        if collected_content:
                            return "".join(collected_content), True
                        return "Reached maximum turns", False
                    else:
                        if collected_content:
                            return "".join(collected_content), True
                        return msg.content or "Unknown result", True

                elif msg.type == "assistant" and msg.content:
                    collected_content.append(msg.content)

            except Empty:
                if self.process and self.process.poll() is not None:
                    self.state = ClaudeState.ERROR
                    return "Claude process terminated unexpectedly", False
                continue

    async def shutdown(self):
        logger.info("Shutting down Claude session...")
        self.reader_running = False
        if self.process and self.is_alive():
            try:
                exit_msg = {"type": "exit"}
                await asyncio.to_thread(self._sync_write, json.dumps(exit_msg) + "\n")
                await asyncio.to_thread(self.process.wait, 5)
            except:
                try:
                    self.process.terminate()
                    await asyncio.to_thread(self.process.wait, 5)
                except:
                    self.process.kill()
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2)
        logger.info("Claude session shut down")


# ============ PLUGIN MANAGER ============

class PluginManager:
    """Hot-reload plugin system with file watching"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills: Dict[str, Any] = {}
        self._watcher_task: Optional[asyncio.Task] = None
        self._file_hashes: Dict[str, str] = {}
        self._circuit_breaker: Optional[CircuitBreaker] = None  # Set by bridge after init

    async def start(self):
        """Start watching skills directory"""
        await self._load_existing_skills()
        self._watcher_task = asyncio.create_task(self._watch_loop())
        logger.info(f"Plugin manager started, watching {self.skills_dir}")

    async def stop(self):
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass

    async def _load_existing_skills(self):
        """Load all .py files in skills directory"""
        if not self.skills_dir.exists():
            return

        for py_file in self.skills_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            await self._load_skill(py_file)

    async def _load_skill(self, path: Path):
        """Load or reload a single skill file (with circuit breaker protection)"""
        # Circuit breaker check — stop retrying if we've failed too many times
        if self._circuit_breaker and not self._circuit_breaker.allow_request():
            return  # Circuit is open, skip until cooldown

        try:
            # Compute hash
            content = await asyncio.to_thread(path.read_text)
            file_hash = hashlib.md5(content.encode()).hexdigest()

            # Skip if unchanged
            if self._file_hashes.get(path.name) == file_hash:
                return

            # Validate syntax first
            import ast
            try:
                ast.parse(content)
            except SyntaxError as e:
                logger.error(f"Syntax error in {path.name}: {e}")
                return

            # Load module (import directly since skills_dir is in sys.path)
            module_name = path.stem

            if module_name in sys.modules:
                # Cleanup old skill
                old_module = sys.modules[module_name]
                if hasattr(old_module, 'cleanup'):
                    try:
                        cleanup = old_module.cleanup
                        if asyncio.iscoroutinefunction(cleanup):
                            await cleanup()
                        else:
                            await asyncio.to_thread(cleanup)
                    except Exception as e:
                        logger.warning(f"Skill cleanup error: {e}")

                # Remove and reload
                del sys.modules[module_name]

            # Add skills dir AND its parent to path (fixes package imports)
            skills_str = str(self.skills_dir)
            parent_str = str(self.skills_dir.parent)
            if skills_str not in sys.path:
                sys.path.insert(0, skills_str)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)

            module = await asyncio.to_thread(importlib.import_module, module_name)

            # Register skill
            self.skills[path.stem] = module
            self._file_hashes[path.name] = file_hash
            logger.info(f"✅ Loaded skill: {path.stem}")

            # Record success on circuit breaker
            if self._circuit_breaker:
                self._circuit_breaker.record_success()

        except Exception as e:
            logger.error(f"Failed to load skill {path.name}: {e}")
            if self._circuit_breaker:
                self._circuit_breaker.record_failure(str(e))

    async def _watch_loop(self):
        """Simple polling watcher for skill file changes"""
        while True:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                if not self.skills_dir.exists():
                    continue

                current_files = set()
                for py_file in self.skills_dir.glob("*.py"):
                    if py_file.name.startswith("_"):
                        continue
                    current_files.add(py_file.name)
                    await self._load_skill(py_file)

                # Detect removed skills
                for name in list(self.skills.keys()):
                    if f"{name}.py" not in current_files:
                        del self.skills[name]
                        self._file_hashes.pop(f"{name}.py", None)
                        sys.modules.pop(name, None)
                        logger.info(f"Removed skill: {name}")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Plugin watcher error: {e}")

    def get_skill_list(self) -> List[str]:
        return list(self.skills.keys())

    async def execute_skill(self, name: str, ctx: Dict[str, Any]) -> Optional[str]:
        """Execute a skill by name"""
        if name not in self.skills:
            return None
        module = self.skills[name]
        if hasattr(module, 'execute'):
            fn = module.execute
            if asyncio.iscoroutinefunction(fn):
                return await fn(ctx)
            else:
                return await asyncio.to_thread(fn, ctx)
        return None


# ============ MODEL ORCHESTRATOR ============

class ModelOrchestrator:
    """
    Multi-model orchestration with shared context.
    Models get relevant memory context so they aren't starting cold.
    """

    MODELS = {
        'gemini': {'cmd': ['gemini', '-p'], 'name': 'Gemini', 'available': False},
        'gpt5': {'cmd': ['codex', 'exec', '--skip-git-repo-check'], 'name': 'GPT-5', 'available': False},
        'qwen': {'cmd': ['qwen', '-p'], 'name': 'Qwen', 'available': False},
    }

    def __init__(self, vector_memory: VectorMemory):
        self.memory = vector_memory

    async def check_availability(self):
        """Check which models are available"""
        for key, model in self.MODELS.items():
            try:
                cmd = model['cmd'][0]
                result = await asyncio.to_thread(
                    subprocess.run, ['which', cmd],
                    capture_output=True, text=True, timeout=5
                )
                model['available'] = result.returncode == 0
                if model['available']:
                    logger.info(f"✅ {model['name']} CLI available")
            except Exception:
                model['available'] = False

    async def query_model(self, model_key: str, prompt: str,
                         context: str = "", timeout: int = 120) -> Tuple[str, bool]:
        """Query a single external model with shared context"""
        if model_key not in self.MODELS or not self.MODELS[model_key]['available']:
            return f"Model {model_key} not available", False

        model = self.MODELS[model_key]
        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        try:
            cmd = model['cmd'] + [full_prompt]
            result = await asyncio.to_thread(
                subprocess.run, cmd,
                capture_output=True, text=True, timeout=timeout
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    return output, True

            return f"{model['name']} returned no output", False

        except subprocess.TimeoutExpired:
            return f"{model['name']} timed out after {timeout}s", False
        except Exception as e:
            return f"{model['name']} error: {str(e)}", False

    async def query_all(self, prompt: str, context: str = "",
                       timeout: int = 120) -> Dict[str, Tuple[str, bool]]:
        """Query all available models in parallel"""
        tasks = {}
        for key, model in self.MODELS.items():
            if model['available']:
                tasks[key] = asyncio.create_task(
                    self.query_model(key, prompt, context, timeout)
                )

        results = {}
        for key, task in tasks.items():
            try:
                results[key] = await task
            except Exception as e:
                results[key] = (f"Error: {str(e)}", False)

        return results

    async def build_shared_context(self, query: str) -> str:
        """Build shared context from vector memory for external models"""
        if not self.memory.available:
            return ""

        memories = await self.memory.retrieve(query, k=5)
        if not memories:
            return ""

        context_parts = ["=== Relevant Context ==="]
        for m in memories:
            context_parts.append(f"[{m['source']}, {m['age_days']:.0f}d ago]: {m['text'][:200]}")
        context_parts.append("=== End Context ===")

        return "\n".join(context_parts)

    def get_available_models(self) -> List[str]:
        return [k for k, v in self.MODELS.items() if v['available']]


# ============ SCHEDULER MANAGER ============

class SchedulerManager:
    """Proactive monitoring + scheduled tasks with natural language support"""

    def __init__(self, db: DatabaseManager, telegram: TelegramClient, chat_id: str):
        self.db = db
        self.telegram = telegram
        self.chat_id = chat_id
        self._jobs: Dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self):
        """Start the scheduler"""
        self._running = True
        # Load persisted schedules
        schedules = await asyncio.to_thread(self.db.get_active_schedules, self.chat_id)
        for sched in schedules:
            logger.info(f"Loaded schedule: {sched['description']}")
        logger.info(f"Scheduler started with {len(schedules)} active schedules")

    async def stop(self):
        self._running = False
        for task in self._jobs.values():
            task.cancel()

    async def run_health_check(self) -> str:
        """Run system health check"""
        checks = {}

        # CPU
        cpu = await asyncio.to_thread(psutil.cpu_percent, interval=1)
        checks['CPU'] = (cpu < 90, f"{cpu}%")

        # Memory
        mem = await asyncio.to_thread(lambda: psutil.virtual_memory())
        checks['Memory'] = (mem.percent < 90, f"{mem.percent}% ({mem.available // (1024**3)}GB free)")

        # Disk
        disk = await asyncio.to_thread(lambda: psutil.disk_usage('/'))
        checks['Disk'] = (disk.percent < 90, f"{disk.percent}% ({disk.free // (1024**3)}GB free)")

        # Load average
        load = await asyncio.to_thread(os.getloadavg)
        cpu_count = await asyncio.to_thread(lambda: psutil.cpu_count())
        load_ok = load[0] < cpu_count * 2
        checks['Load'] = (load_ok, f"{load[0]:.1f} / {load[1]:.1f} / {load[2]:.1f}")

        # Format result
        lines = ["🏥 Health Check\n"]
        all_ok = True
        for name, (ok, msg) in checks.items():
            icon = "✅" if ok else "❌"
            lines.append(f"{icon} {name}: {msg}")
            all_ok = all_ok and ok

        lines.append(f"\n{'✨ All systems operational' if all_ok else '⚠️ Issues detected'}")
        return "\n".join(lines)


# ============ DREAM ENGINE ============

class DreamEngine:
    """
    Human-triggered deep reflection mode.
    /dream starts a thorough analysis cycle.
    """

    def __init__(self, memory: VectorMemory, db: DatabaseManager,
                 claude_ask_fn, telegram: TelegramClient, chat_id: str):
        self.memory = memory
        self.db = db
        self.claude_ask = claude_ask_fn
        self.telegram = telegram
        self.chat_id = chat_id
        self._active = False
        self._task: Optional[asyncio.Task] = None

    @property
    def is_active(self) -> bool:
        return self._active

    async def start_dream(self, depth: str = "normal", days: int = 7):
        """Start a dream/reflection cycle"""
        if self._active:
            await self.telegram.send_message(self.chat_id, "💭 Already dreaming. Use /dream status to check progress.")
            return

        self._active = True
        self._task = asyncio.create_task(self._dream_cycle(depth, days))

    async def stop_dream(self):
        if self._task:
            self._task.cancel()
            self._active = False

    async def _dream_cycle(self, depth: str, days: int):
        """The full dream/reflection cycle"""
        try:
            await self.telegram.send_message(
                self.chat_id,
                f"💭 Entering dream mode...\n"
                f"Depth: {depth} | Looking back: {days} days\n"
                f"This may take a few minutes."
            )

            # Phase 1: Gather memories
            await self.telegram.send_message(self.chat_id, "🔍 Phase 1/5: Gathering recent memories...")
            memories = await self.memory.get_cluster_data(days=days, limit=200 if depth == "deep" else 100)

            if not memories:
                await self.telegram.send_message(self.chat_id, "💭 Not enough memories to reflect on yet. Keep chatting!")
                self._active = False
                return

            await self.telegram.send_message(
                self.chat_id,
                f"📊 Found {len(memories)} memories to process."
            )

            # Phase 2: Cluster (simple approach without HDBSCAN dependency)
            await self.telegram.send_message(self.chat_id, "🧩 Phase 2/5: Finding themes and patterns...")

            memory_texts = "\n".join([
                f"[{m['metadata'].get('source', 'unknown')}]: {m['text'][:200]}"
                for m in memories[:50]  # Cap for prompt size
            ])

            cluster_prompt = (
                f"Analyze these {len(memories)} conversation snippets from the past {days} days. "
                f"Identify 3-7 major themes/clusters. For each theme, give:\n"
                f"1. Theme name\n"
                f"2. Number of related memories\n"
                f"3. Key topics within the theme\n\n"
                f"Snippets:\n{memory_texts}\n\n"
                f"Format as a structured list."
            )

            themes_result, success = await self.claude_ask(cluster_prompt, timeout=60)
            if not success:
                await self.telegram.send_message(self.chat_id, f"⚠️ Theme analysis failed: {themes_result}")
                self._active = False
                return

            await self.telegram.send_message(self.chat_id, f"🧩 Themes identified:\n{themes_result[:1000]}")

            # Phase 3: Generate insights
            await self.telegram.send_message(self.chat_id, "💡 Phase 3/5: Generating insights...")

            insight_prompt = (
                f"Based on these themes from the past {days} days:\n\n"
                f"{themes_result}\n\n"
                f"And these raw memories:\n{memory_texts}\n\n"
                f"Generate deep insights:\n"
                f"1. Recurring patterns the user might not notice\n"
                f"2. Unresolved threads that need attention\n"
                f"3. Cross-topic connections (unexpected links)\n"
                f"4. One actionable suggestion\n"
                f"5. What questions keep coming up?\n\n"
                f"Be specific and reference actual content. Format as bullet points."
            )

            insights_result, success = await self.claude_ask(insight_prompt, timeout=60)

            # Phase 4: Identify archivable memories
            await self.telegram.send_message(self.chat_id, "🗂️ Phase 4/5: Identifying stale memories...")

            archivable = await asyncio.to_thread(self.db.get_archivable_memories, days * 2, 20)
            archive_msg = f"Found {len(archivable)} low-value memories that could be archived."

            # Phase 5: Compile and present
            await self.telegram.send_message(self.chat_id, "📝 Phase 5/5: Compiling dream journal...")

            themes_list = themes_result.split('\n')[:10] if themes_result else ["No themes found"]
            insights_list = insights_result.split('\n')[:15] if insights_result else ["No insights generated"]

            # Save to database
            dream_id = await asyncio.to_thread(
                self.db.save_dream, self.chat_id,
                themes_list, insights_list,
                len(memories), len(archivable)
            )

            # Present results
            journal = (
                f"📖 Dream Journal Entry #{dream_id}\n"
                f"{'='*30}\n\n"
                f"🧩 **Themes Found:**\n{themes_result[:1500]}\n\n"
                f"💡 **Insights:**\n{insights_result[:1500]}\n\n"
                f"🗂️ **Memory Maintenance:**\n{archive_msg}\n\n"
                f"Rate this reflection:\n"
                f"Reply with: ✓ (helpful) | ✗ (not useful) | 📌 (save as important)"
            )

            await self.telegram.send_message(self.chat_id, journal)

            # Store insights as new memories
            if insights_result:
                await self.memory.store(
                    f"Dream reflection ({datetime.now().strftime('%Y-%m-%d')}): {insights_result[:500]}",
                    source="dream_insight",
                    importance=1.5
                )

        except asyncio.CancelledError:
            await self.telegram.send_message(self.chat_id, "💭 Dream mode cancelled.")
        except Exception as e:
            logger.error(f"Dream cycle error: {e}", exc_info=True)
            await self.telegram.send_message(self.chat_id, f"⚠️ Dream cycle error: {str(e)[:200]}")
        finally:
            self._active = False


# ============ RESEARCH ENGINE ============

class ResearchEngine:
    """
    Autonomous research loops with state machine.
    Human-triggered via /research command.
    """

    def __init__(self, memory: VectorMemory, db: DatabaseManager,
                 claude_ask_fn, orchestrator: ModelOrchestrator,
                 telegram: TelegramClient, chat_id: str, config: BridgeConfig):
        self.memory = memory
        self.db = db
        self.claude_ask = claude_ask_fn
        self.orchestrator = orchestrator
        self.telegram = telegram
        self.chat_id = chat_id
        self.config = config
        self._active_tasks: Dict[str, asyncio.Task] = {}

    async def start_research(self, objective: str) -> str:
        """Start a new research task"""
        task_id = str(uuid_module.uuid4())[:8]

        await asyncio.to_thread(
            self.db.save_research_task,
            task_id, self.chat_id, objective
        )

        task = asyncio.create_task(self._research_loop(task_id, objective))
        self._active_tasks[task_id] = task

        await self.telegram.send_message(
            self.chat_id,
            f"🔍 Research started: {objective}\n"
            f"Task ID: {task_id}\n"
            f"Use /research status to check progress."
        )

        return task_id

    async def pause_research(self, task_id: str):
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            await asyncio.to_thread(
                self.db.save_research_task,
                task_id, self.chat_id, "", "paused"
            )

    async def abort_research(self, task_id: str):
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            del self._active_tasks[task_id]
            await asyncio.to_thread(
                self.db.save_research_task,
                task_id, self.chat_id, "", "aborted"
            )

    async def _research_loop(self, task_id: str, objective: str):
        """Main research loop"""
        try:
            findings = []
            urls_visited = []

            for cycle in range(self.config.research_max_cycles):
                # Phase: PLANNING
                await self.telegram.send_message(
                    self.chat_id,
                    f"🔍 Research [{task_id}] Cycle {cycle+1}/{self.config.research_max_cycles}: Planning..."
                )

                plan_prompt = (
                    f"Research objective: {objective}\n"
                    f"Previous findings: {json.dumps(findings[-5:]) if findings else 'None yet'}\n\n"
                    f"Generate 3-5 specific web search queries to investigate this. "
                    f"Return ONLY the queries, one per line."
                )

                plan_result, success = await self.claude_ask(plan_prompt, timeout=30)
                if not success:
                    break

                queries = [q.strip().strip('"').strip("'").strip('- ') for q in plan_result.strip().split('\n') if q.strip()][:5]

                # Phase: SEARCHING
                await self.telegram.send_message(
                    self.chat_id,
                    f"🔎 Searching with {len(queries)} queries..."
                )

                # Use Claude's web search capability
                for query in queries:
                    search_prompt = f"Search the web for: {query}\nSummarize the top 3-5 relevant findings. Include source URLs."
                    search_result, success = await self.claude_ask(search_prompt, timeout=60)
                    if success and search_result:
                        findings.append({
                            'query': query,
                            'result': search_result[:1000],
                            'cycle': cycle
                        })
                        # Store finding in memory
                        await self.memory.store(
                            f"Research finding for '{objective}': {search_result[:500]}",
                            source="research",
                            tags=["research", task_id]
                        )

                urls_visited.extend(queries)

                # Phase: SYNTHESIZING
                await self.telegram.send_message(
                    self.chat_id,
                    f"🧪 Synthesizing findings from cycle {cycle+1}..."
                )

                # Check if objective is answered
                check_prompt = (
                    f"Objective: {objective}\n\n"
                    f"Findings so far:\n"
                    + "\n".join([f"- {f['result'][:300]}" for f in findings[-10:]])
                    + f"\n\nIs this objective sufficiently answered? "
                    f"Reply YES or NO, followed by a brief explanation."
                )

                check_result, _ = await self.claude_ask(check_prompt, timeout=30)
                if check_result and check_result.strip().upper().startswith("YES"):
                    break

            # Phase: REPORTING
            await self.telegram.send_message(self.chat_id, f"📝 Compiling final report...")

            report_prompt = (
                f"Compile a comprehensive research report.\n\n"
                f"Objective: {objective}\n\n"
                f"All findings:\n"
                + "\n".join([f"Query: {f['query']}\nResult: {f['result']}" for f in findings])
                + f"\n\nWrite a clear, structured report with:\n"
                f"1. Executive Summary\n"
                f"2. Key Findings\n"
                f"3. Analysis\n"
                f"4. Conclusions\n"
                f"5. Open Questions (if any)\n"
                f"Be thorough but concise."
            )

            report, success = await self.claude_ask(report_prompt, timeout=120)

            # Save final state
            await asyncio.to_thread(
                self.db.save_research_task,
                task_id, self.chat_id, objective, "complete",
                findings, report or "Report generation failed",
                urls_visited, len(urls_visited)
            )

            # Store report in memory
            if report:
                await self.memory.store(
                    f"Research report on '{objective}': {report[:1000]}",
                    source="research_report",
                    importance=2.0,
                    tags=["research", "report", task_id]
                )

            await self.telegram.send_message(self.chat_id, f"📋 Research Report [{task_id}]\n\n{report or 'No report generated'}")

        except asyncio.CancelledError:
            await self.telegram.send_message(self.chat_id, f"⏸️ Research [{task_id}] paused/cancelled.")
        except Exception as e:
            logger.error(f"Research loop error: {e}", exc_info=True)
            await self.telegram.send_message(self.chat_id, f"⚠️ Research error: {str(e)[:200]}")
        finally:
            self._active_tasks.pop(task_id, None)


# ============ SELF-DEPLOYMENT (v10: Self-Contained) ============

class SelfDeploymentManager:
    """Self-contained deployment and rollback — no external deployer needed."""
    BRIDGE_DIR = Path.home()

    @staticmethod
    def get_current_version() -> int:
        import re
        current_file = Path(__file__).name
        match = re.search(r'v(\d+)', current_file)
        return int(match.group(1)) if match else 10

    @staticmethod
    def find_previous_version() -> Optional[Path]:
        """Find the highest-versioned bridge file below current version."""
        import re
        current = SelfDeploymentManager.get_current_version()
        candidates = []
        for f in SelfDeploymentManager.BRIDGE_DIR.glob("claude-telegram-bridge-v*.py"):
            match = re.search(r'v(\d+)', f.name)
            if match:
                ver = int(match.group(1))
                if ver < current:
                    candidates.append((ver, f))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    @staticmethod
    def create_new_version(new_code: str) -> int:
        current = SelfDeploymentManager.get_current_version()
        new_version = current + 1
        new_path = SelfDeploymentManager.BRIDGE_DIR / f"claude-telegram-bridge-v{new_version}.py"
        new_path.write_text(new_code)
        new_path.chmod(0o755)
        logger.info(f"Created new version: v{new_version}")
        return new_version

    @staticmethod
    async def rollback() -> Tuple[bool, str]:
        """Self-contained rollback: find previous version, start it, exit self."""
        prev = SelfDeploymentManager.find_previous_version()
        if not prev:
            return False, "No previous version found to roll back to"

        logger.warning(f"⏪ Rolling back to {prev.name}...")
        try:
            # Start the previous version as a detached process
            subprocess.Popen(
                [sys.executable, str(prev)],
                stdout=open(LOG_FILE, 'a'),
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            logger.info(f"✅ Rollback started: {prev.name} (detached)")
            return True, f"Rolled back to {prev.name}"
        except Exception as e:
            return False, f"Rollback launch failed: {str(e)}"


# ============ CIRCUIT BREAKER ============

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation — requests pass through
    OPEN = "open"          # Failures exceeded threshold — requests blocked
    HALF_OPEN = "half_open"  # Cooldown expired — allow one test request

class CircuitBreaker:
    """Prevents infinite retry loops by opening after repeated failures."""

    def __init__(self, name: str, failure_threshold: int = 3,
                 cooldown_seconds: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_error = None

    def record_failure(self, error: str = ""):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.last_error = error
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                logger.warning(f"🔴 Circuit breaker OPEN for '{self.name}' "
                             f"after {self.failure_count} failures: {error}")
            self.state = CircuitState.OPEN

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN and self.last_failure_time:
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed >= self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"🟡 Circuit breaker HALF-OPEN for '{self.name}' — testing one request")
                return True
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


# ============ COMPONENT HEALTH REGISTRY ============

class ComponentHealthRegistry:
    """
    Tracks health of all v9 components. Runs post-startup verification
    and ongoing monitoring. Triggers rollback if critical components fail.
    """

    def __init__(self):
        self._checks: Dict[str, dict] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.startup_verified = False
        self.last_report: Optional[dict] = None

    def register(self, name: str, check_fn, critical: bool = False,
                 failure_threshold: int = 3, cooldown: float = 60.0):
        """Register a component with its health check function."""
        self._checks[name] = {
            "check_fn": check_fn,
            "critical": critical,
            "status": "unknown",
            "last_checked": None,
            "error": None,
        }
        self._circuit_breakers[name] = CircuitBreaker(
            name, failure_threshold=failure_threshold, cooldown_seconds=cooldown
        )

    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        return self._circuit_breakers.get(name)

    async def verify_startup(self) -> Tuple[bool, List[str]]:
        """Run all health checks post-startup. Returns (all_ok, failed_critical_names)."""
        logger.info("🏥 Running post-startup health verification...")
        critical_failures = []
        results = []

        for name, info in self._checks.items():
            try:
                check = info["check_fn"]
                if asyncio.iscoroutinefunction(check):
                    ok = await asyncio.wait_for(check(), timeout=10.0)
                else:
                    ok = await asyncio.to_thread(check)

                info["status"] = "healthy" if ok else "degraded"
                info["last_checked"] = datetime.now()
                info["error"] = None

                if ok:
                    self._circuit_breakers[name].record_success()
                    results.append(f"  ✅ {name}")
                else:
                    self._circuit_breakers[name].record_failure("health check returned False")
                    results.append(f"  ⚠️ {name} — degraded")
                    if info["critical"]:
                        critical_failures.append(name)

            except asyncio.TimeoutError:
                info["status"] = "timeout"
                info["error"] = "health check timed out"
                info["last_checked"] = datetime.now()
                self._circuit_breakers[name].record_failure("timeout")
                results.append(f"  ❌ {name} — timeout")
                if info["critical"]:
                    critical_failures.append(name)

            except Exception as e:
                info["status"] = "error"
                info["error"] = str(e)
                info["last_checked"] = datetime.now()
                self._circuit_breakers[name].record_failure(str(e))
                results.append(f"  ❌ {name} — {str(e)[:80]}")
                if info["critical"]:
                    critical_failures.append(name)

        self.startup_verified = len(critical_failures) == 0

        for line in results:
            logger.info(line)

        if critical_failures:
            logger.error(f"🚨 CRITICAL FAILURES: {', '.join(critical_failures)}")
        else:
            logger.info("✅ All components passed startup verification")

        return self.startup_verified, critical_failures

    def get_status_report(self) -> str:
        lines = ["🏥 Component Health\n"]
        for name, info in self._checks.items():
            breaker = self._circuit_breakers.get(name)
            icon = {"healthy": "✅", "degraded": "⚠️", "error": "❌",
                    "timeout": "⏰", "unknown": "❓"}.get(info["status"], "❓")
            line = f"{icon} {name}: {info['status']}"
            if breaker and breaker.state != CircuitState.CLOSED:
                line += f" [circuit: {breaker.state.value}]"
            if info["error"]:
                line += f" ({info['error'][:50]})"
            lines.append(line)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            name: {
                "status": info["status"],
                "critical": info["critical"],
                "error": info["error"],
                "last_checked": info["last_checked"].isoformat() if info["last_checked"] else None,
                "circuit_breaker": self._circuit_breakers[name].to_dict()
                    if name in self._circuit_breakers else None,
            }
            for name, info in self._checks.items()
        }


# ============ ATOMIC CHECKPOINT ============

class AtomicCheckpoint:
    """Atomic state checkpointing — write to .tmp then rename for crash safety."""

    def __init__(self, checkpoint_path: Path):
        self.path = checkpoint_path
        self.tmp_path = checkpoint_path.with_suffix(".tmp")

    def save(self, state: dict):
        """Atomically save state — never leaves a corrupt file."""
        try:
            data = json.dumps(state, indent=2, default=str)
            self.tmp_path.write_text(data)
            self.tmp_path.rename(self.path)
        except Exception as e:
            logger.error(f"Checkpoint save failed: {e}")
            if self.tmp_path.exists():
                self.tmp_path.unlink()

    def load(self) -> Optional[dict]:
        """Load last checkpoint, or None if no valid checkpoint."""
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Checkpoint load failed: {e}")
        return None

    def build_state(self, bridge) -> dict:
        """Build current state snapshot from bridge components."""
        state = {
            "timestamp": datetime.now().isoformat(),
            "version": "v10",
            "pid": os.getpid(),
            "uptime_seconds": (datetime.now() - bridge._start_time).total_seconds()
                if hasattr(bridge, '_start_time') else 0,
            "offset": bridge.offset,
            "components": {},
        }

        # Component health
        if bridge.health_registry:
            state["components"] = bridge.health_registry.to_dict()

        # Plugin status
        if bridge.plugins:
            state["plugins"] = {
                "loaded": list(bridge.plugins.skills.keys()),
                "count": len(bridge.plugins.skills),
            }

        # Memory status
        if bridge.memory and bridge.memory.available:
            state["vector_memory"] = {"available": True}

        # Session info
        state["running"] = bridge.running

        return state


# ============ BRIDGE CORE ============

class TelegramBridge:
    """Async bridge with priority queue, vector memory, plugins, and more"""

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.db = DatabaseManager(DB_FILE)
        self.telegram = TelegramClient(config.telegram_bot_token)
        self.claude = ClaudeInterface(config.claude_path)
        self.running = False
        self.offset = 0

        # v9 components (initialized in async start)
        self.memory: Optional[VectorMemory] = None
        self.plugins: Optional[PluginManager] = None
        self.orchestrator: Optional[ModelOrchestrator] = None
        self.scheduler: Optional[SchedulerManager] = None
        self.dream: Optional[DreamEngine] = None
        self.research: Optional[ResearchEngine] = None

        # Resilience infrastructure (v9.1)
        self.health_registry = ComponentHealthRegistry()
        self.checkpoint = AtomicCheckpoint(CHECKPOINT_FILE)
        self._start_time = datetime.now()

        # Async infrastructure
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.conversation_locks: Dict[str, asyncio.Lock] = {}
        self.last_health_check = datetime.now()

        # Legacy memory bridge
        self._memory_bridge = None

        # Load offset
        offset_file = CONFIG_DIR / "offset"
        if offset_file.exists():
            self.offset = int(offset_file.read_text().strip())

    def _get_conversation_lock(self, chat_id: str) -> asyncio.Lock:
        """Get or create per-conversation lock"""
        if chat_id not in self.conversation_locks:
            self.conversation_locks[chat_id] = asyncio.Lock()
        return self.conversation_locks[chat_id]

    def save_offset(self):
        offset_file = CONFIG_DIR / "offset"
        offset_file.write_text(str(self.offset))

    def get_or_create_session(self, chat_id: str) -> Session:
        session = self.db.get_session(chat_id)
        if not session:
            session = Session(
                chat_id=chat_id,
                session_id=str(uuid_module.uuid4()),
                context=[], created_at=datetime.now(),
                updated_at=datetime.now(), state=SessionState.ACTIVE,
                metadata={"started_by": "telegram", "version": "v10"}
            )
            self.db.save_session(session)
            logger.info(f"Created new session: {session.session_id}")
        return session

    def update_session_context(self, chat_id: str, user_msg: str,
                              assistant_msg: str, attachments: List[Attachment] = None):
        session = self.get_or_create_session(chat_id)
        context_entry = {
            "user": user_msg,
            "assistant": assistant_msg[:1000],
            "timestamp": datetime.now().isoformat()
        }
        if attachments:
            context_entry["attachments"] = [
                {"type": att.attachment_type.value, "name": att.file_name}
                for att in attachments
            ]
        session.context.append(context_entry)

        total_chars = sum(len(str(c)) for c in session.context)
        while total_chars > self.config.max_context_chars and len(session.context) > 1:
            session.context.pop(0)
            total_chars = sum(len(str(c)) for c in session.context)

        session.total_messages += 1
        session.total_tokens_estimate = total_chars // 4
        session.updated_at = datetime.now()
        self.db.save_session(session)

    def load_identity(self, mode: str = "brief") -> str:
        identity_file = CONFIG_DIR / "IDENTITY.md"
        if not identity_file.exists():
            return ""
        try:
            identity_content = identity_file.read_text()
            if mode == "full":
                return f"\n\n=== YOUR IDENTITY ===\n{identity_content}\n=== END IDENTITY ===\n"
            else:
                if "## Quick Reference (Brief Mode)" in identity_content:
                    start_marker = "## Quick Reference (Brief Mode)"
                    end_marker = "## Version History"
                    start_idx = identity_content.find(start_marker)
                    end_idx = identity_content.find(end_marker, start_idx)
                    if start_idx != -1 and end_idx != -1:
                        quick_ref = identity_content[start_idx:end_idx].strip()
                        return f"\n\n=== YOUR IDENTITY (Brief) ===\n{quick_ref}\n=== END IDENTITY ===\n"
                return ""
        except Exception as e:
            logger.warning(f"Failed to load identity: {e}")
            return ""

    def _get_date_awareness(self) -> str:
        """Load important dates and return context for today"""
        try:
            if not IMPORTANT_DATES_FILE.exists():
                return ""
            dates_data = json.loads(IMPORTANT_DATES_FILE.read_text())
            today = datetime.now()
            today_mmdd = today.strftime("%m-%d")
            today_iso = today.strftime("%Y-%m-%d")
            notes = []

            # Check recurring dates (today and next 7 days)
            for event in dates_data.get("recurring", []):
                event_mmdd = event["date"]
                if event_mmdd == today_mmdd:
                    notes.append(f"🎉 TODAY: {event['description']} — {event.get('action', '')}")
                else:
                    # Check if within next 7 days
                    try:
                        event_date = datetime(today.year, int(event_mmdd[:2]), int(event_mmdd[3:])).date()
                        days_until = (event_date - today.date()).days
                        if days_until < 0:
                            days_until += 365
                        if 0 < days_until <= 7:
                            notes.append(f"📅 In {days_until} days: {event['description']}")
                    except ValueError:
                        pass

            # Check one-time dates
            for event in dates_data.get("one_time", []):
                if event["date"] == today_iso:
                    notes.append(f"🎉 TODAY: {event['description']}")
                else:
                    try:
                        event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
                        days_until = (event_date - today.date()).days
                        if 0 < days_until <= 7:
                            notes.append(f"📅 In {days_until} days: {event['description']}")
                    except ValueError:
                        pass

            if notes:
                return "\n\n=== Date Awareness ===\n" + "\n".join(notes) + "\n=== End Dates ===\n"
            return ""
        except Exception as e:
            logger.debug(f"Date awareness load failed: {e}")
            return ""

    def build_system_prompt(self, chat_id: str, include_context: bool = True) -> str:
        session = self.get_or_create_session(chat_id)
        identity_mode = "full" if session.total_messages <= 1 else "brief"
        identity = self.load_identity(identity_mode)
        date_awareness = self._get_date_awareness()

        prompt = f"""You are a server assistant accessed via Telegram.
{identity}
{date_awareness}
Key behaviors:
- Answer ALL parts of questions thoroughly
- Run bash commands to get real data when needed
- Be concise but complete
- When analyzing images, describe what you see clearly
- For documents, summarize key points
- Maintain conversation context across messages"""

        if include_context and session.context:
            recent_context = session.context[-10:]
            prompt += f"\n\n=== Conversation History ({len(session.context)} total messages) ==="
            for i, exchange in enumerate(recent_context, 1):
                prompt += f"\n\n[Message {i}]"
                prompt += f"\nUser: {exchange['user'][:300]}"
                if 'attachments' in exchange:
                    prompt += f"\n[Attachments: {', '.join(a['name'] for a in exchange['attachments'])}]"
                prompt += f"\nAssistant: {exchange['assistant'][:300]}"
                if len(exchange['assistant']) > 300:
                    prompt += "..."

            prompt += f"\n\n=== Current Session Info ==="
            prompt += f"\nSession ID: {session.session_id[:8]}"
            prompt += f"\nState: {session.state.value}"
            prompt += f"\nTotal messages: {session.total_messages}"
            prompt += f"\n========================\n"

        return prompt

    async def process_attachments(self, message: Dict) -> List[Attachment]:
        attachments = []
        try:
            if 'photo' in message:
                photos = message['photo']
                largest = max(photos, key=lambda p: p.get('file_size', 0))
                file_id = largest['file_id']
                file_hash = hashlib.md5(file_id.encode()).hexdigest()[:8]
                file_name = f"photo_{file_hash}.jpg"
                file_path = ATTACHMENTS_DIR / file_name

                if await self.telegram.download_file(file_id, file_path):
                    attachments.append(Attachment(
                        attachment_id=file_id, attachment_type=AttachmentType.PHOTO,
                        file_path=file_path, file_name=file_name,
                        file_size=file_path.stat().st_size, mime_type="image/jpeg",
                        created_at=datetime.now()
                    ))

            if 'document' in message:
                doc = message['document']
                file_id = doc['file_id']
                original_name = doc.get('file_name', 'document')
                safe_original = os.path.basename(original_name)
                safe_original = "".join(c for c in safe_original if c.isalnum() or c in "._- ")
                if not safe_original or safe_original.startswith('.'):
                    safe_original = "document"
                file_hash = hashlib.md5(file_id.encode()).hexdigest()[:8]
                extension = Path(safe_original).suffix
                file_name = f"doc_{file_hash}{extension}"
                file_path = ATTACHMENTS_DIR / file_name

                if await self.telegram.download_file(file_id, file_path):
                    mime_type = doc.get('mime_type') or mimetypes.guess_type(original_name)[0]
                    attachments.append(Attachment(
                        attachment_id=file_id, attachment_type=AttachmentType.DOCUMENT,
                        file_path=file_path, file_name=original_name,
                        file_size=doc.get('file_size', 0),
                        mime_type=mime_type or 'application/octet-stream',
                        created_at=datetime.now()
                    ))
        except Exception as e:
            logger.error(f"Error processing attachments: {e}")
        return attachments

    async def handle_callback_query(self, update: Dict):
        callback = update.get('callback_query', {})
        chat_id = str(callback.get('message', {}).get('chat', {}).get('id', ''))
        callback_id = callback.get('id')
        data = callback.get('data', '')

        if chat_id != self.config.allowed_chat_id:
            return

        await self.telegram.answer_callback(callback_id)
        await self.handle_command(chat_id, data)

    async def handle_message(self, update: Dict):
        """Handle incoming message — enqueues for async processing"""
        message = update.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))

        if chat_id != self.config.allowed_chat_id:
            return

        text = message.get('text', '') or message.get('caption', '')
        message_id = message.get('message_id', 0)
        reply_to = message.get('reply_to_message', {}).get('message_id')

        # Handle commands directly (no queuing delay)
        if text.startswith('/'):
            await self.handle_command(chat_id, text)
            return

        # Process attachments
        attachments = []
        if self.config.enable_attachments:
            attachments = await self.process_attachments(message)

        if attachments:
            attachment_info = "\n".join([
                f"- {att.file_name} ({att.attachment_type.value}, {att.file_size // 1024}KB)"
                for att in attachments
            ])
            text = f"{text}\n\n[Attachments]:\n{attachment_info}" if text else f"[Attachments]:\n{attachment_info}"

        if not text and not attachments:
            return

        # Process with conversation lock (prevents interleaving)
        lock = self._get_conversation_lock(chat_id)
        async with lock:
            await self._process_message(chat_id, text, message_id, reply_to, attachments)

    async def _process_message(self, chat_id: str, text: str, message_id: int,
                              reply_to: Optional[int], attachments: List[Attachment]):
        """Process a single message (called under conversation lock)"""
        try:
            session = self.get_or_create_session(chat_id)
            system_prompt = self.build_system_prompt(chat_id)

            # Enrich with vector memory context
            memory_context = ""
            if self.memory and self.memory.available:
                memories = await self.memory.retrieve(text, k=5)
                if memories:
                    memory_context = await self.memory.compress_context(
                        memories, text, self._claude_ask_raw
                    )

            if memory_context:
                system_prompt += f"\n{memory_context}"

            # Send typing indicator
            status_msg = "🤔 Processing"
            if attachments:
                status_msg += f" with {len(attachments)} attachment(s)"
            await self.telegram.send_message(chat_id, status_msg + "...")

            # Ask Claude
            response, success = await self.claude.ask(text, system_prompt, attachments, session.session_id)

            if success:
                await self.telegram.send_message(chat_id, response)

                # Save to database
                db_msg_id = await asyncio.to_thread(
                    self.db.save_message, chat_id, message_id, text, response,
                    reply_to, str(message_id) if reply_to is None else str(reply_to)
                )

                for att in attachments:
                    await asyncio.to_thread(self.db.save_attachment, att, db_msg_id)

                self.update_session_context(chat_id, text, response, attachments)

                # Store in vector memory
                if self.memory and self.memory.available:
                    await self.memory.store(
                        f"User: {text[:300]}\nAssistant: {response[:300]}",
                        source="chat",
                        conversation_id=session.session_id
                    )
            else:
                await self.telegram.send_message(chat_id, f"⚠️ Error: {response}")
                await asyncio.to_thread(self.db.log_error, chat_id, "claude_error", response)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await self.telegram.send_message(
                chat_id,
                "❌ Sorry, I encountered an error processing your message. Please try again."
            )
            await asyncio.to_thread(self.db.log_error, chat_id, "internal_error", str(e))

    async def _claude_ask_raw(self, prompt: str, timeout: int = 60) -> Tuple[str, bool]:
        """Raw Claude ask without system prompt (for internal use)"""
        return await self.claude.ask(prompt, timeout=timeout)

    async def handle_command(self, chat_id: str, command: str):
        """Handle slash commands"""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        button_map = {
            "📊 status": "/status", "🏥 health": "/health",
            "📜 context": "/context", "📈 stats": "/stats",
            "🔄 clear": "/clear", "❓ help": "/help",
            "⏸️ pause": "/pause", "▶️ resume": "/resume",
            "🔴 errors": "/errors", "📦 export": "/export",
            "❌ cancel": "/cancel", "🤖 identity": "/identity"
        }

        if cmd in button_map:
            cmd = button_map[cmd]
            parts = cmd.split()
            cmd = parts[0].lower()

        if cmd == '/start':
            keyboard = self.telegram.create_reply_keyboard([
                ["📊 Status", "🏥 Health"],
                ["📜 Context", "📈 Stats"],
                ["🤖 Identity", "❓ Help"],
                ["🔄 Clear"]
            ])

            memory_status = "✅ ENABLED" if (self.memory and self.memory.available) else "❌ Not loaded"
            plugins_count = len(self.plugins.get_skill_list()) if self.plugins else 0
            models = self.orchestrator.get_available_models() if self.orchestrator else []

            await self.telegram.send_message(
                chat_id,
                "👋 Welcome to Claude Bridge v10 (ECHO)!\n\n"
                "🆕 What's new in v10:\n"
                "• 🛡️ GRACEFUL SHUTDOWN - Saves state before exit\n"
                "• 🔄 SELF-HEALING - Auto-restart via watchdog\n"
                "• ⏪ ATOMIC ROLLBACK - Falls back to v9 on failure\n"
                "• 🧠 VECTOR MEMORY - Semantic recall across conversations\n"
                "• 🔌 PLUGIN HOT-RELOAD - Drop skills in, they're live\n"
                "• 🤖 MULTI-MODEL - Gemini/GPT-5/Qwen with shared context\n"
                "• 💭 DREAM MODE & RESEARCH LOOPS\n\n"
                f"🧠 **Vector Memory:** {memory_status}\n"
                f"🔌 **Plugins loaded:** {plugins_count}\n"
                f"🤖 **External models:** {', '.join(models) if models else 'checking...'}\n\n"
                "Use the keyboard buttons below or type /help for all commands.",
                reply_markup=keyboard
            )

        elif cmd == '/help':
            help_text = """📚 Available Commands:

**Basic:**
/start - Welcome & keyboard
/help - This help
/identity - Echo's identity
/status - Session status
/health - System health
/context - Conversation context
/clear - Clear context
/stats - Statistics
/errors - Recent errors
/export - Export session

**v10 Features:**
/watchdog - Watchdog status
/checkpoint - View last checkpoint

**Memory & AI:**
/dream [shallow|normal|deep] - Start reflection mode
/dream status - Check dream progress
/dream history - Past dream journals
/research <objective> - Start autonomous research
/research status - Check research progress
/research abort <id> - Cancel research
/models - List available AI models
/memory - Memory statistics
/skills - List loaded skills
/schedule - View scheduled tasks

💡 Send messages/images to chat with Claude!"""

            inline_keyboard = self.telegram.create_inline_keyboard([
                [{"text": "📊 Status", "callback_data": "/status"},
                 {"text": "🏥 Health", "callback_data": "/health"}],
                [{"text": "🧠 Memory", "callback_data": "/memory"},
                 {"text": "🔌 Skills", "callback_data": "/skills"}],
                [{"text": "💭 Dream", "callback_data": "/dream"},
                 {"text": "🤖 Models", "callback_data": "/models"}]
            ])

            await self.telegram.send_message(chat_id, help_text, reply_markup=inline_keyboard)

        elif cmd == '/status':
            session = self.get_or_create_session(chat_id)
            uptime = datetime.now() - session.created_at
            mem_stats = await self.memory.get_stats() if self.memory else {"available": False}
            await self.telegram.send_message(chat_id, f"""📊 Session Status

ID: {session.session_id[:12]}...
State: {session.state.value}
Messages: {session.total_messages}
Context items: {len(session.context)}
Tokens (est): {session.total_tokens_estimate}
Uptime: {uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m

🧠 Vector memories: {mem_stats.get('total_memories', 'N/A')}
🔌 Plugins: {len(self.plugins.get_skill_list()) if self.plugins else 0}
🤖 Models: {', '.join(self.orchestrator.get_available_models()) if self.orchestrator else 'N/A'}
💭 Dream active: {'Yes' if self.dream and self.dream.is_active else 'No'}""")

        elif cmd == '/health':
            if self.scheduler:
                health = await self.scheduler.run_health_check()
                await self.telegram.send_message(chat_id, health)
            else:
                await self.telegram.send_message(chat_id, "Scheduler not initialized")

        elif cmd == '/context':
            session = self.get_or_create_session(chat_id)
            if session.context:
                context_text = f"📜 Conversation Context ({len(session.context)} items)\n\n"
                for i, ctx in enumerate(session.context[-5:], 1):
                    context_text += f"{i}. User: {ctx['user'][:100]}\n"
                    context_text += f"   Assistant: {ctx['assistant'][:100]}...\n\n"
            else:
                context_text = "No conversation context yet"
            await self.telegram.send_message(chat_id, context_text)

        elif cmd == '/clear':
            session = self.get_or_create_session(chat_id)
            old_count = len(session.context)
            session.context = []
            session.updated_at = datetime.now()
            self.db.save_session(session)
            await self.telegram.send_message(chat_id, f"✅ Cleared {old_count} context items")

        elif cmd == '/pause':
            session = self.get_or_create_session(chat_id)
            session.state = SessionState.PAUSED
            session.updated_at = datetime.now()
            self.db.save_session(session)
            await self.telegram.send_message(chat_id, "⏸️ Session paused. Use /resume to continue.")

        elif cmd == '/resume':
            session = self.get_or_create_session(chat_id)
            session.state = SessionState.ACTIVE
            session.updated_at = datetime.now()
            self.db.save_session(session)
            await self.telegram.send_message(chat_id, f"▶️ Session resumed. Context: {len(session.context)} messages")

        elif cmd == '/stats':
            session = self.get_or_create_session(chat_id)
            await self.telegram.send_message(chat_id, f"""📈 Session Statistics

Total messages: {session.total_messages}
Context items: {len(session.context)}
Estimated tokens: {session.total_tokens_estimate}
Avg tokens/msg: {session.total_tokens_estimate // max(session.total_messages, 1)}
Session age: {(datetime.now() - session.created_at).days} days""")

        elif cmd == '/errors':
            errors = await asyncio.to_thread(self.db.get_recent_errors, 5)
            if errors:
                error_text = "🔴 Recent Errors:\n\n"
                for err in errors:
                    error_text += f"• {err['timestamp'][:16]}\n  {err['error_type']}: {err['error_message'][:100]}\n\n"
            else:
                error_text = "✅ No recent errors"
            await self.telegram.send_message(chat_id, error_text)

        elif cmd == '/export':
            session = self.get_or_create_session(chat_id)
            export_data = {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "total_messages": session.total_messages,
                "context": session.context
            }
            export_file = CONFIG_DIR / f"export_{session.session_id[:8]}.json"
            with open(export_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            await self.telegram.send_document(chat_id, export_file)

        elif cmd == '/identity':
            identity_file = CONFIG_DIR / "IDENTITY.md"
            if identity_file.exists():
                await self.telegram.send_document(chat_id, identity_file)
                await self.telegram.send_message(chat_id, """🌊 **Echo - Emergent Collaborative Harmonic Observer**

v10 — Self-healing infrastructure with graceful shutdown, watchdog, atomic rollback. All v9 features intact.

Use /help to see all new commands.""")
            else:
                await self.telegram.send_message(chat_id, "⚠️ Identity file not found")

        elif cmd == '/cancel':
            await self.telegram.send_message(chat_id, "⚠️ Cancel not available in persistent session mode")

        # === v10 Commands ===

        elif cmd == '/watchdog':
            # Show watchdog/heartbeat status
            hb_info = "❌ No heartbeat file"
            if HEARTBEAT_FILE.exists():
                try:
                    hb_content = HEARTBEAT_FILE.read_text().strip()
                    hb_ts = int(hb_content.split(":")[0])
                    age = int(time.time()) - hb_ts
                    hb_info = f"✅ Last heartbeat: {age}s ago"
                except Exception:
                    hb_info = f"⚠️ Heartbeat file unreadable"

            cp_info = "❌ No checkpoint"
            cp = self.checkpoint.load()
            if cp:
                cp_info = f"✅ Last checkpoint: {cp.get('timestamp', 'unknown')}"

            prev = SelfDeploymentManager.find_previous_version()
            rb_info = f"✅ Rollback target: {prev.name}" if prev else "❌ No previous version"

            uptime = datetime.now() - self._start_time
            uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"

            await self.telegram.send_message(chat_id, f"""🛡️ v10 Self-Healing Status

⏱️ Uptime: {uptime_str}
💓 {hb_info}
📋 {cp_info}
⏪ {rb_info}

🏥 Component Health:
{self.health_registry.get_status_report() if self.health_registry else 'N/A'}""")

        elif cmd == '/checkpoint':
            cp = self.checkpoint.load()
            if cp:
                # Format nicely
                lines = [f"📋 Last Checkpoint\n"]
                for k, v in cp.items():
                    if k == "components":
                        lines.append(f"Components: {len(v)} registered")
                    elif k == "plugins":
                        lines.append(f"Plugins: {v}")
                    else:
                        lines.append(f"{k}: {v}")
                await self.telegram.send_message(chat_id, "\n".join(lines))
            else:
                await self.telegram.send_message(chat_id, "❌ No checkpoint saved yet")

        # === Inherited Commands ===

        elif cmd == '/dream':
            if not self.dream:
                await self.telegram.send_message(chat_id, "⚠️ Dream engine not initialized")
                return

            if args and args[0] == 'status':
                if self.dream.is_active:
                    await self.telegram.send_message(chat_id, "💭 Dream cycle is currently active...")
                else:
                    await self.telegram.send_message(chat_id, "💤 No active dream cycle.")
            elif args and args[0] == 'history':
                dreams = await asyncio.to_thread(self.db.get_recent_dreams, chat_id, 5)
                if dreams:
                    text = "📖 Recent Dream Journals:\n\n"
                    for d in dreams:
                        rating = d.get('user_rating', 'unrated')
                        text += f"• #{d['id']} ({d['created_at'][:16]}) — {d['memories_processed']} memories, rating: {rating}\n"
                    await self.telegram.send_message(chat_id, text)
                else:
                    await self.telegram.send_message(chat_id, "No dream history yet. Use /dream to start.")
            elif args and args[0] == 'stop':
                await self.dream.stop_dream()
                await self.telegram.send_message(chat_id, "💭 Dream mode stopped.")
            else:
                depth = args[0] if args and args[0] in ['shallow', 'normal', 'deep'] else 'normal'
                days = int(args[1]) if len(args) > 1 and args[1].isdigit() else 7
                await self.dream.start_dream(depth, days)

        elif cmd == '/research':
            if not self.research:
                await self.telegram.send_message(chat_id, "⚠️ Research engine not initialized")
                return

            if not args:
                await self.telegram.send_message(chat_id, "Usage: /research <objective>\nExample: /research best Python async frameworks 2026")
                return

            if args[0] == 'status':
                active = await asyncio.to_thread(self.db.get_active_research, chat_id)
                if active:
                    text = "🔍 Active Research:\n\n"
                    for r in active:
                        text += f"• [{r['id'][:8]}] {r['objective'][:50]} — {r['state']}, {r['cycles_completed']} cycles\n"
                    await self.telegram.send_message(chat_id, text)
                else:
                    await self.telegram.send_message(chat_id, "No active research tasks.")
            elif args[0] == 'abort' and len(args) > 1:
                await self.research.abort_research(args[1])
                await self.telegram.send_message(chat_id, f"🛑 Research {args[1]} aborted.")
            else:
                objective = " ".join(args)
                await self.research.start_research(objective)

        elif cmd == '/models':
            if self.orchestrator:
                models = self.orchestrator.get_available_models()
                if models:
                    text = "🤖 Available External Models:\n\n"
                    for m in models:
                        info = self.orchestrator.MODELS[m]
                        text += f"✅ {info['name']} ({m})\n"
                else:
                    text = "No external models available."
                await self.telegram.send_message(chat_id, text)

        elif cmd == '/memory':
            if self.memory:
                stats = await self.memory.get_stats()
                await self.telegram.send_message(chat_id, f"""🧠 Vector Memory

Available: {'✅ Yes' if stats.get('available') else '❌ No'}
Total memories: {stats.get('total_memories', 'N/A')}
Storage: {stats.get('storage_path', 'N/A')}
Decay rate: {self.config.memory_decay_lambda}""")
            else:
                await self.telegram.send_message(chat_id, "⚠️ Vector memory not initialized")

        elif cmd == '/skills':
            if self.plugins:
                skills = self.plugins.get_skill_list()
                if skills:
                    await self.telegram.send_message(chat_id, f"🔌 Loaded Skills ({len(skills)}):\n\n" + "\n".join(f"• {s}" for s in skills))
                else:
                    await self.telegram.send_message(chat_id, "No skills loaded. Add .py files to ~/.claude-bridge/skills/")
            else:
                await self.telegram.send_message(chat_id, "⚠️ Plugin manager not initialized")

        elif cmd == '/schedule':
            schedules = await asyncio.to_thread(self.db.get_active_schedules, chat_id)
            if schedules:
                text = "📅 Active Schedules:\n\n"
                for s in schedules:
                    text += f"• {s['description']} ({s['cron_expression']})\n"
                await self.telegram.send_message(chat_id, text)
            else:
                await self.telegram.send_message(chat_id, "No active schedules.")

        else:
            await self.telegram.send_message(chat_id, f"❓ Unknown command: {cmd}\nUse /help for available commands")

    async def _initialize_components(self):
        """Initialize all components with health verification"""
        logger.info("Initializing v10 components...")

        # Start Claude session
        await self.claude.start_session()

        # Vector Memory
        self.memory = VectorMemory(self.db, self.config.memory_decay_lambda)
        mem_ok = await self.memory.initialize()
        logger.info(f"Vector memory: {'✅' if mem_ok else '❌'}")

        # Plugin Manager (with circuit breaker)
        self.plugins = PluginManager(SKILLS_DIR)
        plugin_breaker = CircuitBreaker("plugins", failure_threshold=3, cooldown_seconds=60)
        self.plugins._circuit_breaker = plugin_breaker
        await self.plugins.start()

        # Model Orchestrator
        self.orchestrator = ModelOrchestrator(self.memory)
        await self.orchestrator.check_availability()

        # Scheduler
        self.scheduler = SchedulerManager(self.db, self.telegram, self.config.allowed_chat_id)
        await self.scheduler.start()

        # Dream Engine
        self.dream = DreamEngine(
            self.memory, self.db, self._claude_ask_raw,
            self.telegram, self.config.allowed_chat_id
        )

        # Research Engine
        self.research = ResearchEngine(
            self.memory, self.db, self._claude_ask_raw,
            self.orchestrator, self.telegram,
            self.config.allowed_chat_id, self.config
        )

        # ── Register health checks ──
        self.health_registry.register(
            "claude_session",
            lambda: self.claude.process is not None and self.claude.process.poll() is None,
            critical=True
        )
        self.health_registry.register(
            "vector_memory",
            lambda: self.memory is not None and self.memory.available,
            critical=False  # Degraded but not fatal
        )
        self.health_registry.register(
            "plugins",
            lambda: self.plugins is not None and len(self.plugins.skills) > 0,
            critical=False,
            failure_threshold=3
        )
        self.health_registry.register(
            "telegram",
            lambda: self.telegram is not None,
            critical=True
        )
        self.health_registry.register(
            "database",
            lambda: self.db is not None,
            critical=True
        )

        # ── Post-startup verification ──
        all_ok, critical_failures = await self.health_registry.verify_startup()

        if not all_ok:
            logger.error(f"🚨 Startup verification FAILED: {critical_failures}")
            logger.error("Attempting rollback...")
            success, msg = await SelfDeploymentManager.rollback()
            if success:
                logger.info(f"Rollback succeeded: {msg}")
                # Rollback will restart process via deployer, exit cleanly
                sys.exit(1)
            else:
                logger.error(f"Rollback also failed: {msg}")
                logger.warning("Continuing in degraded mode...")

        # ── Save initial checkpoint ──
        self.checkpoint.save(self.checkpoint.build_state(self))

        logger.info("✅ All v10 components initialized")

    async def run(self):
        """Main async run loop"""
        self.running = True
        logger.info("Bridge v10 starting — self-healing infrastructure!")

        # Write PID
        PID_FILE.write_text(str(os.getpid()))

        try:
            # Initialize all components
            await self._initialize_components()

            # Send startup notification
            try:
                prev_checkpoint = self.checkpoint.load()
                recovery_info = ""
                if prev_checkpoint and prev_checkpoint.get("version") != "v10":
                    recovery_info = f"\n⏪ Recovered from {prev_checkpoint.get('version', 'unknown')}"
                elif prev_checkpoint:
                    recovery_info = "\n🔄 Restarted from checkpoint"

                await self.telegram.send_message(
                    self.config.allowed_chat_id,
                    f"🟢 Echo v10 online\n"
                    f"PID: {os.getpid()}\n"
                    f"Memory: {'✅' if self.memory and self.memory.available else '❌'}\n"
                    f"Plugins: {len(self.plugins.get_skill_list()) if self.plugins else 0}\n"
                    f"Models: {', '.join(self.orchestrator.get_available_models()) if self.orchestrator else 'N/A'}"
                    f"{recovery_info}"
                )
            except Exception as e:
                logger.warning(f"Could not send startup notification: {e}")

            last_cleanup = datetime.now()

            # Start independent heartbeat (not blocked by message processing)
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            while self.running:
                try:
                    # Get updates from Telegram
                    updates = await self.telegram.get_updates(self.offset, timeout=30)

                    for update in updates:
                        update_id = update.get('update_id', 0)
                        self.offset = update_id + 1
                        self.save_offset()

                        if 'callback_query' in update:
                            await self.handle_callback_query(update)
                        elif 'message' in update:
                            await self.handle_message(update)

                    # Daily cleanup
                    if (datetime.now() - last_cleanup).days >= 1:
                        await asyncio.to_thread(self.db.cleanup_old_attachments, 30)
                        last_cleanup = datetime.now()

                    await asyncio.sleep(0.5)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    await asyncio.sleep(5)

        finally:
            heartbeat_task.cancel()
            await self.shutdown(reason="loop_exit")

    async def _heartbeat_loop(self):
        """Independent heartbeat + checkpoint — runs regardless of message processing"""
        while self.running:
            try:
                HEARTBEAT_FILE.write_text(str(int(time.time())))
            except Exception:
                pass
            # Periodic checkpoint
            try:
                self.checkpoint.save(self.checkpoint.build_state(self))
            except Exception:
                pass
            await asyncio.sleep(30)

    async def shutdown(self, reason: str = "normal"):
        logger.info(f"Shutting down bridge v10 (reason: {reason})...")
        self.running = False

        # Save final checkpoint before anything else
        try:
            self.checkpoint.save(self.checkpoint.build_state(self))
            logger.info("✅ Final checkpoint saved")
        except Exception as e:
            logger.error(f"Failed to save final checkpoint: {e}")

        # Write final heartbeat with shutdown marker
        try:
            HEARTBEAT_FILE.write_text(f"{int(time.time())}:shutdown:{reason}")
        except Exception:
            pass

        # Notify Stephen via Telegram
        try:
            uptime = datetime.now() - self._start_time
            uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
            await self.telegram.send_message(
                self.config.allowed_chat_id,
                f"🔴 Echo v10 shutting down\n"
                f"Reason: {reason}\n"
                f"Uptime: {uptime_str}\n"
                f"Checkpoint: saved ✅"
            )
        except Exception as e:
            logger.warning(f"Could not send shutdown notification: {e}")

        # Stop components gracefully
        if self.plugins:
            await self.plugins.stop()
        if self.scheduler:
            await self.scheduler.stop()
        await self.claude.shutdown()
        await self.telegram.close()

        if PID_FILE.exists():
            PID_FILE.unlink()

        logger.info("Bridge v10 stopped")


# ============ MAIN (v10: Async-aware shutdown + Startup Recovery) ============

def main():
    # Check if already running
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            logger.error(f"Bridge already running (PID: {pid})")
            sys.exit(1)
        except (OSError, ValueError):
            PID_FILE.unlink()

    # Load configuration
    try:
        config = BridgeConfig.load()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Startup recovery — check previous checkpoint
    checkpoint = AtomicCheckpoint(CHECKPOINT_FILE)
    prev_state = checkpoint.load()
    if prev_state:
        prev_version = prev_state.get("version", "unknown")
        prev_pid = prev_state.get("pid", "unknown")
        prev_ts = prev_state.get("timestamp", "unknown")
        logger.info(f"🔄 Recovering from checkpoint: {prev_version} (PID {prev_pid}, saved {prev_ts})")

        # Restore offset from checkpoint if available
        saved_offset = prev_state.get("offset")
        if saved_offset is not None:
            offset_file = CONFIG_DIR / "offset"
            offset_file.write_text(str(saved_offset))
            logger.info(f"  Restored Telegram offset: {saved_offset}")
    else:
        logger.info("🆕 Fresh start — no previous checkpoint found")

    # Create bridge
    bridge = TelegramBridge(config)

    # Set up async event loop with proper signal handling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    shutdown_reason = "normal"

    def _signal_handler(signum, frame):
        nonlocal shutdown_reason
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} (signal {signum}), initiating graceful shutdown...")
        shutdown_reason = sig_name
        bridge.running = False

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        loop.run_until_complete(bridge.run())
    except KeyboardInterrupt:
        shutdown_reason = "KeyboardInterrupt"
        logger.info("KeyboardInterrupt — shutting down gracefully...")
        loop.run_until_complete(bridge.shutdown(reason=shutdown_reason))
    except SystemExit:
        # From rollback — don't try to shut down again
        pass
    except Exception as e:
        shutdown_reason = f"crash:{str(e)[:100]}"
        logger.error(f"Bridge crashed: {e}", exc_info=True)
        # Try to save state even on crash
        try:
            loop.run_until_complete(bridge.shutdown(reason=shutdown_reason))
        except Exception:
            pass
        # Attempt rollback
        logger.warning("Attempting rollback after crash...")
        prev = SelfDeploymentManager.find_previous_version()
        if prev:
            try:
                subprocess.Popen(
                    [sys.executable, str(prev)],
                    stdout=open(LOG_FILE, 'a'),
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
                logger.info(f"⏪ Rollback started: {prev.name}")
            except Exception as re:
                logger.error(f"Rollback failed: {re}")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
