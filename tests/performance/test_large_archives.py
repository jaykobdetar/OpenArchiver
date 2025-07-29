"""
Performance tests for Archive Tool with large archives
"""

import pytest
import time
import psutil
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from src.models import Archive, Profile, MetadataField, FieldType
from src.core import (
    FileIngestionService, IndexingService, SearchService,
    IntegrityService, ExportService
)


@pytest.mark.performance
@pytest.mark.slow
class TestLargeArchivePerformance:
    """Test performance with large numbers of files"""
    
    def test_ingest_1000_files_performance(self, performance_archive, tmp_path):
        """Test ingesting 1000 files and measure performance"""
        
        archive, profile = performance_archive
        
        # Create 1000 test files
        files_dir = tmp_path / "perf_files"
        files_dir.mkdir()
        
        test_files = []
        
        print(f"\nCreating 1000 test files...")
        start_create = time.time()
        
        for i in range(1000):
            file_path = files_dir / f"perf_file_{i:04d}.txt"
            content = f"Performance test file {i}\n" + "Content line\n" * 10
            file_path.write_text(content)
            test_files.append(file_path)
        
        create_time = time.time() - start_create
        print(f"Created 1000 files in {create_time:.2f} seconds")
        
        # Measure ingestion performance
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        ingestion_times = []
        indexing_times = []
        
        print(f"Ingesting and indexing 1000 files...")
        overall_start = time.time()
        
        for i, file_path in enumerate(test_files):
            if i % 100 == 0:
                print(f"  Progress: {i}/1000 files")
            
            metadata = {
                "title": f"Performance File {i+1}",
                "category": f"Type{i % 3 + 1}",  # Rotate between 3 types
            }
            
            # Measure ingestion time
            ingest_start = time.time()
            asset = ingestion.ingest_file(file_path, profile=profile, custom_metadata=metadata)
            ingest_time = time.time() - ingest_start
            ingestion_times.append(ingest_time)
            
            # Measure indexing time
            index_start = time.time()
            indexing.index_asset(asset)
            index_time = time.time() - index_start
            indexing_times.append(index_time)
        
        overall_time = time.time() - overall_start
        
        # Performance assertions and reporting
        avg_ingestion_time = sum(ingestion_times) / len(ingestion_times)
        avg_indexing_time = sum(indexing_times) / len(indexing_times)
        
        print(f"\nPerformance Results for 1000 files:")
        print(f"  Total time: {overall_time:.2f} seconds")
        print(f"  Files per second: {1000 / overall_time:.2f}")
        print(f"  Average ingestion time: {avg_ingestion_time:.4f} seconds")
        print(f"  Average indexing time: {avg_indexing_time:.4f} seconds")
        
        # Performance thresholds (adjust based on requirements)
        assert overall_time < 300  # Should complete within 5 minutes
        assert avg_ingestion_time < 0.5  # Each ingestion < 0.5 seconds
        assert avg_indexing_time < 0.1   # Each indexing < 0.1 seconds
        
        # Verify all files were processed
        stats = indexing.get_statistics()
        assert stats['total_assets'] == 1000
    
    def test_search_performance_large_archive(self, performance_archive, benchmark):
        """Test search performance with large number of indexed assets"""
        
        archive, profile = performance_archive
        
        # Pre-populate archive with test data
        if not hasattr(self, '_populated_large_archive'):
            self._populate_large_archive(archive, profile, 500)  # 500 files for search test
            self._populated_large_archive = True
        
        search = SearchService(archive)
        
        # Benchmark different search operations
        def search_all():
            results, total = search.search(limit=100)
            return results, total
        
        def search_by_text():
            results, total = search.search(query="Performance", limit=50)
            return results, total
        
        def search_by_filter():
            results, total = search.search(filters={"category": "Type1"}, limit=50)
            return results, total
        
        def search_by_multiple_filters():
            results, total = search.search(
                filters={"category": "Type1", "title": "Performance File 100"},
                limit=10
            )
            return results, total
        
        # Benchmark search operations
        print(f"\nBenchmarking search operations:")
        
        # Search all assets
        results, total = benchmark(search_all)
        print(f"  Search all: found {total} assets")
        assert total > 0
        
        # Text search
        results, total = benchmark(search_by_text)
        print(f"  Text search: found {total} assets")
        assert total > 0
        
        # Filter search
        results, total = benchmark(search_by_filter)
        print(f"  Filter search: found {total} assets")
        assert total > 0
        
        # Multiple filters
        results, total = benchmark(search_by_multiple_filters)
        print(f"  Multiple filters: found {total} assets")
    
    def test_integrity_verification_performance(self, performance_archive):
        """Test performance of integrity verification on large archive"""
        
        archive, profile = performance_archive
        
        # Pre-populate if needed
        if not hasattr(self, '_populated_integrity_archive'):
            self._populate_large_archive(archive, profile, 1000)  # 1000 files for integrity test  
            self._populated_integrity_archive = True
        
        integrity = IntegrityService(archive)
        
        # Measure memory usage before verification
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"\nRunning integrity verification...")
        print(f"Memory before: {memory_before:.1f} MB")
        
        # Test single-threaded verification
        start_time = time.time()
        report_single = integrity.verify_all(max_workers=1)
        single_time = time.time() - start_time
        
        memory_during = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Single-threaded verification:")
        print(f"  Time: {single_time:.2f} seconds")
        print(f"  Files per second: {report_single.total_assets / single_time:.2f}")
        print(f"  Memory during: {memory_during:.1f} MB")
        print(f"  Success rate: {report_single.success_rate:.1f}%")
        
        # Test multi-threaded verification
        start_time = time.time()
        report_multi = integrity.verify_all(max_workers=4)
        multi_time = time.time() - start_time
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Multi-threaded verification (4 workers):")
        print(f"  Time: {multi_time:.2f} seconds")
        print(f"  Files per second: {report_multi.total_assets / multi_time:.2f}")
        print(f"  Memory after: {memory_after:.1f} MB")
        print(f"  Success rate: {report_multi.success_rate:.1f}%")
        
        # Performance assertions
        assert report_single.success_rate == 100.0
        assert report_multi.success_rate == 100.0
        assert multi_time < single_time  # Multi-threading should be faster
        assert memory_during < memory_before + 100  # Memory usage shouldn't spike too much
        
        # Verify both reports have same results
        assert report_single.total_assets == report_multi.total_assets
        assert report_single.verified_assets == report_multi.verified_assets
    
    def test_concurrent_operations_performance(self, performance_archive, tmp_path):
        """Test performance of concurrent operations"""
        
        archive, profile = performance_archive
        
        # Create test files for concurrent ingestion
        files_dir = tmp_path / "concurrent_files"
        files_dir.mkdir()
        
        test_files = []
        for i in range(50):  # Smaller number for concurrent test
            file_path = files_dir / f"concurrent_file_{i:03d}.txt"
            content = f"Concurrent test file {i}\n" + "Line of content\n" * 20
            file_path.write_text(content)
            test_files.append(file_path)
        
        print(f"\nTesting concurrent operations with {len(test_files)} files...")
        
        # Test concurrent ingestion and indexing
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        def ingest_and_index_file(file_info):
            i, file_path = file_info
            metadata = {
                "title": f"Concurrent File {i+1}",
                "category": f"ConcurrentType{i % 2 + 1}",
            }
            
            start_time = time.time()
            asset = ingestion.ingest_file(file_path, profile=profile, custom_metadata=metadata)
            indexing.index_asset(asset)
            process_time = time.time() - start_time
            
            return i, process_time, asset.metadata.asset_id
        
        # Sequential processing
        print("Sequential processing...")
        sequential_start = time.time()
        sequential_results = []
        
        for i, file_path in enumerate(test_files):
            result = ingest_and_index_file((i, file_path))
            sequential_results.append(result)
        
        sequential_time = time.time() - sequential_start
        
        # Clean up for concurrent test
        for asset_id in [r[2] for r in sequential_results]:
            indexing.remove_asset(asset_id)
        
        # Create fresh test files for concurrent test
        test_files_concurrent = []
        for i in range(50):
            file_path = files_dir / f"concurrent_file_v2_{i:03d}.txt"
            content = f"Concurrent test file v2 {i}\n" + "Line of content\n" * 20
            file_path.write_text(content)
            test_files_concurrent.append(file_path)
        
        # Concurrent processing
        print("Concurrent processing...")
        concurrent_start = time.time()
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            concurrent_results = list(executor.map(
                ingest_and_index_file,
                enumerate(test_files_concurrent)
            ))
        
        concurrent_time = time.time() - concurrent_start
        
        print(f"\nConcurrent Operations Performance:")
        print(f"  Sequential time: {sequential_time:.2f} seconds")
        print(f"  Concurrent time: {concurrent_time:.2f} seconds")
        print(f"  Speedup: {sequential_time / concurrent_time:.2f}x")
        print(f"  Sequential rate: {len(test_files) / sequential_time:.2f} files/sec")
        print(f"  Concurrent rate: {len(test_files_concurrent) / concurrent_time:.2f} files/sec")
        
        # Verify all files were processed correctly
        stats = indexing.get_statistics()
        expected_total = len(test_files_concurrent)
        assert stats['total_assets'] >= expected_total
        
        # Performance assertions
        assert concurrent_time < sequential_time  # Concurrent should be faster
        speedup = sequential_time / concurrent_time
        assert speedup > 1.5  # Should see at least 1.5x speedup with 4 workers
    
    def test_memory_usage_large_operations(self, performance_archive):
        """Test memory usage during large operations"""
        
        archive, profile = performance_archive
        
        process = psutil.Process()
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"\nBaseline memory: {baseline_memory:.1f} MB")
        
        # Pre-populate archive
        if not hasattr(self, '_populated_memory_archive'):
            print("Populating archive for memory test...")
            self._populate_large_archive(archive, profile, 300)
            self._populated_memory_archive = True
        
        # Test search memory usage
        search = SearchService(archive)
        
        memory_measurements = []
        
        # Large search operations
        for i in range(10):
            memory_before = process.memory_info().rss / 1024 / 1024
            
            # Perform large search
            results, total = search.search(limit=1000)
            
            memory_after = process.memory_info().rss / 1024 / 1024
            memory_measurements.append(memory_after - memory_before)
        
        avg_memory_increase = sum(memory_measurements) / len(memory_measurements)
        max_memory_increase = max(memory_measurements)
        
        print(f"Search Memory Usage:")
        print(f"  Average memory increase: {avg_memory_increase:.1f} MB")
        print(f"  Maximum memory increase: {max_memory_increase:.1f} MB")
        
        # Memory assertions
        assert avg_memory_increase < 50  # Average increase should be < 50MB
        assert max_memory_increase < 100  # Max increase should be < 100MB
        
        # Test integrity verification memory usage
        integrity = IntegrityService(archive)
        
        memory_before_integrity = process.memory_info().rss / 1024 / 1024
        
        report = integrity.verify_all(max_workers=2)
        
        memory_after_integrity = process.memory_info().rss / 1024 / 1024
        integrity_memory_increase = memory_after_integrity - memory_before_integrity
        
        print(f"Integrity Verification Memory Usage:")
        print(f"  Memory increase: {integrity_memory_increase:.1f} MB")
        print(f"  Files verified: {report.total_assets}")
        print(f"  Memory per file: {integrity_memory_increase / report.total_assets:.3f} MB")
        
        # Memory assertions for integrity verification
        assert integrity_memory_increase < 200  # Should use < 200MB
        assert integrity_memory_increase / report.total_assets < 1  # < 1MB per file
    
    def test_database_performance_scaling(self, performance_archive):
        """Test database performance as archive size grows"""
        
        archive, profile = performance_archive
        
        # Test at different archive sizes
        sizes_to_test = [100, 300, 500]  # Number of assets
        performance_results = {}
        
        indexing = IndexingService(archive)
        search = SearchService(archive)
        
        current_size = indexing.get_statistics()['total_assets']
        
        for target_size in sizes_to_test:
            if current_size < target_size:
                # Add more files to reach target size
                files_to_add = target_size - current_size
                print(f"\nAdding {files_to_add} files to reach {target_size} total assets...")
                
                self._add_files_to_archive(archive, profile, files_to_add, current_size)
                current_size = target_size
            
            print(f"\nTesting performance with {target_size} assets...")
            
            # Test search performance
            search_times = []
            for _ in range(5):  # 5 search tests
                start_time = time.time()
                results, total = search.search(query="Performance", limit=50)
                search_time = time.time() - start_time
                search_times.append(search_time)
            
            avg_search_time = sum(search_times) / len(search_times)
            
            # Test index performance (add one more file)
            temp_file = archive.root_path / f"temp_perf_test_{target_size}.txt"
            temp_file.write_text(f"Temporary file for performance test at size {target_size}")
            
            ingestion = FileIngestionService(archive)
            
            start_time = time.time()
            asset = ingestion.ingest_file(temp_file, profile=profile, custom_metadata={"title": "Temp File"})
            indexing.index_asset(asset)
            index_time = time.time() - start_time
            
            # Clean up temp file
            temp_file.unlink()
            indexing.remove_asset(asset.metadata.asset_id)
            
            performance_results[target_size] = {
                'search_time': avg_search_time,
                'index_time': index_time
            }
            
            print(f"  Average search time: {avg_search_time:.4f} seconds")
            print(f"  Index time: {index_time:.4f} seconds")
        
        # Analyze scaling characteristics
        print(f"\nPerformance Scaling Analysis:")
        for size in sizes_to_test:
            results = performance_results[size]
            print(f"  {size} assets: search={results['search_time']:.4f}s, index={results['index_time']:.4f}s")
        
        # Performance should not degrade significantly
        if len(sizes_to_test) >= 2:
            small_search = performance_results[sizes_to_test[0]]['search_time']
            large_search = performance_results[sizes_to_test[-1]]['search_time']
            
            # Search time shouldn't increase by more than 5x
            assert large_search / small_search < 5.0
            
            small_index = performance_results[sizes_to_test[0]]['index_time']
            large_index = performance_results[sizes_to_test[-1]]['index_time']
            
            # Indexing time shouldn't increase by more than 2x
            assert large_index / small_index < 2.0
    
    def _populate_large_archive(self, archive, profile, num_files):
        """Helper method to populate archive with test files"""
        
        print(f"Populating archive with {num_files} files for performance testing...")
        
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        for i in range(num_files):
            if i % 50 == 0:
                print(f"  Progress: {i}/{num_files}")
            
            # Create temporary file (larger files for meaningful I/O operations)
            temp_file = archive.root_path / f"temp_populate_{i}.txt"
            # Create larger files (about 50KB each) to make checksum verification meaningful
            content = f"Performance test file {i}\n" + f"Content line {i} with some data to make the file larger for performance testing\n" * 500
            temp_file.write_text(content)
            
            metadata = {
                "title": f"Performance File {i+1}",
                "category": f"Type{i % 3 + 1}",
            }
            
            try:
                asset = ingestion.ingest_file(temp_file, profile=profile, custom_metadata=metadata)
                indexing.index_asset(asset)
            finally:
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()
        
        print(f"Populated archive with {num_files} files")
    
    def _add_files_to_archive(self, archive, profile, num_files, start_index):
        """Helper method to add more files to existing archive"""
        
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        for i in range(num_files):
            file_index = start_index + i
            
            # Create temporary file
            temp_file = archive.root_path / f"temp_add_{file_index}.txt"
            content = f"Added performance test file {file_index}\n" + f"Content for file {file_index}\n" * 5
            temp_file.write_text(content)
            
            metadata = {
                "title": f"Added Performance File {file_index+1}",
                "category": f"Type{file_index % 3 + 1}",
            }
            
            try:
                asset = ingestion.ingest_file(temp_file, profile=profile, custom_metadata=metadata)
                indexing.index_asset(asset)
            finally:
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()


