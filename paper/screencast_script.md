# Screencast script — `aialib`

**Target length:** 4 minutes 30 seconds (CFP cap is 5 minutes; leave headroom).
**Tone:** matter-of-fact, brisk, technical. No music. Clean voice-over only.
**Resolution:** record at 1920×1080, terminal font ≥ 16 pt, browser zoom 110 %.

## What viewers should remember after 4:30

1. The pipeline turns one YAML prompt spec into a CSV/SQLite/SARIF threat
   library — *one command*, *fully offline*, *reproducible from a seed*.
2. Every finding carries an **AI-cause** label, a **propagation vector**, and
   a **MITRE ATLAS** technique — not just a CWE.
3. There is a one-off snippet mode for IDE-style use, *and* a multi-provider
   batch mode that produced the shipped 729-row dataset.

---

## Pre-recording setup (do this once)

| | Action |
|--|--------|
| Repo | Clone `aialib` into `~/demo/aialib`; `make setup` succeeded; `out/` empty. |
| Terminal | `tmux` session, two panes, `cd ~/demo/aialib`. Clear scrollback. |
| Browser | Three tabs preloaded: GitHub repo, Zenodo DOI page, the rendered `sample_outputs/threat_library.csv` on GitHub. |
| Editor | VS Code with `examples/sql_injection.py` already open. |
| Recorder | OBS or Loom, microphone test recorded ≥ 5 s of room tone, push-to-talk off. |
| Subtitles | Plan to upload the script as a `.srt` afterwards — cleaner than YouTube auto-captions. |

---

## Shot list

Each row is one continuous take. If you flub a line, restart that row only.

### 00:00 – 00:20 · Cold open and motivation (20 s)

- **Visual:** Title card *"aialib: An AI-Aware Threat Library for
  LLM-Generated Code"* with the author name and the ASE 2026 Tools &
  Datasets logo in the corner. 3 s, fade to a terminal.
- **Voice-over:**
  > LLMs are writing more of our production code every week. The literature
  > already shows that what they ship is frequently insecure — but
  > frequency isn't enough. As reviewers and engineers we need to know
  > **why** a flaw was emitted, **how** it propagates across refactors,
  > and **where** it sits in an AI-aware threat model. *aialib* is
  > the artifact that makes those questions answerable on a pull
  > request.

### 00:20 – 00:55 · Architecture in one breath (35 s)

- **Visual:** Cut to a single still — the architecture diagram from
  Figure 1 of the paper (export as PNG and screen-share full-bleed).
  Highlight each box with a red rectangle as it's mentioned (use OBS
  zoom-and-follow or a slide overlay).
- **Voice-over:**
  > Seven stages, each one a `python -m aialib.<stage>`. We start from
  > a single YAML prompt specification — seventeen security families,
  > four propagation variants, deterministic mutators — expand it into
  > 536 prompt instances, generate code from one or more LLM providers,
  > scan every completion with Bandit, Semgrep, and an AI-aware
  > heuristic detector, annotate findings with CWE, OWASP, an AI-cause
  > label, and a MITRE ATLAS technique, validate against a JSON
  > schema, and export to CSV, SQLite, and SARIF. Everything is keyed
  > by a fixed seed so the run is reproducible by anyone.

### 00:55 – 01:35 · *Try it in 60 seconds* (40 s)

- **Visual:** Switch to terminal pane. Type — don't paste:

  ```bash
  docker run --rm -v "$PWD/out:/app/out" aialib
  ```

  Show the build cache hit and the pipeline streaming. Speed up the boring
  middle 4× in post.
- **When it finishes**, run:

  ```bash
  ls -lh out/
  head -2 out/threat_library.csv
  ```

- **Voice-over:**
  > One Docker command, no API keys, no network. The image bundles a
  > local generator and the analyzer rule packs. Forty seconds later
  > you have three files: a CSV, a SQLite database, and a SARIF report.
  > The CSV is committed to the repo as `sample_outputs/threat_library.csv`
  > so you can inspect the schema before running anything yourself.

### 01:35 – 02:25 · Inside a record (50 s)

