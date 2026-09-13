-- Claude Skills Metadata Database Schema
-- SQLite Database for tracking and managing Claude Code skills

-- Skills Registry: Core metadata about each skill
CREATE TABLE IF NOT EXISTS skills_registry (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  version TEXT DEFAULT '1.0.0',
  file_path TEXT NOT NULL,
  description TEXT,
  category TEXT,
  allowed_tools TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Skill Executions: Track when and how skills are used
CREATE TABLE IF NOT EXISTS skill_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_name TEXT NOT NULL,
  executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  duration_ms INTEGER,
  success BOOLEAN DEFAULT 1,
  error_message TEXT,
  trigger_keywords TEXT,
  FOREIGN KEY (skill_name) REFERENCES skills_registry(name) ON DELETE CASCADE
);

-- Skill Templates: Track templates provided by each skill
CREATE TABLE IF NOT EXISTS skill_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_name TEXT NOT NULL,
  template_name TEXT NOT NULL,
  template_path TEXT NOT NULL,
  framework TEXT,
  description TEXT,
  FOREIGN KEY (skill_name) REFERENCES skills_registry(name) ON DELETE CASCADE
);

-- Skill Scripts: Track helper scripts provided by skills
CREATE TABLE IF NOT EXISTS skill_scripts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_name TEXT NOT NULL,
  script_name TEXT NOT NULL,
  script_path TEXT NOT NULL,
  is_executable BOOLEAN DEFAULT 0,
  description TEXT,
  FOREIGN KEY (skill_name) REFERENCES skills_registry(name) ON DELETE CASCADE
);

-- Skill Reference Docs: Track reference documentation
CREATE TABLE IF NOT EXISTS skill_references (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_name TEXT NOT NULL,
  reference_name TEXT NOT NULL,
  reference_path TEXT NOT NULL,
  description TEXT,
  FOREIGN KEY (skill_name) REFERENCES skills_registry(name) ON DELETE CASCADE
);

-- Skill Feedback: User ratings and comments
CREATE TABLE IF NOT EXISTS skill_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_name TEXT NOT NULL,
  rating INTEGER CHECK(rating >= 1 AND rating <= 5),
  helpful BOOLEAN,
  comments TEXT,
  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (skill_name) REFERENCES skills_registry(name) ON DELETE CASCADE
);

-- Skill Dependencies: Track which skills might work together
CREATE TABLE IF NOT EXISTS skill_dependencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_name TEXT NOT NULL,
  depends_on_skill TEXT NOT NULL,
  dependency_type TEXT, -- 'complementary', 'prerequisite', 'alternative'
  FOREIGN KEY (skill_name) REFERENCES skills_registry(name) ON DELETE CASCADE,
  FOREIGN KEY (depends_on_skill) REFERENCES skills_registry(name) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_executions_skill ON skill_executions(skill_name);
CREATE INDEX IF NOT EXISTS idx_executions_date ON skill_executions(executed_at);
CREATE INDEX IF NOT EXISTS idx_templates_skill ON skill_templates(skill_name);
CREATE INDEX IF NOT EXISTS idx_feedback_skill ON skill_feedback(skill_name);

-- Views for Analytics

-- Skill Usage Statistics
CREATE VIEW IF NOT EXISTS skill_usage_stats AS
SELECT
  skill_name,
  COUNT(*) as total_executions,
  ROUND(AVG(duration_ms), 2) as avg_duration_ms,
  ROUND(SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as success_rate_percent,
  MAX(executed_at) as last_used,
  MIN(executed_at) as first_used
FROM skill_executions
GROUP BY skill_name;

-- Skill Popularity Ranking
CREATE VIEW IF NOT EXISTS skill_popularity AS
SELECT
  sr.name,
  sr.category,
  sr.description,
  COALESCE(COUNT(DISTINCT se.id), 0) as usage_count,
  COALESCE(ROUND(AVG(sf.rating), 2), 0) as avg_rating,
  COALESCE(COUNT(DISTINCT sf.id), 0) as feedback_count,
  COALESCE(MAX(se.executed_at), sr.created_at) as last_activity
FROM skills_registry sr
LEFT JOIN skill_executions se ON sr.name = se.skill_name
LEFT JOIN skill_feedback sf ON sr.name = sf.skill_name
GROUP BY sr.name, sr.category, sr.description
ORDER BY usage_count DESC, avg_rating DESC;

-- Skill Resources Summary
CREATE VIEW IF NOT EXISTS skill_resources AS
SELECT
  sr.name,
  COUNT(DISTINCT st.id) as template_count,
  COUNT(DISTINCT ss.id) as script_count,
  COUNT(DISTINCT sref.id) as reference_count
FROM skills_registry sr
LEFT JOIN skill_templates st ON sr.name = st.skill_name
LEFT JOIN skill_scripts ss ON sr.name = ss.skill_name
LEFT JOIN skill_references sref ON sr.name = sref.skill_name
GROUP BY sr.name;

-- Error Analysis
CREATE VIEW IF NOT EXISTS skill_errors AS
SELECT
  skill_name,
  COUNT(*) as error_count,
  MAX(executed_at) as last_error,
  GROUP_CONCAT(DISTINCT error_message, ' | ') as error_messages
FROM skill_executions
WHERE success = 0
GROUP BY skill_name
ORDER BY error_count DESC;
