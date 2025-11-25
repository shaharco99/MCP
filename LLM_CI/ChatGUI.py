from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFileDialog,
)

from Utils import get_llm_provider, process_prompt, reset_chat_usage_log, system_message, execute_tool


class Worker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt: str, llm, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.llm = llm

    def run(self):
        try:
            response = process_prompt(self.prompt, self.llm, verbose=False, usage_mode='chat')
            self.finished.emit(response)
        except Exception as exc:
            self.error.emit(str(exc))


class MessageBubble(QWidget):
    """Custom message bubble widget with timestamp and role styling."""
    
    def __init__(self, message: str, is_user: bool, timestamp: str = None, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        #self.setMaximumWidth(700)  # Set max width for bubbles to allow wrapping
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Timestamp label
        if timestamp:
            ts_label = QLabel(timestamp)
            ts_font = QFont()
            ts_font.setPointSize(8)
            ts_label.setFont(ts_font)
            ts_label.setStyleSheet("color: #888;")
            layout.addWidget(ts_label)
        
        # Message text
        text_label = QLabel(message)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        #text_label.setMinimumWidth(100)  # Ensure minimum width for proper wrapping
        
        msg_font = QFont()
        msg_font.setPointSize(10)
        text_label.setFont(msg_font)
        
        # Style based on role
        if is_user:
            # User message: blue background, white text, right-aligned
            text_label.setStyleSheet(
                """
                QWidget {
                    background-color: #d9fdd3;"
                    "padding: 8px 12px; "
                    "border-radius: 14px; "
                }
                """
            )
            layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignRight)
        else:
            # Assistant message: light gray background, dark text, left-aligned
            text_label.setStyleSheet(
                "QWidget { "
                "background-color: #e6e6e6; "
                "color: #333; "
                "padding: 8px 12px; "
                "border-radius: 14px; "
                "}"
            )
            layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignLeft)
        
        self.setLayout(layout)


class ChatWindow(QMainWindow):
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
        self.setWindowTitle('MCP — DevOps Chat Assistant')
        self.resize(900, 700)
        
        # Set dark/light theme colors
        self.setStyleSheet(
            "QMainWindow { background-color: #f5f5f5; }"
            "QLineEdit { padding: 8px; border: 1px solid #ddd; border-radius: 4px; }"
            "QPushButton { padding: 8px 16px; background-color: #0078d4; color: white; "
            "border: none; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #005a9e; }"
        )
        
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header
        header = QLabel('💬 DevOps Chat Assistant')
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        main_layout.addWidget(header)
        
        # Scrollable chat view
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #ddd; border-radius: 4px; }")
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout()
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()
        self.chat_container.setLayout(self.chat_layout)
        
        scroll.setWidget(self.chat_container)
        main_layout.addWidget(scroll)
        
        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(5)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText('Type your message or ask to review/load a file...')
        self.input.returnPressed.connect(self.on_send)
        input_layout.addWidget(self.input)
        
        # Upload file button
        self.upload_btn = QPushButton('📎 Upload')
        self.upload_btn.clicked.connect(self.on_upload_file)
        input_layout.addWidget(self.upload_btn)
        
        # Send button
        self.send_btn = QPushButton('Send')
        self.send_btn.clicked.connect(self.on_send)
        input_layout.addWidget(self.send_btn)
        
        main_layout.addLayout(input_layout)
        
        central.setLayout(main_layout)
        
        # Initialize chat
        reset_chat_usage_log()
        self.append_system_message()
        self.input.setFocus()

    def append_system_message(self):
        """Display the system message (guidance) on startup."""
        bubble = MessageBubble(system_message, is_user=False, timestamp=self.get_timestamp())
        self.chat_layout.removeItem(self.chat_layout.itemAt(self.chat_layout.count() - 1))
        self.chat_layout.addWidget(bubble)
        self.chat_layout.addStretch()
        self.scroll_to_bottom()

    def append_user(self, text: str):
        """Add user message bubble."""
        bubble = MessageBubble(text, is_user=True, timestamp=self.get_timestamp())
        self.chat_layout.removeItem(self.chat_layout.itemAt(self.chat_layout.count() - 1))
        self.chat_layout.addWidget(bubble)
        self.chat_layout.addStretch()
        self.scroll_to_bottom()

    def append_ai(self, text: str):
        """Add assistant message bubble."""
        bubble = MessageBubble(text, is_user=False, timestamp=self.get_timestamp())
        self.chat_layout.removeItem(self.chat_layout.itemAt(self.chat_layout.count() - 1))
        self.chat_layout.addWidget(bubble)
        self.chat_layout.addStretch()
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        """Scroll chat view to the bottom."""
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            scroll_area.verticalScrollBar().setValue(
                scroll_area.verticalScrollBar().maximum()
            )

    def get_timestamp(self) -> str:
        """Return formatted timestamp."""
        return datetime.now().strftime('%H:%M:%S')

    def on_send(self):
        """Handle send button click or Return key."""
        prompt = self.input.text().strip()
        if not prompt:
            return
        
        self.append_user(prompt)
        self.input.clear()
        self.input.setDisabled(True)
        self.send_btn.setDisabled(True)
        self.upload_btn.setDisabled(True)
        
        # Start worker thread
        self.worker = Worker(prompt, self.llm)
        self.worker.finished.connect(self.on_response)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_response(self, response: str):
        """Handle LLM response."""
        self.append_ai(response)
        self.input.setDisabled(False)
        self.send_btn.setDisabled(False)
        self.upload_btn.setDisabled(False)
        self.input.setFocus()

    def on_error(self, err: str):
        """Handle error from LLM."""
        self.append_ai(f"⚠️ Error: {err}")
        self.input.setDisabled(False)
        self.send_btn.setDisabled(False)
        self.upload_btn.setDisabled(False)

    def on_upload_file(self):
        """Handle file upload button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            'Select a file to load',
            os.getcwd(),
            'All Files (*);;Python Files (*.py);;Text Files (*.txt);;PDF Files (*.pdf);;CSV Files (*.csv);;JSON Files (*.json)'
        )
        
        if not file_path:
            return
        
        file_name = os.path.basename(file_path)
        
        # Auto-detect file type and construct default message
        if file_name.endswith('.py'):
            default_prompt = f"Review the code in {file_name} and suggest improvements."
        else:
            default_prompt = f"Load and summarize the contents of {file_name}."
        
        # Show upload confirmation and populate input field (don't auto-send)
        self.append_user(f"📁 Uploaded: {file_name}")
        self.input.setText(default_prompt)
        self.input.setFocus()
        # Move cursor to end of input so user can add more text
        self.input.end(False)


def run_gui():
    """Initialize and run the PyQt6 GUI application."""
    llm = get_llm_provider()
    
    app = QApplication(sys.argv)
    w = ChatWindow(llm)
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    run_gui()

