"""Legacy helpers for running old trading scripts from the repo root."""

from pathlib import Path
import sys


def add_repo_root_to_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root
