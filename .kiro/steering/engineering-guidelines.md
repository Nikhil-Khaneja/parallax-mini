---
inclusion: always
---

# Engineering Guidelines (Karpathy-style)

Principles for all code written in this repository. They favor small, understandable,
correct code over cleverness or premature generality.

## Core philosophy
- Write the smallest solution that fully solves the problem. No speculative features.
- Prefer clarity over cleverness. If a junior can't read it, rewrite it.
- Understand every line you write. No copy-paste you can't explain.
- Delete aggressively. Less code is less to maintain and less to break.
- Build incrementally: make it work, make it right, then (only if needed) make it fast.

## Simplicity
- No abstraction until there are at least two concrete uses. Avoid frameworks-of-one.
- Avoid deep inheritance and indirection. Prefer flat, direct functions.
- One module, one responsibility. Keep functions short and single-purpose.
- Don't add config, flags, or "just in case" parameters that nothing uses yet.

## Correctness
- Every new feature or bug fix ships with a test that would fail without it.
- Test the behavior that matters (e.g., OTA rollback fires on checksum mismatch),
  not implementation trivia.
- Run the build/tests before claiming something works. Cite the result.

## Readability
- Names say what things are/do. Comments explain *why*, not *what*.
- Keep the happy path obvious; handle errors explicitly, don't swallow them.
- Match the existing style, libraries, and conventions of the file you're editing.

## Data & performance
- Get the data model right first; most complexity comes from bad data shapes.
- Don't optimize before measuring. Profile, then fix the actual hotspot.

## Scope discipline for this project
- Follow PLAN.md phases in order. Do the differentiators (OTA, anomaly gate)
  rigorously with tests before polishing UI.
- Keep claims honest: only assert capabilities the code and tests actually demonstrate.
