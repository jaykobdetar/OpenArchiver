"""
Unit tests for file_utils module - Testing file operations and utilities
"""

import pytest
import os
import stat
import tempfile
import platform
from pathlib import Path
from unittest.mock import patch, Mock

from src.utils.file_utils import safe_filename, create_directory_structure, get_file_info


@pytest.mark.unit
class TestSafeFilename:
    """Test safe_filename function for file name sanitization"""
    
    def test_basic_safe_filename(self):
        """Test that valid filenames pass through unchanged"""
        assert safe_filename("document.txt") == "document.txt"
        assert safe_filename("my_file.pdf") == "my_file.pdf"
        assert safe_filename("test-file.json") == "test-file.json"
    
    def test_remove_unsafe_characters(self):
        """Test removal of unsafe filesystem characters"""
        # Windows/POSIX unsafe characters
        assert safe_filename("file<name>") == "file_name_"
        assert safe_filename('file:name"') == "file_name_"
        assert safe_filename("file/name\\") == "file_name_"
        assert safe_filename("file|name?") == "file_name_"
        assert safe_filename("file*name") == "file_name"
        
        # Control characters (0x00-0x1f)
        assert safe_filename("file\x00name") == "file_name"
        assert safe_filename("file\x1fname") == "file_name"
    
    def test_remove_leading_trailing_dots_spaces(self):
        """Test removal of leading/trailing dots and spaces"""
        assert safe_filename("  filename.txt  ") == "filename.txt"
        assert safe_filename("..filename.txt..") == "filename.txt"
        assert safe_filename(". filename.txt .") == "filename.txt"
    
    def test_empty_filename_replacement(self):
        """Test that empty filenames are replaced with 'unnamed'"""
        assert safe_filename("") == "unnamed"
        assert safe_filename("   ") == "unnamed"
        assert safe_filename("...") == "unnamed"
        assert safe_filename("///") == "unnamed"
    
    def test_filename_length_truncation(self):
        """Test filename truncation to max_length"""
        long_name = "a" * 300  # Longer than default 255
        result = safe_filename(long_name)
        assert len(result) == 255
        assert result == "a" * 255
    
    def test_filename_truncation_preserves_extension(self):
        """Test that truncation preserves file extension when possible"""
        long_name = "a" * 300 + ".txt"
        result = safe_filename(long_name, max_length=20)
        assert len(result) == 20
        assert result.endswith(".txt")
        assert result == "a" * 16 + ".txt"  # 16 + 4 = 20
    
    def test_custom_max_length(self):
        """Test custom max_length parameter"""
        result = safe_filename("very_long_filename.txt", max_length=10)
        assert len(result) == 10
        assert result.endswith(".txt")
    
    def test_extension_longer_than_max_length(self):
        """Test behavior when extension is longer than max_length"""
        # Edge case: extension longer than allowed length
        result = safe_filename("test.verylongextension", max_length=10)
        assert len(result) <= 10
    
    def test_unicode_characters(self):
        """Test handling of unicode characters"""
        assert safe_filename("文件名.txt") == "文件名.txt"
        assert safe_filename("файл.pdf") == "файл.pdf"
        assert safe_filename("🎉emoji.doc") == "🎉emoji.doc"
    
    def test_reserved_windows_names(self):
        """Test handling of Windows reserved names"""
        # These should pass through as-is in this implementation
        # (more advanced implementations might handle CON, PRN, etc.)
        assert safe_filename("CON.txt") == "CON.txt"
        assert safe_filename("PRN.doc") == "PRN.doc"
        assert safe_filename("AUX.pdf") == "AUX.pdf"
    
    def test_multiple_unsafe_characters(self):
        """Test filename with multiple unsafe characters"""
        unsafe = 'file<name>:with|many*unsafe?chars"'
        result = safe_filename(unsafe)
        expected = "file_name__with_many_unsafe_chars_"
        assert result == expected
    
    def test_edge_case_only_extension(self):
        """Test filename that is only an extension"""
        assert safe_filename(".txt") == ".txt"
        assert safe_filename(".hidden") == ".hidden"


