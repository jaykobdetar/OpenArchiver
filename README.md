# Archive Tool
<img width="1199" height="838" alt="image" src="https://github.com/user-attachments/assets/d24c354a-06fa-44fd-94b8-193e5a72bb5b" />

A desktop application for creating large-scale, self-contained digital archives with flexible metadata management and BagIt export capabilities.

## Features

- **Human-readable metadata**: Each file has a JSON sidecar with complete metadata
- **Flexible schemas**: Define custom metadata profiles for different content types
- **Full-text search**: Fast SQLite-based indexing with metadata filtering
- **Integrity verification**: SHA-256 checksums with corruption detection
- **Standards compliance**: BagIt (RFC 8493) export for preservation workflows
- **Desktop interface**: PyQt6-based GUI with tabbed workflow
- **Command-line tools**: Scriptable CLI for automation

## Installation

### Requirements

- Python 3.8+
- PyQt6 for desktop interface
- SQLite for search indexing

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd Archiver
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Desktop Application

Launch the GUI interface:
```bash
python main.py
```

### Command Line Interface

Create a new archive:
```bash
python cli.py create /path/to/archive --name "My Archive"
```

Add files to an archive:
```bash
python cli.py add /path/to/archive /path/to/files
```

Search archive contents:
```bash
python cli.py search /path/to/archive --query "annual report"
```

View archive information:
```bash
python cli.py info /path/to/archive
```

Run the demo to see all features:
```bash
python demo.py
```

## Archive Structure

```
archive_root/
├── archive.json              # Archive configuration
├── profiles/                 # Metadata schemas
│   └── profile_name.json
├── assets/                   # Organized files with sidecars
│   └── 2024/01/documents/
│       ├── report.pdf
│       └── report.pdf.metadata.json
└── .index/                   # SQLite search database
    └── index.db
```

## Metadata Profiles

Define custom metadata schemas for different content types:

```json
{
  "id": "documents",
  "name": "Document Profile",
  "fields": [
    {
      "name": "title",
      "display_name": "Title",
      "field_type": "text",
      "required": true
    },
    {
      "name": "tags",
      "display_name": "Tags",
      "field_type": "tags"
    }
  ]
}
```

Supported field types: `text`, `tags`, `select`, `boolean`, `date`, `number`

## Development

### Running Tests

```bash
# All tests
python run_tests.py all

# Specific test types
python run_tests.py unit
python run_tests.py integration
python run_tests.py ui
python run_tests.py performance

# With coverage
python run_tests.py coverage
```

### Project Structure

- `src/models/` - Core data models (Archive, Asset, Profile)
- `src/core/` - Services (ingestion, indexing, search, integrity, export)
- `src/ui/` - PyQt6 interface components
- `tests/` - Comprehensive test suite with 68% coverage

### Architecture

The system uses a unique "disposable index" architecture where:
- Human-readable JSON sidecars are the authoritative source
- SQLite provides fast search capabilities
- The database can be rebuilt from sidecars if corrupted

## License

MIT License - see LICENSE file for details.
