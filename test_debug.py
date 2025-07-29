#!/usr/bin/env python3

"""Quick debug test to understand export widget behavior"""

import sys
from PyQt6.QtWidgets import QApplication
from src.ui.export_widget import ExportWidget

def main():
    app = QApplication([])
    
    widget = ExportWidget()
    
    print(f"Format combo count: {widget.format_combo.count()}")
    print(f"Current index: {widget.format_combo.currentIndex()}")
    print(f"Current data: {widget.format_combo.currentData()}")
    print(f"Current text: {widget.format_combo.currentText()}")
    print(f"BagIt group visible (before): {widget.bagit_group.isVisible()}")
    print(f"BagIt group enabled (before): {widget.bagit_group.isEnabled()}")
    
    # Call the format changed method
    widget.on_format_changed()
    print(f"BagIt group visible (after format_changed): {widget.bagit_group.isVisible()}")
    
    # Try setting index explicitly
    widget.format_combo.setCurrentIndex(0)
    widget.on_format_changed()
    print(f"BagIt group visible (after set index 0): {widget.bagit_group.isVisible()}")
    
    # Check data for both indices
    print(f"Index 0 data: {widget.format_combo.itemData(0)}")
    print(f"Index 1 data: {widget.format_combo.itemData(1)}")
    
    # Debug the on_format_changed logic step by step
    print(f"\nDebugging on_format_changed:")
    print(f"Current data: '{widget.format_combo.currentData()}'")
    print(f"Is 'bagit'?: {widget.format_combo.currentData() == 'bagit'}")
    is_bagit = widget.format_combo.currentData() == "bagit"
    print(f"is_bagit variable: {is_bagit}")
    
    # Manually set visibility to test
    print(f"\nManually setting visibility to True:")
    widget.bagit_group.setVisible(True)
    print(f"BagIt group visible (after manual): {widget.bagit_group.isVisible()}")

if __name__ == "__main__":
    main()