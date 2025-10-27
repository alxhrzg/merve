# Changelog

All notable changes to MLServer FastAPI Wrapper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2025-10-27 - Hierarchical Versioning Release

### Major Features

#### Hierarchical Git Tagging System
- **Complete reproducibility** with `<classifier>-v<X.X.X>-mlserver-<hash>` tag format
- Captures both classifier code commit AND MLServer tool commit
- Enables rebuilding identical containers months or years later
- Full traceability from production back to exact source code

#### Version Management CLI
- `mlserver tag` - Display version status for all classifiers
- `mlserver tag --classifier <name> <patch|minor|major>` - Create hierarchical tags with semantic versioning
- Beautiful rich table output showing version status, MLServer commits, and recommendations
- Automatic version bumping (patch: 1.0.0 → 1.0.1, minor: 1.0.0 → 1.1.0, major: 1.0.0 → 2.0.0)

#### Enhanced Container Labels
- 17 OCI-compliant container labels
- Hierarchical git tag embedded in every container
- Complete version metadata (classifier version, commits, MLServer version)
- Enables audit trails and compliance tracking

### 🔧 Enhancements

#### CLI Improvements
- Enhanced `mlserver build` with validation warnings when code doesn't match tag
- Enhanced `mlserver version --detailed` showing MLServer tool information
- Rich CLI output with colored status indicators and formatted tables
- Helpful next-step recommendations after operations

#### Multi-Classifier Support
- Independent version tracking per classifier in multi-classifier repositories
- Status table shows all classifiers with their versions and MLServer commits
- Each classifier can be tagged and versioned independently

#### Git Integration
- Automatic MLServer commit detection from installed package
- Support for git-based installations (editable mode)
- Intelligent repository detection and metadata extraction
- Clean git tag management with hierarchical format

### 📚 Documentation

#### Comprehensive Documentation Updates
- **CLI Reference**: Complete documentation of tag, build, and version commands
- **Deployment Guide**: GitHub Actions workflows for CI/CD integration (3 workflow options)
- **Development Guide**: Version management in development workflow with practical scenarios
- **Documentation Index**: Updated navigation with versioning tasks

#### New Documentation Sections
- Hierarchical tag format explanation and examples
- Migration path from simple tags to hierarchical format
- Reproducibility testing workflows
- Version bumping guidelines (when to use patch/minor/major)
- Common version management scenarios with solutions

#### Code Examples
- 47+ runnable code examples across documentation
- 3 production-ready GitHub Actions workflows
- 12+ visual CLI output examples
- 6+ scenario walkthroughs (hotfixes, migration, etc.)

### 🐛 Bug Fixes

#### Multi-Classifier Detection
- Fixed multi-classifier config detection to support both `dict` and `list` formats
- Enhanced `list_available_classifiers()` to parse both configuration styles

#### Test Improvements
- Fixed test assertions for `mlserver` command (was `ml_server`)
- Added 6 new tests for `validate_push_readiness()`
- Added container label validation tests

### 📦 New Files

#### Core Implementation
- `mlserver/version_control.py` - Complete version control and git integration (782 lines)
- `mlserver/_version_info.py` - Version information module
- `UPDATED_VERSIONING.md` - Version strategy documentation

#### Testing
- `tests/unit/test_version_control.py` - 21 unit tests for version control
- `tests/integration/test_hierarchical_versioning.py` - 20 integration tests
- `tests/integration/test_container_labels_versioning.py` - 5 container label tests
- `TEST_RESULTS_PHASE1_2.md` through `TEST_RESULTS_PHASE5.md` - Test reports
- `TEST_REVIEW_PHASE5.md` - Comprehensive test quality review
- `TEST_IMPROVEMENT_BACKLOG.md` - Prioritized test improvement roadmap

#### Documentation
- `DOCUMENTATION_UPDATES_PHASE6.md` - Phase 6 documentation summary
- `PHASE7_INTEGRATION_TEST_REPORT.md` - Integration testing report
- Updated `docs/cli-reference.md`, `docs/deployment.md`, `docs/development.md`, `docs/INDEX.md`

### ⚙️ Technical Details

#### Version Control System
- GitVersionManager class for all version control operations
- Hierarchical tag parsing with regex validation
- MLServer commit hash detection from package installation
- Tag status tracking with commit counting
- Push readiness validation (uncommitted changes detection)

#### Container Integration
- Enhanced `generate_container_labels()` with hierarchical tag support
- 17 labels including classifier, MLServer, and OCI standard labels
- Git information embedding (commit, branch, tag, URL)
- MLServer tool metadata (version, commit, installation source)

#### Git Operations
- `parse_hierarchical_tag()` - Extract components from hierarchical tags
- `get_mlserver_commit_hash()` - Detect MLServer installation commit
- `tag_version()` - Create hierarchical tags with validation
- `get_all_classifiers_tag_status()` - Status for all classifiers
- `validate_push_readiness()` - Pre-push validation

### 🧪 Testing

#### Test Coverage
- **Unit Tests**: 21 new tests for version control
- **Integration Tests**: 25 new tests for hierarchical versioning and container labels
- **Coverage**: version_control.py at 86%, container.py hierarchical features at 90%+
- **Total Tests**: 46 new tests (45 passing, 1 with known mock issue)

