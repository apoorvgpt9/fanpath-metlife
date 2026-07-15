# Contributing

This repo is a submission for **PromptWars Challenge 4** (see
[PROGRESS.md](PROGRESS.md)), not an actively-maintained open source project.
Scope is fixed to what's needed for the challenge and the deadline in
[CLAUDE.md](CLAUDE.md) — there's no ongoing roadmap or issue triage process
beyond that. That said, if you're reading the code, forking it, or opening a
PR, here's what you need to know.

## Dev environment

See the [README's "Running locally" section](README.md#running-locally) for
the full setup (venv, `pip install -e ".[dev]"`, required env vars, `make
run`). This file doesn't duplicate those steps.

## Before submitting any change

This project enforces six machine gates, and CI/`make verify-docs` treat a
red gate as a blocker, not a suggestion. Run all of them locally before
proposing a change:

```bash
make lint            # ruff + function-length check
make test             # pytest, 100% coverage floor
make verify-graph     # graph data integrity
make verify-docs      # DECISIONS.md claim table vs. code
make docstrings       # interrogate, 100% docstring coverage
make typecheck        # mypy --strict
```

If a change touches an architectural decision locked in
[DECISIONS.md](DECISIONS.md) or a frontend rule in [DESIGN.md](DESIGN.md),
follow those files' supersession pattern (new numbered entry, don't edit in
place) rather than quietly diverging.

## Scope note

This is a competition submission with a fixed scope and deadline — expect
minimal ongoing maintenance beyond that window.
