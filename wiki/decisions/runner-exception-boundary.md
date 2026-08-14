# ADR: Put the provider exception boundary in the runner

## Decision

Both orchestration engines invoke steps through the same `run_step_safely` boundary. It converts ordinary exceptions and invalid return values into a failed `ProjectState`; process-level interrupts continue to propagate.

## Rationale

Every Agent depends on external or extensible components. Duplicating try/catch blocks in each Agent is inconsistent and easy to forget. A runner-level boundary covers current agents and future plugins while preserving the existing `Step` contract.

## Consequences

- CLI callers always receive structured errors for step failures.
- LangGraph and SequentialRunner now share terminal-state semantics.
- The root exception type and message are retained in `state.errors` without a full traceback.
