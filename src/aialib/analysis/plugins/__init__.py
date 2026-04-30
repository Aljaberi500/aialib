"""Plugin interface placeholder for multi-language analyzers.

Current implementation targets Python. New languages can register tool runners
and normalization adapters here without changing the schema or pipeline.
"""

__all__ = ["LANGUAGES"]

LANGUAGES = {
    "python": {
        "analyzers": ["bandit", "semgrep", "ai-risk-detector", "depcheck"],
        "file_suffix": ".py",
    }
}

