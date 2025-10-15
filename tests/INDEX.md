# Test Suite Index and Evolution Plan

## Overview

This document serves as the central index for the MLServer test suite. It tracks test coverage, organization, and evolution plans. **Always update this document when modifying functionality or adding tests.**

## Current Test Coverage Status (as of 2025-01-16)

- **Total Coverage**: 32% (Target: 80%)
- **Test Results**: 223 passing, 31 failing, 5 errors
- **Critical Files Coverage**:
  - `server.py`: 72% coverage
  - `adapters.py`: 93% coverage
  - `config.py`: 94% coverage
  - `predictor_loader.py`: 9% coverage
  - `metrics.py`: 45% coverage
  - `concurrency_limiter.py`: 63% coverage

## Test Organization

### Unit Tests (`tests/unit/`)

| File | Purpose | Coverage | Status |
|------|---------|----------|--------|
| `test_adapters.py` | Input/output adapters | 93% | ✅ Good |
| `test_config.py` | Configuration validation | 94% | ✅ Good |
| `test_config_extended.py` | Extended config features | Partial | ⚠️ Needs work |
| `test_cli_basic.py` | CLI functionality | Partial | ⚠️ Needs work |
| `test_container.py` | Docker container building | Low | ❌ Many failures |
| `test_server_unit.py` | Server components | 72% | ✅ Improved |
| `test_version_control.py` | Git versioning & safe push | New | ✅ Complete |

### Integration Tests (`tests/integration/`)

| File | Purpose | Coverage | Status |
|------|---------|----------|--------|
| `test_server_endpoints.py` | API endpoint testing | Good | ✅ Working |
| `test_concurrency_simplified.py` | Concurrency control | Partial | ⚠️ Some failures |
| `test_observability.py` | Metrics & logging | Good | ✅ Working |

### Load Tests (`tests/load/`)

| File | Purpose | Status |
|------|---------|--------|
| `locustfile.py` | Load testing with Locust | ✅ Ready |

### Test Fixtures (`tests/fixtures/`)

| File | Purpose | Status |
|------|---------|--------|
| `mock_predictor.py` | Mock ML predictor with delay | ✅ Working |

## Recent Fixes Applied

### Configuration Fixes
- ✅ Added required `classifier` and `api` fields to test configs
- ✅ Changed adapter from "records" to "auto" for broader format support
- ✅ Fixed feature ordering in test configurations

### Endpoint Fixes
- ✅ Updated URLs from `/v1/{classifier}/predict` to `/predict`
- ✅ Fixed payload format to use `{"payload": {"records": [...]}}` wrapper
- ✅ Fixed health endpoint assertions (returns "ok" not "healthy")

### Test Infrastructure
- ✅ Renamed TestPredictor to MockPredictor to avoid pytest collection issues
- ✅ Fixed test fixtures to properly initialize predictor state
- ✅ Added proper lifespan handling in test apps

### Version Control Features (NEW)
- ✅ Added `ml_server tag <major|minor|patch>` command for semantic versioning
- ✅ Implemented safe_push_container with registry tag validation
- ✅ Enhanced /info endpoint to show git-based version information
- ✅ Added comprehensive tests for version control functionality

## Test Evolution Plan

### Phase 1: Core Server Tests ✅ COMPLETED
**File**: `mlserver/server.py` (Current: 72% coverage)
- [x] Fix endpoint tests for unified URLs
- [x] Fix payload format issues
- [ ] Test new /info endpoint with full metadata
- [ ] Test predictor loading with module resolution
- [ ] Test lifespan events (startup/shutdown)
- [ ] Test error handling and fallbacks
- [ ] Test CORS configuration
- [ ] Test concurrency limiter integration

### Phase 2: Adapters Tests ✅ MOSTLY COMPLETE
**File**: `mlserver/adapters.py` (Current: 93% coverage)
- [x] Test RecordsAdapter with various input formats
- [x] Test NdarrayAdapter with nested arrays
- [x] Test AutoAdapter detection logic
- [x] Test error cases (malformed input)
- [x] Test feature ordering cache

### Phase 3: Configuration Tests ✅ GOOD
**File**: `mlserver/config.py` (Current: 94% coverage)
- [x] Test configuration validation
- [ ] Test multi-classifier config loading
- [ ] Test global config inheritance
- [ ] Test environment variable overrides

