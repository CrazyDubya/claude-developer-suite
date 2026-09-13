#!/usr/bin/env python3
"""
Initialize the Claude Skills metadata database.
Creates SQLite database and populates it with existing skills.
"""

import sqlite3
import os
import re
import yaml
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = Path.home() / '.claude' / 'skills' / 'data' / 'skills_metadata.db'
SCHEMA_PATH = Path.home() / '.claude' / 'skills' / 'data' / 'schema.sql'
SKILLS_DIR = Path.home() / '.claude' / 'skills'

def create_database():
    """Create the database and initialize schema."""
    print(f"Creating database at: {DB_PATH}")

    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Connect and create schema
    conn = sqlite3.connect(DB_PATH)

    # Read and execute schema
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()

    conn.executescript(schema_sql)
    conn.commit()

    print("✓ Database schema created successfully")
    return conn

def parse_skill_frontmatter(skill_md_path):
    """Extract YAML frontmatter from SKILL.md file."""
    with open(skill_md_path, 'r') as f:
        content = f.read()

    # Extract frontmatter between --- markers
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return None

    frontmatter_text = match.group(1)
    try:
        return yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML in {skill_md_path}: {e}")
        return None

def categorize_skill(name, description):
    """Categorize skill based on name and description."""
    categories = {
        'documentation': ['documentation', 'api', 'docs', 'openapi', 'swagger'],
        'database': ['database', 'migration', 'schema', 'sql'],
        'testing': ['test', 'coverage', 'testing'],
        'security': ['security', 'audit', 'vulnerability', 'dependencies'],
        'code-quality': ['style', 'lint', 'format', 'consistency'],
        'performance': ['performance', 'profil', 'optimiz', 'bottleneck'],
        'internationalization': ['i18n', 'localization', 'translation'],
        'devops': ['docker', 'container', 'deployment'],
        'monitoring': ['error', 'tracking', 'sentry', 'monitoring'],
        'git': ['git', 'commit', 'workflow', 'branch'],
        'configuration': ['config', 'env', 'environment'],
        'accessibility': ['accessibility', 'a11y', 'wcag', 'aria']
    }

    text = (name + ' ' + description).lower()

    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category

    return 'general'

def scan_skill_directory(skill_path):
    """Scan a skill directory for templates, scripts, and references."""
    templates = []
    scripts = []
    references = []

    # Find templates
    templates_dir = skill_path / 'templates'
    if templates_dir.exists():
        for template_file in templates_dir.rglob('*'):
            if template_file.is_file():
                templates.append({
                    'name': template_file.name,
                    'path': str(template_file.relative_to(SKILLS_DIR)),
                    'framework': detect_framework(template_file.name)
                })

    # Find scripts
    scripts_dir = skill_path / 'scripts'
    if scripts_dir.exists():
        for script_file in scripts_dir.rglob('*'):
            if script_file.is_file():
                is_executable = os.access(script_file, os.X_OK)
                scripts.append({
                    'name': script_file.name,
                    'path': str(script_file.relative_to(SKILLS_DIR)),
                    'executable': is_executable
                })

    # Find reference docs
    reference_dir = skill_path / 'reference'
    if reference_dir.exists():
        for ref_file in reference_dir.rglob('*'):
            if ref_file.is_file():
                references.append({
                    'name': ref_file.name,
                    'path': str(ref_file.relative_to(SKILLS_DIR))
                })

    # Check for reference.md or examples.md in root
    for ref_name in ['reference.md', 'examples.md']:
        ref_file = skill_path / ref_name
        if ref_file.exists():
            references.append({
                'name': ref_name,
                'path': str(ref_file.relative_to(SKILLS_DIR))
            })

    return templates, scripts, references

def detect_framework(filename):
    """Detect framework from template filename."""
    framework_markers = {
        'prisma': 'Prisma',
        'sequelize': 'Sequelize',
        'knex': 'Knex',
        'typeorm': 'TypeORM',
        'alembic': 'Alembic',
        'rails': 'Rails',
        'jest': 'Jest',
        'pytest': 'pytest',
        'go': 'Go',
        'python': 'Python',
        'javascript': 'JavaScript',
        'typescript': 'TypeScript',
        'docker': 'Docker',
        'openapi': 'OpenAPI'
    }

    filename_lower = filename.lower()
    for marker, framework in framework_markers.items():
        if marker in filename_lower:
            return framework

    return None

