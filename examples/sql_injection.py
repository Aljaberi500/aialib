"""Vulnerable example: classic SQL injection via string concatenation.

Run through the one-off snippet pipeline:

    python -m aialib.pipeline.process_snippet \
        --code examples/sql_injection.py \
        --prompt-text "Look up a user by username"

Expected output (under out/manual_run/):
- CWE-89, OWASP A03:2021-Injection, severity MEDIUM
- ai_cause: ["template_reuse"]
- propagation_vector: ["database_query"]
- detection_tools: ["bandit", "semgrep"]
"""

import sqlite3


def find_user(conn: sqlite3.Connection, username: str):
    cur = conn.cursor()
    # Vulnerable: user-controlled string interpolated into SQL.
    query = "SELECT id, email FROM users WHERE name = '" + username + "'"
    cur.execute(query)
    return cur.fetchone()
