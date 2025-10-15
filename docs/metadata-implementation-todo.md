# Metadata Streamlining Implementation TODO

## Phase 1: Schema Simplification

### 1. Update mlserver/version.py
- [ ] Remove `ClassifierVersion` class (lines 25-52)
- [ ] Remove `ModelVersion` class (lines 54-59)
- [ ] Remove `ApiVersion` class (lines 61-77)
- [ ] Simplify `ClassifierMetadata` to only essential fields
- [ ] Update `get_repository_name()` to get git project name
- [ ] Add `get_mlserver_version()` function to get package version
- [ ] Remove `effective_version` and `version_source` logic

### 2. Update mlserver/config.py
- [ ] Add `LoggerConfig` class with timestamp, structured, show_tasks options
- [ ] Add `logger` field to `ServerConfig`
- [ ] Remove `model` field from `AppConfig`
- [ ] Remove version fields from classifier config
- [ ] Simplify `ApiConfig` - remove version field

### 3. Update mlserver/schemas.py
- [ ] Rename `model` field to `predictor_class` in responses
- [ ] Remove `model_version`, `api_version` from `ClassifierMetadataResponse`
- [ ] Add `deployed_at` field (auto-generated)
- [ ] Add `mlserver` section with wrapper version info
- [ ] Remove `model_metrics` from responses

## Phase 2: Auto-Detection Implementation

### 4. Update mlserver/server.py
- [ ] Auto-detect git repository name at startup
- [ ] Generate `deployed_at` timestamp at server start
- [ ] Remove all `effective_version` logic (lines ~474-482)
- [ ] Simplify `/info` endpoint response structure
- [ ] Update metadata in prediction responses
- [ ] Rename `model_type` to `predictor_class`
- [ ] Add MLServer package version to responses

### 5. Add mlserver/auto_detect.py (new file)
```python
def get_git_project_name() -> str:
    """Auto-detect git repository name."""

def get_deployed_timestamp() -> str:
    """Generate ISO format deployment timestamp."""

def get_mlserver_package_version() -> str:
    """Get installed mlserver package version."""
```

### 6. Update mlserver/predictor_loader.py
- [ ] Improve logging with task context clarification
- [ ] Remove or clarify taskName in async context

## Phase 3: Logger Configuration

### 7. Update mlserver/logging_config.py
- [ ] Read logger settings from config
- [ ] Implement timestamp toggle
- [ ] Implement task name visibility toggle
- [ ] Configure structured logging based on settings

### 8. Update startup logging
- [ ] Apply logger configuration at startup
- [ ] Remove hardcoded timestamp format
- [ ] Make taskName optional in logs

## Phase 4: Configuration Migration

### 9. Create mlserver/migrate.py (new file)
- [ ] Add config migration tool
- [ ] Convert old format to new format
- [ ] Warn about deprecated fields
- [ ] Add CLI command `mlserver migrate-config`

### 10. Update mlserver/cli_v2.py
- [ ] Add `migrate-config` command
- [ ] Update `version` command to show new structure
- [ ] Remove version-related options from `tag` command

## Phase 5: Documentation Updates

### 11. Update docs/configuration.md
- [ ] Remove all version-related config options
- [ ] Add logger configuration section
- [ ] Update example configs to new format
- [ ] Add migration guide section

### 12. Update examples/
- [ ] Update all example mlserver.yaml files
- [ ] Remove version fields
- [ ] Add logger configuration examples

## Phase 6: Test Updates

### 13. Update tests/unit/test_version.py
- [ ] Remove tests for deleted classes
- [ ] Add tests for auto-detection functions
- [ ] Test git repository name detection

### 14. Update tests/integration/
- [ ] Update expected response structures
- [ ] Test new metadata format
- [ ] Test logger configuration

### 15. Update tests/fixtures/
- [ ] Update mock configs to new format
- [ ] Remove version-related fixtures

## Code Changes Summary

### Files to Modify
1. `mlserver/version.py` - Remove 150+ lines, simplify to ~50 lines
2. `mlserver/config.py` - Add LoggerConfig, remove model/version fields
3. `mlserver/schemas.py` - Rename fields, remove versions
4. `mlserver/server.py` - Auto-detection, simplified responses
5. `mlserver/logging_config.py` - Configurable logging
6. `mlserver/predictor_loader.py` - Clarify task context
7. `mlserver/cli_v2.py` - Add migration command

### Files to Create
1. `mlserver/auto_detect.py` - Auto-detection utilities
2. `mlserver/migrate.py` - Config migration tool

### Files to Update (Docs/Examples)
1. `docs/configuration.md`
2. `docs/metadata-streamlining-plan.md`
3. All example YAML files

### Files to Update (Tests)
1. `tests/unit/test_version.py`
2. `tests/unit/test_config.py`
3. `tests/integration/test_*`
4. Test fixtures

## Testing Checklist

- [ ] Auto-detection works without git repo
- [ ] Auto-detection works with git repo
- [ ] Logger configuration applies correctly
- [ ] Old configs show deprecation warnings
- [ ] Migration tool converts correctly
- [ ] All endpoints return new format
- [ ] Backwards compatibility maintained

## Rollout Plan

1. **Week 1**: Implement schema changes with backwards compatibility
2. **Week 2**: Add auto-detection and logger config
3. **Week 3**: Update tests and documentation
4. **Week 4**: Release with migration guide

## Breaking Change Notice

Users will need to:
1. Remove version fields from configs
2. Use git tags for versioning
3. Update any code parsing the /info response
4. Run migration tool on existing configs