#### Test Categories
- Tag parsing and validation
- Version bumping (patch, minor, major)
- MLServer commit detection
- Multi-classifier scenarios
- Container label generation
- Git integration workflows

### 📊 Performance

- Tag creation: < 1 second
- Container builds: ~45 seconds (includes wheel build from source)
- CLI commands: < 0.5 second response time
- Status table generation: < 0.5 second for multi-classifier repos

### ⚠️ Known Issues

#### Issue #1: `mlserver version` Command in Multi-Classifier Repos
- **Severity**: High (blocks useful CLI command)
- **Description**: `mlserver version --detailed` fails in multi-classifier repositories
- **Root Cause**: `load_classifier_metadata()` looks for `'classifier'` key, not `'classifiers'`
- **Workaround**: Use `mlserver tag` to see MLServer commit information
- **Status**: Documented, workaround available

#### Issue #2: `mlserver images` Command in Multi-Classifier Repos
- **Severity**: Medium (informational command)
- **Description**: `mlserver images` fails in multi-classifier repositories
- **Root Cause**: Same as Issue #1
- **Workaround**: Use `docker images | grep <classifier-name>` directly
- **Status**: Documented, workaround available

### 🔄 Migration Guide

#### For New Projects
Start using hierarchical tags immediately:
```bash
# Create first tag
mlserver tag --classifier your-classifier-name patch

# Build with tag
mlserver build --classifier your-classifier-name

# Push tags to remote
git push --tags
```

#### For Existing Projects
Migrate gradually:
1. Continue using existing tags (fully backward compatible)
2. Start using `mlserver tag` for new versions
3. Update CI/CD to handle hierarchical tag format
4. Benefit from complete reproducibility going forward

No breaking changes - existing tags and containers continue to work.

### 📈 Statistics

- **Code Added**: ~1,600 lines of production code
- **Tests Added**: 46 new tests
- **Documentation Added**: ~816 lines across 4 files
- **Coverage Improvement**: version_control.py from 0% to 86%
- **Pass Rate**: 98% (45/46 tests)

### 🎯 Use Cases

#### Perfect For
- Production ML deployments requiring audit trails
- Teams needing to reproduce historical model versions
- Multi-classifier repositories with independent versioning
- CI/CD pipelines with automatic builds from tags
- Compliance and regulatory requirements for traceability

#### Benefits
- **Complete Reproducibility**: Rebuild exact container from any historical tag
- **Audit Trail**: Full traceability from production to source code
- **Multi-Classifier**: Independent version management per classifier
- **CI/CD Integration**: Automatic builds triggered by tags
- **Developer Experience**: Simple CLI commands, clear visual feedback
- **Container Metadata**: All version info embedded in container labels
- **Backward Compatible**: Existing projects work without changes

### 🙏 Credits

**Development**: 7 phases of implementation (October 2025)
**Testing**: 46 new tests, 3 test reports
**Documentation**: 4 major documentation files updated

---

## [0.2.0] - 2025-01-16 - Previous Features

*(Previous changelog entries preserved here)*

### Features
- AI-powered initialization with `mlserver ainit`
- Multi-classifier repository support
- Comprehensive observability with Prometheus and structured logging
- Flexible input adapters (records, ndarray, auto)
- Container build workflow
- Process-based scaling
- Load testing framework

### Documentation
- Complete API reference
- Configuration guide
- Architecture overview
- Examples and tutorials
- Development guide

---

## [0.1.0] - Initial Release

### Initial Features
- FastAPI-based ML server
- Dynamic predictor loading
- YAML configuration
- Basic metrics and logging
- Docker containerization
- CORS support
- Health check endpoints

---

## Upgrade Guide

### From 0.2.0 to 0.3.0

#### No Breaking Changes
All existing functionality continues to work. The hierarchical versioning system is additive.

#### Optional: Adopt Hierarchical Versioning

**Benefits**:
- Complete reproducibility
- Better version tracking
- Enhanced container labels
- CI/CD integration

**Steps**:
1. Update to 0.3.0: `pip install --upgrade mlserver-fastapi-wrapper`
2. Check current status: `mlserver tag`
3. Create first hierarchical tag: `mlserver tag --classifier <name> patch`
4. Update CI/CD (optional): Use new GitHub Actions workflows from docs
5. Continue normal workflow

**Timeline**: Migrate at your own pace - no urgency, fully backward compatible

---

## Future Roadmap

### Version 0.4.0 (Planned)
- Fix Issue #1: Multi-classifier support in `mlserver version` command
- Fix Issue #2: Multi-classifier support in `mlserver images` command
- Add `--all` flag to tag all classifiers at once
- Enhanced error messages for multi-classifier scenarios
- Additional multi-classifier examples in documentation

### Version 0.5.0 (Planned)
- Performance improvements for large repositories
- Batch operations for multi-classifier repos
- Enhanced status reporting with commit diffs
- Integration with container registries

---

## Support

- **Issues**: https://github.com/alxhrzg/merve/issues
- **Documentation**: https://github.com/alxhrzg/merve/tree/main/docs
- **Examples**: https://github.com/alxhrzg/merve/tree/main/examples

---

**Note**: This is a development version (0.3.0). Production release pending final validation.
