"""
Security Hooks for Autonomous Coding Agent
==========================================

PreToolUse hook that validates bash commands using an allowlist.
Only commands in ALLOWED_COMMANDS are permitted.
"""

import os
import re
import shlex


ALLOWED_COMMANDS = {
    # File inspection
    "ls", "cat", "head", "tail", "wc", "grep", "find", "stat", "file", "readlink", "diff",
    # Text processing
    "tr", "sed", "awk", "cut", "sort", "uniq", "tee", "xargs", "tac", "jq", "yq",
    # File operations
    "cp", "mv", "rm", "mkdir", "rmdir", "chmod", "touch", "ln",
    # Archive
    "tar", "gzip", "gunzip", "zip", "unzip",
    # Directory / env / misc
    "pwd", "cd", "echo", "printf", "date", "which", "whoami", "hostname", "uname",
    "env", "printenv", "export", "source", ".", "basename", "dirname", "true", "false", "test", "[",
    # Shell
    "bash", "sh",
    # Python
    "python", "python3", "pip", "pip3",
    # Node.js ecosystem
    "npm", "node", "npx", "pnpm", "yarn", "bun", "deno", "tsx", "ts-node",
    # Version control
    "git",
    # Process management
    "ps", "lsof", "sleep", "pkill", "kill", "nohup", "disown", "timeout",
    # Network (sandbox + filesystem scope still contain blast radius)
    "curl", "wget", "nc",
    # Script execution
    "init.sh",
}

COMMANDS_NEEDING_EXTRA_VALIDATION = {"pkill", "chmod", "init.sh"}


def split_command_segments(command_string: str) -> list[str]:
    """Split compound commands on && || ; preserving pipes as single segments."""
    segments = re.split(r"\s*(?:&&|\|\|)\s*", command_string)
    result = []
    for segment in segments:
        sub_segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', segment)
        for sub in sub_segments:
            sub = sub.strip()
            if sub:
                result.append(sub)
    return result


def _tokenize(segment: str) -> list[str]:
    """Tokenize a single segment, tolerant of unbalanced/multi-line quotes."""
    try:
        return shlex.split(segment)
    except ValueError:
        try:
            return shlex.split(segment, posix=False)
        except ValueError:
            return re.findall(r'''(?:"[^"]*"|'[^']*'|\S)+''', segment)


def extract_commands(command_string: str) -> list[str]:
    """Extract base command names from a shell command string."""
    commands = []
    segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', command_string)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        tokens = _tokenize(segment)
        if not tokens:
            continue

        expect_command = True
        for token in tokens:
            if token in ("|", "||", "&&", "&"):
                expect_command = True
                continue
            if token in (
                "if", "then", "else", "elif", "fi",
                "for", "while", "until", "do", "done",
                "case", "esac", "in", "!", "{", "}",
            ):
                continue
            if token.startswith("-"):
                continue
            if "=" in token and not token.startswith("="):
                continue
            if expect_command:
                cmd = os.path.basename(token)
                commands.append(cmd)
                expect_command = False

    return commands


def validate_pkill_command(command_string: str) -> tuple[bool, str]:
    """pkill only for dev-related processes."""
    allowed = {
        "node", "npm", "npx", "pnpm", "yarn", "bun", "deno",
        "vite", "next", "nuxt", "esbuild", "webpack", "turbo", "rollup", "parcel",
        "tsc", "ts-node", "tsx", "vitest", "jest", "playwright",
        "python", "python3", "uvicorn", "gunicorn", "flask", "fastapi",
        "watchman", "nodemon",
    }
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse pkill command"
    if not tokens:
        return False, "Empty pkill command"

    args = [t for t in tokens[1:] if not t.startswith("-")]
    if not args:
        return False, "pkill requires a process name"

    target = args[-1]
    if " " in target:
        target = target.split()[0]

    if target in allowed:
        return True, ""
    return False, f"pkill only allowed for dev processes: {allowed}"


def validate_chmod_command(command_string: str) -> tuple[bool, str]:
    """chmod only allowed with +x variants, no flags, no recursion."""
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse chmod command"
    if not tokens or tokens[0] != "chmod":
        return False, "Not a chmod command"

    mode = None
    files = []
    for token in tokens[1:]:
        if token.startswith("-"):
            return False, "chmod flags are not allowed"
        elif mode is None:
            mode = token
        else:
            files.append(token)

    if mode is None:
        return False, "chmod requires a mode"
    if not files:
        return False, "chmod requires at least one file"
    if not re.match(r"^[ugoa]*\+x$", mode):
        return False, f"chmod only allowed with +x mode, got: {mode}"

    return True, ""


def validate_init_script(command_string: str) -> tuple[bool, str]:
    """init.sh must be invoked as ./init.sh or a path ending in /init.sh."""
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse init script command"
    if not tokens:
        return False, "Empty command"

    script = tokens[0]
    if script == "./init.sh" or script.endswith("/init.sh"):
        return True, ""
    return False, f"Only ./init.sh is allowed, got: {script}"


def get_command_for_validation(cmd: str, segments: list[str]) -> str:
    """Find the segment containing a given command."""
    for segment in segments:
        if cmd in extract_commands(segment):
            return segment
    return ""


async def bash_security_hook(input_data, tool_use_id=None, context=None):
    """PreToolUse hook: allowlist + per-command validators. Fail-safe (block on parse error)."""
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    commands = extract_commands(command)
    if not commands:
        return {
            "decision": "block",
            "reason": f"Could not parse command for security validation: {command}",
        }

    segments = split_command_segments(command)

    for cmd in commands:
        if cmd not in ALLOWED_COMMANDS:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' is not in the allowed commands list",
            }

        if cmd in COMMANDS_NEEDING_EXTRA_VALIDATION:
            cmd_segment = get_command_for_validation(cmd, segments) or command

            if cmd == "pkill":
                ok, reason = validate_pkill_command(cmd_segment)
            elif cmd == "chmod":
                ok, reason = validate_chmod_command(cmd_segment)
            elif cmd == "init.sh":
                ok, reason = validate_init_script(cmd_segment)
            else:
                ok, reason = True, ""

            if not ok:
                return {"decision": "block", "reason": reason}

    return {}