@pytest.mark.performance
class TestExportPerformance:
    """Test export performance with large archives"""
    
    def test_bagit_export_performance(self, archive_with_assets, tmp_path):
        """Test BagIt export performance"""
        
        archive, assets = archive_with_assets
        
        # Add more assets for export test if needed
        if len(assets) < 50:
            self._add_more_assets(archive, 50 - len(assets))
        
        export_service = ExportService(archive)
        
        bagit_path = tmp_path / "performance_export.bag"
        
        metadata = {
            'Source-Organization': 'Performance Test',
            'Contact-Name': 'Test Runner',
            'External-Description': 'Performance test export'
        }
        
        print(f"\nTesting BagIt export performance...")
        
        # Measure export time and memory
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        start_time = time.time()
        result_path = export_service.export_to_bagit(bagit_path, metadata=metadata)
        export_time = time.time() - start_time
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # Verify export completed
        assert result_path.exists()
        assert (result_path / "bagit.txt").exists()
        
        # Count exported files
        data_dir = result_path / "data"
        exported_files = list(data_dir.rglob("*"))
        asset_files = [f for f in exported_files if not f.name.endswith('.metadata.json')]
        
        print(f"Export Performance Results:")
        print(f"  Export time: {export_time:.2f} seconds")
        print(f"  Files exported: {len(asset_files)}")
        print(f"  Files per second: {len(asset_files) / export_time:.2f}")
        print(f"  Memory increase: {memory_increase:.1f} MB")
        
        # Performance assertions
        assert export_time < 60  # Should complete within 1 minute for test size
        assert len(asset_files) > 0
        assert memory_increase < 100  # Memory increase should be reasonable
    
    def _add_more_assets(self, archive, num_assets):
        """Helper to add more assets to archive for testing"""
        
        from src.core.ingestion import FileIngestionService
        from src.core.indexing import IndexingService
        
        ingestion = FileIngestionService(archive)
        indexing = IndexingService(archive)
        
        for i in range(num_assets):
            # Create temporary file
            temp_file = archive.root_path / f"temp_export_test_{i}.txt"
            content = f"Export test file {i}\n" + "Test content\n" * 10
            temp_file.write_text(content)
            
            metadata = {"title": f"Export Test File {i+1}"}
            
            try:
                asset = ingestion.ingest_file(temp_file, custom_metadata=metadata)
                indexing.index_asset(asset)
            finally:
                if temp_file.exists():
                    temp_file.unlink()