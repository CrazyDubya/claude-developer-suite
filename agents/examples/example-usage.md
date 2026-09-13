# Claude Agent Manager - Usage Examples

This document provides practical examples of using the Claude Agent Manager in different scenarios.

## Scenario 1: Web Development Project

### Initial Setup

```bash
# Navigate to your web project
cd ~/projects/my-web-app

# Initialize with web development agents
/agent-manager setup web

# View the generated manifest
/agent-manager manifest show
```

**Generated manifest includes:**
- react-specialist (frontend development)
- api-specialist (backend APIs)
- database-specialist (data layer)
- testing-specialist (quality assurance)

### Customizing Your Setup

```bash
# Search for additional agents
/agent-manager search "security authentication" --domain web

# Search for performance optimization
/agent-manager search --capability optimization --limit 3

# Save your customized setup
/agent-manager profile save web-app-2024
```

### Team Collaboration

```bash
# Share your setup with team members
# They can load your exact configuration:
/agent-manager profile load web-app-2024

# View all available team profiles
/agent-manager profile list
```

## Scenario 2: Data Science Research

### Setting Up Data Science Environment

```bash
# Create new research project
mkdir ~/research/market-analysis && cd ~/research/market-analysis

# Initialize with data science stack
/agent-manager setup data-science

# Verify agents are loaded
/agent-manager manifest show
```

**Default data science agents:**
- pandas-specialist (data manipulation)
- scikit-learn-specialist (machine learning)
- plotly-specialist (visualization)
- jupyter-specialist (notebook development)

### Adding Domain-Specific Agents

```bash
# Add financial analysis capabilities
/agent-manager search "finance economics" --domain data-science

# Add natural language processing
/agent-manager search "nlp text analysis" --capability analysis

# Update manifest and save
/agent-manager profile save financial-research
```

## Scenario 3: API Development

### Microservices Architecture

```bash
# New microservice project
cd ~/projects/user-service

# Set up backend-focused agents
/agent-manager setup backend

# Add specific API development agents
/agent-manager search --capability api-development --domain backend

# Include database optimization
/agent-manager search --capability optimization --domain database
```

### Testing & Documentation

```bash
# Add comprehensive testing support
/agent-manager search "api testing integration" --capability testing

# Include documentation generation
/agent-manager search --capability documentation

# Save complete API development setup
/agent-manager profile save microservice-api
```

## Scenario 4: Mobile App Development

### Cross-Platform Setup

```bash
# React Native project
cd ~/projects/mobile-app

# Search for mobile development agents
/agent-manager search --domain mobile --limit 10

# Add cross-platform specialists
/agent-manager search "react native flutter" --domain mobile

# Include testing for mobile
/agent-manager search --capability testing --domain mobile
```

### Platform-Specific Optimization

```bash
# iOS-specific agents
/agent-manager search "ios swift xcode" --domain mobile

# Android-specific agents  
/agent-manager search "android kotlin" --domain mobile

# Save mobile development profile
/agent-manager profile save mobile-crossplatform
```

## Scenario 5: Infrastructure & DevOps

### Cloud Infrastructure

```bash
# Infrastructure as Code project
cd ~/projects/terraform-aws

# Set up infrastructure agents
/agent-manager setup infrastructure

# Add cloud-specific agents
/agent-manager search "aws terraform kubernetes" --domain infrastructure

# Include monitoring and observability
/agent-manager search --capability monitoring
```

### CI/CD Pipeline

```bash
# Add deployment automation
/agent-manager search "cicd pipeline deployment" --capability automation

# Include security scanning
/agent-manager search --capability security --domain infrastructure

# Save DevOps setup
/agent-manager profile save aws-devops
```

## Scenario 6: Machine Learning Operations (MLOps)

### ML Pipeline Development

```bash
# MLOps project setup
cd ~/projects/ml-pipeline

# Initialize with AI infrastructure profile
/agent-manager profile load ai-infrastructure

# Add specific ML frameworks
/agent-manager search "pytorch tensorflow" --domain data-science

# Include container orchestration
/agent-manager search "docker kubernetes" --domain infrastructure
```

### Model Deployment

```bash
# Add API serving capabilities
/agent-manager search "fastapi serving" --domain backend

# Include monitoring for ML models
/agent-manager search "monitoring metrics" --capability monitoring

# Save MLOps configuration
/agent-manager profile save mlops-production
```

## Advanced Usage Patterns

### Multi-Project Workspace

```bash
# Different profiles for different microservices
cd ~/workspace/auth-service
/agent-manager profile load secure-api

cd ~/workspace/data-service  
/agent-manager profile load data-processing

cd ~/workspace/frontend
/agent-manager profile load react-frontend
```

### Dynamic Agent Loading

```bash
# Start with minimal setup
/agent-manager setup minimal

# Add agents as needed during development
/agent-manager search "specific requirement" --limit 3

# Temporarily load additional capability
/agent-manager search --capability debugging --limit 1
```

### Performance Optimization Workflow

```bash
# Load performance-focused agents
/agent-manager search --capability optimization

# Add profiling and monitoring
/agent-manager search "profiling performance monitoring"

# Include database optimization
/agent-manager search --domain database --capability optimization

# Save performance optimization profile
/agent-manager profile save performance-focused
```

### Troubleshooting & Debugging

```bash
# Load debugging specialists
/agent-manager search --capability debugging --limit 5

# Add error handling experts
/agent-manager search "error handling logging" --capability debugging

# Include monitoring for issue detection
/agent-manager search --capability monitoring

# Save debugging toolkit profile
/agent-manager profile save debug-toolkit
```

## Best Practices

### Profile Naming Conventions

```bash
# Use descriptive names
/agent-manager profile save web-react-2024
/agent-manager profile save api-python-fastapi  
/agent-manager profile save ml-pytorch-production

# Include team or project context
/agent-manager profile save team-frontend-stack
/agent-manager profile save project-analytics-v2
```

### Agent Selection Strategy

```bash
# Start broad, then narrow
/agent-manager search --domain web                    # Broad search
/agent-manager search "react testing" --domain web    # More specific
/agent-manager search "react unit jest" --limit 2     # Very specific
```

### Manifest Validation

```bash
# Always validate after changes
/agent-manager manifest validate

# Check for missing agents
/agent-manager manifest show | grep "not found"

# Refresh if agents updated
/agent-manager index
```

### Registry Maintenance

```bash
# Regular statistics review
/agent-manager stats

# Explore available domains and capabilities
/agent-manager domains
/agent-manager capabilities

# Re-index when adding new agents
/agent-manager index
```

## Tips for Teams

1. **Standardize Profiles**: Create team-specific profiles for consistent development environments
2. **Document Custom Setups**: Include agent manager commands in project README files  
3. **Version Control**: Commit `.claude-agents` files to ensure consistent team setups
4. **Regular Updates**: Periodically review and update agent profiles as needs evolve
5. **Knowledge Sharing**: Share effective agent combinations across team members

## Common Workflows

### New Project Setup
```bash
./scripts/new-project.sh
# 1. Create project directory
# 2. Initialize git repository  
# 3. Run /agent-manager setup <type>
# 4. Customize agent selection
# 5. Save as project-specific profile
```

### Code Review Preparation
```bash
/agent-manager search --capability analysis --limit 3
/agent-manager search "code review quality" --capability analysis
# Load agents focused on code quality and analysis
```

### Production Deployment
```bash
/agent-manager profile load production-ready
# Includes: security-auditor, performance-optimizer, monitoring-specialist
```

These examples demonstrate the flexibility and power of the Claude Agent Manager across different development scenarios and team workflows.