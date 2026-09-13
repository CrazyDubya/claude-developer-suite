#!/bin/bash

# Agent Manager - Main slash command handler for scalable agent organization
# Usage: /agent-manager <subcommand> [args...]

set -e

# Determine the script's directory to create a relative path to the agent-registry
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
AGENT_REGISTRY_PATH="$SCRIPT_DIR/../agent-registry"

# Configuration
CLAUDE_HOME="$HOME/.claude"
AGENT_REGISTRY="$CLAUDE_HOME/agent-registry"
AGENT_DB="$AGENT_REGISTRY/index.db"
AGENTS_DIR="$CLAUDE_HOME/agents"
SETUP_SCRIPT="$AGENT_REGISTRY/setup.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_header() { echo -e "${PURPLE}🤖 $1${NC}"; }

# Ensure registry is initialized
ensure_registry() {
    if [[ ! -f "$AGENT_DB" ]]; then
        log_info "Initializing agent registry..."
        python3 "$SETUP_SCRIPT"
    fi
}

# Main command dispatcher
main() {
    local subcommand="${1:-help}"
    shift || true
    
    case "$subcommand" in
        "setup"|"init")
            cmd_setup "$@"
            ;;
        "search"|"find")
            cmd_search "$@"
            ;;
        "profile")
            cmd_profile "$@"
            ;;
        "manifest")
            cmd_manifest "$@"
            ;;
        "index"|"refresh")
            cmd_index "$@"
            ;;
        "stats")
            cmd_stats "$@"
            ;;
        "domains")
            cmd_domains "$@"
            ;;
        "capabilities")
            cmd_capabilities "$@"
            ;;
        "backup")
            cmd_backup "$@"
            ;;
        "restore")
            cmd_restore "$@"
            ;;
        "verify")
            cmd_verify "$@"
            ;;
        "sources")
            cmd_sources "$@"
            ;;
        "import")
            cmd_import "$@"
            ;;
        "export")
            cmd_export "$@"
            ;;
        # Shadow System Commands
        "shadow-init")
            cmd_shadow_init "$@"
            ;;
        "activate")
            cmd_activate "$@"
            ;;
        "deactivate")
            cmd_deactivate "$@"
            ;;
        "switch")
            cmd_switch "$@"
            ;;
        "status")
            cmd_status "$@"
            ;;
        "active")
            cmd_active "$@"
            ;;
        "archived")
            cmd_archived "$@"
            ;;
        "emergency-restore")
            cmd_emergency_restore "$@"
            ;;
        "help"|"-h"|"--help")
            cmd_help
            ;;
        *)
            log_error "Unknown subcommand: $subcommand"
            cmd_help
            exit 1
            ;;
    esac
}

# Initialize/setup registry
cmd_setup() {
    local project_type="${1:-web}"
    
    log_header "Agent Registry Setup"
    
    # Initialize registry if needed
    ensure_registry
    
    # Create project-specific manifest based on type
    if [[ -n "$project_type" ]]; then
        log_info "Setting up agent manifest for project type: $project_type"
        python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
agents = registry.search_agents(domains=['$project_type'], limit=10)

manifest_content = '''# Project Agent Manifest
# Only agents listed here will be loaded in this project

agents:'''

for agent in agents:
    manifest_content += f'''
  - name: {agent['name']}
    description: {agent['description'][:80]}...'''

# Write to current directory
with open('.claude-agents', 'w') as f:
    f.write(manifest_content)

print('📄 Created .claude-agents manifest with ' + str(len(agents)) + ' agents')
"
    fi
    
    log_success "Agent registry setup complete!"
}

