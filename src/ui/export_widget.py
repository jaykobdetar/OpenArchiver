from typing import Optional
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QCheckBox, QFileDialog,
    QGroupBox, QLabel, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ..models import Archive
from ..core.export import ExportService


class ExportThread(QThread):
    progress_updated = pyqtSignal(int, int, str)
    export_completed = pyqtSignal(str)  # Result path
    export_failed = pyqtSignal(str)     # Error message
    
    def __init__(self, archive: Archive, output_path: Path, export_format: str, metadata: dict):
        super().__init__()
        self.archive = archive
        self.output_path = output_path
        self.export_format = export_format
        self.metadata = metadata
        self.export_service = ExportService(archive)
    
    def run(self):
        # Set up progress callback
        self.export_service.set_progress_callback(self.progress_updated.emit)
        
        try:
            if self.export_format == "bagit":
                result_path = self.export_service.export_to_bagit(
                    self.output_path,
                    metadata=self.metadata
                )
            else:  # directory
                from ..core.search import SearchService
                search_service = SearchService(self.archive)
                all_assets, _ = search_service.search(limit=10000)
                asset_ids = [asset.asset_id for asset in all_assets]
                
                result_path = self.export_service.export_selection(
                    asset_ids,
                    self.output_path,
                    format="directory",
                    preserve_structure=True
                )
            
            self.export_completed.emit(str(result_path))
            
        except Exception as e:
            self.export_failed.emit(str(e))


class ExportWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.archive: Optional[Archive] = None
        self.export_thread: Optional[ExportThread] = None
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Export settings
        settings_group = QGroupBox("Export Settings")
        settings_layout = QFormLayout(settings_group)
        
        # Output path
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Choose export destination...")
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_output_path)
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.browse_button)
        settings_layout.addRow("Output Path:", output_layout)
        
        # Export format
        self.format_combo = QComboBox()
        self.format_combo.addItem("BagIt Archive (Recommended)", "bagit")
        self.format_combo.addItem("Directory Structure", "directory")
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        settings_layout.addRow("Format:", self.format_combo)
        
        # BagIt metadata section
        self.bagit_group = QGroupBox("BagIt Metadata")
        bagit_layout = QFormLayout(self.bagit_group)
        
        self.source_org_edit = QLineEdit("Archive Tool")
        bagit_layout.addRow("Source Organization:", self.source_org_edit)
        
        self.contact_name_edit = QLineEdit("Archive Administrator")
        bagit_layout.addRow("Contact Name:", self.contact_name_edit)
        
        self.contact_email_edit = QLineEdit("admin@archive.local")
        bagit_layout.addRow("Contact Email:", self.contact_email_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Description of this export...")
        bagit_layout.addRow("Description:", self.description_edit)
        
        settings_layout.addRow(self.bagit_group)
        
        layout.addWidget(settings_group)
        
        # Progress section
        progress_group = QGroupBox("Export Progress") 
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        progress_layout.addWidget(self.progress_label)
        
        # Status text
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setPlainText("Ready to export archive.")
        progress_layout.addWidget(self.status_text)
        
        layout.addWidget(progress_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("Start Export")
        self.export_button.clicked.connect(self.start_export)
        button_layout.addWidget(self.export_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_export)
        self.cancel_button.setVisible(False)
        button_layout.addWidget(self.cancel_button)
        
        self.manifest_button = QPushButton("Generate Manifest")
        self.manifest_button.clicked.connect(self.generate_manifest)
        button_layout.addWidget(self.manifest_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Initially disable everything
        self.set_enabled(False)
    
    def set_archive(self, archive: Optional[Archive]):
        self.archive = archive
        if archive:
            self.set_enabled(True)
            self.status_text.setPlainText(f"Ready to export '{archive.config.name}' archive.")
            
            # Set default description
            self.description_edit.setPlainText(
                f"Export from '{archive.config.name}' archive created on "
                f"{archive.config.created_at[:10]}"
            )
        else:
            self.set_enabled(False)
            self.status_text.setPlainText("No archive loaded.")
    
    def set_enabled(self, enabled: bool):
        self.output_path_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.format_combo.setEnabled(enabled)
        self.export_button.setEnabled(enabled)
        self.manifest_button.setEnabled(enabled)
        self.bagit_group.setEnabled(enabled)
    
    def on_format_changed(self):
        is_bagit = self.format_combo.currentData() == "bagit"
        self.bagit_group.setVisible(is_bagit)
    
    def browse_output_path(self):
        if self.format_combo.currentData() == "bagit":
            # For BagIt, select directory where the bag will be created
            path = QFileDialog.getExistingDirectory(
                self, "Select Export Directory"
            )
            if path:
                # Suggest a bag name
                if self.archive:
                    bag_name = f"{self.archive.config.name}_export"
                    self.output_path_edit.setText(str(Path(path) / bag_name))
                else:
                    self.output_path_edit.setText(path)
        else:
            # For directory export, select target directory
            path = QFileDialog.getExistingDirectory(
                self, "Select Export Directory"
            )
            if path:
                self.output_path_edit.setText(path)
    
    def start_export(self):
        if not self.archive:
            return
        
        output_path = self.output_path_edit.text().strip()
        
        if not output_path:
            QMessageBox.warning(self, "Invalid Input", "Please specify an output path.")
            return
        
        # Collect metadata for BagIt
        metadata = {}
        if self.format_combo.currentData() == "bagit":
            metadata = {
                'Source-Organization': self.source_org_edit.text().strip(),
                'Contact-Name': self.contact_name_edit.text().strip(),
                'Contact-Email': self.contact_email_edit.text().strip(),
                'External-Description': self.description_edit.toPlainText().strip()
            }
        
        # Disable controls
        self.set_enabled(False)
        self.cancel_button.setVisible(True)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Update status
        self.status_text.append(f"Starting export to: {output_path}")
        
        # Start export thread
        self.export_thread = ExportThread(
            self.archive,
            Path(output_path),
            self.format_combo.currentData(),
            metadata
        )
        self.export_thread.progress_updated.connect(self.on_progress_updated)
        self.export_thread.export_completed.connect(self.on_export_completed)
        self.export_thread.export_failed.connect(self.on_export_failed)
        self.export_thread.start()
    
    def cancel_export(self):
        if self.export_thread and self.export_thread.isRunning():
            self.export_thread.terminate()
            self.export_thread.wait()
            self.status_text.append("Export cancelled by user.")
        
        self.reset_ui()
    
    def on_progress_updated(self, current: int, total: int, message: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            progress_pct = (current / total) * 100
            self.progress_label.setText(f"Progress: {current}/{total} ({progress_pct:.1f}%) - {message}")
    
    def on_export_completed(self, result_path: str):
        self.status_text.append(f"Export completed successfully!")
        self.status_text.append(f"Output: {result_path}")
        
        # Ask if user wants to open the output location
        reply = QMessageBox.question(
            self, "Export Complete",
            f"Export completed successfully!\n\nOutput: {result_path}\n\n"
            "Would you like to open the output location?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.open_output_location(result_path)
        
        self.reset_ui()
    
    def on_export_failed(self, error_message: str):
        self.status_text.append(f"Export failed: {error_message}")
        QMessageBox.critical(self, "Export Failed", f"Export failed:\n{error_message}")
        self.reset_ui()
    
    def reset_ui(self):
        # Re-enable controls
        self.set_enabled(True)
        self.cancel_button.setVisible(False)
        
        # Hide progress
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        # Clean up thread
        if self.export_thread:
            self.export_thread.deleteLater()
            self.export_thread = None
    
    def generate_manifest(self):
        if not self.archive:
            return
        
        output_file, _ = QFileDialog.getSaveFileName(
            self, "Save Manifest",
            f"{self.archive.config.name}_manifest.json",
            "JSON files (*.json);;CSV files (*.csv)"
        )
        
        if output_file:
            try:
                from ..core.export import ExportService
                export_service = ExportService(self.archive)
                
                # Determine format from extension
                format_type = "csv" if output_file.endswith('.csv') else "json"
                
                result_path = export_service.generate_manifest(Path(output_file), format_type)
                
                QMessageBox.information(
                    self, "Success",
                    f"Manifest generated successfully:\n{result_path}"
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to generate manifest:\n{e}")
    
    def open_output_location(self, path: str):
        import subprocess
        import platform
        
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.call(["open", "-R", path])
            elif platform.system() == "Windows":
                subprocess.call(["explorer", path])
            else:  # Linux
                subprocess.call(["xdg-open", str(Path(path).parent)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open location:\n{e}")