@pytest.mark.unit
class TestCreateDirectoryStructure:
    """Test create_directory_structure function"""
    
    def test_create_single_directory(self, tmp_path):
        """Test creating a single directory"""
        result = create_directory_structure(tmp_path, "test_dir")
        
        expected_path = tmp_path / "test_dir"
        assert result == expected_path
        assert result.exists()
        assert result.is_dir()
    
    def test_create_nested_directories(self, tmp_path):
        """Test creating nested directory structure"""
        result = create_directory_structure(tmp_path, "level1/level2/level3")
        
        expected_path = tmp_path / "level1" / "level2" / "level3"
        assert result == expected_path
        assert result.exists()
        assert result.is_dir()
        
        # Verify all parent directories were created
        assert (tmp_path / "level1").exists()
        assert (tmp_path / "level1" / "level2").exists()
    
    def test_create_existing_directory(self, tmp_path):
        """Test creating directory that already exists"""
        # Create directory first
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        
        # Should not raise error when creating existing directory
        result = create_directory_structure(tmp_path, "existing")
        assert result == existing_dir
        assert result.exists()
    
    def test_create_with_empty_structure(self, tmp_path):
        """Test with empty structure string"""
        result = create_directory_structure(tmp_path, "")
        assert result == tmp_path
    
    def test_create_with_trailing_slash(self, tmp_path):
        """Test structure string with trailing slash"""
        result = create_directory_structure(tmp_path, "test_dir/")
        expected_path = tmp_path / "test_dir" / ""  # Path handles this correctly
        assert result.parent == tmp_path / "test_dir"
        assert (tmp_path / "test_dir").exists()
    
    def test_create_deep_nesting(self, tmp_path):
        """Test creating very deep directory structure"""
        deep_structure = "/".join([f"level{i}" for i in range(10)])
        result = create_directory_structure(tmp_path, deep_structure)
        
        assert result.exists()
        assert result.is_dir()
        # Verify path depth
        relative_path = result.relative_to(tmp_path)
        assert len(relative_path.parts) == 10
    
    def test_create_with_special_characters(self, tmp_path):
        """Test directory names with special characters"""
        if platform.system() != "Windows":  # Skip on Windows due to path restrictions
            result = create_directory_structure(tmp_path, "dir with spaces/special-chars_123")
            assert result.exists()
            assert result.is_dir()
    
    def test_create_permissions_error(self, tmp_path):
        """Test handling of permission errors"""
        if platform.system() != "Windows":  # Skip on Windows
            # Create a directory and remove write permissions
            protected_dir = tmp_path / "protected"
            protected_dir.mkdir()
            protected_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # Read and execute only
            
            try:
                # This should raise a PermissionError
                with pytest.raises(PermissionError):
                    create_directory_structure(protected_dir, "new_dir")
            finally:
                # Restore permissions for cleanup
                protected_dir.chmod(stat.S_IRWXU)


