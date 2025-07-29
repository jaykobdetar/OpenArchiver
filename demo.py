#!/usr/bin/env python3
"""
Archive Tool Demo Script

This script demonstrates the core functionality of the Archive Tool by:
1. Creating a demo archive
2. Setting up sample profiles
3. Adding sample files
4. Performing searches
5. Running integrity verification
6. Exporting to BagIt format

Run with: python demo.py
"""

import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.models import Archive, Profile, MetadataField, FieldType, Asset, AssetMetadata
from src.core import FileIngestionService, IndexingService, SearchService, IntegrityService, ExportService


def create_sample_files(temp_dir: Path) -> list[Path]:
    """Create some sample files for demonstration"""
    sample_files = []
    
    # Create sample text files
    for i in range(5):
        file_path = temp_dir / f"document_{i+1}.txt"
        with open(file_path, 'w') as f:
            f.write(f"This is sample document number {i+1}\n")
            f.write(f"Created on {datetime.now()}\n")
            f.write(f"Contains some demo content for archiving.\n")
        sample_files.append(file_path)
    
    # Create a sample "image" (actually just text)
    image_path = temp_dir / "photo.jpg"
    with open(image_path, 'w') as f:
        f.write("This would be image data in a real scenario")
    sample_files.append(image_path)
    
    return sample_files


def create_sample_profile(archive: Archive) -> Profile:
    """Create a sample metadata profile"""
    profile = Profile(
        id="demo_docs",
        name="Demo Documents",
        description="Sample profile for demonstration",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    
    # Add some fields
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
        options=["Document", "Image", "Report", "Other"]
    ))
    
    profile.add_field(MetadataField(
        name="tags",
        display_name="Tags",
        field_type=FieldType.TAGS
    ))
    
    # Save profile
    profile_path = archive.profiles_path / f"{profile.id}.json"
    profile.save_to_file(profile_path)
    
    return profile


def main():
    print("🗂️  Archive Tool Demo")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 1. Create demo archive
        print("\n1. Creating demo archive...")
        archive_path = temp_path / "demo_archive"
        archive = Archive(archive_path)
        archive.create("Demo Archive", "Demonstration of Archive Tool features")
        print(f"   ✓ Archive created at: {archive_path}")
        
        # 2. Create sample profile
        print("\n2. Setting up metadata profile...")
        profile = create_sample_profile(archive)
        print(f"   ✓ Profile '{profile.name}' created with {len(profile.fields)} fields")
        
        # 3. Create sample files
        print("\n3. Creating sample files...")
        sample_dir = temp_path / "sample_files"
        sample_dir.mkdir()
        sample_files = create_sample_files(sample_dir)
        print(f"   ✓ Created {len(sample_files)} sample files")
        
        # 4. Ingest files into archive
        print("\n4. Ingesting files into archive...")
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        assets = []
        for i, file_path in enumerate(sample_files):
            # Add custom metadata
            custom_metadata = {
                "title": f"Sample File {i+1}",
                "category": "Image" if file_path.suffix == ".jpg" else "Document",
                "tags": ["demo", "sample", f"file_{i+1}"]
            }
            
            asset = ingestion.ingest_file(file_path, profile=profile, custom_metadata=custom_metadata)
            indexing.index_asset(asset)
            assets.append(asset)
            print(f"   ✓ Ingested: {file_path.name}")
        
        # 5. Display archive statistics
        print("\n5. Archive Statistics:")
        stats = indexing.get_statistics()
        print(f"   Total assets: {stats['total_assets']}")
        print(f"   Total size: {stats['total_size']:,} bytes")
        print(f"   File types: {len(stats['by_type'])}")
        
        # 6. Demonstrate search functionality
        print("\n6. Search Functionality:")
        search = SearchService(archive)
        
        # Search by query
        results, total = search.search(query="sample", limit=10)
        print(f"   Search for 'sample': {total} results")
        
        # Search by metadata field
        results, total = search.search(filters={"category": "Document"}, limit=10)
        print(f"   Documents only: {total} results")
        
        # Search by tags
        results, total = search.search(filters={"tags": "demo"}, limit=10)
        print(f"   Tagged with 'demo': {total} results")
        
        # 7. Verify integrity
        print("\n7. Integrity Verification:")
        integrity = IntegrityService(archive)
        report = integrity.verify_all(max_workers=2)
        print(f"   Verified {report.verified_assets}/{report.total_assets} assets")
        print(f"   Success rate: {report.success_rate:.1f}%")
        print(f"   Duration: {report.duration:.2f} seconds")
        
        # 8. Export to BagIt
        print("\n8. BagIt Export:")
        export_service = ExportService(archive)
        bagit_path = temp_path / "demo_export.bag"
        
        metadata = {
            'Source-Organization': 'Archive Tool Demo',
            'Contact-Name': 'Demo User',
            'External-Description': 'Demonstration export from Archive Tool'
        }
        
        result_path = export_service.export_to_bagit(bagit_path, metadata=metadata)
        print(f"   ✓ BagIt export created: {result_path}")
        
        # Verify the bag
        import bagit
        bag = bagit.Bag(str(result_path))
        try:
            bag.validate()
            print("   ✓ BagIt validation successful")
        except bagit.BagValidationError as e:
            print(f"   ✗ BagIt validation failed: {e}")
        
        # 9. Generate manifest
        print("\n9. Manifest Generation:")
        manifest_path = temp_path / "archive_manifest.json"
        export_service.generate_manifest(manifest_path, format="json")
        print(f"   ✓ Manifest generated: {manifest_path}")
        
        # 10. Summary
        print("\n" + "=" * 50)
        print("🎉 Demo completed successfully!")
        print(f"\nDemo files created in: {temp_path}")
        print("\nKey features demonstrated:")
        print("  ✓ Archive creation and configuration")
        print("  ✓ Metadata profile definition")
        print("  ✓ File ingestion with custom metadata")
        print("  ✓ SQLite indexing for fast search")
        print("  ✓ Multiple search methods (text, filters)")
        print("  ✓ Integrity verification with checksums")
        print("  ✓ BagIt-compliant export")
        print("  ✓ Manifest generation")
        
        print(f"\nArchive structure:")
        print(f"  {archive_path}/")
        print(f"  ├── archive.json")
        print(f"  ├── profiles/")
        print(f"  │   └── demo_docs.json")
        print(f"  ├── assets/")
        print(f"  │   └── [organized files with metadata]")
        print(f"  └── .index/")
        print(f"      └── index.db")
        
        input("\nPress Enter to continue (files will be cleaned up)...")


if __name__ == "__main__":
    main()