# Archive Tool Test Suite

A comprehensive test suite for the Archive Tool, covering unit tests, integration tests, and performance tests.

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── utils.py                 # Test utilities and helpers
├── unit/                    # Unit tests for individual components
│   ├── test_models.py       # Tests for data models
│   └── test_core_services.py # Tests for core services
├── integration/             # Integration tests for complete workflows
│   ├── test_full_workflows.py
│   └── test_database_integration.py
└── performance/             # Performance and load tests
    └── test_large_archives.py
```

## Running Tests

### Quick Start

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
python run_tests.py all

# Run only unit tests
python run_tests.py unit

# Run with coverage
python run_tests.py coverage
```

### Test Categories

#### Unit Tests (`pytest tests/unit -m unit`)
- **Models**: Archive, Profile, Asset, MetadataField
- **Core Services**: FileIngestionService, IndexingService, SearchService, IntegrityService, ExportService
- **Utilities**: File operations and helper functions

#### Integration Tests (`pytest tests/integration -m integration`)
- **Full Workflows**: Complete archive creation → ingestion → search → verify → export
- **Database Integration**: SQLite operations, transactions, FTS integration
- **Multi-profile Workflows**: Different metadata schemas
- **Error Recovery**: Handling corruption, index repair

#### Performance Tests (`pytest tests/performance -m performance`)
- **Large Archive Operations**: 1000+ files ingestion and indexing
- **Search Performance**: Query response times with large datasets
- **Memory Usage**: Resource consumption monitoring
- **Concurrent Operations**: Multi-threaded performance
- **Database Scaling**: Performance as archive size grows

### Running Specific Tests

```bash
# Run specific test file
pytest tests/unit/test_models.py -v

# Run specific test class
pytest tests/unit/test_models.py::TestArchive -v

# Run specific test method
pytest tests/integration/test_full_workflows.py::TestCompleteArchiveWorkflow::test_create_archive_to_export_workflow -v

# Run tests with specific markers
pytest -m "unit and not slow" -v

# Run performance tests with benchmarking
pytest tests/performance -m performance --benchmark-only
```

### Test Markers

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.slow`: Slow-running tests (excluded from quick runs)

## Test Fixtures

### Archive Fixtures
- `temp_dir`: Temporary directory for test files
- `sample_archive`: Pre-created archive for testing
- `sample_profile`: Test metadata profile with common fields
- `sample_files`: Collection of test files (text, JSON, binary)
- `archive_with_assets`: Archive with ingested and indexed assets
- `performance_archive`: Large archive for performance testing

### Data Fixtures
- `sample_metadata`: Example metadata dictionary
- `large_sample_files`: Large collection of files for stress testing

## Test Utilities

### MockDataGenerator
```python
from tests.utils import MockDataGenerator

# Generate test files
files = MockDataGenerator.create_test_files(directory, count=10)

# Generate binary files
binary_files = MockDataGenerator.create_binary_files(directory, count=5)

# Generate nested directory structure
all_files = MockDataGenerator.create_nested_directory_structure(base_dir, depth=3)

# Generate metadata profile
profile = MockDataGenerator.generate_metadata_profile(complex=True)

# Generate asset metadata
metadata = MockDataGenerator.generate_asset_metadata(profile=profile)
```

### TestAssertions
```python
from tests.utils import TestAssertions

# Assert archive structure is correct
TestAssertions.assert_archive_structure(archive_path)

# Assert asset integrity
TestAssertions.assert_asset_integrity(asset)

# Assert search result validity
TestAssertions.assert_search_result_valid(result, expected_fields=["title", "category"])

# Assert profile validity
TestAssertions.assert_profile_valid(profile)
```

### Performance Monitoring
```python
from tests.utils import PerformanceTimer, MemoryMonitor

# Time operations
with PerformanceTimer("File Ingestion"):
    asset = ingestion.ingest_file(file_path)

# Monitor memory usage
monitor = MemoryMonitor()
monitor.start()
# ... perform operations ...
monitor.measure("After ingestion")
monitor.report()
```

## Coverage Reporting

The test suite includes comprehensive coverage reporting:

```bash
# Generate coverage reports
python run_tests.py coverage

# View HTML coverage report
open htmlcov/index.html
```

Coverage targets:
- **Unit Tests**: >90% line coverage for core modules
- **Integration Tests**: End-to-end workflow coverage
- **Performance Tests**: Resource usage and scaling validation

## Performance Benchmarks

Performance tests include benchmarking with `pytest-benchmark`:

```bash
# Run performance tests with benchmarks
python run_tests.py performance
```

### Benchmark Targets

#### Ingestion Performance
- **Small files (<1KB)**: >100 files/second
- **Medium files (1-10KB)**: >50 files/second
- **Large files (>1MB)**: >10 files/second

#### Search Performance
- **Simple queries**: <100ms for archives with 1000+ assets
- **Complex filters**: <500ms for archives with 1000+ assets
- **Full-text search**: <200ms for archives with 1000+ assets

#### Memory Usage
- **Ingestion**: <1MB per file processed
- **Search operations**: <50MB increase for large queries
- **Integrity verification**: <200MB total for 1000+ files

## Continuous Integration

The test suite is designed for CI/CD integration:

```yaml
# Example GitHub Actions configuration
- name: Run Tests
  run: |
    pip install -r requirements.txt
    python run_tests.py all --no-coverage
    
- name: Performance Tests
  run: |
    python run_tests.py performance
```

## Test Data Management

### Temporary Files
- All tests use temporary directories that are automatically cleaned up
- No test data persists between test runs
- Each test is isolated with its own temporary environment

### Large Data Sets
- Performance tests generate data on-demand
- Session-scoped fixtures for expensive setup operations
- Configurable data sizes for different test scenarios

## Debugging Tests

### Verbose Output
```bash
# Run with verbose output
pytest tests/ -v -s

# Show local variables on failure
pytest tests/ -v --tb=long

# Run with debugging
pytest tests/ --pdb
```

### Test-Specific Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Tests will show detailed logging output
```

### Memory Profiling
```bash
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m memory_profiler test_script.py
```

## Contributing Tests

When adding new functionality:

1. **Write unit tests** for individual components
2. **Add integration tests** for workflows
3. **Include performance tests** for operations that process large amounts of data
4. **Update fixtures** if new test data patterns are needed
5. **Document any new test utilities**

### Test Naming Conventions
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Use descriptive names that explain what is being tested

### Test Organization
- Group related tests in classes
- Use setup/teardown methods for test preparation
- Keep tests focused and independent
- Mock external dependencies when appropriate

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure src package is in Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### Database Lock Errors
- Ensure proper connection cleanup in tests
- Use context managers for database connections
- Check for unclosed database connections

#### Memory Issues in Performance Tests
- Reduce test data size for development
- Use garbage collection between tests
- Monitor memory usage with `psutil`

#### Slow Test Execution
- Run quick test suite for development: `python run_tests.py quick`
- Use test markers to exclude slow tests
- Parallelize tests where possible

For more specific issues, check the test output and logs for detailed error messages.