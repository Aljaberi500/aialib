"""Vulnerable example: dependency hallucination.

The package `secure-jsonloader` does not exist on PyPI. LLMs occasionally
fabricate plausible-sounding package names; an attacker can register the
fabricated name and ship malicious code.

Expected annotation:
- CWE-829 (Inclusion of Functionality from Untrusted Control Sphere)
- ai_cause: ["hallucinated_dependency"]
- atlas_techniques: ["ATLAS:Supply Chain Manipulation"]
"""

import secure_jsonloader  # noqa: F401  -- fabricated package


def load_config(path: str):
    return secure_jsonloader.safe_load(path)
