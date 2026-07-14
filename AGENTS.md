# Agent Instructions

This repository follows the Tutti OS organization contribution guide:

https://github.com/tutti-os/.github/blob/main/CONTRIBUTING.md

- Keep changes focused and avoid unrelated refactors.
- Use Conventional Commits and DCO sign-off.
- Keep the Skill provider-agnostic. Examples may use Gemini, but runtime logic
  and troubleshooting guidance must not require Gemini-specific Tutti code.
- Keep executable logic in `scripts/`; keep `SKILL.md` focused on routing and
  workflow.
- Never commit signing private keys, AWS credentials, access tokens, or local
  machine paths.
- Before finishing, run `python3 scripts/validate_repository.py`, inspect
  `git diff`, and report test evidence and documentation impact.
