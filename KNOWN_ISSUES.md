# Known Issues

This file tracks known issues and bugs that need to be addressed in future releases.

---

## Issue #1: `mlserver version` Command Requires Config File

**Severity**: Low
**Status**: Open
**Date Reported**: 2025-10-27
**Affects**: CLI v2 (`cli_v2.py`)

### Description
The `mlserver version` command incorrectly requires `mlserver.yaml` or `classifier.yaml` to be present in the current directory, even though it should only display the MLServer package version.

### Expected Behavior
```bash
python -m mlserver.cli version
# Should display MLServer version without needing config files
```

### Actual Behavior
```bash
python -m mlserver.cli version
# Error: Neither mlserver.yaml nor classifier.yaml found in .
```

### Impact
- Cannot verify MLServer installation in clean directories
- GitHub Actions workflows fail when trying to verify installation before building
- Confusing for users who just want to check installed version

### Workaround
Use `pip show` instead:
```bash
pip show mlserver-fastapi-wrapper
```

### Root Cause
The CLI framework is loading config files even for commands that don't need them. The `version` command should be exempt from config file requirements.

### Recommended Fix
1. Add a `requires_config` flag to command definitions
2. Mark `version` command with `requires_config=False`
3. Skip config loading for commands that don't require it

### Files Affected
- `mlserver/cli_v2.py` - CLI command implementation
- Potentially the command registration/dispatch logic

### References
- Discovered during GitHub Actions workflow development
- Issue found in `test-classifier/.github/workflows/build_and_push.yml`
- Workaround implemented in commit fixing the workflow

---

## Future Issues

Add new issues below...