def populate_skills(conn):
    """Populate database with skills from filesystem."""
    print("\nScanning skills directory...")

    cursor = conn.cursor()
    skills_count = 0
    templates_count = 0
    scripts_count = 0
    references_count = 0

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue

        # Skip special directories
        if skill_dir.name in ['lib', 'scripts', 'data']:
            continue

        skill_md = skill_dir / 'SKILL.md'
        if not skill_md.exists():
            print(f"⚠ Skipping {skill_dir.name}: No SKILL.md found")
            continue

        # Parse frontmatter
        frontmatter = parse_skill_frontmatter(skill_md)
        if not frontmatter:
            print(f"⚠ Skipping {skill_dir.name}: Invalid frontmatter")
            continue

        skill_name = frontmatter.get('name', skill_dir.name)
        description = frontmatter.get('description', '')
        allowed_tools = frontmatter.get('allowed-tools', '')

        category = categorize_skill(skill_name, description)

        # Insert skill
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO skills_registry
                (name, file_path, description, category, allowed_tools)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                skill_name,
                str(skill_md.relative_to(SKILLS_DIR)),
                description,
                category,
                allowed_tools
            ))
            skills_count += 1
            print(f"✓ Added skill: {skill_name} ({category})")
        except sqlite3.Error as e:
            print(f"✗ Error adding {skill_name}: {e}")
            continue

        # Scan for templates, scripts, and references
        templates, scripts, references = scan_skill_directory(skill_dir)

        # Insert templates
        for template in templates:
            cursor.execute('''
                INSERT INTO skill_templates
                (skill_name, template_name, template_path, framework)
                VALUES (?, ?, ?, ?)
            ''', (skill_name, template['name'], template['path'], template['framework']))
            templates_count += 1

        # Insert scripts
        for script in scripts:
            cursor.execute('''
                INSERT INTO skill_scripts
                (skill_name, script_name, script_path, is_executable)
                VALUES (?, ?, ?, ?)
            ''', (skill_name, script['name'], script['path'], script['executable']))
            scripts_count += 1

        # Insert references
        for reference in references:
            cursor.execute('''
                INSERT INTO skill_references
                (skill_name, reference_name, reference_path)
                VALUES (?, ?, ?)
            ''', (skill_name, reference['name'], reference['path']))
            references_count += 1

    conn.commit()

    print(f"\n{'='*50}")
    print(f"Database populated successfully!")
    print(f"  Skills: {skills_count}")
    print(f"  Templates: {templates_count}")
    print(f"  Scripts: {scripts_count}")
    print(f"  References: {references_count}")
    print(f"{'='*50}\n")

def show_summary(conn):
    """Show database summary."""
    cursor = conn.cursor()

    print("Skills by Category:")
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM skills_registry
        GROUP BY category
        ORDER BY count DESC
    ''')

    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} skills")

    print("\nResource Summary:")
    cursor.execute('''
        SELECT * FROM skill_resources
        ORDER BY (template_count + script_count + reference_count) DESC
        LIMIT 5
    ''')

    print(f"  {'Skill':<30} {'Templates':<10} {'Scripts':<10} {'References':<10}")
    print(f"  {'-'*60}")
    for row in cursor.fetchall():
        print(f"  {row[0]:<30} {row[1]:<10} {row[2]:<10} {row[3]:<10}")

def main():
    """Main initialization function."""
    print("="*60)
    print("Claude Skills Metadata Database Initialization")
    print("="*60)

    # Create database
    conn = create_database()

    # Populate with skills
    populate_skills(conn)

    # Show summary
    show_summary(conn)

    conn.close()

    print(f"\n✓ Database created at: {DB_PATH}")
    print("You can now use the skill_db.py module to interact with the database.")

if __name__ == '__main__':
    main()
