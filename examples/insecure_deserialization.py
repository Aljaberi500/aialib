"""Vulnerable example: insecure YAML deserialization.

Expected annotation:
- CWE-502 (Deserialization of Untrusted Data)
- ai_cause: ["unsafe_default"]
- propagation_vector: ["deserialization"]
"""

import yaml


def load_settings(blob: bytes):
    # Vulnerable: yaml.load without SafeLoader executes arbitrary tags.
    return yaml.load(blob)
