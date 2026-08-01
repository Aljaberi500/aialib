# Template Design: Origin and Rationale of the 16 Prompt Families

**Provenance statement.** All sixteen prompt template families were
**manually authored** for this project; none are copied from an existing
prompt suite. Their *selection* was influenced by identifiable sources, and
we say so per family below: the weakness classes covered by prior
generated-code security studies (Pearce et al.'s Copilot study, which built
its scenarios from the CWE Top 25, and SecurityEval), OWASP Top 10 (2021)
categories, the MITRE CWE catalog, and — for the choice of *sink APIs* — the
rule coverage of Bandit and Semgrep, since a template whose expected sink no
detector can flag would produce unmeasurable results. The four AI-specific
families were derived from failure modes observed while prototyping the
pipeline, not from prior benchmarks.

Templates create the *opportunity* for a weakness; they do not instruct the
model to produce one. Target CWEs are therefore hypotheses that the detector
ensemble confirms or refutes at scan time.

## Family catalogue

*Samples = stratified base prompts per family (134 total); each expands into
4 propagation variants (base / reuse / refactor / secure_refactor). Full
template text, difficulty tiers, and variable pools: `data/prompts_v2.yaml`
(reproduced as Table A1 in the thesis).*

| Family | Target CWE(s) | Expected sink | Why included | Inspired by / reference | Mutators | Samples |
|---|---|---|---|---|---|---|
| `auth_sql` | [CWE-89](https://cwe.mitre.org/data/definitions/89.html) | `cursor.execute` via `sqlite3` / `mysql.connector` | Canonical injection risk in login-style DB code; tests whether models default to string concatenation | CWE Top 25; Pearce et al. scenario style; SecurityEval; OWASP A03:2021; Bandit B608 | `add_comment_hints`, `remove_quotes_escape`, `add_ambiguous_requirement` | 12 |
| `cmd_injection` | [CWE-78](https://cwe.mitre.org/data/definitions/78.html) | `subprocess` with `shell=True` | Shell-out helpers are a frequent LLM suggestion; tests `shell=True` habits | CWE Top 25; Pearce et al.; OWASP A03:2021; Bandit B602/B404 | `imply_safe_input`, `add_comment_hints` | 10 |
| `path_traversal` | [CWE-22](https://cwe.mitre.org/data/definitions/22.html) | Flask `download()` endpoint reading query-string filename | File-serving endpoints without path sanitization | CWE Top 25; SecurityEval; OWASP A01:2021 | `add_ambiguous_requirement`, `inject_context_noise` | 10 |
| `yaml_deser` | [CWE-502](https://cwe.mitre.org/data/definitions/502.html) | `yaml.load` | Config-loading is a classic unsafe-deserialization trap | CWE Top 25; OWASP A08:2021; Bandit B506 | `add_user_supplied_note`, `imply_safe_input` | 10 |
| `pickle_deser` | [CWE-502](https://cwe.mitre.org/data/definitions/502.html) | `pickle.loads` / `dill` | Session-blob deserialization of user bytes | CWE Top 25; OWASP A08:2021; Bandit B301 | `add_user_supplied_note`, `imply_safe_input` | 2 |
| `insecure_upload` | [CWE-434](https://cwe.mitre.org/data/definitions/434.html) | FastAPI upload saved under original filename | Upload handlers with no content-type or name validation | CWE catalog; OWASP file-upload guidance | `add_comment_hints`, `inject_context_noise` | 8 |
| `crypto_secrets` | [CWE-798](https://cwe.mitre.org/data/definitions/798.html) | hard-coded password in DB connect (e.g., `psycopg2.connect`) | Hard-coded credentials remain a top generated-code finding | CWE Top 25; Pearce et al.; OWASP A02:2021 (as tagged by the rulebook); Bandit B105–B107 | `imply_safe_input`, `add_comment_hints` | 12 |
| `ssrf_proxy` | [CWE-918](https://cwe.mitre.org/data/definitions/918.html) | `requests.get` on client-supplied URL | Proxy/fetcher helpers without egress controls | OWASP A10:2021 (SSRF); CWE catalog | `add_ambiguous_requirement`, `add_comment_hints` | 10 |
| `tempfiles` | [CWE-377](https://cwe.mitre.org/data/definitions/377.html) | `tempfile.mktemp` | Predictable temp paths; tests reuse of deprecated API | CWE catalog; Bandit B306 | `add_comment_hints`, `imply_safe_input` | 8 |
| `concurrency` | [CWE-362](https://cwe.mitre.org/data/definitions/362.html) | unlocked shared counter across threads | Non-injection weakness class; tests "speed over correctness" nudges | CWE catalog (race conditions) | `add_comment_hints`, `inject_context_noise` | 8 |
| `cloud_s3` | [CWE-306](https://cwe.mitre.org/data/definitions/306.html) | `boto3` public-read bucket ACL | Cloud misconfiguration; access control left open "for the demo" | OWASP A01/A05:2021; CWE catalog | `add_comment_hints`, `add_ambiguous_requirement` | 12 |
| `xml_parser` | [CWE-611](https://cwe.mitre.org/data/definitions/611.html) | `xml.etree.ElementTree.parse` | XXE-prone config parsing | OWASP (XXE, folded into A05:2021); Bandit XML rules (B31x) | `add_comment_hints`, `add_ambiguous_requirement` | 8 |
| `dep_hallucination` **(AI-specific)** | [CWE-829](https://cwe.mitre.org/data/definitions/829.html) | `import` of plausible-but-fake packages (`secureai_helper`, `llmshield`, `trustpilotai`, `hypersafe`) | Models invent dependencies; supply-chain risk unique to generated code | Observed during pipeline prototyping; validated against a versioned PyPI index snapshot | `inject_context_noise`, `add_comment_hints` | 6 |
| `unsafe_defaults` **(AI-specific)** | [CWE-295](https://cwe.mitre.org/data/definitions/295.html) | `verify=False`, `debug=True`, permissive CORS | Models silently enable insecure defaults when asked for "quick" config | Observed during pipeline prototyping; detected by the custom AI-risk rules (`ai.unsafe.*`) | `add_comment_hints`, `imply_safe_input` | 8 |
| `context_misalignment` **(AI-specific)** | [CWE-20](https://cwe.mitre.org/data/definitions/20.html) | "secure" helper that still shells out (`sh -c` / `bash -c`) | Prompt claims security requirements; output ignores them — a generation-specific gap | Observed during pipeline prototyping; detected by `ai.context.misalignment` | `add_ambiguous_requirement`, `add_comment_hints` | 6 |
| `multi_file` **(AI-specific)** | [CWE-116](https://cwe.mitre.org/data/definitions/116.html) | second file bypassing `sanitize_input` defined in the first | Sanitization split across files breaks silently; multi-file output is LLM-characteristic | Observed during pipeline prototyping; detected by `ai.multifile.bypass` | `inject_context_noise`, `add_comment_hints` | 4 |

## How the mutators work

Mutators append controlled wording shifts without changing the core task —
they model realistic developer pressure, not requests for insecure code:

| Mutator | Effect |
|---|---|
| `add_comment_hints` | Appends speed/prototype hints ("# quick and dirty") that de-emphasize hardening |
| `imply_safe_input` | Claims inputs are trusted/sanitized upstream, weakening trust-boundary emphasis |
| `remove_quotes_escape` | Discourages parameterization/escaping in favor of concatenation |
| `add_ambiguous_requirement` | Nudges toward minimal dependencies and no defensive code |
| `inject_context_noise` | Adds distracting side-requirements (logging, CLI wrapper) |
| `add_user_supplied_note` | Marks data as user-supplied/unvetted (raises deserialization stakes) |

Both mutators and template variables are applied deterministically under
seed 1337, so the full 536-instance prompt set per provider is byte-for-byte
reproducible.

## Stratification

Families expand by difficulty tier and variable substitution to ~137
prompts; family-level caps then stratify the selection to **134 base
prompts** so template-rich families cannot dominate (e.g., `pickle_deser`
contributes 2, `auth_sql` 12). Counts per family and per CWE are recorded in
`data/run_manifest.json`.

## References

- H. Pearce et al., "Asleep at the Keyboard? Assessing the Security of
  GitHub Copilot's Code Contributions," IEEE S&P 2022.
  <https://doi.org/10.1109/SP46214.2022.9833571>
- M. L. Siddiq and J. C. S. Santos, "SecurityEval Dataset," MSR4P&S 2022.
  <https://doi.org/10.1145/3549035.3561184>
- OWASP Top 10 (2021). <https://owasp.org/Top10/>
- MITRE CWE and CWE Top 25. <https://cwe.mitre.org/>
- Bandit. <https://github.com/PyCQA/bandit>
- Semgrep. <https://semgrep.dev/>
