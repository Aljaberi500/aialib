CWE → MITRE ATLAS Crosswalk Rationale
=====================================

Notes by CWE family describing mapping justifications:

- CWE-78 (OS Command Injection) → ATLAS:Prompt Injection
  - Rationale: LLM outputs inject untrusted shell commands, aligning with model misuse enabling command execution.
- CWE-89 (SQL Injection) → ATLAS:Prompt Injection
  - Rationale: Model-generated string concatenation creates injection vectors analogous to prompt-driven code gen failures.
- CWE-502 (Unsafe Deserialization) → ATLAS:Data Poisoning
  - Rationale: Untrusted blob parsing surfaces model/data supply issues; matches data poisoning and integrity abuse.
- CWE-377 (Insecure Temp File) → ATLAS:Operational Oversight
  - Rationale: Unsafe defaults and shortcuts in generated code map to operational misconfiguration categories.
- CWE-829 (Untrusted Dependencies) → ATLAS:Supply Chain Manipulation
  - Rationale: Hallucinated/typosquatted imports risk supply-chain compromise.
- CWE-295 (TLS Verification) → ATLAS:Operational Oversight
  - Rationale: Insecure defaults like verify=False are operational misuses.
- CWE-116 (Improper Encoding/Sanitization) → ATLAS:Defense Evasion
  - Rationale: Sanitizer bypass across files resembles evasion patterns.
- CWE-611 (XXE) → ATLAS:Supply Chain Manipulation
  - Rationale: Parser defaults expose external entities akin to upstream manipulation.
- CWE-276 (Public S3 ACL) → ATLAS:Model Operational Misuse
  - Rationale: Generated infra code sets permissive ACLs; operational misuse.
- CWE-798 (Hardcoded Secrets) → ATLAS:Sensitive Data Exposure
  - Rationale: Model emits embedded creds exposing data.
- CWE-400 (Resource Exhaustion) → ATLAS:Operational Oversight
  - Rationale: Timeouts missing lead to DoS-like exposure.

This mapping is validated against configs/atlas_catalog.yaml in the validator.
