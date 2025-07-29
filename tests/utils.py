"""
Test utilities and helper functions for Archive Tool tests
"""

import json
import random
import string
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.models import Profile, MetadataField, FieldType, Asset, AssetMetadata


class MockDataGenerator:
    """Generate mock data for testing"""
    
    @staticmethod
    def generate_random_string(length: int = 10) -> str:
        """Generate random string of specified length"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def generate_random_content(lines: int = 10) -> str:
        """Generate random text content"""
        content_lines = []
        for i in range(lines):
            line_length = random.randint(20, 80)
            line = MockDataGenerator.generate_random_string(line_length)
            content_lines.append(line)
        return '\n'.join(content_lines)
    
    @staticmethod
    def create_test_files(directory: Path, count: int = 10, file_types: List[str] = None) -> List[Path]:
        """Create multiple test files with different types"""
        if file_types is None:
            file_types = ['.txt', '.json', '.csv', '.md']
        
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        
        for i in range(count):
            file_type = random.choice(file_types)
            filename = f"test_file_{i:03d}{file_type}"
            file_path = directory / filename
            
            if file_type == '.txt':
                content = MockDataGenerator.generate_random_content(random.randint(5, 20))
            elif file_type == '.json':
                content = json.dumps({
                    "id": i,
                    "name": f"Test Item {i}",
                    "data": MockDataGenerator.generate_random_string(50),
                    "items": [random.randint(1, 100) for _ in range(5)]
                }, indent=2)
            elif file_type == '.csv':
                headers = ["id", "name", "value", "category"]
                rows = [",".join(headers)]
                for j in range(random.randint(10, 50)):
                    row = [
                        str(j),
                        f"Item_{j}",
                        str(random.randint(1, 1000)),
                        random.choice(["A", "B", "C"])
                    ]
                    rows.append(",".join(row))
                content = '\n'.join(rows)
            elif file_type == '.md':
                content = f"""# Test Document {i}

This is a test markdown document generated for testing purposes.

## Section 1

{MockDataGenerator.generate_random_content(3)}

## Section 2

{MockDataGenerator.generate_random_content(5)}

### Subsection

