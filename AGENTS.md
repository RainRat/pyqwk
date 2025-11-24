# AGENTS

## Scope
This file applies to the entire repository.

## General guidelines
- Update or add unit tests alongside code changes when behaviour changes.
- You may do moderate refactoring if needed (ie. expose some code as a function in order to test it specifically)
- Since packets may have become corrupted over the years, and may be the last copy of their content, code should be written defensively, but still try to make a best effort to recover content.

## Testing
- Run `pytest` from the repository root before submitting changes.