"""
Prompt Loading Utilities
========================

Loads prompt templates from the prompts/ directory and copies the app spec
into each new project directory.
"""

import os
import shutil
from pathlib import Path


PROMPTS_DIR = Path(os.environ.get("AGENT_PROMPTS_DIR") or (Path(__file__).parent / "prompts"))


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def get_initializer_prompt() -> str:
    return load_prompt("initializer_prompt")


def get_coding_prompt() -> str:
    return load_prompt("coding_prompt")


def get_follow_up_prompt(user_request: str) -> str:
    """Return the follow-up coding prompt with the user's request spliced in."""
    template = load_prompt("follow_up_prompt")
    return template.replace("{follow_up_prompt}", user_request.strip())


def copy_spec_to_project(project_dir: Path) -> None:
    """Copy the app spec into the project directory for the agent to read."""
    spec_source = PROMPTS_DIR / "app_spec.txt"
    spec_dest = project_dir / "app_spec.txt"
    if not spec_dest.exists():
        shutil.copy(spec_source, spec_dest)
        print("Copied app_spec.txt to project directory")
