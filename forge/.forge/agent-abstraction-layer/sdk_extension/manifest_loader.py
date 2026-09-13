"""
Manifest Loader for AAL.

Loads and validates agent manifests, preparing them for the SDK.
"""

from pathlib import Path
from typing import Union
import yaml

from ..core.manifest import AgentManifest


def load_manifest(path: Union[str, Path]) -> AgentManifest:
    """
    Load an agent manifest from a file.

    Args:
        path: Path to the manifest file (YAML or JSON)

    Returns:
        Parsed and validated AgentManifest

    Raises:
        FileNotFoundError: If manifest file doesn't exist
        ValueError: If manifest is invalid
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    return AgentManifest.from_file(path)


class ManifestLoader:
    """
    Loader with caching and validation.
    """

    def __init__(self, search_paths: list = None):
        self.search_paths = search_paths or [Path.cwd()]
        self.cache: dict = {}

    def load(self, name: str) -> AgentManifest:
        """
        Load a manifest by name.

        Searches in configured paths for:
        - {name}.manifest.yaml
        - {name}/agent.manifest.yaml
        - agent.manifest.yaml (in {name} directory)
        """
        if name in self.cache:
            return self.cache[name]

        # Search for manifest
        candidates = [
            f"{name}.manifest.yaml",
            f"{name}/agent.manifest.yaml",
            f"agents/{name}.manifest.yaml",
        ]

        for search_path in self.search_paths:
            for candidate in candidates:
                path = Path(search_path) / candidate
                if path.exists():
                    manifest = load_manifest(path)
                    self.cache[name] = manifest
                    return manifest

        raise FileNotFoundError(
            f"Could not find manifest for '{name}' in {self.search_paths}"
        )

    def validate(self, manifest: AgentManifest) -> list:
        """Validate a manifest and return list of errors."""
        return manifest.validate()

    def clear_cache(self) -> None:
        """Clear the manifest cache."""
        self.cache = {}
