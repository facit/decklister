import sys
import os
import subprocess
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit, QGroupBox,
    QProgressBar, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont

try:
    from .deck_image_generator import DeckImageGenerator
    from .config import Config
except ImportError:
    from decklister.deck_image_generator import DeckImageGenerator
    from decklister.config import Config


class LogSignal(QObject):
    """Signal bridge to send log messages from worker threads to the GUI."""
    message = Signal(str)
    finished = Signal(bool, str)  # success, message


class DeckListerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Deck Image Generator")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon_256.png")
        if os.path.isfile(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        self.log_signal = LogSignal()
        self.log_signal.message.connect(self._append_log)
        self.log_signal.finished.connect(self._on_finished)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Input Files ---
        input_group = QGroupBox("Input Files")
        input_layout = QVBoxLayout(input_group)

        # Deck file
        deck_row = QHBoxLayout()
        deck_row.addWidget(QLabel("Deck File:"))
        self.deck_input = QLineEdit()
        self.deck_input.setPlaceholderText("Select a deck JSON or Melee CSV file...")
        self.deck_input.textChanged.connect(self._update_csv_visibility)
        deck_row.addWidget(self.deck_input)
        deck_browse = QPushButton("Browse...")
        deck_browse.clicked.connect(self._browse_deck)
        deck_row.addWidget(deck_browse)
        input_layout.addLayout(deck_row)

        # Config file
        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Config File:"))
        self.config_input = QLineEdit()
        self.config_input.setPlaceholderText("Select a config JSON file...")
        config_row.addWidget(self.config_input)
        config_browse = QPushButton("Browse...")
        config_browse.clicked.connect(self._browse_config)
        config_row.addWidget(config_browse)
        input_layout.addLayout(config_row)

        # Output file (optional)
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output File:"))
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("(Optional) Auto-named if left empty")
        output_row.addWidget(self.output_input)
        output_browse = QPushButton("Browse...")
        output_browse.clicked.connect(self._browse_output)
        output_row.addWidget(output_browse)
        input_layout.addLayout(output_row)

        layout.addWidget(input_group)

        # --- CSV Options (shown only when a .csv file is selected) ---
        self.csv_group = QGroupBox("CSV Options")
        csv_layout = QVBoxLayout(self.csv_group)

        player_row = QHBoxLayout()
        player_row.addWidget(QLabel("Player:"))
        self.player_input = QLineEdit()
        self.player_input.setPlaceholderText("(Optional) Player name to select from a multi-deck CSV")
        player_row.addWidget(self.player_input)
        csv_layout.addLayout(player_row)

        index_row = QHBoxLayout()
        index_row.addWidget(QLabel("Deck Index:"))
        self.index_input = QLineEdit()
        self.index_input.setPlaceholderText("0")
        self.index_input.setText("0")
        self.index_input.setToolTip("0-based row index (used when Player is empty)")
        index_row.addWidget(self.index_input)
        index_row.addStretch()
        csv_layout.addLayout(index_row)

        self.csv_group.setVisible(False)  # Hidden until a .csv is selected
        layout.addWidget(self.csv_group)

        # --- Variant Options ---
        options_group = QGroupBox("Card Variants")
        options_layout = QHBoxLayout(options_group)

        self.hyperspace_check = QCheckBox("Hyperspace")
        self.hyperspace_check.setToolTip("Use hyperspace variants for all cards")
        options_layout.addWidget(self.hyperspace_check)

        self.showcase_check = QCheckBox("Showcase leaders")
        self.showcase_check.setToolTip("Use showcase variant art for leader cards (overrides hyperspace for leaders)")
        options_layout.addWidget(self.showcase_check)

        options_layout.addStretch()
        layout.addWidget(options_group)

        # --- Actions ---
        actions_layout = QHBoxLayout()

        self.generate_btn = QPushButton("Generate Image")
        self.generate_btn.setMinimumHeight(40)
        font = self.generate_btn.font()
        font.setPointSize(11)
        font.setBold(True)
        self.generate_btn.setFont(font)
        self.generate_btn.clicked.connect(self._generate)
        actions_layout.addWidget(self.generate_btn)

        self.config_drawer_btn = QPushButton("Open Config Drawer")
        self.config_drawer_btn.setMinimumHeight(40)
        self.config_drawer_btn.clicked.connect(self._open_config_drawer)
        actions_layout.addWidget(self.config_drawer_btn)

        self.export_examples_btn = QPushButton("Export Examples")
        self.export_examples_btn.setMinimumHeight(40)
        self.export_examples_btn.clicked.connect(self._export_examples)
        actions_layout.addWidget(self.export_examples_btn)

        layout.addLayout(actions_layout)

        # --- Progress ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # --- Log Output ---
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_output)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.log_output.clear)
        log_layout.addWidget(clear_log_btn, alignment=Qt.AlignRight)

        layout.addWidget(log_group)

    # --- File Browsers ---

    def _browse_deck(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Deck File", "",
            "Deck Files (*.json *.csv);;JSON Files (*.json);;CSV Files (*.csv);;All Files (*)"
        )
        if path:
            self.deck_input.setText(path)

    def _browse_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Config File", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            self.config_input.setText(path)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output As", "", "PNG Files (*.png);;All Files (*)"
        )
        if path:
            self.output_input.setText(path)

    # --- Generation ---

    def _generate(self):
        deck_file = self.deck_input.text().strip()
        config_file = self.config_input.text().strip()
        output_file = self.output_input.text().strip() or None

        if not deck_file:
            self._append_log("Error: No deck file selected.")
            return
        if not config_file:
            self._append_log("Error: No config file selected.")
            return
        if not os.path.isfile(deck_file):
            self._append_log(f"Error: Deck file not found: {deck_file}")
            return
        if not os.path.isfile(config_file):
            self._append_log(f"Error: Config file not found: {config_file}")
            return

        self._set_running(True)
        self._append_log(f"Starting generation...")
        self._append_log(f"  Deck: {deck_file}")
        self._append_log(f"  Config: {config_file}")
        if output_file:
            self._append_log(f"  Output: {output_file}")

        hyperspace = self.hyperspace_check.isChecked()
        showcase = self.showcase_check.isChecked()
        if hyperspace:
            self._append_log("  Variant: Hyperspace")
        if showcase:
            self._append_log("  Variant: Showcase leaders")

        # CSV-specific options
        player = None
        deck_index = 0
        if deck_file.lower().endswith(".csv"):
            player = self.player_input.text().strip() or None
            try:
                deck_index = int(self.index_input.text().strip() or "0")
            except ValueError:
                self._append_log("Error: Deck Index must be a number.")
                self._set_running(False)
                return
            if player:
                self._append_log(f"  Player: {player}")
            else:
                self._append_log(f"  Deck Index: {deck_index}")

        # Run in a thread to keep the GUI responsive
        thread = threading.Thread(
            target=self._run_generator,
            args=(deck_file, config_file, output_file, hyperspace, showcase, player, deck_index),
            daemon=True,
        )
        thread.start()

    def _run_generator(self, deck_file, config_file, output_file, hyperspace, showcase, player, deck_index):
        """Worker thread that runs the generator and streams log messages in real-time."""

        # Custom stream that emits each line to the GUI as it's written
        class SignalStream:
            def __init__(self, signal):
                self.signal = signal
                self.buffer = ""

            def write(self, text):
                self.buffer += text
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if line:
                        self.signal.emit(line)

            def flush(self):
                if self.buffer:
                    self.signal.emit(self.buffer)
                    self.buffer = ""

        stream = SignalStream(self.log_signal.message)

        try:
            config = Config.from_file(config_file)
            generator = DeckImageGenerator(config=config, hyperspace=hyperspace, showcase=showcase)

            # Replace sys.stdout directly so all print() calls in this thread go to our stream
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = stream
            sys.stderr = stream
            try:
                generator.run(deck_file, output_path=output_file, player=player, deck_index=deck_index)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            stream.flush()

            self.log_signal.finished.emit(True, "Generation complete!")

        except Exception as e:
            stream.flush()
            self.log_signal.finished.emit(False, f"Error: {e}")

    # --- Config Drawer ---

    def _open_config_drawer(self):
        """Launch the config drawer."""
        self._append_log("Opening Config Drawer...")
        try:
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller bundle — import and run directly in a thread
                def run_drawer():
                    try:
                        import tkinter as tk
                        try:
                            from .config_drawer import AreaDrawer
                        except ImportError:
                            from decklister.config_drawer import AreaDrawer
                        root = tk.Tk()
                        AreaDrawer(root)
                        root.mainloop()
                    except Exception as e:
                        self.log_signal.message.emit(f"Config Drawer error: {e}")

                thread = threading.Thread(target=run_drawer, daemon=True)
                thread.start()
            else:
                # Running in development — launch as subprocess
                subprocess.Popen(
                    [sys.executable, "-m", "decklister.config_drawer"],
                    cwd=os.getcwd(),
                )
        except Exception as e:
            self._append_log(f"Error launching Config Drawer: {e}")

    # --- Export Examples ---

    def _get_base_path(self):
        """Get the base path for bundled resources (works for both PyInstaller and dev)."""
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            return sys._MEIPASS
        else:
            # Running in development — examples are in the project root
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _export_examples(self):
        """Export bundled example files to a user-chosen folder."""
        import shutil

        target_dir = QFileDialog.getExistingDirectory(self, "Select Folder for Example Files")
        if not target_dir:
            return

        base_path = self._get_base_path()
        example_files = [
            "example_background.png",
            "example_foreground.png",
            "example_count_background.png",
            "example_config.json",
        ]

        exported = 0
        for filename in example_files:
            src = os.path.join(base_path, filename)
            dst = os.path.join(target_dir, filename)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, dst)
                    self._append_log(f"Exported: {filename}")
                    exported += 1
                except Exception as e:
                    self._append_log(f"Failed to export {filename}: {e}")
            else:
                self._append_log(f"Not found: {filename}")

        if exported > 0:
            self._append_log(f"✓ {exported} example file(s) exported to {target_dir}")
        else:
            self._append_log("✗ No example files found to export.")

    # --- UI Helpers ---

    def _update_csv_visibility(self, text):
        """Show CSV options only when a .csv file is in the deck input."""
        is_csv = text.strip().lower().endswith(".csv")
        self.csv_group.setVisible(is_csv)

    def _append_log(self, text):
        self.log_output.append(text)
        # Auto-scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # Force the GUI to process this update immediately
        QApplication.processEvents()

    def _set_running(self, running):
        self.generate_btn.setEnabled(not running)
        self.progress_bar.setVisible(running)

    def _on_finished(self, success, message):
        self._set_running(False)
        if success:
            self._append_log(f"✓ {message}")
        else:
            self._append_log(f"✗ {message}")


def main():
    app = QApplication(sys.argv)
    window = DeckListerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()