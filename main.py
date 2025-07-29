#!/usr/bin/env python3

import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDir
from PyQt6.QtGui import QIcon

from src.ui.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('archive_tool.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Archive Tool")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Archive Tool")
    app.setOrganizationDomain("archive-tool.local")
    
    # Set application icon if available
    icon_path = Path(__file__).parent / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Create main window
    main_window = MainWindow()
    main_window.show()
    
    logger.info("Archive Tool started")
    
    # Run application
    sys.exit(app.exec())


if __name__ == '__main__':
    main()