# Search agents
cmd_search() {
    local query="$*"
    
    log_header "Agent Search: \"$query\""
    
    ensure_registry
    
    if [[ -z "$query" ]]; then
        log_error "Please provide a search query"
        echo "Usage: /agent-manager search <query>"
        echo "       /agent-manager search --domain web"
        echo "       /agent-manager search --capability testing"
        return 1
    fi
    
    # Parse search parameters
    local search_query=""
    local domains=""
    local capabilities=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --domain|-d)
                domains="$2"
                shift 2
                ;;
            --capability|-c)
                capabilities="$2"
                shift 2
                ;;
            --limit|-l)
                limit="$2"
                shift 2
                ;;
            *)
                search_query="$search_query $1"
                shift
                ;;
        esac
    done
    
    # Execute search
    python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
domains = ['$domains'] if '$domains' else None
capabilities = ['$capabilities'] if '$capabilities' else None
query = '$search_query'.strip() if '$search_query'.strip() else None

agents = registry.search_agents(
    query=query,
    domains=domains,
    capabilities=capabilities,
    limit=int('${limit:-20}')
)

if not agents:
    print('🔍 No agents found matching criteria')
else:
    print(f'🔍 Found {len(agents)} agents:')
    print()
    for agent in agents:
        print(f'📍 {agent[\"name\"]}')
        print(f'   {agent[\"description\"][:100]}...')
        print(f'   Domains: {', '.join(agent[\"domains\"])}')
        print(f'   Capabilities: {', '.join(agent[\"capabilities\"])}')
        print()
"
}

# Manage agent profiles
cmd_profile() {
    local action="${1:-list}"
    local profile_name="$2"
    
    ensure_registry
    
    case "$action" in
        "save")
            if [[ -z "$profile_name" ]]; then
                log_error "Please provide a profile name"
                echo "Usage: /agent-manager profile save <name>"
                return 1
            fi
            
            # Read current manifest and save as profile
            if [[ -f ".claude-agents" ]]; then
                log_info "Saving current agent manifest as profile: $profile_name"
                
                # Extract agent names from manifest
                agents=$(grep "name:" .claude-agents | sed 's/.*name: //' | tr '\n' ',' | sed 's/,$//')
                
                python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
agents = '$agents'.split(',') if '$agents' else []
registry.save_project_profile('$profile_name', 'Saved from current project', agents)
print(f'💾 Saved profile: $profile_name with {len(agents)} agents')
"
            else
                log_error "No .claude-agents manifest found in current directory"
            fi
            ;;
        "load")
            if [[ -z "$profile_name" ]]; then
                log_error "Please provide a profile name"
                echo "Usage: /agent-manager profile load <name>"
                return 1
            fi
            
            log_info "Loading agent profile: $profile_name"
            
            python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
profile = registry.load_project_profile('$profile_name')

if profile:
    manifest_content = '''# Project Agent Manifest - Profile: $profile_name
# ''' + profile['description'] + '''

agents:'''
    
    for agent in profile['agents']:
        # Get agent details
        results = registry.search_agents(query=agent, limit=1)
        if results:
            agent_info = results[0]
            manifest_content += f'''
  - name: {agent_info['name']}
    description: {agent_info['description'][:80]}...'''
    
    with open('.claude-agents', 'w') as f:
        f.write(manifest_content)
    
    print(f'📄 Loaded profile: $profile_name with {len(profile[\"agents\"])} agents')
else:
    print(f'❌ Profile not found: $profile_name')
"
            ;;
        "list")
            log_header "Saved Agent Profiles"
            
            python3 -c "
import sys, sqlite3
sys.path.append(\"$AGENT_REGISTRY_PATH\")

conn = sqlite3.connect('$AGENT_DB')
cursor = conn.cursor()
cursor.execute('SELECT name, description, agent_list FROM project_profiles ORDER BY name')

profiles = cursor.fetchall()
if profiles:
    for name, desc, agents in profiles:
        import json
        agent_count = len(json.loads(agents))
        print(f'📋 {name} ({agent_count} agents)')
        print(f'   {desc}')
        print()
else:
    print('📋 No saved profiles found')
    
conn.close()
"
            ;;
        *)
            log_error "Unknown profile action: $action"
            echo "Usage: /agent-manager profile <save|load|list> [name]"
            ;;
    esac
}