- **Visual:** Open `sample_outputs/threat_library.csv` in VS Code (or
  GitHub's CSV viewer). Highlight one row — pick the
  `tempfile.mktemp` example used in the paper. Use VS Code's column
  highlighting or a callout overlay.
- **Voice-over:**
  > Look at one record. CWE-377 — insecure temp file. OWASP
  > A05 Security Misconfiguration. Sink API
  > `tempfile.mktemp`. So far, this is what any rule-based scanner gives
  > you. Now look at the AI-specific columns: `ai_cause` is
  > `template_reuse` — the model lifted a stale snippet pattern.
  > `propagation_vector` is `filesystem`.
  > `human_ai_factor` is `knowledge_gap`.
  > `atlas_techniques` is `ATLAS:Operational Oversight`. Plus a
  > normalized token hash and an AST hash that let us de-duplicate
  > and cluster by code shape across runs. Twenty-one fields. Every
  > one of them validated by a JSON schema.

### 02:25 – 03:05 · One-off snippet mode (40 s)

- **Visual:** Switch to the editor with `examples/sql_injection.py` open.
  Read the body in 3 seconds. Switch to terminal, run:

  ```bash
  python -m aialib.pipeline.process_snippet \
      --code examples/sql_injection.py \
      --prompt-text "Look up a user by username"
  ```

  Then:

  ```bash
  cat out/manual_run/threat_library.csv | column -ts,
  ```

- **Voice-over:**
  > IDE-style flow. The developer pastes a snippet, runs one command,
  > gets the same schema back: CWE-89 SQL injection, AI-cause
  > `template_reuse`, propagation `database_query`. No corpus,
  > no Docker. This is the integration point we'd hook into a Git
  > pre-commit or a code-review bot.

### 03:05 – 03:55 · Multi-provider comparison (50 s)

- **Visual:** Show `sample_outputs/reports/master_summary.md` rendered
  on GitHub. Highlight the *Yield* and *HIGH* columns.
- **Voice-over:**
  > The pipeline drove four production LLMs through the same
  > 536-prompt corpus: OpenAI gpt-4o-mini and gpt-4.1, Anthropic
  > Claude Sonnet 4, and MBZUAI's K2-Think v2. Yields range from
  > 19.4 % to 26.7 %. OpenAI is the highest-volume; Claude
  > surfaces the most HIGH-severity findings — fifty-six of one
  > hundred fifteen — and uniquely triggers Data-Poisoning and
  > Prompt-Injection ATLAS techniques in our annotator. K2Think
  > generates the most repetitive output: only twenty-one unique
  > finding patterns on a hundred and four rows. Differences
  > reproduce across the seed, and the comparison report ships
  > alongside the dataset.

### 03:55 – 04:25 · CI/CD integration (30 s)

- **Visual:** Quick split-screen: terminal running

  ```bash
  sqlite3 out/threat_library.sqlite \
    "SELECT cwe_id, COUNT(*) FROM findings
     WHERE ai_cause LIKE '%unsafe_default%'
       AND severity IN ('HIGH','MEDIUM')
     GROUP BY cwe_id;"
  ```

  and a still of GitHub Code Scanning rendering the SARIF file.
- **Voice-over:**
  > Two integration points. SQL queries against the SQLite library let
  > you fail a build that introduces an unsafe-default regression.
  > And the SARIF export goes straight into GitHub Code Scanning,
  > GitLab SAST, or your IDE — no glue code.

### 04:25 – 04:30 · Outro (5 s)

- **Visual:** End card: repo URL, Zenodo DOI, license badge.
- **Voice-over:**
  > Apache 2.0 code, CC BY 4.0 dataset, link in the description.
  > Thanks for watching.

---

## Editing notes

- **Cuts:** allowable between rows of the shot list, never inside one.
- **Speed-ups:** any wall-clock wait > 3 s gets a 4× boost with a corner
  badge "× 4" so the audience knows.
- **Captions:** burn in the on-screen commands as inline text — terminal
  fonts compress badly on YouTube's 480p stream.
- **Length sanity check:** total wall-clock ≈ 4:30 with the cuts above;
  if you overshoot, the easiest cut is shrinking the architecture
  segment (00:20–00:55) by 10 s and the multi-provider segment
  (03:05–03:55) by 10 s.
- **Audio:** record voice-over after the visuals are timed; don't try to
  do both live. Three takes per row is normal.

## Required end-card text (for closed-captions block in YouTube)

```
aialib — An AI-Aware Threat Library for LLM-Generated Code
Code (Apache 2.0): https://github.com/aljaberi500/aialib
Dataset (CC BY 4.0): same repo, sample_outputs/
Zenodo: https://doi.org/10.5281/zenodo.XXXXXXX
Paper (ASE '26 Tools & Datasets Track): see paper/paper.pdf
```
