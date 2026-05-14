#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with Claude.
This script implements the two-agent pattern (initializer + coding agent) and
incorporates the strategies from the long-running agents guide:

    https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

Reference implementation:
    https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding

Example Usage:
    python autonomous_agent_demo.py --project-dir ./my_project
    python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 5
"""

import argparse
import asyncio
import os
from pathlib import Path

from agent import run_autonomous_agent


DEFAULT_MODEL = "ppio/pa/claude-opus-4-7"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Long-running agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh project
  python autonomous_agent_demo.py --project-dir ./my_project

  # Use a specific model
  python autonomous_agent_demo.py --project-dir ./my_project --model claude-sonnet-4-5-20250929

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 5

  # Continue existing project (same command resumes)
  python autonomous_agent_demo.py --project-dir ./my_project

Environment Variables:
  ANTHROPIC_API_KEY    Your Anthropic API key (required)
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./autonomous_demo_project"),
        help="Directory for the project. Relative paths are placed under generations/.",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--follow-up-prompt",
        type=str,
        default=None,
        help="Follow-up change request. If set, skips the initializer and applies an incremental change to the existing project.",
    )

    parser.add_argument(
        "--follow-up-prompt-file",
        type=Path,
        default=None,
        help="Path to a file containing the follow-up change request (alternative to --follow-up-prompt; avoids shell-quoting long text).",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("\nGet your API key from: https://console.anthropic.com/")
        print("\nThen set it:")
        print("  export ANTHROPIC_API_KEY='your-api-key-here'")
        return

    project_dir = args.project_dir
    if not str(project_dir).startswith("generations/") and not project_dir.is_absolute():
        project_dir = Path("generations") / project_dir

    follow_up = args.follow_up_prompt
    if args.follow_up_prompt_file:
        follow_up = args.follow_up_prompt_file.read_text()

    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=args.model,
                max_iterations=args.max_iterations,
                follow_up_prompt=follow_up,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
