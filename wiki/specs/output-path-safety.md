# Generated output path safety

## Goal

Treat project names and Builder file paths as untrusted LLM output. Generated files must stay below the selected app root on Windows, macOS, and Linux.

## Requirements

- Reject absolute, drive-qualified, blank, NUL-containing, and parent-traversal file paths before any write.
- Resolve paths and verify containment to prevent escape through an existing symlink.
- Convert display names into portable directory names and npm-compatible package names.
- Return structured build-gate failures when npm is missing or exceeds the configured timeout.

## Acceptance

- Unit tests cover POSIX traversal, Windows paths, package naming, timeout, and missing executable cases.
- The full offline test suite remains green.
