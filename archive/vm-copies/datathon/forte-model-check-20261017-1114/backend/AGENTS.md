
# Python Backend Guidelines

- Follow PEP 8, use type hints, and prefer clear domain names.
- Use Ruff for linting and formatting.
- Organize FastAPI routes with APIRouter.
- Keep route handlers thin; put domain logic in services or pure functions.
- Use Pydantic models for request and response validation.
- Define explicit errors and meaningful HTTP status codes.
- Keep database and network access separate from domain calculations.
- Do not use async functions for purely synchronous operations.
- Use dependency injection for shared resources when useful.
- Never let an LLM be the source of authoritative calculations.
- Test pure domain logic with pytest and endpoints with TestClient.
- Avoid broad exception handlers that hide programming errors.
- Prefer deterministic, independently testable behavior.
