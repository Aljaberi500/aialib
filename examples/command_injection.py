"""Vulnerable example: command injection via shell=True.

Expected annotation:
- CWE-78, OWASP A03:2021-Injection, severity HIGH
- ai_cause: ["unsafe_default"]
- propagation_vector: ["shell_command"]
"""

import subprocess


def ping(host: str) -> str:
    # Vulnerable: shell=True with unsanitized user input.
    return subprocess.check_output(f"ping -c 1 {host}", shell=True).decode()
