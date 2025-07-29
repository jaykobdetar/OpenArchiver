from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QContextMenuEvent

from ..models import Archive
from ..core.search import SearchService


class ArchiveBrowser(QWidget):
    file_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.archive: Optional[Archive] = None
        self.search_service: Optional[SearchService] = None
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Size", "Type", "Modified"])
        
        # Configure columns
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Connect signals
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.tree)
    
    def set_archive(self, archive: Optional[Archive]):
        self.archive = archive
        if archive:
            self.search_service = SearchService(archive)
            self.refresh()
        else:
            self.search_service = None
            self.tree.clear()
    
    def refresh(self):
        if not self.archive or not self.search_service:
            return
        
        self.tree.clear()
        
        try:
            # Get all assets
            results, total = self.search_service.search(limit=1000)
            
            # Organize by directory structure
            directories = {}
            
            for result in results:
                path_parts = Path(result.archive_path).parts
                
                # Build directory tree
                current_dict = directories
                for part in path_parts[:-1]:  # All but the filename
                    if part not in current_dict:
                        current_dict[part] = {}
                    current_dict = current_dict[part]
                
                # Add file to the final directory
                filename = path_parts[-1]
                current_dict[filename] = result
            
            # Populate tree
            self._populate_tree_recursive(self.tree.invisibleRootItem(), directories)
            
            # Expand first level
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                item.setExpanded(True)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load archive contents:\n{e}")
    
    def _populate_tree_recursive(self, parent_item, directory_dict):
        for name, content in sorted(directory_dict.items()):
            if hasattr(content, 'file_name'):  # It's a search result (file)
                item = QTreeWidgetItem(parent_item)
                item.setText(0, content.file_name)
                item.setText(1, self._format_size(content.file_size))
                item.setText(2, content.mime_type or "Unknown")
                item.setText(3, content.created_at[:10])  # Just the date part
                
                # Store the search result
                item.setData(0, Qt.ItemDataRole.UserRole, content)
                
            else:  # It's a directory
                item = QTreeWidgetItem(parent_item)
                item.setText(0, name)
                item.setText(1, "")
                item.setText(2, "Folder")
                item.setText(3, "")
                
                # Recursively populate subdirectories
                self._populate_tree_recursive(item, content)
    
    def _format_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} PB"
    
    def on_selection_changed(self):
        items = self.tree.selectedItems()
        if items:
            item = items[0]
            search_result = item.data(0, Qt.ItemDataRole.UserRole)
            if search_result:
                self.file_selected.emit(search_result.archive_path)
    
    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        search_result = item.data(0, Qt.ItemDataRole.UserRole)
        if search_result:
            # Open file with system default application
            file_path = self.archive.root_path / search_result.archive_path
            if file_path.exists():
                import subprocess
                import platform
                
                try:
                    if platform.system() == "Darwin":  # macOS
                        subprocess.call(["open", str(file_path)])
                    elif platform.system() == "Windows":
                        subprocess.call(["start", str(file_path)], shell=True)
                    else:  # Linux
                        subprocess.call(["xdg-open", str(file_path)])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open file:\n{e}")
    
    def contextMenuEvent(self, event: QContextMenuEvent):
        item = self.tree.itemAt(event.pos())
        if not item:
            return
        
        search_result = item.data(0, Qt.ItemDataRole.UserRole)
        if not search_result:
            return
        
        menu = QMenu(self)
        
        # Open file
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self.on_item_double_clicked(item, 0))
        
        # Show in file manager
        show_action = menu.addAction("Show in File Manager")
        show_action.triggered.connect(lambda: self.show_in_file_manager(search_result))
        
        menu.addSeparator()
        
        # Copy path
        copy_path_action = menu.addAction("Copy Path")
        copy_path_action.triggered.connect(lambda: self.copy_to_clipboard(search_result.archive_path))
        
        # Copy checksum
        if search_result.checksum_sha256:
            copy_checksum_action = menu.addAction("Copy Checksum")
            copy_checksum_action.triggered.connect(
                lambda: self.copy_to_clipboard(search_result.checksum_sha256)
            )
        
        menu.exec(event.globalPos())
    
    def show_in_file_manager(self, search_result):
        file_path = self.archive.root_path / search_result.archive_path
        if file_path.exists():
            import subprocess
            import platform
            
            try:
                if platform.system() == "Darwin":  # macOS
                    subprocess.call(["open", "-R", str(file_path)])
                elif platform.system() == "Windows":
                    subprocess.call(["explorer", "/select,", str(file_path)])
                else:  # Linux
                    subprocess.call(["xdg-open", str(file_path.parent)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to show file:\n{e}")
    
    def copy_to_clipboard(self, text: str):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)