"""
Integration tests for complete Archive Tool workflows
"""

import pytest
import json
import shutil
from pathlib import Path
from datetime import datetime

from src.models import Archive, Profile, MetadataField, FieldType
from src.core import (
    FileIngestionService, IndexingService, SearchService, 
    IntegrityService, ExportService
)


@pytest.mark.integration
class TestCompleteArchiveWorkflow:
    """Test complete archive workflow from creation to export"""
    
    def test_create_archive_to_export_workflow(self, temp_dir, sample_files):
        """Test complete workflow: create → profile → ingest → search → verify → export"""
        
        # Step 1: Create archive
        archive_path = temp_dir / "workflow_archive"
        archive = Archive(archive_path)
        archive.create("Workflow Test Archive", "Integration test archive")
        
        assert archive.exists()
        assert archive.config.name == "Workflow Test Archive"
        
        # Step 2: Create and save profile
        profile = Profile(
            id="workflow_profile",
            name="Workflow Profile",
            description="Test profile for workflow",
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
            options=["Document", "Image", "Data"]
        ))
        
        profile.add_field(MetadataField(
            name="tags",
            display_name="Tags",
            field_type=FieldType.TAGS
        ))
        
        # Save profile
        profile_path = archive.profiles_path / f"{profile.id}.json"
        profile.save_to_file(profile_path)
        
        # Step 3: Ingest files
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        ingested_assets = []
        for i, file_path in enumerate(sample_files):
            custom_metadata = {
                "title": f"Workflow File {i+1}",
                "category": "Document" if file_path.suffix == ".txt" else "Data",
                "tags": ["workflow", "test", f"file_{i+1}"]
            }
            
            asset = ingestion.ingest_file(
                file_path,
                profile=profile,
                custom_metadata=custom_metadata
            )
            
            # Index asset
            success = indexing.index_asset(asset)
            assert success is True
            
            ingested_assets.append(asset)
        
        # Step 4: Verify all files were ingested and indexed
        stats = indexing.get_statistics()
        assert stats['total_assets'] == len(sample_files)
        assert stats['total_size'] > 0
        
        # Step 5: Test search functionality
        search = SearchService(archive)
        
        # Search all assets
        all_results, total = search.search()
        assert total == len(sample_files)
        assert len(all_results) == len(sample_files)
        
        # Search by text query
        text_results, text_total = search.search(query="workflow")
        assert text_total > 0  # Should find files with "workflow" in metadata
        
        # Search by category filter
        doc_results, doc_total = search.search(filters={"category": "Document"})
        assert doc_total > 0
        
        for result in doc_results:
            assert result.custom_metadata["category"] == "Document"
        
        # Search by tags
        tag_results, tag_total = search.search(filters={"tags": "test"})
        assert tag_total == len(sample_files)  # All files have "test" tag
        
        # Step 6: Verify integrity
        integrity = IntegrityService(archive)
        report = integrity.verify_all()
        
        assert report.total_assets == len(sample_files)
        assert report.verified_assets == len(sample_files)
        assert report.success_rate == 100.0
        assert len(report.corrupted_assets) == 0
        assert len(report.missing_assets) == 0
        
        # Step 7: Export to BagIt
        export_service = ExportService(archive)
        bagit_path = temp_dir / "workflow_export.bag"
        
        metadata = {
            'Source-Organization': 'Integration Test',
            'Contact-Name': 'Test Runner',
            'External-Description': 'Integration test export'
        }
        
        result_path = export_service.export_to_bagit(bagit_path, metadata=metadata)
        
        assert result_path.exists()
        assert (result_path / "bagit.txt").exists()
        assert (result_path / "bag-info.txt").exists()
        assert (result_path / "data").exists()
        
        # Verify exported files exist
        data_dir = result_path / "data"
        exported_files = list(data_dir.rglob("*"))
        asset_files = [f for f in exported_files if f.is_file() and not f.name.endswith('.metadata.json')]
        assert len(asset_files) == len(sample_files)
        
        # Step 8: Generate manifest
        manifest_path = temp_dir / "workflow_manifest.json"
        export_service.generate_manifest(manifest_path, format="json")
        
        assert manifest_path.exists()
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert manifest['archive']['name'] == "Workflow Test Archive"
        assert len(manifest['assets']) == len(sample_files)
        
        # Verify manifest contains expected metadata
        first_asset = manifest['assets'][0]
        assert 'asset_id' in first_asset
        assert 'archive_path' in first_asset
        assert 'checksum_sha256' in first_asset
        assert first_asset['custom_metadata']['title'].startswith('Workflow File')
    
    def test_multi_profile_workflow(self, temp_dir, sample_files):
        """Test workflow with multiple profiles and different metadata schemas"""
        
        # Create archive
        archive_path = temp_dir / "multi_profile_archive"
        archive = Archive(archive_path)
        archive.create("Multi-Profile Archive", "Test archive with multiple profiles")
        
        # Create document profile
        doc_profile = Profile(
            id="documents",
            name="Documents",
            description="Profile for documents",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        doc_profile.add_field(MetadataField(
            name="title",
            display_name="Document Title",
            field_type=FieldType.TEXT,
            required=True
        ))
        
        doc_profile.add_field(MetadataField(
            name="author",
            display_name="Author",
            field_type=FieldType.TEXT
        ))
        
        doc_profile.add_field(MetadataField(
            name="document_type",
            display_name="Document Type",
            field_type=FieldType.SELECT,
            options=["Report", "Letter", "Manual"]
        ))
        
        # Create media profile
        media_profile = Profile(
            id="media",
            name="Media Files",
            description="Profile for media files",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        media_profile.add_field(MetadataField(
            name="title",
            display_name="Media Title",
            field_type=FieldType.TEXT,
            required=True
        ))
        
        media_profile.add_field(MetadataField(
            name="format",
            display_name="Format",
            field_type=FieldType.SELECT,
            options=["Image", "Video", "Audio"]
        ))
        
        media_profile.add_field(MetadataField(
            name="resolution",
            display_name="Resolution",
            field_type=FieldType.TEXT
        ))
        
        # Save profiles
        doc_profile.save_to_file(archive.profiles_path / f"{doc_profile.id}.json")
        media_profile.save_to_file(archive.profiles_path / f"{media_profile.id}.json")
        
        # Ingest files with different profiles
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        # Text files use document profile
        doc_assets = []
        text_files = [f for f in sample_files if f.suffix == ".txt"]
        
        for i, file_path in enumerate(text_files):
            metadata = {
                "title": f"Document {i+1}",
                "author": f"Author {i+1}",
                "document_type": "Report"
            }
            
            asset = ingestion.ingest_file(file_path, profile=doc_profile, custom_metadata=metadata)
            indexing.index_asset(asset)
            doc_assets.append(asset)
        
        # Non-text files use media profile
        media_assets = []
        non_text_files = [f for f in sample_files if f.suffix != ".txt"]
        
        for i, file_path in enumerate(non_text_files):
            metadata = {
                "title": f"Media File {i+1}",
                "format": "Image" if file_path.suffix == ".jpg" else "Data",
                "resolution": "1920x1080"
            }
            
            asset = ingestion.ingest_file(file_path, profile=media_profile, custom_metadata=metadata)
            indexing.index_asset(asset)
            media_assets.append(asset)
        
        # Test profile-specific searches
        search = SearchService(archive)
        
        # Search documents only
        doc_results, doc_total = search.search(filters={"profile_id": doc_profile.id})
        assert doc_total == len(doc_assets)
        
        for result in doc_results:
            assert result.profile_id == doc_profile.id
            assert "author" in result.custom_metadata
            assert "document_type" in result.custom_metadata
        
        # Search media only
        media_results, media_total = search.search(filters={"profile_id": media_profile.id})
        assert media_total == len(media_assets)
        
        for result in media_results:
            assert result.profile_id == media_profile.id
            assert "format" in result.custom_metadata
            assert "resolution" in result.custom_metadata
        
        # Search by profile-specific fields
        report_results, report_total = search.search(filters={"document_type": "Report"})
        assert report_total == len(doc_assets)
        
        image_results, image_total = search.search(filters={"format": "Image"})
        assert image_total > 0
    
    def test_large_file_workflow(self, temp_dir):
        """Test workflow with larger files to verify chunked operations"""
        
        # Create archive
        archive_path = temp_dir / "large_file_archive"
        archive = Archive(archive_path)
        archive.create("Large File Archive", "Test archive with larger files")
        
        # Create profile
        profile = Profile(
            id="large_files",
            name="Large Files",
            description="Profile for large files",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        profile.add_field(MetadataField(
            name="title",
            display_name="Title",
            field_type=FieldType.TEXT,
            required=True
        ))
        
        profile.save_to_file(archive.profiles_path / f"{profile.id}.json")
        
        # Create larger test files
        large_files = []
        for i in range(3):
            file_path = temp_dir / f"large_file_{i}.txt"
            
            # Create ~1MB file
            content = f"Large file {i} content\n" * 50000
            file_path.write_text(content)
            large_files.append(file_path)
        
        # Ingest and verify
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        progress_calls = []
        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))
        
        ingestion.set_progress_callback(progress_callback)
        
        assets = []
        for i, file_path in enumerate(large_files):
            metadata = {"title": f"Large File {i+1}"}
            
            asset = ingestion.ingest_file(file_path, profile=profile, custom_metadata=metadata)
            indexing.index_asset(asset)
            assets.append(asset)
        
        # Verify all files processed
        assert len(assets) == len(large_files)
        
        # Verify checksums are calculated correctly
        for asset in assets:
            assert asset.metadata.checksum_sha256 is not None
            assert len(asset.metadata.checksum_sha256) == 64
            
            # Verify checksum by recalculating
            assert asset.verify_checksum() is True
        
        # Test integrity verification
        integrity = IntegrityService(archive)
        report = integrity.verify_all()
        
        assert report.total_assets == len(large_files)
        assert report.verified_assets == len(large_files)
        assert report.success_rate == 100.0
        
        # Test search
        search = SearchService(archive)
        results, total = search.search()
        
        assert total == len(large_files)
        
        # Verify file sizes in results
        for result in results:
            assert result.file_size > 1000000  # Should be ~1MB
    
    def test_error_recovery_workflow(self, temp_dir, sample_files):
        """Test workflow behavior when encountering errors and recovery"""
        
        # Create archive
        archive_path = temp_dir / "error_recovery_archive"
        archive = Archive(archive_path)
        archive.create("Error Recovery Archive", "Test archive for error recovery")
        
        # Create profile
        profile = Profile(
            id="recovery_profile",
            name="Recovery Profile",
            description="Profile for error recovery tests",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        profile.add_field(MetadataField(
            name="title",
            display_name="Title",
            field_type=FieldType.TEXT,
            required=True
        ))
        
        profile.save_to_file(archive.profiles_path / f"{profile.id}.json")
        
        # Step 1: Normal ingestion
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        assets = []
        for i, file_path in enumerate(sample_files[:2]):  # Only first 2 files
            metadata = {"title": f"Recovery File {i+1}"}
            
            asset = ingestion.ingest_file(file_path, profile=profile, custom_metadata=metadata)
            indexing.index_asset(asset)
            assets.append(asset)
        
        # Step 2: Simulate corruption by modifying a file
        first_asset = assets[0]
        corrupted_file_path = archive.root_path / first_asset.metadata.archive_path
        
        # Modify the file content to corrupt it
        original_content = corrupted_file_path.read_text()
        corrupted_file_path.write_text(original_content + "\nCORRUPTED DATA")
        
        # Step 3: Test integrity verification detects corruption  
        integrity = IntegrityService(archive)
        report = integrity.verify_all()
        
        assert report.total_assets == 2
        assert report.verified_assets == 1  # One should fail
        assert len(report.corrupted_assets) == 1
        assert report.success_rate == 50.0
        
        # Step 4: Restore file and verify recovery
        corrupted_file_path.write_text(original_content)
        
        # Re-verify
        recovery_report = integrity.verify_all()
        
        assert recovery_report.total_assets == 2
        assert recovery_report.verified_assets == 2
        assert len(recovery_report.corrupted_assets) == 0
        assert recovery_report.success_rate == 100.0
        
        # Step 5: Test index repair after manual file operations
        # Manually add a file without proper ingestion
        orphan_file = archive.assets_path / "orphan.txt"
        orphan_file.parent.mkdir(parents=True, exist_ok=True)
        orphan_file.write_text("Orphaned file content")
        
        # Find orphaned files
        orphaned = integrity.find_orphaned_files()
        assert len(orphaned) == 1
        assert orphaned[0].name == "orphan.txt"
        
        # Test repair index
        repair_stats = integrity.repair_index()
        
        assert repair_stats['newly_indexed'] == 1  # The orphan file
        assert repair_stats['errors'] == 0
        
        # Verify orphan is now searchable
        search = SearchService(archive)
        results, total = search.search()
        
        assert total == 3  # Original 2 + orphaned file