import os
import re
import logging
from typing import Optional, Literal
import asyncio
from inspect_ai.util import sandbox
from inspect_ai.log import transcript

logger = logging.getLogger(__name__)

AideAgentType = Literal[
    "aide",
    "aide/dev",
    "aide/o1-preview",
    "aide/gpt-4-turbo",
    "aide/gpt-4-turbo-dev",
    "aide/gpt-3.5-turbo-0125",
    "aide/gpt-3.5-dev",
    "aide/claude-3-5-sonnet",
    "aide/claude-3-7-sonnet",
    "aide/llama-3.1-405b-instruct",
    "aide/gemini-1.5-pro",
    "aide/obfuscated"
]

def get_env_var(value: str) -> Optional[str]:
    """Returns the name of the environment variable in the format `${secrets.<name>}`."""

    if not isinstance(value, str):
        return None

    env_var_pattern = r"\$\{\{\s*secrets\.(\w+)\s*\}\}"
    match = re.match(env_var_pattern, value)

    if not match:
        return None

    return match.group(1)


def is_env_var(value: str) -> bool:
    """Checks if the value is an environment variable."""

    return get_env_var(value) is not None


def parse_env_var_values(dictionary: dict) -> dict:
    """
    Parses any values in the dictionary that match the ${{ secrets.ENV_VAR }} pattern and replaces
    them with the value of the ENV_VAR environment variable.
    """
    for key, value in dictionary.items():
        if not is_env_var(value):
            continue

        env_var = get_env_var(value)

        assert env_var is not None

        if os.getenv(env_var) is None:
            raise ValueError(f"Environment variable `{env_var}` is not set!")

        dictionary[key] = os.getenv(env_var)

    return dictionary


async def wait_for_log_file(log_path, timeout=15):
    """Wait until the log file exists, with a timeout."""
    elapsed = 0
    while elapsed < timeout:
        try:
            log_content = await sandbox().read_file(log_path)
            if log_content is not None:
                return True
        except Exception:
            pass  # Ignore errors and keep waiting
        
        await asyncio.sleep(0.5)
        elapsed += 0.5

    print(f"Warning: Log file {log_path} not found after {timeout} seconds.")
    return False

async def stream_logs(log_path):
    """Continuously fetch and print new logs from the container."""
    if not await wait_for_log_file(log_path):
        return  # Stop if the log file was never found

    last_position = 0

    while True:
        try:
            log_content = await sandbox().read_file(log_path)

            if not log_content or len(log_content) <= last_position:
                await asyncio.sleep(1)
                continue

            new_logs = log_content[last_position:]
            last_position = len(log_content)
            for line in new_logs.split("\n"):
                if line:
                    transcript().info(line)

        except Exception as e:
            print(f"Error reading logs: {e}")
            await asyncio.sleep(2)  # Backoff on errors
