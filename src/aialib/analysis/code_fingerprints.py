"""Helpers for computing normalized code fingerprints."""

from __future__ import annotations

import ast
import io
import tokenize
from typing import Tuple

from ..utils.io import hash_text

IGNORED_TOKENS = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}


def normalized_token_hash(code: str) -> str:
    """Hash tokens after stripping whitespace and comments."""
    if not code:
        return hash_text("")
    try:
        stream = io.StringIO(code).readline
        tokens = []
        for tok in tokenize.generate_tokens(stream):
            if tok.type in IGNORED_TOKENS:
                continue
            tokens.append(tok.string.strip())
        normalized = "".join(part for part in tokens if part)
    except tokenize.TokenError:
        normalized = "".join(code.split())
    if not normalized:
        normalized = "".join(code.split())
    return hash_text(normalized)


def ast_hash(code: str) -> str:
    """Hash a normalized AST dump."""
    if not code:
        return hash_text("")
    try:
        tree = ast.parse(code)
        normalized = ast.dump(tree, include_attributes=False)
    except SyntaxError:
        normalized = f"syntax_error:{hash_text(code)}"
    return hash_text(normalized)


def compute_fingerprints(code: str) -> Tuple[str, str]:
    """Return (normalized_token_hash, ast_hash) for the given code."""
    return normalized_token_hash(code), ast_hash(code)
