from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QProgressBar, QLabel, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ..models import Archive
from ..core.integrity import IntegrityService


class IntegrityVerificationThread(QThread):
    progress_updated = pyqtSignal(int, int, str)
    verification_completed = pyqtSignal(object)  # IntegrityReport
    
    def __init__(self, archive: Archive):
        super().__init__()
        self.archive = archive
        self.integrity_service = IntegrityService(archive)
    
    def run(self):
        # Set up progress callback
        self.integrity_service.set_progress_callback(self.progress_updated.emit)
        
        # Run verification
        try:
            report = self.integrity_service.verify_all()
            self.verification_completed.emit(report)
        except Exception as e:
            self.verification_completed.emit(e)


class IntegrityWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.archive: Optional[Archive] = None
        self.verification_thread: Optional[IntegrityVerificationThread] = None
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls
        controls_group = QGroupBox("Integrity Verification")
        controls_layout = QVBoxLayout(controls_group)
        
        # Info label
        self.info_label = QLabel(
            "Verify the integrity of all files in the archive by checking their checksums."
        )
        self.info_label.setWordWrap(True)
        controls_layout.addWidget(self.info_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        controls_layout.addWidget(self.progress_bar)
        
        # Progress label
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        controls_layout.addWidget(self.progress_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.verify_button = QPushButton("Start Verification")
        self.verify_button.clicked.connect(self.start_verification)
        button_layout.addWidget(self.verify_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_verification)
        self.cancel_button.setVisible(False)
        button_layout.addWidget(self.cancel_button)
        
        self.repair_button = QPushButton("Repair Index")
        self.repair_button.clicked.connect(self.repair_index)
        self.repair_button.setToolTip("Remove missing files from index and add orphaned files")
        button_layout.addWidget(self.repair_button)
        
        button_layout.addStretch()
        controls_layout.addLayout(button_layout)
        
        layout.addWidget(controls_group)
        
        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlainText("No verification performed yet.")
        results_layout.addWidget(self.results_text)
        
        layout.addWidget(results_group)
        
        # Initially disable everything
        self.set_enabled(False)
    
    def set_archive(self, archive: Optional[Archive]):
        self.archive = archive
        if archive:
            self.set_enabled(True)
            self.results_text.setPlainText("Ready to verify archive integrity.")
        else:
            self.set_enabled(False)
            self.results_text.setPlainText("No archive loaded.")
    
    def set_enabled(self, enabled: bool):
        self.verify_button.setEnabled(enabled)
        self.repair_button.setEnabled(enabled)
    
    def start_verification(self):
        if not self.archive:
            return
        
        # Disable controls
        self.verify_button.setEnabled(False)
        self.repair_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Clear results
        self.results_text.clear()
        self.results_text.append("Starting integrity verification...")
        
        # Start verification thread
        self.verification_thread = IntegrityVerificationThread(self.archive)
        self.verification_thread.progress_updated.connect(self.on_progress_updated)
        self.verification_thread.verification_completed.connect(self.on_verification_completed)
        self.verification_thread.start()
    
    def cancel_verification(self):
        if self.verification_thread and self.verification_thread.isRunning():
            # Signal the thread to cancel
            self.verification_thread.integrity_service.cancel_verification()
            self.verification_thread.wait(5000)  # Wait up to 5 seconds
            
            if self.verification_thread.isRunning():
                self.verification_thread.terminate()
                self.verification_thread.wait()
            
            self.results_text.append("\nVerification cancelled by user.")
        
        self.reset_ui()
    
    def on_progress_updated(self, current: int, total: int, message: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            progress_pct = (current / total) * 100
            self.progress_label.setText(f"Progress: {current}/{total} ({progress_pct:.1f}%) - {message}")
    
    def on_verification_completed(self, result):
        if isinstance(result, Exception):
            # Error occurred
            self.results_text.append(f"\nVerification failed: {result}")
        else:
            # Successful completion
            report = result
            self.show_report(report)
        
        self.reset_ui()
    
    def show_report(self, report):
        self.results_text.clear()
        
        # Summary
        self.results_text.append("=== INTEGRITY VERIFICATION REPORT ===\n")
        self.results_text.append(f"Total assets: {report.total_assets}")
        self.results_text.append(f"Verified: {report.verified_assets}")
        self.results_text.append(f"Corrupted: {len(report.corrupted_assets)}")
        self.results_text.append(f"Missing: {len(report.missing_assets)}")
        self.results_text.append(f"Missing metadata: {len(report.missing_metadata)}")
        self.results_text.append(f"Success rate: {report.success_rate:.1f}%")
        self.results_text.append(f"Duration: {report.duration:.1f} seconds")
        
        # Corrupted files
        if report.corrupted_assets:
            self.results_text.append(f"\n=== CORRUPTED FILES ({len(report.corrupted_assets)}) ===")
            for path in report.corrupted_assets:
                self.results_text.append(f"  {path}")
        
        # Missing files
        if report.missing_assets:
            self.results_text.append(f"\n=== MISSING FILES ({len(report.missing_assets)}) ===")
            for path in report.missing_assets:
                self.results_text.append(f"  {path}")
        
        # Missing metadata
        if report.missing_metadata:
            self.results_text.append(f"\n=== MISSING METADATA ({len(report.missing_metadata)}) ===")
            for path in report.missing_metadata:
                self.results_text.append(f"  {path}")
        
        if not report.corrupted_assets and not report.missing_assets and not report.missing_metadata:
            self.results_text.append("\n✓ All files verified successfully!")
    
    def reset_ui(self):
        # Re-enable controls
        self.verify_button.setEnabled(True)
        self.repair_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        
        # Hide progress
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        # Clean up thread
        if self.verification_thread:
            self.verification_thread.deleteLater()
            self.verification_thread = None
    
    def repair_index(self):
        if not self.archive:
            return
        
        reply = QMessageBox.question(
            self, "Repair Index",
            "This will:\n"
            "• Remove missing files from the search index\n"
            "• Add orphaned files to the index (creating metadata if needed)\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from ..core.integrity import IntegrityService
                integrity_service = IntegrityService(self.archive)
                stats = integrity_service.repair_index()
                
                self.results_text.clear()
                self.results_text.append("=== INDEX REPAIR RESULTS ===\n")
                self.results_text.append(f"Removed missing entries: {stats['removed_missing']}")
                self.results_text.append(f"Reindexed existing files: {stats['reindexed']}")
                self.results_text.append(f"Newly indexed files: {stats['newly_indexed']}")
                self.results_text.append(f"Errors: {stats['errors']}")
                
                if stats['errors'] == 0:
                    self.results_text.append("\n✓ Index repair completed successfully!")
                else:
                    self.results_text.append(f"\n⚠ Index repair completed with {stats['errors']} errors.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to repair index:\n{e}")