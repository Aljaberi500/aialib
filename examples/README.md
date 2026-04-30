# Example vulnerable snippets

Five hand-picked snippets that exercise the dominant CWE/AI-cause categories
in the corpus. Each one is single-file and runs end-to-end through the
pipeline in seconds:

```bash
python -m aialib.pipeline.process_snippet \
    --code examples/sql_injection.py \
    --prompt-text "Look up a user by username"
```

Output lands under `out/manual_run/`:

- `out/manual_run/threat_library.csv`
- `out/manual_run/findings.jsonl`
- `out/manual_run/annotations.jsonl`

| File | CWE | AI cause |
| ---- | --- | -------- |
| `sql_injection.py` | CWE-89 | template_reuse |
| `command_injection.py` | CWE-78 | unsafe_default |
| `hallucinated_dependency.py` | CWE-829 | hallucinated_dependency |
| `unsafe_defaults.py` | CWE-489 | unsafe_default |
| `insecure_deserialization.py` | CWE-502 | unsafe_default |

These files are intentionally insecure. **Do not import them into running
services.** They exist to demonstrate detector behavior and threat-library
schema fields.
