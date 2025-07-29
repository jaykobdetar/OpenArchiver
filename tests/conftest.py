"""
Pytest configuration and fixtures for Archive Tool tests
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import json

from src.models import Archive, Profile, MetadataField, FieldType


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_archive(temp_dir):
    """Create a sample archive for testing"""
    archive_path = temp_dir / "test_archive"
    archive = Archive(archive_path)
    archive.create("Test Archive", "Test archive for unit tests")
    yield archive
    # Cleanup handled by temp_dir fixture


@pytest.fixture
def sample_profile():
    """Create a sample metadata profile"""
    profile = Profile(
        id="test_profile",
        name="Test Profile",
        description="Profile for testing",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    
    profile.add_field(MetadataField(
        name="title",
        display_name="Title",
        field_type=FieldType.TEXT,
        required=True
    ))
    
    profile.add_field(MetadataField(
        name="description",
        display_name="Description",
        field_type=FieldType.TEXTAREA
    ))
    
    profile.add_field(MetadataField(
        name="tags",
        display_name="Tags",
        field_type=FieldType.TAGS
    ))
    
    profile.add_field(MetadataField(
        name="category",
        display_name="Category",
        field_type=FieldType.SELECT,
        options=["Document", "Image", "Video", "Other"]
    ))
    
    return profile


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing"""
    files_dir = temp_dir / "sample_files"
    files_dir.mkdir()
    
    files = []
    
    # Text files
    for i in range(3):
        file_path = files_dir / f"document_{i+1}.txt"
        with open(file_path, 'w') as f:
            f.write(f"This is test document {i+1}\n")
            f.write(f"Created for testing purposes\n")
            f.write(f"Content: Lorem ipsum dolor sit amet\n")
        files.append(file_path)
    
    # Binary file (simulate image)
    binary_path = files_dir / "image.jpg"
    with open(binary_path, 'wb') as f:
        f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01')  # JPEG header
        f.write(b'fake image data for testing' * 100)
    files.append(binary_path)
    
    # JSON file
    json_path = files_dir / "data.json"
    with open(json_path, 'w') as f:
        json.dump({"test": "data", "items": [1, 2, 3]}, f)
    files.append(json_path)
    
    return files


@pytest.fixture
def large_sample_files(temp_dir):
    """Create a large number of sample files for performance testing"""
    files_dir = temp_dir / "large_sample"
    files_dir.mkdir()
    
    files = []
    
    # Create 100 files in subdirectories
    for i in range(10):
        subdir = files_dir / f"dir_{i}"
        subdir.mkdir()
        
        for j in range(10):
            file_path = subdir / f"file_{i}_{j}.txt"
            with open(file_path, 'w') as f:
                f.write(f"File {i}-{j} content\n" * 50)  # Make files larger
            files.append(file_path)
    
    return files


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing"""
    return {
        "title": "Test Document",
        "description": "This is a test document for unit testing",
        "tags": ["test", "unit", "sample"],
        "category": "Document"
    }


@pytest.fixture
def archive_with_assets(sample_archive, sample_files, sample_profile, sample_metadata):
    """Archive with ingested assets for testing"""
    from src.core.ingestion import FileIngestionService
    from src.core.indexing import IndexingService
    
    # Save profile
    profile_path = sample_archive.profiles_path / f"{sample_profile.id}.json"
    sample_profile.save_to_file(profile_path)
    
    # Ingest files
    ingestion = FileIngestionService(sample_archive)
    indexing = IndexingService(sample_archive)
    
    assets = []
    for i, file_path in enumerate(sample_files):
        metadata = sample_metadata.copy()
        metadata["title"] = f"Test File {i+1}"
        
        asset = ingestion.ingest_file(file_path, profile=sample_profile, custom_metadata=metadata)
        indexing.index_asset(asset)
        assets.append(asset)
    
    return sample_archive, assets


@pytest.fixture(scope="session")
def performance_archive(tmp_path_factory):
    """Large archive for performance testing (session-scoped)"""
    temp_path = tmp_path_factory.mktemp("perf_archive")
    archive_path = temp_path / "performance_archive"
    
    archive = Archive(archive_path)
    archive.create("Performance Test Archive", "Large archive for performance testing")
    
    # Create profile
    profile = Profile(
        id="perf_profile",
        name="Performance Profile",
        description="Profile for performance testing",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    
    profile.add_field(MetadataField(
        name="title",
        display_name="Title",
        field_type=FieldType.TEXT,
        required=True
    ))
    
    profile.add_field(MetadataField(
        name="category",
        display_name="Category", 
        field_type=FieldType.SELECT,
        options=["Type1", "Type2", "Type3"]
    ))
    
    profile_path = archive.profiles_path / f"{profile.id}.json"
    profile.save_to_file(profile_path)
    
    yield archive, profile
    
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)