### Phase 4: CLI Tests (Priority: HIGH)
**Files**: `mlserver/cli.py`, `mlserver/cli_v2.py`
- [ ] Test classic CLI commands
- [ ] Add tests for new Typer CLI (cli_v2.py)
- [ ] Test config file auto-detection
- [ ] Test multi-classifier selection
- [ ] Test build/push/clean commands

### Phase 5: Multi-Classifier Tests (Priority: HIGH)
**File**: `mlserver/multi_classifier.py`
- [ ] Test loading multi-classifier configs
- [ ] Test classifier extraction
- [ ] Test default classifier selection
- [ ] Test config merging

### Phase 6: Integration Tests (Priority: MEDIUM)
**Files**: `tests/integration/`
- [x] Fix MockPredictor references
- [x] Update endpoint URLs in all tests
- [ ] Add tests for /info and /status endpoints
- [ ] Test complete multi-classifier flow
- [ ] Test concurrent predictions with limiter
- [ ] Test metrics collection accuracy

### Phase 7: AI Init Tests (Priority: LOW)
**Files**: `mlserver/ainit/`
- [ ] Test notebook analysis
- [ ] Test code generation
- [ ] Test template rendering
- [ ] Mock LLM responses for testing

### Phase 8: Container Tests (Priority: MEDIUM)
**File**: `mlserver/container.py`
- [ ] Fix Docker detection tests
- [ ] Test wheel building
- [ ] Test Dockerfile generation
- [ ] Test image building/pushing

## Test Commands

### Run All Tests
```bash
pytest tests/
```

### Run with Coverage
```bash
pytest tests/ --cov=mlserver --cov-report=term-missing
```

### Run Specific Test File
```bash
pytest tests/unit/test_server_unit.py -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/ -v
```

### Run Load Tests
```bash
cd tests/load && locust -f locustfile.py --host http://localhost:8000
```

## Testing Guidelines

### When Adding New Functionality

1. **Before Implementation**:
   - Check this INDEX.md for existing test patterns
   - Plan test cases for the new feature

2. **During Implementation**:
   - Write tests alongside the code
   - Ensure tests cover both success and error cases

3. **After Implementation**:
   - Update this INDEX.md with new test information
   - Run full test suite to ensure no regressions
   - Update coverage metrics in this document

### Test Naming Conventions

- Unit tests: `test_<component>_<functionality>`
- Integration tests: `test_<workflow>_<scenario>`
- Fixtures: `<type>_<purpose>` (e.g., `mock_predictor`, `sample_config`)

### Common Test Patterns

#### Testing API Endpoints
```python
async def test_predict_endpoint(async_client):
    payload = {"payload": {"records": [{"f1": 1.0}]}}
    response = await async_client.post("/predict", json=payload)
    assert response.status_code == 200
    assert "predictions" in response.json()
```

#### Testing with Mock Predictor
```python
@pytest.fixture
def mock_config():
    return AppConfig(
        predictor=PredictorConfig(
            module="tests.fixtures.mock_predictor",
            class_name="MockPredictor"
        ),
        # ... other config
    )
```

#### Testing Configuration
```python
def test_config_validation():
    with pytest.raises(ValidationError):
        AppConfig(server={"port": -1})  # Invalid port
```

## Known Issues and TODOs

### High Priority
- [ ] Fix remaining container.py test failures
- [ ] Add comprehensive CLI v2 tests
- [ ] Test multi-classifier functionality end-to-end

### Medium Priority
- [ ] Improve concurrency control test coverage
- [ ] Add performance regression tests
- [ ] Test model hot-reloading scenarios

### Low Priority
- [ ] Mock AI init LLM calls for deterministic testing
- [ ] Add property-based tests for adapters
- [ ] Create test data generators

## Maintenance Notes

- **Test Data**: Keep test payloads small and focused
- **Mocking**: Use `MockPredictor` for predictable test behavior
- **Async Tests**: Use `pytest-asyncio` fixtures for async endpoints
- **Cleanup**: Ensure tests clean up resources (files, ports, etc.)

---

**Remember**: This document should be the first stop when working with tests. Keep it updated!