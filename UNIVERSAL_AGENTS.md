# UNIVERSAL_AGENTS.md

## 🧠 Baseline Guidelines for New Projects (2025‑06)

This document provides a starting point for repositories that want a concise, opinionated agent policy. Copy it into new projects and adapt as needed.

### 1  Core Principles

1. **Clarity first** – favour readable, self-documenting code.
2. **Small PRs** – keep changes under ~400 LOC.
3. **Revertibility** – every change should be revertible via `git revert`.
4. **Security over convenience** – never expose secrets or weaken auth.
5. **Follow language standards** – see §2.
6. **Prompt awareness** – obey in‑code comment directives.
7. **Idempotent diffs** – the same instruction should yield identical patches.

### 2  Language Defaults

| Language  | Formatter/Linter | Test Framework |
|-----------|-----------------|----------------|
| Python    | `ruff`           | `pytest`       |
| TypeScript| `biome`          | `vitest`       |
| Go        | `go vet`        | `go test`      |
| Rust      | `clippy`        | `cargo test`   |
| Java      | `spotless`      | `JUnit`        |
| Shell     | `shfmt`         | `bats-core`    |

Adapt these as necessary for your stack.

### 3  Prohibited Actions

* No commits to protected branches without an approved PR.
* No force pushes unless coordinated via `--force-with-lease`.
* No non‑OSS licensed dependencies without maintainer approval.

### 4  Continuous Improvement

Projects may refine this guide when adopting new tools or rules. Keep updates brief and retain existing constraints unless explicitly removed.

© 2025 Vsevolod Dobrovolskyi • Licensed under the repository’s primary `LICENSE`.

### Version History

* **1.0 – 2025‑06** – Initial template.
* **1.1 – 2025‑06‑07** – Added version history section.
* **1.2 – 2025‑06‑07** – Documented combined keyword search rule and Gemini integration note.