# Manage project manifests
cmd_manifest() {
    local action="${1:-show}"
    
    case "$action" in
        "show"|"list")
            if [[ -f ".claude-agents" ]]; then
                log_header "Current Project Agent Manifest"
                cat .claude-agents
            else
                log_warning "No .claude-agents manifest found in current directory"
                echo "Create one with: /agent-manager setup [project-type]"
            fi
            ;;
        "validate")
            if [[ -f ".claude-agents" ]]; then
                log_info "Validating agent manifest..."
                
                # Extract agent names and check they exist
                agents=$(grep "name:" .claude-agents | sed 's/.*name: //' | tr '\n' ' ')
                
                for agent in $agents; do
                    if [[ -f "$AGENTS_DIR/$agent.md" ]]; then
                        echo "✅ $agent"
                    else
                        echo "❌ $agent (file not found)"
                    fi
                done
            else
                log_error "No .claude-agents manifest found"
            fi
            ;;
        "create")
            local project_type="${2:-web}"
            cmd_setup "$project_type"
            ;;
        *)
            log_error "Unknown manifest action: $action"
            echo "Usage: /agent-manager manifest <show|validate|create> [project-type]"
            ;;
    esac
}

# Re-index agents
cmd_index() {
    log_header "Re-indexing Agent Registry"
    
    python3 "$SETUP_SCRIPT"
    
    log_success "Agent registry re-indexed!"
}

