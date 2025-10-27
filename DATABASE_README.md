# Claude Skills Database Infrastructure

This directory contains a SQLite database infrastructure for tracking and managing Claude Code skills.

## Quick Start

### 1. Initialize Database

```bash
python3 ~/.claude/skills/scripts/init_db.py
```

This will:
- Create `~/.claude/skills/data/skills_metadata.db`
- Scan all skills in `~/.claude/skills/`
- Populate metadata, templates, scripts, and references
- Show summary statistics

### 2. View Dashboard

```bash
# Interactive mode
python3 ~/.claude/skills/scripts/skill_dashboard.py

# Quick views
python3 ~/.claude/skills/scripts/skill_dashboard.py summary
python3 ~/.claude/skills/scripts/skill_dashboard.py skills
python3 ~/.claude/skills/scripts/skill_dashboard.py popular
python3 ~/.claude/skills/scripts/skill_dashboard.py detail <skill-name>
```

### 3. Use Python API

```python
from skill_db import SkillDB

db = SkillDB()

# Get all skills
skills = db.get_all_skills()

# Get skills by category
database_skills = db.get_all_skills(category='database')

# Get skill details
skill = db.get_skill('api-documentation-generator')

# Log execution
db.log_execution(
    skill_name='test-coverage-analyzer',
    duration_ms=1250,
    success=True
)

# Add feedback
db.add_feedback(
    skill_name='docker-optimizer',
    rating=5,
    helpful=True,
    comments='Helped reduce image size by 60%!'
)

# Get statistics
stats = db.get_skill_stats('performance-profiler')
popular = db.get_skill_popularity(limit=5)
```

## Database Schema

### Core Tables

**skills_registry**
- Metadata about each skill (name, description, category, tools)

**skill_executions**
- Log of when skills were used, duration, success/failure

**skill_templates**
- Templates provided by each skill (Dockerfiles, migrations, etc.)

**skill_scripts**
- Helper scripts (bash, python) included with skills

**skill_references**
- Reference documentation files

**skill_feedback**
- User ratings and comments

**skill_dependencies**
- Relationships between skills

### Views

**skill_usage_stats**
- Total executions, average duration, success rate per skill

**skill_popularity**
- Usage count and average rating by skill

**skill_resources**
- Count of templates, scripts, and references per skill

**skill_errors**
- Skills with execution errors and error messages

## Directory Structure

```
~/.claude/skills/
├── data/
│   ├── schema.sql             # Database schema
│   └── skills_metadata.db     # SQLite database
├── lib/
│   └── skill_db.py           # Python connector module
├── scripts/
│   ├── init_db.py            # Initialize and populate database
│   └── skill_dashboard.py    # Dashboard and analytics
└── <skill-name>/
    ├── SKILL.md
    ├── templates/
    ├── scripts/
    └── reference/
```

## Use Cases

### Track Skill Usage

Log when skills are used to identify:
- Most/least popular skills
- Skills that may need improvement
- Execution patterns and performance

```python
db = SkillDB()
db.log_execution('api-documentation-generator', duration_ms=850, success=True)
```

### Analyze Performance

Monitor skill execution times:

```python
stats = db.get_skill_stats('performance-profiler')
print(f"Average duration: {stats['avg_duration_ms']}ms")
print(f"Success rate: {stats['success_rate_percent']}%")
```

### Collect Feedback

Gather user feedback to improve skills:

```python
db.add_feedback(
    skill_name='accessibility-auditor',
    rating=4,
    helpful=True,
    comments='Very thorough WCAG checks!'
)
```

### Find Related Skills

Discover complementary skills:

```python
# Search for skills
results = db.search_skills('database')

# Get skills by category
devops_skills = db.get_all_skills(category='devops')

# Get skill resources
resources = db.get_skill_resources('database-migration-helper')
print(f"Templates: {len(resources['templates'])}")
```

## Integration Examples

### Hook into Claude Code Events

If you want to automatically log skill executions, you could create a wrapper:

```python
from skill_db import SkillDB
import time

def track_skill_execution(skill_name):
    """Decorator to track skill execution."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            db = SkillDB()
            start = time.time()
            success = True
            error = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration_ms = int((time.time() - start) * 1000)
                db.log_execution(skill_name, duration_ms, success, error)

        return wrapper
    return decorator
```

### Export Data

Export for analysis:

```python
import json
import csv

db = SkillDB()

# Export all skills to JSON
skills = db.get_all_skills()
with open('skills.json', 'w') as f:
    json.dump(skills, f, indent=2)

# Export popularity to CSV
popular = db.get_skill_popularity()
with open('popularity.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=popular[0].keys())
    writer.writeheader()
    writer.writerows(popular)
```

## Maintenance

### Refresh Metadata

If you add/modify skills, re-run initialization:

```bash
python3 ~/.claude/skills/scripts/init_db.py
```

Note: This will update existing skills and add new ones. Execution history and feedback are preserved.

### Backup Database

```bash
cp ~/.claude/skills/data/skills_metadata.db \
   ~/.claude/skills/data/skills_metadata.db.backup
```

### Query Directly

```bash
sqlite3 ~/.claude/skills/data/skills_metadata.db

# Example queries
SELECT * FROM skills_registry;
SELECT * FROM skill_usage_stats;
SELECT * FROM skill_popularity;
```

## Dashboard Commands

```bash
# Interactive menu
python3 ~/.claude/skills/scripts/skill_dashboard.py

# Summary stats
python3 ~/.claude/skills/scripts/skill_dashboard.py summary

# List all skills by category
python3 ~/.claude/skills/scripts/skill_dashboard.py skills

# Show popular skills
python3 ~/.claude/skills/scripts/skill_dashboard.py popular

# Show recent activity
python3 ~/.claude/skills/scripts/skill_dashboard.py activity

# Show errors
python3 ~/.claude/skills/scripts/skill_dashboard.py errors

# Skill details
python3 ~/.claude/skills/scripts/skill_dashboard.py detail api-documentation-generator
```

## Future Enhancements

Potential additions:
- Web dashboard using Flask/FastAPI
- Skill recommendation engine
- A/B testing for skill descriptions
- Automatic skill updates/versioning
- Multi-user support
- Cloud sync
- Analytics visualization (charts, graphs)
- Skill dependency graph visualization

## Troubleshooting

**Database not found**
```bash
python3 ~/.claude/skills/scripts/init_db.py
```

**Module not found errors**
```bash
# Make sure you're using Python 3
python3 --version

# Install PyYAML if needed
pip3 install pyyaml
```

**Permission errors**
```bash
chmod +x ~/.claude/skills/scripts/*.py
```

## API Reference

See `lib/skill_db.py` for full API documentation. Main methods:

- `get_skill(name)` - Get skill metadata
- `get_all_skills(category)` - List skills
- `log_execution(...)` - Log skill usage
- `add_feedback(...)` - Add user feedback
- `get_skill_stats(name)` - Get usage statistics
- `get_skill_popularity()` - Get popular skills
- `search_skills(query)` - Search by name/description
- `get_skill_resources(name)` - Get templates/scripts/references
- `get_summary()` - Overall database summary
