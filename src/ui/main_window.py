import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QMenuBar, QMenu, QToolBar, QStatusBar, QLabel, QProgressBar,
    QMessageBox, QFileDialog, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence

from ..models import Archive
from .archive_browser import ArchiveBrowser
from .search_widget import SearchWidget
from .profile_manager import ProfileManager
from .integrity_widget import IntegrityWidget
from .export_widget import ExportWidget
from .dialogs import NewArchiveDialog, OpenArchiveDialog

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
        
        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - Archive browser
        self.archive_browser = ArchiveBrowser()
        splitter.addWidget(self.archive_browser)
        
        # Right panel - Tabs
        self.tab_widget = QTabWidget()
        splitter.addWidget(self.tab_widget)
        
        # Search tab
        self.search_widget = SearchWidget()
        self.tab_widget.addTab(self.search_widget, "Search")
        
        # Profile manager tab
        self.profile_manager = ProfileManager()
        self.tab_widget.addTab(self.profile_manager, "Profiles")
        
        # Integrity tab
        self.integrity_widget = IntegrityWidget()
        self.tab_widget.addTab(self.integrity_widget, "Integrity")
        
        # Export tab
        self.export_widget = ExportWidget()
        self.tab_widget.addTab(self.export_widget, "Export")
        
        # Set splitter proportions
        splitter.setSizes([400, 800])
        
        # Connect widget signals
        self.archive_browser.file_selected.connect(self.on_file_selected)
        self.search_widget.search_performed.connect(self.on_search_performed)
    
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
        new_action = QAction("New", self)
        new_action.setToolTip("Create new archive")
        new_action.triggered.connect(self.new_archive)
        toolbar.addAction(new_action)
        
        # Open archive
        open_action = QAction("Open", self)
        open_action.setToolTip("Open existing archive")
        open_action.triggered.connect(self.open_archive)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        # Add files
        self.add_files_action = QAction("Add Files", self)
        self.add_files_action.setToolTip("Add files to archive")
        self.add_files_action.triggered.connect(self.add_files)
        self.add_files_action.setEnabled(False)
        toolbar.addAction(self.add_files_action)
        
        # Search
        self.search_action = QAction("Search", self)
        self.search_action.setToolTip("Search archive")
        self.search_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(0))
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
            self.add_files_action.setEnabled(False)
            self.search_action.setEnabled(False)
            self.archive_info_label.setText("")
            self.show_status("Archive closed")
    
    def load_archive(self, archive: Archive):
        self.current_archive = archive
        self.archive_changed.emit(archive)
        self.archive_menu.setEnabled(True)
        self.add_files_action.setEnabled(True)
        self.search_action.setEnabled(True)
        
        # Update status
        from ..core.indexing import IndexingService
        indexing = IndexingService(archive)
        stats = indexing.get_statistics()
        self.archive_info_label.setText(
            f"{archive.config.name} | {stats['total_assets']} assets | "
            f"{stats['total_size']:,} bytes"
        )
    
    def add_files(self):
        if not self.current_archive:
            return
        
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Files to Archive", "",
            "All Files (*)"
        )
        
        if files:
            self.ingest_files([Path(f) for f in files])
    
    def add_folder(self):
        if not self.current_archive:
            return
        
        folder = QFileDialog.getExistingDirectory(
            self, "Add Folder to Archive"
        )
        
        if folder:
            self.ingest_files([Path(folder)])
    
    def ingest_files(self, paths: list[Path]):
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
                    asset = ingestion.ingest_file(path)
                    indexing.index_asset(asset)
                    total_assets += 1
                elif path.is_dir():
                    assets = ingestion.ingest_directory(path)
                    for asset in assets:
                        indexing.index_asset(asset)
                    total_assets += len(assets)
            
            self.show_status(f"Added {total_assets} assets")
            self.archive_browser.refresh()
            
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
        self.archive_browser.set_archive(archive)
        self.search_widget.set_archive(archive)
        self.profile_manager.set_archive(archive)
        self.integrity_widget.set_archive(archive)
        self.export_widget.set_archive(archive)
    
    def on_file_selected(self, file_path: str):
        # Handle file selection from browser
        pass
    
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