- Item 1
- Item 2
- Item 3
"""
            else:
                content = MockDataGenerator.generate_random_content()
            
            file_path.write_text(content)
            files.append(file_path)
        
        return files
    
    @staticmethod
    def create_binary_files(directory: Path, count: int = 5) -> List[Path]:
        """Create binary test files"""
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        
        for i in range(count):
            filename = f"binary_file_{i:03d}.bin"
            file_path = directory / filename
            
            # Generate random binary content
            size = random.randint(1024, 10240)  # 1KB to 10KB
            content = bytes([random.randint(0, 255) for _ in range(size)])
            
            file_path.write_bytes(content)
            files.append(file_path)
        
        return files
    
    @staticmethod
    def create_nested_directory_structure(base_dir: Path, depth: int = 3, files_per_dir: int = 5) -> List[Path]:
        """Create nested directory structure with files"""
        all_files = []
        
        def create_level(current_dir: Path, current_depth: int):
            if current_depth == 0:
                return
            
            current_dir.mkdir(parents=True, exist_ok=True)
            
            # Create files in current directory
            files = MockDataGenerator.create_test_files(current_dir, files_per_dir)
            all_files.extend(files)
            
            # Create subdirectories
            for i in range(random.randint(1, 3)):
                subdir = current_dir / f"subdir_{current_depth}_{i}"
                create_level(subdir, current_depth - 1)
        
        create_level(base_dir, depth)
        return all_files
    
    @staticmethod
    def generate_metadata_profile(profile_id: str = None, complex: bool = False) -> Profile:
        """Generate a test metadata profile"""
        if profile_id is None:
            profile_id = f"test_profile_{MockDataGenerator.generate_random_string(8)}"
        
        profile = Profile(
            id=profile_id,
            name=f"Test Profile {profile_id}",
            description=f"Generated test profile for {profile_id}",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        # Basic fields
        profile.add_field(MetadataField(
            name="title",
            display_name="Title",
            field_type=FieldType.TEXT,
            required=True,
            description="Title of the item"
        ))
        
        profile.add_field(MetadataField(
            name="description",
            display_name="Description",
            field_type=FieldType.TEXTAREA,
            description="Detailed description"
        ))
        
        profile.add_field(MetadataField(
            name="category",
            display_name="Category",
            field_type=FieldType.SELECT,
            options=["Type1", "Type2", "Type3", "Other"],
            description="Item category"
        ))
        
        profile.add_field(MetadataField(
            name="tags",
            display_name="Tags",
            field_type=FieldType.TAGS,
            description="Keywords and tags"
        ))
        
        if complex:
            # Add more complex fields
            profile.add_field(MetadataField(
                name="priority",
                display_name="Priority",
                field_type=FieldType.SELECT,
                options=["Low", "Medium", "High", "Critical"],
                default_value="Medium"
            ))
            
            profile.add_field(MetadataField(
                name="date_created",
                display_name="Date Created",
                field_type=FieldType.DATE,
                description="Creation date"
            ))
            
            profile.add_field(MetadataField(
                name="is_public",
                display_name="Public",
                field_type=FieldType.BOOLEAN,
                default_value=False,
                description="Whether item is public"
            ))
            
            profile.add_field(MetadataField(
                name="rating",
                display_name="Rating",
                field_type=FieldType.NUMBER,
                description="Rating from 1-10"
            ))
        
        return profile
    
    @staticmethod
    def generate_asset_metadata(asset_id: str = None, profile: Profile = None) -> Dict[str, Any]:
        """Generate sample asset metadata"""
        if asset_id is None:
            asset_id = f"asset_{MockDataGenerator.generate_random_string(12)}"
        
        base_metadata = {
            "title": f"Test Asset {MockDataGenerator.generate_random_string(8)}",
            "description": MockDataGenerator.generate_random_content(3),
            "category": random.choice(["Type1", "Type2", "Type3", "Other"]),
            "tags": [
                MockDataGenerator.generate_random_string(6),
                MockDataGenerator.generate_random_string(8),
                "test"
            ]
        }
        
        if profile:
            # Generate metadata based on profile fields
            metadata = {}
            for field in profile.fields:
                if field.field_type == FieldType.TEXT:
                    metadata[field.name] = f"Test {field.display_name} {MockDataGenerator.generate_random_string(8)}"
                elif field.field_type == FieldType.TEXTAREA:
                    metadata[field.name] = MockDataGenerator.generate_random_content(random.randint(2, 5))
                elif field.field_type == FieldType.SELECT:
                    if field.options:
                        metadata[field.name] = random.choice(field.options)
                elif field.field_type == FieldType.TAGS:
                    metadata[field.name] = [
                        MockDataGenerator.generate_random_string(6),
                        MockDataGenerator.generate_random_string(8),
                        "test"
                    ]
                elif field.field_type == FieldType.BOOLEAN:
                    metadata[field.name] = random.choice([True, False])
                elif field.field_type == FieldType.NUMBER:
                    metadata[field.name] = random.randint(1, 100)
                elif field.field_type == FieldType.DATE:
                    # Random date within last year
                    base_date = datetime.now()
                    random_days = random.randint(0, 365)
                    random_date = base_date - timedelta(days=random_days)
                    metadata[field.name] = random_date.strftime("%Y-%m-%d")
                elif field.field_type == FieldType.DATETIME:
                    # Random datetime within last year
                    base_date = datetime.now()
                    random_seconds = random.randint(0, 365 * 24 * 60 * 60)
                    random_datetime = base_date - timedelta(seconds=random_seconds)
                    metadata[field.name] = random_datetime.isoformat()
                else:
                    metadata[field.name] = field.default_value
            
            return metadata
        
        return base_metadata


class TestAssertions:
    """Custom assertions for testing"""
    
    @staticmethod
    def assert_archive_structure(archive_path: Path):
        """Assert that archive has correct directory structure"""
        assert archive_path.exists(), f"Archive path does not exist: {archive_path}"
        assert (archive_path / "archive.json").exists(), "archive.json missing"
        assert (archive_path / "profiles").exists(), "profiles directory missing"
        assert (archive_path / "assets").exists(), "assets directory missing"
        assert (archive_path / ".index").exists(), ".index directory missing"
    
    @staticmethod
    def assert_asset_integrity(asset: Asset):
        """Assert that asset has proper integrity"""
        assert asset.file_path.exists(), f"Asset file does not exist: {asset.file_path}"
        assert asset.metadata is not None, "Asset metadata is None"
        assert asset.metadata.asset_id is not None, "Asset ID is None"
        assert asset.metadata.checksum_sha256 is not None, "Checksum is None"
        assert len(asset.metadata.checksum_sha256) == 64, "Invalid checksum length"
        
        # Verify sidecar file exists
        assert asset.sidecar_path.exists(), f"Sidecar file missing: {asset.sidecar_path}"
        
        # Verify checksum is correct
        assert asset.verify_checksum(), "Checksum verification failed"
    
    @staticmethod
    def assert_search_result_valid(result, expected_fields: List[str] = None):
        """Assert that search result is valid"""
        assert hasattr(result, 'asset_id'), "Search result missing asset_id"
        assert hasattr(result, 'archive_path'), "Search result missing archive_path"
        assert hasattr(result, 'file_name'), "Search result missing file_name"
        assert hasattr(result, 'custom_metadata'), "Search result missing custom_metadata"
        
        assert result.asset_id is not None, "Asset ID is None"
        assert result.archive_path is not None, "Archive path is None"
        assert result.file_name is not None, "File name is None"
        assert isinstance(result.custom_metadata, dict), "Custom metadata is not a dict"
        
        if expected_fields:
            for field in expected_fields:
                assert field in result.custom_metadata, f"Expected field {field} not in metadata"
    
    @staticmethod
    def assert_profile_valid(profile: Profile):
        """Assert that profile is valid"""
        assert profile.id is not None, "Profile ID is None"
        assert profile.name is not None, "Profile name is None"
        assert isinstance(profile.fields, list), "Profile fields is not a list"
        
        # Check field uniqueness
        field_names = [field.name for field in profile.fields]
        assert len(field_names) == len(set(field_names)), "Duplicate field names in profile"
        
        # Validate each field
        for field in profile.fields:
            assert field.name is not None, "Field name is None"
            assert field.display_name is not None, "Field display name is None"
            assert isinstance(field.field_type, FieldType), "Invalid field type"


class PerformanceTimer:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = self.duration
        print(f"{self.operation_name}: {duration:.4f} seconds")
    
    @property
    def duration(self) -> float:
        """Get duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class MemoryMonitor:
    """Monitor memory usage during operations"""
    
    def __init__(self):
        self.measurements = []
        self.baseline = None
    
    def start(self):
        """Start monitoring"""
        try:
            import psutil
            process = psutil.Process()
            self.baseline = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            self.baseline = 0
    
    def measure(self, label: str = ""):
        """Take a memory measurement"""
        try:
            import psutil
            process = psutil.Process() 
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            increase = current_memory - self.baseline if self.baseline else 0
            
            self.measurements.append({
                'label': label,
                'total_memory': current_memory,
                'increase': increase
            })
            
            return current_memory, increase
        except ImportError:
            return 0, 0
    
    def report(self):
        """Print memory usage report"""
        if not self.measurements:
            print("No memory measurements taken")
            return
        
        print(f"\nMemory Usage Report:")
        print(f"Baseline: {self.baseline:.1f} MB")
        
        for measurement in self.measurements:
            label = measurement['label'] or "Unnamed"
            total = measurement['total_memory']
            increase = measurement['increase']
            print(f"  {label}: {total:.1f} MB (+{increase:.1f} MB)")
        
        max_increase = max(m['increase'] for m in self.measurements)
        print(f"Maximum increase: {max_increase:.1f} MB")