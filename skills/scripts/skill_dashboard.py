#!/usr/bin/env python3
"""
Claude Skills Dashboard

Display statistics and analytics about your Claude Code skills.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add lib directory to Python path
lib_path = Path.home() / '.claude' / 'skills' / 'lib'
sys.path.insert(0, str(lib_path))

from skill_db import SkillDB

def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def print_table(headers, rows, col_widths=None):
    """Print a formatted table."""
    if not rows:
        print("  No data available.\n")
        return

    if col_widths is None:
        # Auto-calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Print header
    header_row = "  " + " | ".join(
        headers[i].ljust(col_widths[i]) for i in range(len(headers))
    )
    print(header_row)
    print("  " + "-" * (len(header_row) - 2))

    # Print rows
    for row in rows:
        row_str = "  " + " | ".join(
            str(row[i]).ljust(col_widths[i]) for i in range(len(row))
        )
        print(row_str)

    print()

def show_summary(db):
    """Show overall summary."""
    print_header("Skills Database Summary")

    summary = db.get_summary()

    print(f"  Total Skills:      {summary['total_skills']}")
    print(f"  Total Executions:  {summary['total_executions']}")
    print(f"  Total Templates:   {summary['total_templates']}")
    print(f"  Total Scripts:     {summary['total_scripts']}")
    print(f"  Total Feedback:    {summary['total_feedback']}")

    if summary['most_used_skill']:
        most_used = summary['most_used_skill']
        print(f"\n  Most Used: {most_used['skill_name']} ({most_used['total_executions']} executions)")

    if summary['highest_rated_skill']:
        highest = summary['highest_rated_skill']
        print(f"  Highest Rated: {highest['name']} ({highest['avg_rating']}/5.0)")

def show_skills_by_category(db):
    """Show skills organized by category."""
    print_header("Skills by Category")

    categories = db.get_skill_categories()

    for cat_info in categories:
        category = cat_info['category']
        count = cat_info['skill_count']

        print(f"\n{category.upper()} ({count} skills)")
        print("-" * 50)

        skills = db.get_all_skills(category=category)
        for skill in skills:
            tools = skill['allowed_tools'] or 'Not specified'
            print(f"  • {skill['name']}")
            print(f"    {skill['description'][:100]}...")
            print(f"    Tools: {tools}\n")

def show_popularity(db):
    """Show most popular skills."""
    print_header("Most Popular Skills")

    popular = db.get_skill_popularity(limit=10)

    if not popular:
        print("  No usage data yet. Skills haven't been executed.\n")
        return

    headers = ["Skill", "Category", "Usage", "Avg Rating"]
    rows = [
        [
            p['name'][:30],
            p['category'],
            str(p['usage_count']),
            f"{p['avg_rating']:.1f}" if p['avg_rating'] > 0 else "N/A"
        ]
        for p in popular
    ]

    print_table(headers, rows)

def show_skill_details(db, skill_name):
    """Show detailed information about a specific skill."""
    skill = db.get_skill(skill_name)

    if not skill:
        print(f"\nSkill '{skill_name}' not found.\n")
        return

    print_header(f"Skill: {skill['name']}")

    print(f"Category: {skill['category']}")
    print(f"Allowed Tools: {skill['allowed_tools'] or 'Not specified'}")
    print(f"\nDescription:")
    print(f"  {skill['description']}\n")

    # Show resources
    resources = db.get_skill_resources(skill_name)

    if resources['templates']:
        print("Templates:")
        for t in resources['templates']:
            framework = f" ({t['framework']})" if t['framework'] else ""
            print(f"  • {t['template_name']}{framework}")
        print()

    if resources['scripts']:
        print("Scripts:")
        for s in resources['scripts']:
            executable = " [executable]" if s['is_executable'] else ""
            print(f"  • {s['script_name']}{executable}")
        print()

    if resources['references']:
        print("Reference Documentation:")
        for r in resources['references']:
            print(f"  • {r['reference_name']}")
        print()

    # Show stats if available
    stats = db.get_skill_stats(skill_name)
    if stats:
        print("Usage Statistics:")
        print(f"  Total Executions: {stats['total_executions']}")
        print(f"  Avg Duration: {stats['avg_duration_ms']:.0f}ms")
        print(f"  Success Rate: {stats['success_rate_percent']:.1f}%")
        print(f"  Last Used: {stats['last_used']}")
        print()

    # Show feedback
    feedback = db.get_skill_feedback(skill_name)
    if feedback:
        print(f"Feedback ({len(feedback)} reviews):")
        avg_rating = sum(f['rating'] for f in feedback) / len(feedback)
        print(f"  Average Rating: {avg_rating:.1f}/5.0")
        for f in feedback[:3]:  # Show first 3
            print(f"  • Rating: {f['rating']}/5 - {f['comments'] or 'No comment'}")
        print()

def show_errors(db):
    """Show skills with errors."""
    print_header("Skills with Errors")

    errors = db.get_skill_errors()

    if not errors:
        print("  No errors recorded. Great job!\n")
        return

    headers = ["Skill", "Error Count", "Last Error"]
    rows = [
        [
            e['skill_name'],
            str(e['error_count']),
            e['last_error']
        ]
        for e in errors
    ]

    print_table(headers, rows)

def show_recent_activity(db):
    """Show recent skill executions."""
    print_header("Recent Activity (Last 10 Executions)")

    history = db.get_execution_history(limit=10)

    if not history:
        print("  No execution history yet.\n")
        return

    headers = ["Skill", "Time", "Duration", "Status"]
    rows = [
        [
            h['skill_name'][:30],
            h['executed_at'],
            f"{h['duration_ms']}ms" if h['duration_ms'] else "N/A",
            "✓" if h['success'] else f"✗ {h['error_message']}"
        ]
        for h in history
    ]

    print_table(headers, rows)

def interactive_menu(db):
    """Interactive menu for exploring skills."""
    while True:
        print("\n" + "="*70)
        print("Claude Skills Dashboard - Menu")
        print("="*70)
        print("\n1. Show Summary")
        print("2. List All Skills")
        print("3. Show Popular Skills")
        print("4. Show Skill Details")
        print("5. Search Skills")
        print("6. Show Recent Activity")
        print("7. Show Errors")
        print("8. Exit")

        choice = input("\nEnter your choice (1-8): ").strip()

        if choice == '1':
            show_summary(db)
        elif choice == '2':
            show_skills_by_category(db)
        elif choice == '3':
            show_popularity(db)
        elif choice == '4':
            skill_name = input("Enter skill name: ").strip()
            show_skill_details(db, skill_name)
        elif choice == '5':
            query = input("Enter search query: ").strip()
            results = db.search_skills(query)
            print(f"\nFound {len(results)} skills:")
            for skill in results:
                print(f"  • {skill['name']} - {skill['description'][:60]}...")
        elif choice == '6':
            show_recent_activity(db)
        elif choice == '7':
            show_errors(db)
        elif choice == '8':
            print("\nGoodbye!\n")
            break
        else:
            print("\nInvalid choice. Please try again.")

def main():
    """Main dashboard function."""
    try:
        db = SkillDB()
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Please run: python3 ~/.claude/skills/scripts/init_db.py")
        return 1

    # If arguments provided, show specific view
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'summary':
            show_summary(db)
        elif command == 'skills':
            show_skills_by_category(db)
        elif command == 'popular':
            show_popularity(db)
        elif command == 'errors':
            show_errors(db)
        elif command == 'activity':
            show_recent_activity(db)
        elif command == 'detail' and len(sys.argv) > 2:
            show_skill_details(db, sys.argv[2])
        else:
            print("Usage:")
            print("  skill_dashboard.py              # Interactive mode")
            print("  skill_dashboard.py summary      # Show summary")
            print("  skill_dashboard.py skills       # List all skills")
            print("  skill_dashboard.py popular      # Show popular skills")
            print("  skill_dashboard.py errors       # Show errors")
            print("  skill_dashboard.py activity     # Show recent activity")
            print("  skill_dashboard.py detail <name> # Show skill details")
    else:
        # Interactive mode
        interactive_menu(db)

    return 0

if __name__ == '__main__':
    sys.exit(main())
