# Contributing to Claude App Forge

Thank you for your interest in contributing to Claude App Forge!

## Ways to Contribute

### 1. Curriculum Content

- Add exercises to existing nodes
- Improve explanations
- Fix errors in examples
- Add new examples

### 2. Blueprints

- Create new blueprints
- Improve existing blueprints
- Add implementation examples
- Enhance decision points

### 3. Validation

- Improve test coverage
- Add new validation rules
- Fix validation issues
- Expand SDK version matrix

### 4. Documentation

- Fix typos and errors
- Improve clarity
- Add tutorials
- Translate content

## Contribution Process

### For Small Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run validation: `python .forge/validation/validate.py`
5. Submit a pull request

### For New Content

1. Open an issue to discuss your proposal
2. Get feedback from maintainers
3. Follow the process above

### For Blueprints

New blueprints must include:
- `README.md` - Overview and intent
- `specification.yaml` - Formal specification
- `decisions.yaml` - Decision points
- `examples/` - At least one example

## Code Standards

### Python
- Format with `black`
- Lint with `ruff`
- Type hints required
- Docstrings for public functions

### TypeScript
- Format with `prettier`
- Lint with `eslint`
- Types required
- JSDoc for exports

### Documentation
- Clear, concise language
- Code examples where helpful
- Cross-references to related content

## Validation Requirements

All contributions must:
- Pass syntax validation
- Include working examples
- Be compatible with current SDK version
- Include appropriate tests

## Review Process

1. Automated checks run on PR
2. Maintainer review
3. Community feedback period (for significant changes)
4. Merge when approved

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on the content, not the person
- Assume good intent

## Questions?

- Open an issue for questions
- Check existing issues first
- Use clear, descriptive titles

Thank you for helping make Claude App Forge better!