@pytest.mark.unit
class TestGetFileInfo:
    """Test get_file_info function for file metadata extraction"""
    
    def test_get_info_text_file(self, tmp_path):
        """Test getting info for a text file"""
        test_file = tmp_path / "test.txt"
        content = "This is a test file"
        test_file.write_text(content)
        
        info = get_file_info(test_file)
        
        assert info["name"] == "test.txt"
        assert info["size"] == len(content.encode('utf-8'))
        assert info["mime_type"] == "text/plain"
        assert info["extension"] == ".txt"
        assert "created" in info
        assert "modified" in info
        assert isinstance(info["created"], float)
        assert isinstance(info["modified"], float)
    
    def test_get_info_binary_file(self, tmp_path):
        """Test getting info for a binary file"""
        test_file = tmp_path / "test.jpg"
        # Create a small "fake" JPEG file
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        test_file.write_bytes(jpeg_header)
        
        info = get_file_info(test_file)
        
        assert info["name"] == "test.jpg"
        assert info["size"] == len(jpeg_header)
        assert info["mime_type"] == "image/jpeg"
        assert info["extension"] == ".jpg"
    
    def test_get_info_file_without_extension(self, tmp_path):
        """Test getting info for file without extension"""
        test_file = tmp_path / "README"
        test_file.write_text("This is a readme file")
        
        info = get_file_info(test_file)
        
        assert info["name"] == "README"
        assert info["extension"] == ""
        assert info["mime_type"] is None  # Unknown without extension
    
    def test_get_info_unknown_extension(self, tmp_path):
        """Test getting info for file with unknown extension"""
        test_file = tmp_path / "test.unknownext"
        test_file.write_text("Unknown file type")
        
        info = get_file_info(test_file)
        
        assert info["name"] == "test.unknownext"
        assert info["extension"] == ".unknownext"
        assert info["mime_type"] is None  # Unknown extension
    
    def test_get_info_empty_file(self, tmp_path):
        """Test getting info for empty file"""
        test_file = tmp_path / "empty.txt"
        test_file.touch()
        
        info = get_file_info(test_file)
        
        assert info["name"] == "empty.txt"
        assert info["size"] == 0
        assert info["mime_type"] == "text/plain"
        assert info["extension"] == ".txt"
    
    def test_get_info_large_file(self, tmp_path):
        """Test getting info for large file"""
        test_file = tmp_path / "large.txt"
        # Create a 1MB file
        large_content = "A" * (1024 * 1024)
        test_file.write_text(large_content)
        
        info = get_file_info(test_file)
        
        assert info["name"] == "large.txt"
        assert info["size"] == len(large_content.encode('utf-8'))
        assert info["mime_type"] == "text/plain"
    
    def test_get_info_file_with_encoding(self, tmp_path):
        """Test getting info for file that has encoding information"""
        test_file = tmp_path / "test.txt.gz"
        test_file.write_bytes(b"fake gzip content")
        
        info = get_file_info(test_file)
        
        assert info["name"] == "test.txt.gz"
        # Different systems may return different MIME types for .gz files
        assert info["mime_type"] in ["application/gzip", "text/plain", "application/x-gzip"]
        # Encoding can vary by system - gzip files might return 'gzip' or None
        assert info["encoding"] in [None, 'gzip']
        assert info["extension"] == ".gz"
    
    def test_get_info_file_stat_error(self, tmp_path):
        """Test handling of file stat errors"""
        nonexistent_file = tmp_path / "nonexistent.txt"
        
        with pytest.raises(FileNotFoundError):
            get_file_info(nonexistent_file)
    
    def test_get_info_various_mime_types(self, tmp_path):
        """Test MIME type detection for various file types"""
        test_cases = [
            ("document.pdf", "application/pdf"),
            ("image.png", "image/png"),
            ("video.mp4", "video/mp4"),
            ("audio.mp3", "audio/mpeg"),
            ("archive.zip", "application/zip"),
            ("webpage.html", "text/html"),
            ("stylesheet.css", "text/css"),
            ("script.js", ["application/javascript", "text/javascript"]),
            ("data.xml", "application/xml"),
            ("config.json", "application/json")
        ]
        
        for filename, expected_mime in test_cases:
            test_file = tmp_path / filename
            test_file.write_text("test content")
            
            info = get_file_info(test_file)
            # Handle both single MIME types and lists of acceptable MIME types
            if isinstance(expected_mime, list):
                assert info["mime_type"] in expected_mime, f"Failed for {filename}: got {info['mime_type']}, expected one of {expected_mime}"
            else:
                assert info["mime_type"] == expected_mime, f"Failed for {filename}"
            assert info["name"] == filename
    
    def test_get_info_file_times_precision(self, tmp_path):
        """Test that file times are returned with proper precision"""
        test_file = tmp_path / "time_test.txt"
        test_file.write_text("time test")
        
        info = get_file_info(test_file)
        
        # Times should be positive floats (Unix timestamps)
        assert info["created"] > 0
        assert info["modified"] > 0
        assert isinstance(info["created"], float)
        assert isinstance(info["modified"], float)
    
    def test_get_info_unicode_filename(self, tmp_path):
        """Test getting info for file with unicode characters in name"""
        test_file = tmp_path / "测试文件.txt"
        test_file.write_text("Unicode test content")
        
        info = get_file_info(test_file)
        
        assert info["name"] == "测试文件.txt"
        assert info["mime_type"] == "text/plain"
        assert info["extension"] == ".txt"
        assert info["size"] > 0
    
    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_get_info_symlink(self, tmp_path):
        """Test getting info for symbolic links (Unix only)"""
        # Create target file
        target_file = tmp_path / "target.txt"
        target_file.write_text("Target file content")
        
        # Create symlink
        symlink_file = tmp_path / "link.txt" 
        symlink_file.symlink_to(target_file)
        
        info = get_file_info(symlink_file)
        
        # Should get info about the target file, not the symlink
        assert info["name"] == "link.txt"
        assert info["size"] == len("Target file content".encode('utf-8'))
        assert info["mime_type"] == "text/plain"
    
    def test_get_info_cross_platform_compatibility(self, tmp_path):
        """Test cross-platform compatibility of file info"""
        test_file = tmp_path / "cross_platform.txt"
        test_file.write_text("Cross platform test")
        
        info = get_file_info(test_file)
        
        # Basic checks that should work on all platforms
        assert isinstance(info["name"], str)
        assert isinstance(info["size"], int)
        assert isinstance(info["created"], float)
        assert isinstance(info["modified"], float)
        assert isinstance(info["extension"], str)
        # mime_type and encoding can be None
        assert info["mime_type"] is None or isinstance(info["mime_type"], str)
        assert info["encoding"] is None or isinstance(info["encoding"], str)


