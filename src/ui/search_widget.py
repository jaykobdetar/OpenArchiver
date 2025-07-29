from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLabel, QSpinBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..models import Archive
from ..core.search import SearchService


class SearchWidget(QWidget):
    search_performed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.archive: Optional[Archive] = None
        self.search_service: Optional[SearchService] = None
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Search controls
        search_group = QGroupBox("Search")
        search_layout = QVBoxLayout(search_group)
        
        # Search input
        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search query...")
        self.search_input.returnPressed.connect(self.perform_search)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_search)
        
        search_input_layout.addWidget(self.search_input)
        search_input_layout.addWidget(self.search_button)
        search_layout.addLayout(search_input_layout)
        
        # Filters
        filters_layout = QFormLayout()
        
        # MIME type filter
        self.mime_filter = QComboBox()
        self.mime_filter.addItem("All Types", None)
        filters_layout.addRow("File Type:", self.mime_filter)
        
        # Size filters
        size_layout = QHBoxLayout()
        self.size_min = QSpinBox()
        self.size_min.setMaximum(999999999)
        self.size_min.setSuffix(" bytes")
        self.size_max = QSpinBox()
        self.size_max.setMaximum(999999999)
        self.size_max.setSuffix(" bytes")
        size_layout.addWidget(self.size_min)
        size_layout.addWidget(QLabel("to"))
        size_layout.addWidget(self.size_max)
        filters_layout.addRow("Size:", size_layout)
        
        # Results limit
        self.limit_spin = QSpinBox()
        self.limit_spin.setMinimum(1)
        self.limit_spin.setMaximum(10000)
        self.limit_spin.setValue(100)
        filters_layout.addRow("Max Results:", self.limit_spin)
        
        search_layout.addLayout(filters_layout)
        layout.addWidget(search_group)
        
        # Results table
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Name", "Size", "Type", "Created", "Checksum", "Path"
        ])
        
        # Configure table
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        results_layout.addWidget(self.results_table)
        
        # Results info
        self.results_info = QLabel("No search performed")
        results_layout.addWidget(self.results_info)
        
        layout.addWidget(results_group)
        
        # Initially disable search
        self.set_search_enabled(False)
    
    def set_archive(self, archive: Optional[Archive]):
        self.archive = archive
        if archive:
            self.search_service = SearchService(archive)
            self.set_search_enabled(True)
            self.populate_filters()
        else:
            self.search_service = None
            self.set_search_enabled(False)
            self.clear_results()
    
    def set_search_enabled(self, enabled: bool):
        self.search_input.setEnabled(enabled)
        self.search_button.setEnabled(enabled)
        self.mime_filter.setEnabled(enabled)
        self.size_min.setEnabled(enabled)
        self.size_max.setEnabled(enabled)
        self.limit_spin.setEnabled(enabled)
    
    def populate_filters(self):
        if not self.search_service:
            return
        
        # Clear existing MIME types
        self.mime_filter.clear()
        self.mime_filter.addItem("All Types", None)
        
        try:
            # Get available MIME types from index
            stats = self.search_service.get_statistics()
            if 'by_type' in stats:
                for mime_type in sorted(stats['by_type'].keys()):
                    if mime_type != 'unknown':
                        display_name = mime_type.split('/')[0].title() if '/' in mime_type else mime_type
                        self.mime_filter.addItem(display_name, mime_type)
        except Exception as e:
            print(f"Error populating filters: {e}")
    
    def perform_search(self):
        if not self.search_service:
            return
        
        query = self.search_input.text().strip()
        
        # Build filters
        filters = {}
        
        # MIME type filter
        mime_type = self.mime_filter.currentData()
        if mime_type:
            filters['mime_type'] = mime_type
        
        # Size filters
        if self.size_min.value() > 0:
            filters['file_size_min'] = self.size_min.value()
        if self.size_max.value() > 0:
            filters['file_size_max'] = self.size_max.value()
        
        try:
            # Perform search
            results, total = self.search_service.search(
                query=query if query else None,
                filters=filters if filters else None,
                limit=self.limit_spin.value()
            )
            
            # Update results table
            self.populate_results(results, total, query)
            
            # Emit signal
            self.search_performed.emit(query)
            
        except Exception as e:
            self.results_info.setText(f"Search error: {e}")
    
    def populate_results(self, results, total, query):
        self.results_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            # Name
            name_item = QTableWidgetItem(result.file_name)
            name_item.setData(Qt.ItemDataRole.UserRole, result)
            self.results_table.setItem(row, 0, name_item)
            
            # Size
            size_item = QTableWidgetItem(self._format_size(result.file_size))
            size_item.setData(Qt.ItemDataRole.UserRole, result.file_size)
            self.results_table.setItem(row, 1, size_item)
            
            # Type
            type_item = QTableWidgetItem(result.mime_type or "Unknown")
            self.results_table.setItem(row, 2, type_item)
            
            # Created
            created_item = QTableWidgetItem(result.created_at[:10])  # Just date
            self.results_table.setItem(row, 3, created_item)
            
            # Checksum (first 16 chars)
            checksum_text = result.checksum_sha256[:16] + "..." if result.checksum_sha256 else ""
            checksum_item = QTableWidgetItem(checksum_text)
            if result.checksum_sha256:
                checksum_item.setToolTip(result.checksum_sha256)
            self.results_table.setItem(row, 4, checksum_item)
            
            # Path
            path_item = QTableWidgetItem(result.archive_path)
            self.results_table.setItem(row, 5, path_item)
        
        # Update info label
        query_text = f" for '{query}'" if query else ""
        self.results_info.setText(f"Found {total} results{query_text} (showing {len(results)})")
    
    def clear_results(self):
        self.results_table.setRowCount(0)
        self.results_info.setText("No search performed")
    
    def _format_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} PB"