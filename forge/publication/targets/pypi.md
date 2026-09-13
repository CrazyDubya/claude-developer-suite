# Publishing to PyPI

Guide for publishing Python packages to the Python Package Index.

## Prerequisites

- PyPI account (https://pypi.org/account/register/)
- `twine` installed (`pip install twine`)
- `build` installed (`pip install build`)

## Package Structure

```
my-package/
├── src/
│   └── my_package/
│       ├── __init__.py
│       └── ...
├── tests/
├── pyproject.toml    # Modern packaging config
├── README.md
├── LICENSE
└── CHANGELOG.md
```

## pyproject.toml Template

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-claude-app"
version = "0.1.0"
description = "A Claude-powered application"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["claude", "ai", "anthropic"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "anthropic>=0.34.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
    "black",
    "ruff",
]

[project.urls]
Homepage = "https://github.com/you/my-claude-app"
Documentation = "https://github.com/you/my-claude-app#readme"
Repository = "https://github.com/you/my-claude-app"

[project.scripts]
my-claude-app = "my_package.cli:main"
```

## Publication Steps

### 1. Prepare

```bash
# Clean old builds
rm -rf dist/ build/ *.egg-info/

# Run tests
pytest

# Check version
grep version pyproject.toml
```

### 2. Build

```bash
# Build distribution packages
python -m build

# This creates:
# dist/my_package-0.1.0.tar.gz
# dist/my_package-0.1.0-py3-none-any.whl
```

### 3. Test Upload (TestPyPI)

```bash
# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Test install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ my-package
```

### 4. Publish to PyPI

```bash
# Upload to production PyPI
twine upload dist/*
```

### 5. Verify

```bash
# Install from PyPI
pip install my-package

# Test it works
python -c "import my_package; print(my_package.__version__)"
```

## Authentication

### Using API Tokens (Recommended)

1. Generate token at https://pypi.org/manage/account/token/
2. Create `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-<your-token>

[testpypi]
username = __token__
password = pypi-<your-test-token>
```

### Using Trusted Publishing (Best)

For GitHub Actions, use trusted publishing:

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

## Common Issues

### Package name taken
- Check https://pypi.org/project/your-name/
- Consider prefixes like `claude-` or `anthropic-`

### Version already exists
- PyPI doesn't allow re-uploading the same version
- Bump version number and rebuild

### README not rendering
- Ensure README.md is valid markdown
- Check with `twine check dist/*`

## Post-Publication

1. Tag the release in git
2. Update documentation
3. Announce on relevant channels
4. Monitor for issues
