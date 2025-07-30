import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QMenuBar, QMenu, QToolBar, QStatusBar, QLabel, QProgressBar,
    QMessageBox, QFileDialog, QSplitter, QGroupBox, QPushButton,
    QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QIcon

import subprocess
import platform
from ..models import Archive
from ..utils.settings import settings
from .search_widget import SearchWidget
from .profile_manager import ProfileManager
from .integrity_widget import IntegrityWidget
from .export_widget import ExportWidget
from .dialogs import NewArchiveDialog, OpenArchiveDialog, ProfileSelectionDialog, MetadataCollectionDialog, SettingsDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    archive_changed = pyqtSignal(Archive)
    
    def __init__(self):
        super().__init__()
        self.current_archive: Optional[Archive] = None
        self.status_timer = QTimer()
        
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        
        # Connect signals
        self.archive_changed.connect(self.on_archive_changed)
        
        # Load settings
        self.load_settings()
        
        logger.info("Main window initialized")
    
    def setup_ui(self):
        self.setWindowTitle("Archive Tool")
        self.setMinimumSize(1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Main content area (no splitter needed)
        main_content = QWidget()
        main_layout = QVBoxLayout(main_content)
        layout.addWidget(main_content)
        
        # Add Files Section (Most Prominent)
        self.setup_add_files_section(main_layout)
        
        # Archive controls section
        self.setup_archive_controls_section(main_layout)
        
        # Secondary functions in tabs
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Profile manager tab (moved to first position as it's needed for adding files)
        self.profile_manager = ProfileManager()
        self.tab_widget.addTab(self.profile_manager, "Profiles")
        
        # Search tab (moved to secondary position)
        self.search_widget = SearchWidget()
        self.tab_widget.addTab(self.search_widget, "Search")
        
        # Integrity tab
        self.integrity_widget = IntegrityWidget()
        self.tab_widget.addTab(self.integrity_widget, "Integrity")
        
        # Export tab
        self.export_widget = ExportWidget()
        self.tab_widget.addTab(self.export_widget, "Export")
        
        # Connect widget signals
        self.search_widget.search_performed.connect(self.on_search_performed)
    
    def setup_add_files_section(self, parent_layout):
        """Create a prominent section for adding files to the archive."""
        # Add Files Group Box
        add_files_group = QGroupBox("Add Files to Archive")
        add_files_group.setMaximumHeight(200)
        add_files_layout = QVBoxLayout(add_files_group)
        
        # Description
        self.add_files_desc = QLabel("Select files or folders to add to your archive")
        self.add_files_desc.setWordWrap(True)
        self.add_files_desc.setStyleSheet("color: gray; margin-bottom: 10px;")
        add_files_layout.addWidget(self.add_files_desc)
        
        # Main add files buttons
        buttons_layout = QGridLayout()
        
        # Add Files button
        self.add_files_btn = QPushButton("Add Files...")
        self.add_files_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
        self.add_files_btn.setMinimumHeight(50)
        self.add_files_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 10px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_files_btn.setEnabled(False)
        buttons_layout.addWidget(self.add_files_btn, 0, 0)
        
        # Add Folder button
        self.add_folder_btn = QPushButton("Add Folder...")
        self.add_folder_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
        self.add_folder_btn.setMinimumHeight(50)
        self.add_folder_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 10px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                text-align: left;
                padding-left: 15px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.add_folder_btn.setEnabled(False)
        buttons_layout.addWidget(self.add_folder_btn, 0, 1)
        
        add_files_layout.addLayout(buttons_layout)
        
        parent_layout.addWidget(add_files_group)
    
    def setup_archive_controls_section(self, parent_layout):
        """Create archive management controls section."""
        controls_group = QGroupBox("Archive Controls")
        controls_group.setMaximumHeight(120)
        controls_layout = QVBoxLayout(controls_group)
        
        # Archive status
        self.archive_status = QLabel("No archive loaded")
        self.archive_status.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        controls_layout.addWidget(self.archive_status)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Open archive folder button
        self.open_folder_btn = QPushButton("Open Archive Folder")
        self.open_folder_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirOpenIcon))
        self.open_folder_btn.clicked.connect(self.open_archive_folder)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.setToolTip("Open the archive folder in your file manager")
        buttons_layout.addWidget(self.open_folder_btn)
        
        # Rebuild index button
        self.rebuild_btn = QPushButton("Rebuild Index")
        self.rebuild_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload))
        self.rebuild_btn.clicked.connect(self.rebuild_index)
        self.rebuild_btn.setEnabled(False)
        self.rebuild_btn.setToolTip("Rebuild the search index for the archive")
        buttons_layout.addWidget(self.rebuild_btn)
        
        # Verify integrity button
        self.verify_btn = QPushButton("Verify Integrity")
        self.verify_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton))
        self.verify_btn.clicked.connect(self.verify_integrity)
        self.verify_btn.setEnabled(False)
        self.verify_btn.setToolTip("Verify the integrity of all files in the archive")
        buttons_layout.addWidget(self.verify_btn)
        
        buttons_layout.addStretch()  # Push buttons to the left
        controls_layout.addLayout(buttons_layout)
        
        parent_layout.addWidget(controls_group)
    
    def open_archive_folder(self):
        """Open the current archive folder in the system file manager."""
        if not self.current_archive:
            return
        
        archive_path = str(self.current_archive.root_path)
        
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", archive_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", archive_path])
            else:  # Linux and other Unix-like systems
                subprocess.run(["xdg-open", archive_path])
        except Exception as e:
            QMessageBox.warning(
                self, "Error", 
                f"Failed to open archive folder:\n{e}"
            )
    
    def setup_menus(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New Archive...", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_archive)
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open Archive...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_archive)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        close_action = QAction("&Close Archive", self)
        close_action.triggered.connect(self.close_archive)
        file_menu.addAction(close_action)
        
        file_menu.addSeparator()
        
        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Archive menu
        self.archive_menu = menubar.addMenu("&Archive")
        
        add_files_action = QAction("Add &Files...", self)
        add_files_action.setShortcut(QKeySequence("Ctrl+I"))
        add_files_action.triggered.connect(self.add_files)
        self.archive_menu.addAction(add_files_action)
        
        add_folder_action = QAction("Add F&older...", self)
        add_folder_action.triggered.connect(self.add_folder)
        self.archive_menu.addAction(add_folder_action)
        
        self.archive_menu.addSeparator()
        
        rebuild_index_action = QAction("&Rebuild Index", self)
        rebuild_index_action.triggered.connect(self.rebuild_index)
        self.archive_menu.addAction(rebuild_index_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        verify_action = QAction("&Verify Integrity", self)
        verify_action.triggered.connect(self.verify_integrity)
        tools_menu.addAction(verify_action)
        
        export_action = QAction("&Export Archive...", self)
        export_action.triggered.connect(self.export_archive)
        tools_menu.addAction(export_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # Disable archive-specific actions initially
        self.archive_menu.setEnabled(False)
    
    def setup_toolbar(self):
        toolbar = self.addToolBar("Main")
        
        # New archive
        new_action = QAction("New Archive", self)
        new_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogNewFolder))
        new_action.setToolTip("Create new archive")
        new_action.triggered.connect(self.new_archive)
        toolbar.addAction(new_action)
        
        # Open archive
        open_action = QAction("Open Archive", self)
        open_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirOpenIcon))
        open_action.setToolTip("Open existing archive")
        open_action.triggered.connect(self.open_archive)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        # Search (moved to toolbar since it's no longer the first tab)
        self.search_action = QAction("Search", self)
        self.search_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView))
        self.search_action.setToolTip("Search archive")
        self.search_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(1))  # Search is now tab index 1
        self.search_action.setEnabled(False)
        toolbar.addAction(self.search_action)
    
    def setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Archive info
        self.archive_info_label = QLabel()
        self.status_bar.addPermanentWidget(self.archive_info_label)
        
        # Setup status timer
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(lambda: self.status_label.setText("Ready"))
    
    def show_status(self, message: str, timeout: int = 3000):
        self.status_label.setText(message)
        if timeout > 0:
            self.status_timer.start(timeout)
    
    def show_progress(self, current: int, total: int, message: str = ""):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.setVisible(True)
            
            if message:
                self.show_status(message, 0)
                
            if current >= total:
                self.progress_bar.setVisible(False)
        else:
            self.progress_bar.setVisible(False)
    
    def new_archive(self):
        dialog = NewArchiveDialog(self)
        if dialog.exec() == NewArchiveDialog.DialogCode.Accepted:
            path, name, description = dialog.get_values()
            
            try:
                archive = Archive(Path(path))
                archive.create(name, description)
                self.load_archive(archive)
                self.show_status(f"Created archive '{name}'")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create archive:\n{e}")
    
    def open_archive(self):
        dialog = OpenArchiveDialog(self)
        if dialog.exec() == OpenArchiveDialog.DialogCode.Accepted:
            path = dialog.get_path()
            
            try:
                archive = Archive(Path(path))
                archive.load()
                self.load_archive(archive)
                self.show_status(f"Opened archive '{archive.config.name}'")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open archive:\n{e}")
    
    def close_archive(self):
        if self.current_archive:
            self.current_archive = None
            self.archive_changed.emit(None)
            self.archive_menu.setEnabled(False)
            self.add_files_btn.setEnabled(False)
            self.add_folder_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.rebuild_btn.setEnabled(False)
            self.verify_btn.setEnabled(False)
            self.search_action.setEnabled(False)
            self.archive_info_label.setText("")
            self.archive_status.setText("No archive loaded")
            self.add_files_desc.setText("Load an archive to start adding files")
            self.show_status("Archive closed")
    
    def load_archive(self, archive: Archive):
        self.current_archive = archive
        self.archive_changed.emit(archive)
        self.archive_menu.setEnabled(True)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        self.rebuild_btn.setEnabled(True)
        self.verify_btn.setEnabled(True)
        self.search_action.setEnabled(True)
        
        # Add to recent archives
        settings.add_recent_archive(archive.root_path)
        
        # Update status
        from ..core.indexing import IndexingService
        indexing = IndexingService(archive)
        stats = indexing.get_statistics()
        self.archive_info_label.setText(
            f"{archive.config.name} | {stats['total_assets']} assets | "
            f"{stats['total_size']:,} bytes"
        )
        self.archive_status.setText(f"Archive: {archive.config.name} ({stats['total_assets']} assets)")
        self.add_files_desc.setText("Select files or folders to add to your archive")
    
    def add_files(self):
        if not self.current_archive:
            return
        
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Files to Archive", "",
            "All Files (*)"
        )
        
        if files:
            self.ingest_files_with_profile([Path(f) for f in files])
    
    def add_folder(self):
        if not self.current_archive:
            return
        
        folder = QFileDialog.getExistingDirectory(
            self, "Add Folder to Archive"
        )
        
        if folder:
            self.ingest_files_with_profile([Path(folder)])
    
    def ingest_files_with_profile(self, paths: list[Path]):
        """Ingest files with individual profile selection and metadata collection per file."""
        if not self.current_archive:
            return
        
        # Load available profiles once
        try:
            from ..models import Profile
            profile_files = self.current_archive.get_profiles()
            profiles = []
            for profile_file in profile_files:
                profiles.append(Profile.load_from_file(profile_file))
            
            if not profiles:
                reply = QMessageBox.question(
                    self, "No Profiles",
                    "No profiles are available. Would you like to add files without metadata?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.ingest_files(paths)
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load profiles:\n{e}")
            return
        
        # Expand all paths to individual files
        all_files = []
        for path in paths:
            if path.is_file():
                all_files.append(path)
            elif path.is_dir():
                # Recursively find all files in directory
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        all_files.append(file_path)
        
        if not all_files:
            QMessageBox.information(self, "No Files", "No files found to add.")
            return
        
        # Process each file individually
        from ..core.ingestion import FileIngestionService
        from ..core.indexing import IndexingService
        
        ingestion = FileIngestionService(self.current_archive)
        indexing = IndexingService(self.current_archive)
        
        # Set up progress callback
        def progress_callback(current, total, message):
            self.show_progress(current, total, message)
        
        ingestion.set_progress_callback(progress_callback)
        
        successful_assets = 0
        total_files = len(all_files)
        
        try:
            for i, file_path in enumerate(all_files):
                # Create detailed file info for dialogs
                file_size = file_path.stat().st_size
                file_size_str = f"{file_size:,} bytes"
                if file_size > 1024:
                    file_size_str = f"{file_size/1024:.1f} KB"
                if file_size > 1024*1024:
                    file_size_str = f"{file_size/(1024*1024):.1f} MB"
                
                file_info = f"File: {file_path.name}\nLocation: {file_path.parent}\nSize: {file_size_str}\nProgress: File {i+1} of {total_files}"
                
                # Update progress
                self.show_progress(i + 1, total_files, f"Processing {file_path.name}...")
                
                # Show profile selection for this specific file
                profile_dialog = ProfileSelectionDialog(profiles, self, file_info)
                profile_dialog.setWindowTitle(f"Select Profile - File {i+1}/{total_files}")
                
                if profile_dialog.exec() != ProfileSelectionDialog.DialogCode.Accepted:
                    # User cancelled - ask if they want to skip this file or cancel all
                    reply = QMessageBox.question(
                        self, "Cancel File",
                        f"Skip '{file_path.name}' and continue with remaining files?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        continue  # Skip this file
                    elif reply == QMessageBox.StandardButton.No:
                        break  # Cancel all remaining files
                    else:  # Cancel button
                        break
                
                selected_profile = profile_dialog.get_selected_profile()
                if not selected_profile:
                    continue
                
                # Show metadata collection dialog for this file if profile has fields
                custom_metadata = {}
                if selected_profile.fields:
                    metadata_dialog = MetadataCollectionDialog(selected_profile, self, file_info)
                    metadata_dialog.setWindowTitle(f"Metadata - File {i+1}/{total_files}")
                    
                    if metadata_dialog.exec() != MetadataCollectionDialog.DialogCode.Accepted:
                        # User cancelled metadata - ask if they want to skip this file
                        reply = QMessageBox.question(
                            self, "Cancel Metadata",
                            f"Skip metadata for '{file_path.name}' and continue?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.Yes:
                            continue  # Skip this file
                        else:
                            break  # Cancel all remaining files
                    
                    custom_metadata = metadata_dialog.get_metadata()
                
                # Ingest this specific file
                try:
                    asset = ingestion.ingest_file(file_path, profile=selected_profile, custom_metadata=custom_metadata)
                    indexing.index_asset(asset)
                    successful_assets += 1
                except Exception as e:
                    QMessageBox.warning(
                        self, "File Ingestion Error", 
                        f"Failed to ingest '{file_path.name}':\n{e}\n\nContinue with remaining files?"
                    )
                    continue
            
            # Final status update
            if successful_assets > 0:
                self.show_status(f"Added {successful_assets} of {total_files} files")
                
                # Refresh archive status and browser only once at the end
                if self.current_archive:
                    try:
                        from ..core.indexing import IndexingService
                        indexing = IndexingService(self.current_archive)
                        stats = indexing.get_statistics()
                        self.archive_status.setText(f"Archive: {self.current_archive.config.name} ({stats['total_assets']} assets)")
                        self.archive_info_label.setText(
                            f"{self.current_archive.config.name} | {stats['total_assets']} assets | "
                            f"{stats['total_size']:,} bytes"
                        )
                        
                        # Archive browser removed - no refresh needed
                    except Exception as e:
                        logger.warning(f"Failed to refresh archive browser: {e}")
            else:
                self.show_status("No files were added")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add files:\n{e}")
        finally:
            self.show_progress(0, 0)
    
    def ingest_files(self, paths: list[Path], profile=None, custom_metadata=None):
        from ..core.ingestion import FileIngestionService
        from ..core.indexing import IndexingService
        
        ingestion = FileIngestionService(self.current_archive)
        indexing = IndexingService(self.current_archive)
        
        # Set up progress callback
        def progress_callback(current, total, message):
            self.show_progress(current, total, message)
        
        ingestion.set_progress_callback(progress_callback)
        
        try:
            total_assets = 0
            for path in paths:
                if path.is_file():
                    asset = ingestion.ingest_file(path, profile=profile, custom_metadata=custom_metadata)
                    indexing.index_asset(asset)
                    total_assets += 1
                elif path.is_dir():
                    assets = ingestion.ingest_directory(path, profile=profile, custom_metadata=custom_metadata)
                    for asset in assets:
                        indexing.index_asset(asset)
                    total_assets += len(assets)
            
            profile_text = f" with profile '{profile.name}'" if profile else ""
            self.show_status(f"Added {total_assets} assets{profile_text}")
            
            # Refresh archive status
            if self.current_archive:
                from ..core.indexing import IndexingService
                indexing = IndexingService(self.current_archive)
                stats = indexing.get_statistics()
                self.archive_status.setText(f"Archive: {self.current_archive.config.name} ({stats['total_assets']} assets)")
                self.archive_info_label.setText(
                    f"{self.current_archive.config.name} | {stats['total_assets']} assets | "
                    f"{stats['total_size']:,} bytes"
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add files:\n{e}")
        finally:
            self.show_progress(0, 0)
    
    def rebuild_index(self):
        if not self.current_archive:
            return
        
        from ..core.indexing import IndexingService
        
        reply = QMessageBox.question(
            self, "Rebuild Index",
            "This will rebuild the search index from scratch. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                indexing = IndexingService(self.current_archive)
                success, errors = indexing.index_all_assets(force_reindex=True)
                
                self.show_status(f"Index rebuilt: {success} successful, {errors} errors")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rebuild index:\n{e}")
    
    def verify_integrity(self):
        if not self.current_archive:
            return
        
        self.tab_widget.setCurrentIndex(2)  # Switch to integrity tab
        self.integrity_widget.start_verification()
    
    def export_archive(self):
        if not self.current_archive:
            return
        
        self.tab_widget.setCurrentIndex(3)  # Switch to export tab
    
    def show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def show_about(self):
        QMessageBox.about(
            self, "About Archive Tool",
            "<h2>Archive Tool v1.0</h2>"
            "<p>A desktop application for building large-scale, "
            "self-contained, and future-proof archives.</p>"
            "<p>Built with Python and PyQt6</p>"
        )
    
    def on_archive_changed(self, archive: Optional[Archive]):
        # Update all widgets with new archive
        self.search_widget.set_archive(archive)
        self.profile_manager.set_archive(archive)
        self.integrity_widget.set_archive(archive)
        self.export_widget.set_archive(archive)
    
    def on_search_performed(self, query: str):
        # Handle search performed
        self.show_status(f"Search: {query}")
    
    def load_settings(self):
        # Load application settings
        pass
    
    def save_settings(self):
        # Save application settings
        pass
    
    def closeEvent(self, event):
        self.save_settings()
        event.accept()