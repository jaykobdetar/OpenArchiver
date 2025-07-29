# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Archive Tool is a desktop application for creating large-scale, self-contained digital archives. It uses a unique architecture where the "source of truth" is stored in human-readable JSON sidecar files alongside assets, while SQLite provides a disposable search index.

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Desktop GUI
python main.py

# Command-line interface
python cli.py --help
python cli.py create /path/to/archive --name "My Archive"
python cli.py add /path/to/archive /path/to/files

# Demo (shows all features)
python demo.py
```

### Testing
```bash
# Run all tests with the test runner
python run_tests.py all

# Specific test categories
python run_tests.py unit          # Fast unit tests
python run_tests.py integration   # End-to-end workflows  
python run_tests.py performance   # Performance benchmarks
python run_tests.py coverage      # With coverage report
python run_tests.py quick         # Fast subset for development

# Direct pytest usage
pytest tests/unit -m unit -v
pytest tests/integration -m integration
pytest tests/performance -m performance --benchmark-only

# Run specific test
pytest tests/unit/test_models.py::TestArchive::test_create_archive -v
```

### Test Markers
- `@pytest.mark.unit`: Unit tests (fast, isolated)
- `@pytest.mark.integration`: Integration tests (slower, full workflows)
- `@pytest.mark.performance`: Performance tests with benchmarking
- `@pytest.mark.slow`: Slow tests (excluded from quick runs)

## Architecture Overview

### Core Principles
1. **Human-Readable Source of Truth**: Each archived file has a `.metadata.json` sidecar with all metadata
2. **Disposable SQLite Index**: Fast search cache that can be rebuilt from sidecar files
3. **File-Type Agnostic**: Works with any digital content without format bias
4. **Standards Compliance**: BagIt (RFC 8493) export for preservation workflows

### Archive Structure
```
archive_root/
├── archive.json              # Archive configuration
├── profiles/                 # Metadata schemas
│   └── profile_name.json
├── assets/                   # Organized files with sidecars
│   └── 2024/01/image/
│       ├── photo.jpg
│       └── photo.jpg.metadata.json
└── .index/                   # SQLite search database (disposable)
    └── index.db
```

### Key Components

#### Models (`src/models/`)
- **Archive**: Main container managing configuration and directory structure
- **Profile**: Metadata schema definitions with typed fields (text, tags, select, etc.)
- **Asset**: Individual files with associated AssetMetadata
- **AssetMetadata**: Complete metadata including checksums, custom fields, timestamps

#### Core Services (`src/core/`)
- **FileIngestionService**: File import, organization, and metadata creation
- **IndexingService**: SQLite database operations and FTS indexing
- **SearchService**: Query interface with text search and metadata filters
- **IntegrityService**: SHA-256 verification, corruption detection, index repair
- **ExportService**: BagIt and directory exports with manifest generation

#### UI Components (`src/ui/`)
PyQt6-based desktop interface with tabbed layout:
- **MainWindow**: Central application controller
- **ArchiveBrowser**: Tree view of archive contents
- **SearchWidget**: Query interface with filters
- **IntegrityWidget**: Verification and repair operations
- **ExportWidget**: BagIt export with metadata forms

### Data Flow Architecture

1. **Ingestion**: Files → FileIngestionService → Asset creation → Sidecar writing → IndexingService
2. **Search**: Query → SearchService → SQLite FTS → Results with metadata
3. **Verification**: IntegrityService → Read sidecar → Calculate checksum → Compare
4. **Export**: SearchService → Filter assets → ExportService → BagIt creation

### Critical Design Patterns

#### Sidecar Metadata Pattern
Every asset file gets a companion `.metadata.json` with complete information:
```json
{
  "asset_id": "uuid",
  "checksum_sha256": "hash",
  "custom_metadata": {"title": "...", "tags": [...]}
}
```

#### Disposable Index Pattern
SQLite database can be deleted and rebuilt from sidecar files:
```python
# Index rebuilding
indexing = IndexingService(archive)
success, errors = indexing.index_all_assets(force_reindex=True)
```

#### Profile-Based Metadata
Flexible schemas defined in JSON:
```python
profile.add_field(MetadataField(
    name="tags",
    field_type=FieldType.TAGS,
    required=False
))
```

## Development Guidelines

### Working with Archives
- Always use `Archive.create()` or `Archive.load()` to get properly initialized instances
- Archive paths are resolved to absolute paths internally
- Check `archive.exists()` before operations

### Metadata Handling
- Custom metadata is stored as key-value pairs in `AssetMetadata.custom_metadata`
- Field types (FieldType enum) determine storage and validation
- Tags and lists are JSON-serialized in the database but appear as Python objects in results

### Database Operations
- IndexingService manages all SQLite operations
- Database includes FTS5 virtual table for text search
- Foreign key constraints ensure metadata cleanup when assets are removed
- Use `_get_connection()` context manager for database access

### Testing Approach
- Unit tests mock external dependencies and test individual components
- Integration tests use real temporary directories and databases
- Performance tests benchmark operations with large datasets (1000+ files)
- All tests use temporary directories that auto-cleanup

### Error Handling Patterns
- Services return boolean success indicators for operations
- IntegrityService provides detailed reports with lists of issues
- Missing files and corruption are tracked separately in verification reports
- Database operations use transactions for consistency

### Memory Management
- Large operations use progress callbacks to avoid blocking UI
- Multi-threaded verification with configurable worker counts
- SQLite connections are properly closed using context managers
- Performance tests monitor memory usage with psutil

## Important Implementation Details

### Checksum Calculation
SHA-256 checksums are calculated in 64KB chunks to handle large files efficiently without excessive memory usage.

### File Organization
Default organization is `year/month/type` but configurable via archive settings. Files can be organized by date, MIME type, or custom schemes.

### Search Implementation
Combines SQLite FTS5 for text queries with EXISTS subqueries for metadata filters. Tag searches use LIKE patterns to find items within JSON arrays.

### Thread Safety
Database operations are thread-safe. IntegrityService uses ThreadPoolExecutor for concurrent verification with a cancellation mechanism.

### Virtual Environment Usage
Always work within the virtual environment as the project uses specific package versions, particularly for PyQt6 and bagit compatibility.