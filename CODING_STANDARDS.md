# Coding standards

The reviewer applies these. Formatting, imports and mechanical lint are checked by `ruff` and types by `mypy` in CI; this file holds the judgement calls those tools can't make.

## Domain language

- Names, comments and docs use the terms in `GLOSSARY.md` (Bridge, Controller, CFI, SHI, Calculations, Holdings, Command, …), capitalised as there, and none of its _Avoid_ synonyms.
- A decision that is hard to reverse gets an ADR in `docs/adr/`; code that follows one cites it (`(ADR 0001)`).

## Tests

- A test reads "given this ENV and Controller state, when this happens, these topics have these payloads". It asserts on what an outside subscriber sees on the broker: topics, payloads, retained flags, status topics.
- Tests reach the Bridge through `tests/harness.py` and the fake Controller. Helpers shared by more than one test file live in the harness, not copied into each file.
- `retained(port)` only for a Bridge the test steps or has stopped; `latest(port)` inside `wait_until` for anything publishing in real time (`docs/testing.md`).
- Time-dependent behaviour is driven with `FakeClock`; real-time waits are bounded by `TIMEOUT`.

## Configuration

- Every setting comes from a `LUX_*` variable and fails fast at startup with a message that names the variable.
- An empty variable counts as unset, the way Docker Compose passes a declared but unset variable.
- A default lives in one place, `config.py`, matching the spec's ENV table and the README.

## Comments

- Comments say why, in one or two short sentences, and point to the related file when behaviour spans two (`(release.yml)`, `(tests/harness.py)`).
- A value repeated across files (the Python version, the build inputs) has a comment naming the other places it appears.

## Tickets

- Decisions made while implementing, and agreed with the maintainer, go under the ticket's `## Comments` with a date, so the next session finds them without the chat.