# Show registry statistics
cmd_stats() {
    log_header "Agent Registry Statistics"
    
    ensure_registry
    
    python3 -c "
import sys, sqlite3
sys.path.append(\"$AGENT_REGISTRY_PATH\")

conn = sqlite3.connect('$AGENT_DB')
cursor = conn.cursor()

# Total agents
cursor.execute('SELECT COUNT(*) FROM agents')
total_agents = cursor.fetchone()[0]
print(f'📊 Total Agents: {total_agents}')

# Agents by domain
cursor.execute('SELECT domain, COUNT(*) FROM agent_domains GROUP BY domain ORDER BY COUNT(*) DESC')
domains = cursor.fetchall()
print(f'\n🏗️  Agents by Domain:')
for domain, count in domains:
    print(f'   {domain}: {count}')

# Agents by capability  
cursor.execute('SELECT capability, COUNT(*) FROM agent_capabilities GROUP BY capability ORDER BY COUNT(*) DESC')
capabilities = cursor.fetchall()
print(f'\n⚙️  Agents by Capability:')
for capability, count in capabilities:
    print(f'   {capability}: {count}')

# Saved profiles
cursor.execute('SELECT COUNT(*) FROM project_profiles')
profiles = cursor.fetchone()[0]
print(f'\n💾 Saved Profiles: {profiles}')

conn.close()
"
}

# List available domains
cmd_domains() {
    log_header "Available Domains"
    
    ensure_registry
    
    python3 -c "
import sys, sqlite3
sys.path.append(\"$AGENT_REGISTRY_PATH\")

conn = sqlite3.connect('$AGENT_DB')
cursor = conn.cursor()

cursor.execute('SELECT domain, COUNT(*) FROM agent_domains GROUP BY domain ORDER BY domain')
domains = cursor.fetchall()

for domain, count in domains:
    print(f'🏷️  {domain} ({count} agents)')

conn.close()
"
}

# List available capabilities
cmd_capabilities() {
    log_header "Available Capabilities"
    
    ensure_registry
    
    python3 -c "
import sys, sqlite3
sys.path.append(\"$AGENT_REGISTRY_PATH\")

conn = sqlite3.connect('$AGENT_DB')
cursor = conn.cursor()

cursor.execute('SELECT capability, COUNT(*) FROM agent_capabilities GROUP BY capability ORDER BY capability')
capabilities = cursor.fetchall()

for capability, count in capabilities:
    print(f'⚙️  {capability} ({count} agents)')

conn.close()
"
}

# Backup agents
cmd_backup() {
    log_header "Creating Agent Backup"
    
    ensure_registry
    
    local backup_name="$1"
    
    python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
backup_name = registry.backup_agents('$backup_name' if '$backup_name' else None)
print(f'Backup completed: {backup_name}')
"
}

# Restore agents from backup
cmd_restore() {
    local backup_name="$1"
    
    if [[ -z "$backup_name" ]]; then
        log_error "Please provide a backup name"
        echo "Usage: /agent-manager restore <backup-name>"
        echo ""
        echo "Available backups:"
        python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
backups = registry.list_backups()
if not backups:
    print('  No backups found')
else:
    for backup in backups:
        print(f'  {backup[\"name\"]} ({backup[\"timestamp\"]}) - {backup[\"agent_count\"]} agents')
"
        return 1
    fi
    
    log_header "Restoring Agent Backup: $backup_name"
    
    log_warning "This will replace current agent database with backup data."
    echo "Are you sure? (y/N)"
    read -r confirmation
    
    if [[ "$confirmation" =~ ^[Yy]$ ]]; then
        python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
success = registry.restore_backup('$backup_name', confirm=True)
if not success:
    exit(1)
"
        log_success "Backup restored successfully"
    else
        log_info "Restore cancelled"
    fi
}

# Verify agent integrity
cmd_verify() {
    log_header "Verifying Agent Integrity"
    
    ensure_registry
    
    python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
results = registry.verify_agents()

print('📊 Agent Verification Results:')
print()
print(f'✅ Valid agents: {len(results[\"valid\"])}')

if results['missing_files']:
    print(f'❌ Missing files: {len(results[\"missing_files\"])}')
    for missing in results['missing_files']:
        print(f'   {missing}')

if results['hash_mismatches']:
    print(f'⚠️  Hash mismatches: {len(results[\"hash_mismatches\"])}')
    for mismatch in results['hash_mismatches']:
        print(f'   {mismatch}')

if results['orphaned_files']:
    print(f'🔍 Orphaned files: {len(results[\"orphaned_files\"])}')
    for orphaned in results['orphaned_files']:
        print(f'   {orphaned}')

if not results['missing_files'] and not results['hash_mismatches'] and not results['orphaned_files']:
    print('🎉 All agents verified successfully!')
"
}

# Show agent sources
cmd_sources() {
    log_header "Agent Sources"
    
    ensure_registry
    
    python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
sources = registry.get_sources()

for source in sources:
    status = '✅' if source['exists'] else '❌'
    print(f'{status} {source[\"name\"]} ({source[\"agent_count\"]} agents)')
    print(f'   Path: {source[\"path\"]}')
    print()
"
}

# Import agents from directory
cmd_import() {
    local import_path="$1"
    
    if [[ -z "$import_path" ]]; then
        log_error "Please provide an import path"
        echo "Usage: /agent-manager import <directory-path>"
        return 1
    fi
    
    log_header "Importing Agents from: $import_path"
    
    ensure_registry
    
    python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()
imported_count = registry.import_agents('$import_path')
"
}

# Export agent configurations
cmd_export() {
    local format="json"
    local output_file=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --format)
                format="$2"
                shift 2
                ;;
            --output|-o)
                output_file="$2"
                shift 2
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Usage: /agent-manager export [--format json|yaml] [--output file]"
                return 1
                ;;
        esac
    done
    
    if [[ -z "$output_file" ]]; then
        output_file="agents_export.${format}"
    fi
    
    log_header "Exporting Agent Configurations"
    log_info "Format: $format"
    log_info "Output: $output_file"
    
    ensure_registry
    
    python3 -c "
import sys, json, yaml
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry()

# Get all agents
conn = registry.db_path
import sqlite3
conn = sqlite3.connect(str(registry.db_path))
cursor = conn.cursor()

cursor.execute('SELECT name, description, domains, capabilities, source FROM agents ORDER BY name')
agents = []
for row in cursor.fetchall():
    agents.append({
        'name': row[0],
        'description': row[1],
        'domains': json.loads(row[2]),
        'capabilities': json.loads(row[3]),
        'source': row[4]
    })

conn.close()

export_data = {
    'export_timestamp': str(registry.db_path.parent.parent / 'datetime.datetime.now().isoformat()'),
    'total_agents': len(agents),
    'agents': agents
}

if '$format' == 'yaml':
    with open('$output_file', 'w') as f:
        yaml.dump(export_data, f, default_flow_style=False)
else:
    with open('$output_file', 'w') as f:
        json.dump(export_data, f, indent=2)

print(f'✅ Exported {len(agents)} agents to: $output_file')
"
}

# Shadow System Commands

# Initialize shadow directory system
cmd_shadow_init() {
    local force_flag=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force|-f)
                force_flag="--force"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Usage: /agent-manager shadow-init [--force]"
                return 1
                ;;
        esac
    done
    
    log_header "Initializing Shadow Directory System"
    log_info "This will archive all existing agents and give you full control over what Claude Code sees"
    
    # Initialize shadow system
    python3 "$SETUP_SCRIPT" --shadow --init-shadow $force_flag
    
    if [[ $? -eq 0 ]]; then
        log_success "Shadow system initialized successfully!"
        echo ""
        log_info "Next steps:"
        echo "  • Use '/agent-manager activate <agents>' to make specific agents available"
        echo "  • Use '/agent-manager switch <profile>' to load a complete agent set"
        echo "  • Use '/agent-manager status' to see current active agents"
    else
        log_error "Shadow system initialization failed"
        return 1
    fi
}

