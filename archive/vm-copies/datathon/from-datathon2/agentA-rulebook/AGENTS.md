
# Engineering Guidelines

## Stack
- Backend: Python 3.12+, FastAPI, Pydantic.
- Frontend: React, TypeScript (strict mode).
- Follow existing project conventions before introducing new ones.

## Engineering Principles
- Prefer simple, maintainable solutions over unnecessary abstractions.
- Implement complete vertical slices, not disconnected modules.
- Keep business logic separate from HTTP handlers and UI components.
- Use one authoritative implementation for every business rule.
- Avoid duplicated logic, hidden fallbacks, and invented mock results.
- Keep dependencies minimal and justified.

## Multi-Agent Collaboration
- Respect assigned file ownership and task boundaries.
- Do not overwrite another agent's work.
- Agree on shared contracts before parallel implementation.
- Communicate changes to shared interfaces before modifying them.
- Integrate and test across boundaries early.
- Do not create competing implementations of the same functionality.

## Quality
- Test business-critical logic and important failure paths.
- Validate all external inputs.
- Report errors explicitly; do not silently swallow exceptions.
- Never hardcode credentials or expose secrets to the frontend.
- Run relevant tests, linting, and type checks after changes.
- Never claim a test passed unless it actually ran.

## Delivery
- Keep the main user flow runnable throughout development.
- Prioritize mandatory functionality before optional enhancements.
- Update documentation when interfaces or setup steps change.
- At completion, report changes, tests, and remaining limitations.
