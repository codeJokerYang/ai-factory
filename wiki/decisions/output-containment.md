# ADR: Contain generated output at the filesystem boundary

## Decision

All Builder paths are validated when parsed and resolved again immediately before writing. Project display names are never used directly as filesystem or npm identifiers.

## Rationale

Builder responses are model output and can be malformed or adversarial. Prompt instructions alone cannot provide a filesystem security boundary. Central validation keeps every current and future runner on the same deterministic policy without spending model tokens.

## Consequences

- Invalid Builder paths fail fast with a validation error.
- Portable output names may differ from the human-facing project title.
- Existing valid relative paths remain unchanged.
