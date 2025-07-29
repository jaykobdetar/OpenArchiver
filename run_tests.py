#!/usr/bin/env python3
"""
Test runner script for Archive Tool

This script provides convenient commands to run different types of tests
with appropriate configurations and reporting.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle the output"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"\n✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"\n❌ Command not found. Make sure pytest is installed.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run Archive Tool tests")
    parser.add_argument(
        "test_type",
        choices=["all", "unit", "integration", "performance", "coverage", "quick"],
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage reporting"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel (where supported)"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        base_cmd.append("-v")
    else:
        base_cmd.append("-q")
    
    # Add coverage if not disabled
    if not args.no_coverage and args.test_type != "performance":
        base_cmd.extend(["--cov=src", "--cov-report=term-missing"])
    
    success = True
    
    if args.test_type == "all":
        # Run all tests
        commands = [
            (base_cmd + ["tests/unit", "-m", "unit"], "Unit Tests"),
            (base_cmd + ["tests/integration", "-m", "integration"], "Integration Tests"),
            (base_cmd + ["tests/performance", "-m", "performance", "--benchmark-skip"], "Performance Tests (Structure Only)")
        ]
        
        for cmd, desc in commands:
            if not run_command(cmd, desc):
                success = False
    
    elif args.test_type == "unit":
        # Run unit tests only
        cmd = base_cmd + ["tests/unit", "-m", "unit"]
        success = run_command(cmd, "Unit Tests")
    
    elif args.test_type == "integration":
        # Run integration tests only
        cmd = base_cmd + ["tests/integration", "-m", "integration"]
        success = run_command(cmd, "Integration Tests")
    
    elif args.test_type == "performance":
        # Run performance tests with benchmarking
        cmd = base_cmd + [
            "tests/performance", 
            "-m", "performance",
            "--benchmark-only",
            "--benchmark-sort=mean"
        ]
        
        if args.no_coverage:
            # Remove coverage for performance tests
            cmd = [c for c in cmd if not c.startswith("--cov")]
        
        success = run_command(cmd, "Performance Tests with Benchmarking")
    
    elif args.test_type == "coverage":
        # Run tests with detailed coverage report
        cmd = base_cmd + [
            "tests/unit", "tests/integration",
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ]
        success = run_command(cmd, "Tests with Coverage Report")
        
        if success:
            print(f"\n📊 Coverage reports generated:")
            print(f"  - HTML: htmlcov/index.html")
            print(f"  - XML: coverage.xml")
    
    elif args.test_type == "quick":
        # Run a quick subset of tests
        cmd = base_cmd + [
            "tests/unit/test_models.py",
            "tests/integration/test_full_workflows.py::TestCompleteArchiveWorkflow::test_create_archive_to_export_workflow",
            "-m", "not slow"
        ]
        success = run_command(cmd, "Quick Test Suite")
    
    # Print summary
    print(f"\n{'='*60}")
    if success:
        print("🎉 All tests completed successfully!")
        print("\nNext steps:")
        print("  - Review any warnings or deprecations")
        print("  - Check coverage reports if generated")
        if args.test_type == "performance":
            print("  - Analyze performance benchmarks")
    else:
        print("❌ Some tests failed!")
        print("\nTroubleshooting:")
        print("  - Check test output for specific failures")
        print("  - Ensure all dependencies are installed")
        print("  - Run with --verbose for more details")
    print(f"{'='*60}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())