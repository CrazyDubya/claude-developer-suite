#!/usr/bin/env python3
"""
Claude App Forge Validation Engine

Validates curriculum examples, blueprints, and reference implementations
against the Claude SDK version matrix.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ValidationResult:
    """Result of validating a single file."""
    path: str
    success: bool
    sdk_version: str
    duration_ms: int
    error: str | None = None
    output: str | None = None


@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str
    sdk_version: str
    total_files: int
    passed: int
    failed: int
    skipped: int
    results: list[ValidationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "sdk_version": self.sdk_version,
            "summary": {
                "total": self.total_files,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
            },
            "results": [
                {
                    "path": r.path,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def load_config() -> dict[str, Any]:
    """Load validation configuration."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def find_files(patterns: list[str], root: Path) -> list[Path]:
    """Find files matching glob patterns."""
    files = []
    for pattern in patterns:
        files.extend(root.glob(pattern))
    return sorted(set(files))


def validate_python_file(path: Path, timeout: int = 30) -> ValidationResult:
    """Validate a Python example file."""
    import time
    start = time.time()

    try:
        # First check syntax
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            return ValidationResult(
                path=str(path),
                success=False,
                sdk_version=get_sdk_version(),
                duration_ms=int((time.time() - start) * 1000),
                error=f"Syntax error: {result.stderr}",
            )

        # Then try to execute (with mocked API if configured)
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                **dict(subprocess.os.environ),
                "FORGE_VALIDATION_MODE": "true",
            },
        )

        duration_ms = int((time.time() - start) * 1000)

        if result.returncode == 0:
            return ValidationResult(
                path=str(path),
                success=True,
                sdk_version=get_sdk_version(),
                duration_ms=duration_ms,
                output=result.stdout[:1000] if result.stdout else None,
            )
        else:
            return ValidationResult(
                path=str(path),
                success=False,
                sdk_version=get_sdk_version(),
                duration_ms=duration_ms,
                error=result.stderr[:1000] if result.stderr else "Unknown error",
            )

    except subprocess.TimeoutExpired:
        return ValidationResult(
            path=str(path),
            success=False,
            sdk_version=get_sdk_version(),
            duration_ms=timeout * 1000,
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return ValidationResult(
            path=str(path),
            success=False,
            sdk_version=get_sdk_version(),
            duration_ms=int((time.time() - start) * 1000),
            error=str(e),
        )


def get_sdk_version() -> str:
    """Get installed Claude SDK version."""
    try:
        import anthropic
        return anthropic.__version__
    except ImportError:
        return "not-installed"


def validate_category(
    category: str,
    config: dict[str, Any],
    root: Path,
) -> list[ValidationResult]:
    """Validate all files in a category."""
    cat_config = config["categories"].get(category)
    if not cat_config:
        print(f"Unknown category: {category}")
        return []

    files = find_files(cat_config["paths"], root)
    results = []

    for path in files:
        if path.suffix == ".py":
            result = validate_python_file(path, config["runner"]["timeout"])
            results.append(result)

            status = "✓" if result.success else "✗"
            print(f"  {status} {path.relative_to(root)}")

    return results


def generate_report(results: list[ValidationResult]) -> ValidationReport:
    """Generate validation report from results."""
    return ValidationReport(
        timestamp=datetime.now().isoformat(),
        sdk_version=get_sdk_version(),
        total_files=len(results),
        passed=sum(1 for r in results if r.success),
        failed=sum(1 for r in results if not r.success),
        skipped=0,
        results=results,
    )


def save_report(report: ValidationReport, output_dir: Path) -> None:
    """Save validation report to files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    json_path = output_dir / "latest.json"
    with open(json_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)

    # Markdown report
    md_path = output_dir / "latest.md"
    with open(md_path, "w") as f:
        f.write(f"# Validation Report\n\n")
        f.write(f"**Timestamp:** {report.timestamp}\n\n")
        f.write(f"**SDK Version:** {report.sdk_version}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total: {report.total_files}\n")
        f.write(f"- Passed: {report.passed} ✓\n")
        f.write(f"- Failed: {report.failed} ✗\n")
        f.write(f"\n## Results\n\n")

        for result in report.results:
            status = "✓" if result.success else "✗"
            f.write(f"### {status} `{result.path}`\n\n")
            if result.error:
                f.write(f"**Error:** {result.error}\n\n")


def main():
    parser = argparse.ArgumentParser(description="Validate Claude App Forge content")
    parser.add_argument(
        "--category",
        choices=["curriculum", "blueprints", "reference", "challenges", "all"],
        default="all",
        help="Category to validate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".forge/validation/reports"),
        help="Output directory for reports",
    )
    args = parser.parse_args()

    root = Path(__file__).parent.parent.parent
    config = load_config()

    print(f"Claude App Forge Validation Engine")
    print(f"SDK Version: {get_sdk_version()}")
    print(f"=" * 50)

    all_results = []

    categories = (
        list(config["categories"].keys())
        if args.category == "all"
        else [args.category]
    )

    for category in categories:
        print(f"\nValidating {category}...")
        results = validate_category(category, config, root)
        all_results.extend(results)

    report = generate_report(all_results)
    save_report(report, args.output)

    print(f"\n{'=' * 50}")
    print(f"Total: {report.total_files} | Passed: {report.passed} | Failed: {report.failed}")

    # Exit with error if any failures
    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
