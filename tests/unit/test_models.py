"""
Unit tests for Archive Tool models
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from src.models import Archive, Profile, MetadataField, FieldType, Asset, AssetMetadata


@pytest.mark.unit
class TestMetadataField:
    """Test MetadataField class"""
    
    def test_create_field(self):
        field = MetadataField(
            name="test_field",
            display_name="Test Field",
            field_type=FieldType.TEXT,
            required=True,
            description="Test description"
        )
        
        assert field.name == "test_field"
        assert field.display_name == "Test Field"
        assert field.field_type == FieldType.TEXT
        assert field.required is True
        assert field.description == "Test description"
    
    def test_field_with_options(self):
        field = MetadataField(
            name="category",
            display_name="Category",
            field_type=FieldType.SELECT,
            options=["Option1", "Option2", "Option3"]
        )
        
        assert field.options == ["Option1", "Option2", "Option3"]
    
    def test_field_to_dict(self):
        field = MetadataField(
            name="test_field",
            display_name="Test Field",
            field_type=FieldType.TEXTAREA,
            required=False,
            default_value="default",
            description="Test field"
        )
        
        field_dict = field.to_dict()
        
        assert field_dict["name"] == "test_field"
        assert field_dict["display_name"] == "Test Field"
        assert field_dict["field_type"] == "textarea"
        assert field_dict["required"] is False
        assert field_dict["default_value"] == "default"
    
    def test_field_from_dict(self):
        field_data = {
            "name": "test_field",
            "display_name": "Test Field",
            "field_type": "text",
            "required": True,
            "description": "Test field"
        }
        
        field = MetadataField.from_dict(field_data)
        
        assert field.name == "test_field"
        assert field.display_name == "Test Field"
        assert field.field_type == FieldType.TEXT
        assert field.required is True


@pytest.mark.unit
class TestProfile:
    """Test Profile class"""
    
    def test_create_profile(self):
        profile = Profile(
            id="test_profile",
            name="Test Profile",
            description="Test description",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )
        
        assert profile.id == "test_profile"
        assert profile.name == "Test Profile"
        assert profile.description == "Test description"
        assert len(profile.fields) == 0
    
    def test_add_field(self):
        profile = Profile(
            id="test_profile",
            name="Test Profile",
            description="Test description"
        )
        
        field = MetadataField(
            name="title",
            display_name="Title",
            field_type=FieldType.TEXT
        )
        
        profile.add_field(field)
        assert len(profile.fields) == 1
        assert profile.fields[0].name == "title"
    
    def test_add_duplicate_field_raises_error(self):
        profile = Profile(
            id="test_profile",
            name="Test Profile",
            description="Test description"
        )
        
        field1 = MetadataField(name="title", display_name="Title", field_type=FieldType.TEXT)
        field2 = MetadataField(name="title", display_name="Title 2", field_type=FieldType.TEXT)
        
        profile.add_field(field1)
        
        with pytest.raises(ValueError, match="Field with name 'title' already exists"):
            profile.add_field(field2)
    
    def test_remove_field(self):
        profile = Profile(
            id="test_profile",
            name="Test Profile",
            description="Test description"
        )
        
        field = MetadataField(name="title", display_name="Title", field_type=FieldType.TEXT)
        profile.add_field(field)
        
        assert len(profile.fields) == 1
        
        profile.remove_field("title")
        assert len(profile.fields) == 0
    
    def test_get_field(self):
        profile = Profile(
            id="test_profile",
            name="Test Profile", 
            description="Test description"
        )
        
        field = MetadataField(name="title", display_name="Title", field_type=FieldType.TEXT)
        profile.add_field(field)
        
        retrieved_field = profile.get_field("title")
        assert retrieved_field is not None
        assert retrieved_field.name == "title"
        
        nonexistent_field = profile.get_field("nonexistent")
        assert nonexistent_field is None
    
    def test_profile_to_dict(self):
        profile = Profile(
            id="test_profile",
            name="Test Profile",
            description="Test description",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )
        
        field = MetadataField(name="title", display_name="Title", field_type=FieldType.TEXT)
        profile.add_field(field)
        
        profile_dict = profile.to_dict()
        
        assert profile_dict["id"] == "test_profile"
        assert profile_dict["name"] == "Test Profile"
        assert len(profile_dict["fields"]) == 1
        assert profile_dict["fields"][0]["name"] == "title"
    
    def test_profile_from_dict(self):
        profile_data = {
            "id": "test_profile",
            "name": "Test Profile",
            "description": "Test description",
            "fields": [
                {
                    "name": "title",
                    "display_name": "Title",
                    "field_type": "text",
                    "required": True
                }
            ],
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
        
        profile = Profile.from_dict(profile_data)
        
        assert profile.id == "test_profile"
        assert profile.name == "Test Profile"
        assert len(profile.fields) == 1
        assert profile.fields[0].name == "title"
        assert profile.fields[0].required is True
    
    def test_profile_save_and_load(self, temp_dir):
        profile = Profile(
            id="test_profile",
            name="Test Profile",
            description="Test description"
        )
        
        field = MetadataField(name="title", display_name="Title", field_type=FieldType.TEXT)
        profile.add_field(field)
        
        # Save profile
        profile_path = temp_dir / "test_profile.json"
        profile.save_to_file(profile_path)
        
        assert profile_path.exists()
        
        # Load profile
        loaded_profile = Profile.load_from_file(profile_path)
        
        assert loaded_profile.id == profile.id
        assert loaded_profile.name == profile.name
        assert len(loaded_profile.fields) == 1
        assert loaded_profile.fields[0].name == "title"


@pytest.mark.unit
class TestArchive:
    """Test Archive class"""
    
    def test_create_archive(self, temp_dir):
        archive_path = temp_dir / "test_archive"
        archive = Archive(archive_path)
        
        assert not archive.exists()
        
        created_archive = archive.create("Test Archive", "Test description")
        
        assert archive.exists()
        assert archive.config_path.exists()
        assert archive.profiles_path.exists()
        assert archive.assets_path.exists()
        assert archive.index_path.exists()
        assert created_archive.config.name == "Test Archive"
        assert created_archive.config.description == "Test description"
    
    def test_create_existing_archive_raises_error(self, temp_dir):
        archive_path = temp_dir / "test_archive"
        archive = Archive(archive_path)
        
        # Create archive
        archive.create("Test Archive", "Test description")
        
        # Try to create again
        with pytest.raises(ValueError, match="Archive already exists"):
            archive.create("Another Archive", "Another description")
    
    def test_load_archive(self, sample_archive):
        # sample_archive fixture creates and loads an archive
        assert sample_archive.config is not None
        assert sample_archive.config.name == "Test Archive"
        assert sample_archive.config.description == "Test archive for unit tests"
    
    def test_load_nonexistent_archive_raises_error(self, temp_dir):
        archive_path = temp_dir / "nonexistent_archive"
        archive = Archive(archive_path)
        
        with pytest.raises(ValueError, match="No archive found"):
            archive.load()
    
    def test_archive_paths(self, sample_archive):
        assert sample_archive.config_path.name == "archive.json"
        assert sample_archive.profiles_path.name == "profiles"
        assert sample_archive.assets_path.name == "assets"
        assert sample_archive.index_path.name == ".index"
    
    def test_get_profiles(self, sample_archive, sample_profile):
        # Save a profile
        profile_path = sample_archive.profiles_path / f"{sample_profile.id}.json"
        sample_profile.save_to_file(profile_path)
        
        profiles = sample_archive.get_profiles()
        assert len(profiles) == 1
        assert profiles[0].name == "test_profile.json"
    
    def test_get_asset_count(self, sample_archive, sample_files):
        # Initially no assets
        assert sample_archive.get_asset_count() == 0
        
        # Copy some files to assets directory
        for i, file_path in enumerate(sample_files[:2]):  # Just copy 2 files
            target_path = sample_archive.assets_path / f"test_file_{i}.txt"
            target_path.write_text(file_path.read_text())
        
        assert sample_archive.get_asset_count() == 2


@pytest.mark.unit
class TestAssetMetadata:
    """Test AssetMetadata class"""
    
    def test_create_asset_metadata(self):
        metadata = AssetMetadata(
            asset_id="test-id-123",
            original_path="/original/path/file.txt",
            archive_path="assets/2024/01/file.txt",
            file_size=1024,
            mime_type="text/plain",
            checksum_sha256="abc123",
            created_at="2024-01-01T00:00:00"
        )
        
        assert metadata.asset_id == "test-id-123"
        assert metadata.original_path == "/original/path/file.txt"
        assert metadata.archive_path == "assets/2024/01/file.txt"
        assert metadata.file_size == 1024
        assert metadata.mime_type == "text/plain"
        assert metadata.checksum_sha256 == "abc123"
    
    def test_metadata_to_dict(self):
        metadata = AssetMetadata(
            asset_id="test-id-123",
            original_path="/original/path/file.txt",
            archive_path="assets/2024/01/file.txt",
            file_size=1024,
            custom_metadata={"title": "Test File", "tags": ["test"]}
        )
        
        metadata_dict = metadata.to_dict()
        
        assert metadata_dict["asset_id"] == "test-id-123"
        assert metadata_dict["file_size"] == 1024
        assert metadata_dict["custom_metadata"]["title"] == "Test File"
        assert metadata_dict["custom_metadata"]["tags"] == ["test"]
    
    def test_metadata_from_dict(self):
        metadata_data = {
            "asset_id": "test-id-123",
            "original_path": "/original/path/file.txt",
            "archive_path": "assets/2024/01/file.txt",
            "file_size": 1024,
            "mime_type": "text/plain",
            "custom_metadata": {"title": "Test File"}
        }
        
        metadata = AssetMetadata.from_dict(metadata_data)
        
        assert metadata.asset_id == "test-id-123"
        assert metadata.file_size == 1024
        assert metadata.custom_metadata["title"] == "Test File"


@pytest.mark.unit
class TestAsset:
    """Test Asset class"""
    
    def test_create_asset(self, temp_dir):
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")
        
        archive_root = temp_dir / "archive"
        asset = Asset(test_file, archive_root)
        
        assert asset.file_path == test_file
        assert asset.archive_root == archive_root
        assert asset.metadata is None
    
    def test_sidecar_path(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")
        
        archive_root = temp_dir / "archive"
        asset = Asset(test_file, archive_root)
        
        expected_sidecar = test_file.parent / "test.txt.metadata.json"
        assert asset.sidecar_path == expected_sidecar
    
    def test_calculate_checksum(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_content = "Test content for checksum"
        test_file.write_text(test_content)
        
        archive_root = temp_dir / "archive"
        asset = Asset(test_file, archive_root)
        
        checksum = asset.calculate_checksum()
        
        # Verify checksum is a valid hex string
        assert len(checksum) == 64  # SHA-256 produces 64 hex chars
        assert all(c in '0123456789abcdef' for c in checksum)
        
        # Calculate again to ensure consistency
        checksum2 = asset.calculate_checksum()
        assert checksum == checksum2
    
    def test_save_and_load_metadata(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")
        
        archive_root = temp_dir / "archive"
        asset = Asset(test_file, archive_root)
        
        # Create metadata
        metadata = AssetMetadata(
            asset_id="test-123",
            original_path=str(test_file),
            archive_path="test.txt",
            file_size=test_file.stat().st_size,
            checksum_sha256="abc123",
            custom_metadata={"title": "Test File"}
        )
        
        asset.metadata = metadata
        asset.save_metadata()
        
        # Verify sidecar file was created
        assert asset.sidecar_path.exists()
        
        # Create new asset instance and load metadata
        new_asset = Asset(test_file, archive_root)
        assert new_asset.load_metadata() is True
        assert new_asset.metadata.asset_id == "test-123"
        assert new_asset.metadata.custom_metadata["title"] == "Test File"
    
    def test_load_nonexistent_metadata(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")
        
        archive_root = temp_dir / "archive"
        asset = Asset(test_file, archive_root)
        
        assert asset.load_metadata() is False
        assert asset.metadata is None
    
    def test_verify_checksum(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_content = "Test content for verification"
        test_file.write_text(test_content)
        
        archive_root = temp_dir / "archive"
        asset = Asset(test_file, archive_root)
        
        # Calculate and store correct checksum
        correct_checksum = asset.calculate_checksum()
        metadata = AssetMetadata(
            asset_id="test-123",
            original_path=str(test_file),
            archive_path="test.txt",
            file_size=test_file.stat().st_size,
            checksum_sha256=correct_checksum
        )
        asset.metadata = metadata
        
        # Verification should pass
        assert asset.verify_checksum() is True
        
        # Modify checksum to make it incorrect
        asset.metadata.checksum_sha256 = "incorrect_checksum"
        
        # Verification should fail
        assert asset.verify_checksum() is False
    
    def test_get_relative_path(self, temp_dir):
        archive_root = temp_dir / "archive"
        test_file = archive_root / "subfolder" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("Test content")
        
        asset = Asset(test_file, archive_root)
        relative_path = asset.get_relative_path()
        
        assert relative_path == Path("subfolder/test.txt")
    
    def test_get_relative_path_outside_archive(self, temp_dir):
        archive_root = temp_dir / "archive"
        test_file = temp_dir / "outside" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("Test content")
        
        asset = Asset(test_file, archive_root)
        relative_path = asset.get_relative_path()
        
        # Should return the full path when file is outside archive
        assert relative_path == test_file