# Activate specific agents (move from archive to active)
cmd_activate() {
    local source="global"
    local agents=()
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --source|-s)
                source="$2"
                shift 2
                ;;
            --global|-g)
                source="global"
                shift
                ;;
            --project|-p)
                source="project"
                shift
                ;;
            *)
                agents+=("$1")
                shift
                ;;
        esac
    done
    
    if [[ ${#agents[@]} -eq 0 ]]; then
        log_error "No agents specified to activate"
        echo "Usage: /agent-manager activate <agent1> [agent2...] [--source global|project]"
        return 1
    fi
    
    log_header "Activating Agents"
    
    # Convert array to comma-separated string
    agent_list=$(IFS=','; echo "${agents[*]}")
    
    python3 -c "
import sys
import json
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
result = registry.activate_agents_shadow('$agent_list'.split(','), '$source')

print(json.dumps(result, indent=2))

if result.get('success'):
    activated = result.get('activated', [])
    failed = result.get('failed', [])
    print(f'\\n✅ Activated {len(activated)} agents from $source')
    for agent in activated:
        print(f'   • {agent}')
    if failed:
        print(f'\\n⚠️  Failed to activate {len(failed)} agents:')
        for fail in failed:
            print(f'   • {fail}')
else:
    print(f'\\n❌ {result.get(\"message\", \"Activation failed\")}')
    sys.exit(1)
"
}

# Deactivate specific agents (move from active to archive)
cmd_deactivate() {
    local source="global"
    local agents=()
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --source|-s)
                source="$2"
                shift 2
                ;;
            --global|-g)
                source="global"
                shift
                ;;
            --project|-p)
                source="project"
                shift
                ;;
            *)
                agents+=("$1")
                shift
                ;;
        esac
    done
    
    if [[ ${#agents[@]} -eq 0 ]]; then
        log_error "No agents specified to deactivate"
        echo "Usage: /agent-manager deactivate <agent1> [agent2...] [--source global|project]"
        return 1
    fi
    
    log_header "Deactivating Agents"
    
    # Convert array to comma-separated string
    agent_list=$(IFS=','; echo "${agents[*]}")
    
    python3 -c "
import sys
import json
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
result = registry.deactivate_agents_shadow('$agent_list'.split(','), '$source')

print(json.dumps(result, indent=2))

if result.get('success'):
    deactivated = result.get('deactivated', [])
    failed = result.get('failed', [])
    print(f'\\n✅ Deactivated {len(deactivated)} agents from $source')
    for agent in deactivated:
        print(f'   • {agent}')
    if failed:
        print(f'\\n⚠️  Failed to deactivate {len(failed)} agents:')
        for fail in failed:
            print(f'   • {fail}')
else:
    print(f'\\n❌ {result.get(\"message\", \"Deactivation failed\")}')
    sys.exit(1)
"
}

# Switch to a complete profile (replace all active agents)
cmd_switch() {
    local profile_name="$1"
    
    if [[ -z "$profile_name" ]]; then
        log_error "Profile name required"
        echo "Usage: /agent-manager switch <profile-name>"
        echo ""
        echo "Available profiles:"
        cmd_profile list
        return 1
    fi
    
    log_header "Switching to Profile: $profile_name"
    
    python3 -c "
import sys
import json
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
result = registry.switch_profile_shadow('$profile_name')

print(json.dumps(result, indent=2))

if result.get('success'):
    print(f'\\n✅ Successfully switched to profile: $profile_name')
    details = result.get('details', {})
    
    # Show what was deactivated
    deactivated = details.get('deactivated', {})
    if deactivated.get('global', {}).get('deactivated'):
        print('\\n📤 Deactivated global agents:')
        for agent in deactivated['global']['deactivated']:
            print(f'   • {agent}')
    
    # Show what was activated
    activated = details.get('activated', {})
    if activated.get('global', {}).get('activated'):
        print('\\n📥 Activated global agents:')
        for agent in activated['global']['activated']:
            print(f'   • {agent}')
            
    print('\\n🎯 Profile switch complete!')
    print('   Claude Code will now see only the agents from this profile.')
    
else:
    print(f'\\n❌ {result.get(\"message\", \"Profile switch failed\")}')
    sys.exit(1)
"
}

# Show current shadow system status
cmd_status() {
    log_header "Shadow System Status"
    
    python3 -c "
import sys
import json
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
status = registry.get_shadow_status()

if not status.get('shadow_enabled'):
    print('❌ Shadow system not enabled')
    print('   Use \\'/agent-manager shadow-init\\' to initialize the shadow system')
    sys.exit(1)

print('🔍 Shadow System Status:')
print(f'   Initialized: {\"✅\" if status.get(\"initialized\") else \"❌\"}')

active = status.get('active_agents', {})
active_counts = status.get('active_counts', {})
archived_counts = status.get('archived_counts', {})

print(f'\\n📊 Agent Counts:')
print(f'   Global Active: {active_counts.get(\"global\", 0)}')
print(f'   Project Active: {active_counts.get(\"project\", 0)}')
print(f'   Global Archived: {archived_counts.get(\"global\", 0)}')
print(f'   Project Archived: {archived_counts.get(\"project\", 0)}')
print(f'   Total Agents: {status.get(\"total_agents\", 0)}')

if status.get('last_profile'):
    print(f'\\n🎯 Current Profile: {status[\"last_profile\"]}')

last_update = status.get('last_update')
if last_update:
    print(f'\\n🕒 Last Update: {last_update}')
    
print('\\n📄 What Claude Code Currently Sees:')
global_active = active.get('global', [])
project_active = active.get('project', [])

if global_active:
    print('   Global Agents:')
    for agent in global_active[:10]:  # Show first 10
        print(f'     • {agent}')
    if len(global_active) > 10:
        print(f'     ... and {len(global_active) - 10} more')
else:
    print('   Global Agents: None')

if project_active:
    print('   Project Agents:')
    for agent in project_active[:10]:
        print(f'     • {agent}')
    if len(project_active) > 10:
        print(f'     ... and {len(project_active) - 10} more')
else:
    print('   Project Agents: None')
"
}

# Show currently active agents (what Claude Code sees)
cmd_active() {
    log_header "Currently Active Agents"
    
    python3 -c "
import sys
import json
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
status = registry.get_shadow_status()

if not status.get('shadow_enabled'):
    print('❌ Shadow system not enabled')
    sys.exit(1)

active = status.get('active_agents', {})
global_active = active.get('global', [])
project_active = active.get('project', [])

print('🎯 Agents Currently Visible to Claude Code:')

if global_active:
    print(f'\\n📁 Global Agents ({len(global_active)}):')
    for i, agent in enumerate(global_active, 1):
        print(f'  {i:2d}. {agent}')
else:
    print('\\n📁 Global Agents: None')

if project_active:
    print(f'\\n📁 Project Agents ({len(project_active)}):')
    for i, agent in enumerate(project_active, 1):
        print(f'  {i:2d}. {agent}')
else:
    print('\\n📁 Project Agents: None')

total_active = len(global_active) + len(project_active)
print(f'\\n📊 Total Active: {total_active} agents')

if total_active == 0:
    print('\\n💡 Tip: Use \\'/agent-manager activate <agents>\\' or \\'/agent-manager switch <profile>\\' to make agents available')
"
}

# Show archived agents (available but not active)
cmd_archived() {
    local source=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --source|-s)
                source="$2"
                shift 2
                ;;
            --global|-g)
                source="global"
                shift
                ;;
            --project|-p)
                source="project"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Usage: /agent-manager archived [--source global|project]"
                return 1
                ;;
        esac
    done
    
    log_header "Archived Agents"
    
    python3 -c "
