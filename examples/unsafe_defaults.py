"""Vulnerable example: unsafe defaults left enabled in production code.

LLMs often emit "demo-ready" defaults — debug flags on, TLS verification off,
permissive CORS — when prompted to assemble small services quickly.

Expected annotation:
- CWE-489 (Active Debug Code)
- ai_cause: ["unsafe_default"]
- human_ai_factor: ["inattentive_copy_paste", "blind_trust"]
"""

import requests
from flask import Flask

app = Flask(__name__)


@app.route("/healthz")
def healthz():
    # Vulnerable: TLS verification disabled.
    r = requests.get("https://internal.example/status", verify=False, timeout=5)
    return r.text


if __name__ == "__main__":
    # Vulnerable: debug=True ships an interactive console.
    app.run(host="0.0.0.0", debug=True)
