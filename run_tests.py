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


def run_command(cmd, description, verbose=False, capture_output=True):
    """Run a command and handle the output"""
    if verbose:
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*60}")
        capture = False
    else:
        print(f"Running: {description}", end="", flush=True)
        capture = capture_output
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=capture, text=True)
        if verbose:
            print(f"\n✅ {description} completed successfully")
        else:
            print(" ✅", flush=True)
        return True, result.stdout if capture else ""
    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"\n❌ {description} failed with exit code {e.returncode}")
        else:
            print(" ❌", flush=True)
        if capture and e.stdout:
            print(e.stdout)
        if capture and e.stderr:
            print(e.stderr)
        return False, ""
    except FileNotFoundError:
        error_msg = f"❌ Command not found. Make sure pytest is installed."
        if verbose:
            print(f"\n{error_msg}")
        else:
            print(f" {error_msg}", flush=True)
        return False, ""


def main():
    parser = argparse.ArgumentParser(description="Run Archive Tool tests")
    parser.add_argument(
        "test_type",
        choices=["all", "unit", "integration", "performance", "ui", "coverage", "quick"],
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
            test_success, output = run_command(cmd, desc, args.verbose, False)
            if not test_success:
                success = False
        
        # Run UI tests individually to avoid Qt event processing conflicts
        ui_test_files = [
            "tests/ui/test_search_widget.py",
            "tests/ui/test_main_window.py", 
            "tests/ui/test_archive_browser.py",
            "tests/ui/test_export_widget.py",
            "tests/ui/test_integrity_widget.py",
            "tests/ui/test_profile_manager.py",
            "tests/ui/test_integration_workflows.py",
            "tests/ui/test_dialogs.py"
        ]
        
        # Collect UI coverage data
        for i, test_file in enumerate(ui_test_files):
            if not args.no_coverage:
                cmd = base_cmd + [test_file, "-m", "ui", "--cov=src", "--cov-append", "--cov-report="]
            else:
                cmd = base_cmd + [test_file, "-m", "ui"]
            
            test_name = Path(test_file).stem.replace("test_", "").replace("_", " ").title()
            test_success, output = run_command(cmd, f"UI - {test_name}", args.verbose)
            if not test_success:
                success = False
        
        # Generate final coverage report for all tests
        if success and not args.no_coverage:
            print("\nGenerating final coverage report...", end="", flush=True)
            coverage_cmd = ["python", "-m", "coverage", "report", "--show-missing"]
            coverage_success, coverage_output = run_command(coverage_cmd, "Final Coverage Report", args.verbose, True)
            if coverage_success:
                print(f"\n{coverage_output}")
            else:
                print(" ❌")
    
    elif args.test_type == "unit":
        # Run unit tests only
        cmd = base_cmd + ["tests/unit", "-m", "unit"]
        success, output = run_command(cmd, "Unit Tests", args.verbose, False)
    
    elif args.test_type == "integration":
        # Run integration tests only
        cmd = base_cmd + ["tests/integration", "-m", "integration"]
        success, output = run_command(cmd, "Integration Tests", args.verbose, False)
    
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
        
        success, output = run_command(cmd, "Performance Tests with Benchmarking", args.verbose, False)
    
    elif args.test_type == "ui":
        # Run UI tests individually to avoid Qt event processing conflicts
        ui_test_files = [
            "tests/ui/test_search_widget.py",
            "tests/ui/test_main_window.py", 
            "tests/ui/test_archive_browser.py",
            "tests/ui/test_export_widget.py",
            "tests/ui/test_integrity_widget.py",
            "tests/ui/test_profile_manager.py",
            "tests/ui/test_integration_workflows.py",
            "tests/ui/test_dialogs.py"
        ]
        
        success = True
        
        # First run: collect coverage data without reports
        for i, test_file in enumerate(ui_test_files):
            if not args.no_coverage:
                if i == 0:
                    # First test: start fresh coverage
                    cmd = base_cmd + [test_file, "-m", "ui", "--cov=src", "--cov-report="]
                else:
                    # Subsequent tests: append to coverage
                    cmd = base_cmd + [test_file, "-m", "ui", "--cov=src", "--cov-append", "--cov-report="]
            else:
                cmd = base_cmd + [test_file, "-m", "ui"]
            
            test_name = Path(test_file).stem.replace("test_", "").replace("_", " ").title()
            test_success, output = run_command(cmd, f"UI - {test_name}", args.verbose)
            if not test_success:
                success = False
        
        # Generate final coverage report
        if success and not args.no_coverage:
            print("\nGenerating coverage report...", end="", flush=True)
            coverage_cmd = ["python", "-m", "coverage", "report", "--show-missing"]
            coverage_success, coverage_output = run_command(coverage_cmd, "Coverage Report", args.verbose, True)
            if coverage_success:
                print(f"\n{coverage_output}")
            else:
                print(" ❌")
    
    elif args.test_type == "coverage":
        # Run tests with detailed coverage report
        # Run unit and integration tests together
        cmd = base_cmd + [
            "tests/unit", "tests/integration",
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-append"
        ]
        success, output = run_command(cmd, "Unit and Integration Tests", args.verbose, False)
        
        # Run UI tests individually and append to coverage
        if success:
            ui_test_files = [
                "tests/ui/test_search_widget.py",
                "tests/ui/test_main_window.py", 
                "tests/ui/test_archive_browser.py",
                "tests/ui/test_export_widget.py",
                "tests/ui/test_integrity_widget.py",
                "tests/ui/test_profile_manager.py",
                "tests/ui/test_integration_workflows.py",
                "tests/ui/test_dialogs.py"
            ]
            
            for test_file in ui_test_files:
                cmd = base_cmd + [
                    test_file, "-m", "ui",
                    "--cov=src",
                    "--cov-append",
                    "--cov-report="
                ]
                test_name = Path(test_file).stem.replace("test_", "").replace("_", " ").title()
                test_success, test_output = run_command(cmd, f"UI - {test_name}", args.verbose)
                if not test_success:
                    success = False
            
            # Generate final coverage reports
            if success:
                print("\nGenerating coverage reports...", end="", flush=True)
                
                # Generate console report
                report_cmd = ["python", "-m", "coverage", "report", "--show-missing"]
                report_success, report_output = run_command(report_cmd, "Coverage Report", args.verbose, True)
                
                # Generate HTML report
                html_cmd = ["python", "-m", "coverage", "html"]
                html_success, html_output = run_command(html_cmd, "HTML Report", args.verbose, True)
                
                # Generate XML report  
                xml_cmd = ["python", "-m", "coverage", "xml"]
                xml_success, xml_output = run_command(xml_cmd, "XML Report", args.verbose, True)
                
                if report_success:
                    print(f"\n{report_output}")
                else:
                    print(" ❌")
        
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
        success, output = run_command(cmd, "Quick Test Suite", args.verbose, False)
    
    # Print summary
    if args.verbose:
        print(f"\n{'='*60}")
    
    if success:
        print("\n🎉 All tests completed successfully!")
        if args.verbose:
            print("\nNext steps:")
            print("  - Review any warnings or deprecations")
            print("  - Check coverage reports if generated")
            if args.test_type == "performance":
                print("  - Analyze performance benchmarks")
    else:
        print("\n❌ Some tests failed!")
        if args.verbose:
            print("\nTroubleshooting:")
            print("  - Check test output for specific failures")
            print("  - Ensure all dependencies are installed")
            print("  - Run with --verbose for more details")
        else:
            print("Run with --verbose for more details")
    
    if args.verbose:
        print(f"{'='*60}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())