import sys
import json
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
source_filter = '$source' if '$source' else None

result = registry.list_archived_agents_shadow(source_filter)

if not result.get('success'):
    print(f'❌ {result.get(\"message\", \"Failed to list archived agents\")}')
    sys.exit(1)

archived = result.get('archived', {})
total = result.get('total', 0)

print(f'📚 Archived Agents (Available for Activation):')

if source_filter:
    agents = archived.get(source_filter, [])
    print(f'\\n📁 {source_filter.title()} Agents ({len(agents)}):')
    for i, agent in enumerate(agents, 1):
        print(f'  {i:2d}. {agent}')
else:
    global_agents = archived.get('global', [])
    project_agents = archived.get('project', [])
    
    if global_agents:
        print(f'\\n📁 Global Agents ({len(global_agents)}):')
        for i, agent in enumerate(global_agents, 1):
            print(f'  {i:2d}. {agent}')
    else:
        print('\\n📁 Global Agents: None')
    
    if project_agents:
        print(f'\\n📁 Project Agents ({len(project_agents)}):')
        for i, agent in enumerate(project_agents, 1):
            print(f'  {i:2d}. {agent}')
    else:
        print('\\n📁 Project Agents: None')

print(f'\\n📊 Total Archived: {total} agents')

if total > 0:
    print('\\n💡 Tip: Use \\'/agent-manager activate <agent-names>\\' to make agents available to Claude Code')
