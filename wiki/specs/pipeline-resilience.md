# Pipeline resilience

## Goal

Provider, network, or plugin failures must produce a diagnosable failed `ProjectState` instead of terminating the CLI with an uncaught exception.

## Requirements

- Apply one exception boundary consistently in Sequential and LangGraph runners.
- Reject steps that return anything other than `ProjectState`.
- Treat Gate 2 rejection as terminal in both runners.
- Configure finite LLM SDK retries and request timeout through environment variables.
- Reuse a compiled LangGraph across repeated invocations.

## Acceptance

- Tests cover provider exceptions, invalid step output, terminal routing, client configuration, and graph reuse.
- Existing offline pipeline behavior remains unchanged for successful steps.