@pytest.mark.unit 
class TestFileUtilsEdgeCases:
    """Test edge cases and error conditions for file_utils"""
    
    def test_safe_filename_with_none_input(self):
        """Test safe_filename with None input"""
        with pytest.raises(AttributeError):
            safe_filename(None)
    
    def test_safe_filename_with_numeric_input(self):
        """Test safe_filename with numeric input"""
        assert safe_filename(str(12345)) == "12345"
    
    def test_create_directory_structure_with_none_base(self):
        """Test create_directory_structure with None base_path"""
        with pytest.raises(AttributeError):
            create_directory_structure(None, "test")
    
    def test_create_directory_structure_with_none_structure(self):
        """Test create_directory_structure with None structure"""
        with pytest.raises(AttributeError):
            create_directory_structure(Path("/tmp"), None)
    
    def test_get_file_info_with_string_path(self, tmp_path):
        """Test get_file_info accepts string path"""
        test_file = tmp_path / "string_path.txt"
        test_file.write_text("String path test")
        
        # Should work with string path
        info = get_file_info(str(test_file))
        assert info["name"] == "string_path.txt"
    
    def test_safe_filename_max_length_zero(self):
        """Test safe_filename with max_length of zero"""
        result = safe_filename("test.txt", max_length=0)
        assert len(result) == 0
    
    def test_safe_filename_max_length_negative(self):
        """Test safe_filename with negative max_length"""
        result = safe_filename("test.txt", max_length=-1)
        # Should handle gracefully (implementation dependent)
        assert isinstance(result, str)
    
    @patch('mimetypes.guess_type')
    def test_get_file_info_mimetypes_error(self, mock_guess_type, tmp_path):
        """Test get_file_info when mimetypes.guess_type raises error"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        # Mock mimetypes to raise an exception
        mock_guess_type.side_effect = Exception("MIME type error")
        
        with pytest.raises(Exception, match="MIME type error"):
            get_file_info(test_file)
    
    @patch('pathlib.Path.stat')
    def test_get_file_info_stat_permission_error(self, mock_stat, tmp_path):
        """Test get_file_info when stat() raises PermissionError"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        mock_stat.side_effect = PermissionError("Permission denied")
        
        with pytest.raises(PermissionError):
            get_file_info(test_file)
    
    def test_create_directory_structure_with_absolute_path_components(self, tmp_path):
        """Test create_directory_structure handles path components correctly"""
        # This tests the split('/') behavior
        result = create_directory_structure(tmp_path, "dir1//dir2///dir3")
        
        # Should handle multiple slashes gracefully
        assert result.exists()
        assert result.is_dir()


@pytest.mark.unit
class TestFileUtilsPerformance:
    """Test performance characteristics of file_utils functions"""
    
    def test_safe_filename_performance_long_strings(self):
        """Test performance with very long filename strings"""
        # Create a very long filename
        long_filename = "a" * 10000 + ".txt"
        
        # Should complete quickly
        import time
        start_time = time.time()
        result = safe_filename(long_filename)
        end_time = time.time()
        
        assert end_time - start_time < 1.0  # Should take less than 1 second
        assert len(result) <= 255  # Should be truncated
    
    def test_get_file_info_performance_large_files(self, tmp_path):
        """Test get_file_info performance with large files"""
        # Create a moderately large file (10MB would be too slow for tests)
        test_file = tmp_path / "large.bin"
        with open(test_file, 'wb') as f:
            f.write(b"x" * (1024 * 100))  # 100KB
        
        import time
        start_time = time.time()
        info = get_file_info(test_file)
        end_time = time.time()
        
        assert end_time - start_time < 1.0  # Should be fast
        assert info["size"] == 1024 * 100