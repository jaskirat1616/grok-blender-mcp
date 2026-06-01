# Safety Guide

This tool gives an LLM significant control over Blender. Treat it seriously.

## Protections Built In
- Safe Mode (default ON) — raw code execution restricted
- Every mutation pushes an undo step
- Big red "EMERGENCY UNDO" button in the Blender UI
- High-level tools are the recommended path
- Dry-run mode for code execution

## Recommendations
- Save your .blend frequently (use version numbers or git-lfs)
- Start complex sessions from a clean file
- Use the undo tool the moment something looks wrong
- Keep Safe Mode on unless you have a recent backup

The combination of vision feedback + high-level tools + undo makes this dramatically safer than raw code execution approaches.