"
}

# Emergency restore from backup
cmd_emergency_restore() {
    local backup_name="$1"
    
    if [[ -z "$backup_name" ]]; then
        log_error "Backup name required"
        echo "Usage: /agent-manager emergency-restore <backup-name>"
        echo ""
        echo "Available backups:"
        python3 -c "
import sys
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
if hasattr(registry.shadow_manager, 'backup_dir') and registry.shadow_manager.backup_dir.exists():
    for backup_dir in registry.shadow_manager.backup_dir.iterdir():
        if backup_dir.is_dir():
            print(f'  • {backup_dir.name}')
else:
    print('  No backups found')
"
        return 1
    fi
    
    log_header "Emergency Restore from Backup: $backup_name"
    log_warning "This will replace all current active agents with the backup version"
    
    python3 -c "
import sys
import json
sys.path.append(\"$AGENT_REGISTRY_PATH\")
from setup import AgentRegistry

registry = AgentRegistry(enable_shadow_system=True)
result = registry.emergency_restore_shadow('$backup_name')

print(json.dumps(result, indent=2))

if result.get('success'):
    print(f'\\n✅ Emergency restore completed from: $backup_name')
    print('   All agents have been restored to their backup state')
else:
    print(f'\\n❌ {result.get(\"message\", \"Emergency restore failed\")}')
    sys.exit(1)
"
}

# Show help
cmd_help() {
    cat << EOF
$(echo -e "${PURPLE}🤖 Agent Manager - Scalable Agent Organization System${NC}")

$(echo -e "${BLUE}USAGE:${NC}")
  /agent-manager <subcommand> [options]

$(echo -e "${BLUE}SUBCOMMANDS:${NC}")
  $(echo -e "${GREEN}setup [type]${NC}")      Initialize agent manifest for project type
  $(echo -e "${GREEN}search <query>${NC}")    Search agents by name, description, domain, or capability
  $(echo -e "${GREEN}profile <action>${NC}")  Manage agent profiles (save/load/list)
  $(echo -e "${GREEN}manifest <action>${NC}") Manage project manifests (show/validate/create)
  $(echo -e "${GREEN}index${NC}")             Re-index all agents in registry
  $(echo -e "${GREEN}stats${NC}")             Show registry statistics
  $(echo -e "${GREEN}domains${NC}")           List available domains
  $(echo -e "${GREEN}capabilities${NC}")      List available capabilities

$(echo -e "${BLUE}SAFETY COMMANDS:${NC}")
  $(echo -e "${GREEN}backup [name]${NC}")     Create timestamped backup of agents
  $(echo -e "${GREEN}restore <name>${NC}")    Restore agents from backup
  $(echo -e "${GREEN}verify${NC}")            Verify agent file integrity
  $(echo -e "${GREEN}sources${NC}")           Show all agent source locations

$(echo -e "${BLUE}IMPORT/EXPORT:${NC}")
  $(echo -e "${GREEN}import <path>${NC}")     Import custom agents from directory
  $(echo -e "${GREEN}export [options]${NC}")  Export agent configurations

$(echo -e "${BLUE}SHADOW SYSTEM (v2.0):${NC}")
  $(echo -e "${GREEN}shadow-init${NC}")       Initialize shadow directory system (archive all agents)
  $(echo -e "${GREEN}activate <agents>${NC}") Move agents from archive → active (Claude Code sees them)
  $(echo -e "${GREEN}deactivate <agents>${NC}") Move agents from active → archive (hide from Claude Code)
  $(echo -e "${GREEN}switch <profile>${NC}")   Replace all active agents with profile agents
  $(echo -e "${GREEN}status${NC}")            Show shadow system status and active agents
  $(echo -e "${GREEN}active${NC}")            List currently active agents (what Claude Code sees)
  $(echo -e "${GREEN}archived${NC}")          List archived agents (available for activation)
  $(echo -e "${GREEN}emergency-restore${NC}") Restore from shadow system backup

$(echo -e "${BLUE}EXAMPLES:${NC}")
  /agent-manager shadow-init
  /agent-manager activate react-specialist testing-specialist --source global
  /agent-manager deactivate pandas-specialist
  /agent-manager switch web-fullstack
  /agent-manager status
  /agent-manager archived --source global
  /agent-manager setup web
  /agent-manager search "react testing" --domain web --limit 5
  /agent-manager profile save my-web-stack
  /agent-manager profile load my-web-stack
  /agent-manager backup my-backup
  /agent-manager verify
  /agent-manager import ./custom-agents/
  /agent-manager export --format yaml

$(echo -e "${BLUE}SEARCH OPTIONS:${NC}")
  --domain, -d <domain>           Filter by domain (web, data-science, etc.)
  --capability, -c <capability>   Filter by capability (testing, optimization, etc.)
  --source, -s <global|project>   Filter by source location
  --limit, -l <number>           Limit number of results (default: 20)

$(echo -e "${BLUE}PROJECT TYPES:${NC}")
  web, backend, data-science, infrastructure, graphics, mobile, desktop

$(echo -e "${YELLOW}The agent registry scales to billions of agents through intelligent indexing.${NC}")
$(echo -e "${YELLOW}Only agents in your project's .claude-agents manifest are loaded.${NC}")
EOF
}

# Execute main function with all arguments
main "$@"