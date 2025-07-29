# Archive Tool

A desktop application for building large-scale, self-contained, and future-proof archives. The tool is designed to organize and catalog any type of digital file, from documents and source code to large-scale audio/video assets, without being architecturally biased towards a specific media type.

## Key Features

- **File-Type Agnostic**: Works with any file format without bias
- **Desktop-First & Private**: Runs entirely locally with no cloud dependencies
- **Future-Proof Design**: Human-readable metadata sidecar files ensure data accessibility
- **High-Performance Search**: SQLite-based indexing for fast search across large archives
- **Data Integrity**: SHA-256 checksums with verification capabilities
- **True Portability**: Archives can be moved between systems without breaking
- **Standards-Compliant Export**: BagIt (RFC 8493) export for maximum interoperability

## Architecture

### Core Principles

1. **Source of Truth**: Metadata is stored in human-readable JSON sidecar files alongside assets
2. **Disposable Index**: SQLite database serves as a fast search cache that can be rebuilt
3. **Universal Compatibility**: No proprietary formats or vendor lock-in
4. **Integrity First**: All files are checksummed and can be verified for corruption

### Directory Structure

```
archive_root/
├── archive.json          # Archive configuration
├── profiles/             # Metadata profiles (schemas)
│   ├── photos.json
│   └── documents.json
├── assets/               # All archived files
│   ├── 2024/01/image/
│   │   ├── photo.jpg
│   │   └── photo.jpg.metadata.json
│   └── documents/
│       ├── report.pdf
│       └── report.pdf.metadata.json
└── .index/               # Search index (disposable cache)
    └── index.db
```

## Installation

### Requirements

- Python 3.8+
- PyQt6
- SQLite3 (included with Python)

### Setup

1. Clone or extract the Archive Tool
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Desktop Application

Launch the GUI application:

```bash
python main.py
```

### Command Line Interface

The CLI provides full functionality for scripting and automation:

```bash
# Create a new archive
python cli.py create /path/to/archive --name "My Archive" --description "Personal files"

# Open and show archive info
python cli.py info /path/to/archive

# Add files to archive
python cli.py add /path/to/archive /path/to/file.jpg

# Add entire directory
python cli.py add /path/to/archive /path/to/directory/

# Search archive
python cli.py search /path/to/archive --query "vacation photos"

# Verify integrity
python cli.py verify /path/to/archive

# Export to BagIt format
python cli.py export /path/to/archive /path/to/output.bag --format bagit

# Create metadata profile
python cli.py create-profile /path/to/archive --name "Photos" --description "Photo metadata"

# Rebuild search index
python cli.py rebuild-index /path/to/archive
```

## Metadata Profiles

Profiles define custom metadata schemas for different types of content:

```json
{
  "id": "photos",
  "name": "Photo Collection",
  "description": "Metadata for photographs",
  "fields": [
    {
      "name": "title",
      "display_name": "Title",
      "field_type": "text",
      "required": true
    },
    {
      "name": "description",
      "display_name": "Description", 
      "field_type": "textarea"
    },
    {
      "name": "tags",
      "display_name": "Tags",
      "field_type": "tags"
    },
    {
      "name": "date_taken",
      "display_name": "Date Taken",
      "field_type": "date"
    }
  ]
}
```

## Metadata Sidecar Files

Each archived file has a corresponding `.metadata.json` file:

```json
{
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_path": "/Users/john/Photos/vacation.jpg",
  "archive_path": "assets/2024/01/image/vacation.jpg",
  "file_size": 2048576,
  "mime_type": "image/jpeg",
  "checksum_sha256": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
  "checksum_verified_at": "2024-01-15T10:30:00Z",
  "profile_id": "photos",
  "custom_metadata": {
    "title": "Beach Vacation",
    "description": "Sunset at the beach",
    "tags": ["vacation", "beach", "sunset"],
    "date_taken": "2024-01-10"
  },
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

## Data Integrity

### Checksum Verification

All files are SHA-256 checksummed on ingestion. You can verify integrity:

- **Desktop**: Use the Integrity tab to run verification
- **CLI**: `python cli.py verify /path/to/archive`

### Index Repair

If the search index becomes corrupted or out of sync:

- **Desktop**: Use "Repair Index" in the Integrity tab
- **CLI**: `python cli.py rebuild-index /path/to/archive`

## Export Options

### BagIt Format

Export to BagIt specification for maximum compatibility:

```bash
python cli.py export /path/to/archive /path/to/output.bag --format bagit
```

### Directory Structure

Export as simple directory hierarchy:

```bash
python cli.py export /path/to/archive /path/to/output_dir --format directory
```

## Development

### Project Structure

```
src/
├── models/           # Data models (Archive, Profile, Asset)
├── core/            # Core services (Ingestion, Search, Integrity, Export)
├── ui/              # PyQt6 desktop interface
└── utils/           # Utility functions

cli.py               # Command-line interface
main.py              # Desktop application entry point
```

### Key Components

- **Archive**: Main container with configuration
- **Profile**: Metadata schema definition  
- **Asset**: Individual file with metadata
- **FileIngestionService**: Handles file import and organization
- **IndexingService**: Manages SQLite search index
- **SearchService**: Provides search functionality
- **IntegrityService**: Handles verification and repair
- **ExportService**: BagIt and directory exports

## Best Practices

1. **Regular Verification**: Run integrity checks periodically
2. **Profile Design**: Create specific profiles for different content types
3. **Descriptive Metadata**: Use meaningful titles and descriptions
4. **Backup Strategy**: The entire archive directory can be copied/synced
5. **Index Maintenance**: Rebuild index if performance degrades

## Technical Details

- **Database**: SQLite with FTS5 full-text search
- **Checksums**: SHA-256 for integrity verification
- **Standards**: BagIt (RFC 8493) for exports
- **File Organization**: Configurable by date/type/custom schemes
- **Threading**: Multi-threaded operations for large archives
- **Cross-Platform**: Works on Windows, macOS, and Linux

## License

This project is provided as-is for demonstration and educational purposes.