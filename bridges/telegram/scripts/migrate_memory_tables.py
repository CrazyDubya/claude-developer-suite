#!/usr/bin/env python3
"""
Memory System Migration Script
Adds multi-tier memory tables to existing bridge.db
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_FILE = Path.home() / ".claude-bridge" / "bridge.db"

MIGRATION_SQL = """
-- ============================================================
-- SHORT-TERM MEMORY TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS conversation_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    summary_date DATE NOT NULL,
    message_count INTEGER,
    key_topics TEXT,
    summary_text TEXT,
    importance_score REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recent_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_type TEXT,
    title TEXT,
    description TEXT,
    related_session_id TEXT,
    confidence REAL DEFAULT 1.0,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS active_contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_type TEXT,
    context_key TEXT UNIQUE,
    context_data TEXT,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pending_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT,
    action_text TEXT,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'pending',
    due_date TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- LONG-TERM MEMORY TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    subject TEXT,
    knowledge TEXT,
    source_session_id TEXT,
    confidence REAL DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT UNIQUE,
    project_type TEXT,
    description TEXT,
    key_files TEXT,
    last_activity TEXT,
    activity_count INTEGER DEFAULT 0,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_component TEXT,
    knowledge_type TEXT,
    content TEXT,
    file_paths TEXT,
    related_services TEXT,
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interaction_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT,
    pattern_name TEXT,
    description TEXT,
    examples TEXT,
    confidence REAL DEFAULT 0.5,
    observation_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table TEXT,
    source_id INTEGER,
    content_snippet TEXT,
    embedding_vector TEXT,
    embedding_hash TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_conversation_summaries_session
    ON conversation_summaries(session_id, summary_date DESC);

CREATE INDEX IF NOT EXISTS idx_recent_insights_type
    ON recent_insights(insight_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_active_contexts_key
    ON active_contexts(context_key, last_accessed DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_subject
    ON knowledge_base(subject, category);

CREATE INDEX IF NOT EXISTS idx_project_memory_name
    ON project_memory(project_name, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_knowledge_component
    ON system_knowledge(system_component, knowledge_type);

CREATE INDEX IF NOT EXISTS idx_semantic_embeddings_hash
    ON semantic_embeddings(embedding_hash);

-- ============================================================
-- MIGRATION METADATA
-- ============================================================

CREATE TABLE IF NOT EXISTS migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_name TEXT UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO migrations (migration_name)
VALUES ('memory_system_v1');
"""


def run_migration():
    """Run the memory system migration"""
    print("🔄 Starting memory system migration...")

    # Backup existing database
    backup_file = DB_FILE.parent / f"backups/bridge_memory_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_file.parent.mkdir(exist_ok=True)

    import shutil
    shutil.copy2(DB_FILE, backup_file)
    print(f"✅ Backup created: {backup_file}")

    # Run migration
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.executescript(MIGRATION_SQL)
        conn.commit()
        print("✅ Migration completed successfully!")

        # Show new tables
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sessions', 'messages', 'attachments', 'errors', 'sqlite_sequence') ORDER BY name"
        )
        tables = cursor.fetchall()
        print(f"\n📊 New memory tables created ({len(tables)}):")
        for table in tables:
            # Count rows in each table
            count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
            print(f"  - {table[0]:30s} ({count} rows)")

        # Show database size
        import os
        db_size = os.path.getsize(DB_FILE) / 1024
        print(f"\n💾 Database size: {db_size:.1f} KB")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

    print("\n🎉 Memory system ready to use!")
    print("\nNext steps:")
    print("  1. Test with: /memory-stats in Telegram")
    print("  2. Try: /remember 'Test memory'")
    print("  3. Search: /recall 'test'")


if __name__ == "__main__":
    run_migration()
