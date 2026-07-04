# ecc-init repository instructions

<!-- ecc-init-development:start -->
## Source of truth
- Read `DEVELOPMENT_PLAN_CODEX.md` before planning or changing architecture.
- This repository evolves the existing `ecc-init`; do not create a replacement repository.
- GSD Core is an external workflow dependency. Do not fork, vendor, or directly modify GSD.

## First implementation boundary
- Follow the current phase and task boundary in the development plan.
- Do not implement later phases early.
- Inspect current code and tests before treating the plan as fact.

## Verification
- Run targeted tests after each logical change.
- Before finishing a batch, run `python -m pytest`.
- Also run `python -m compileall src`.
- Review `git diff --check` and `git diff`.

## Safety
- Do not overwrite user-authored files.
- Do not delete user-modified legacy skills.
- Do not add a production dependency without documenting the need.
- Do not execute unpinned external installers in tests.

## Subagents
- Default to the main agent for small or tightly coupled work.
- Use at most two delegated workers concurrently.
- Delegated workers must not recursively spawn agents.
- Parallel write work requires disjoint file ownership and worktrees.
- A subagent must return evidence, tests, changed files, and unresolved risks.
<!-- ecc-init-development:end -->
