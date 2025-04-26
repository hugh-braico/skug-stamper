# native python libraries

import configparser
import os
import re

# qt stuff
# from PyQt6.QtCore import QSize, QDate, Qt, QThreadPool
from PyQt6.QtCore import QSize, QDate, Qt, QThread
from PyQt6 import QtGui
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    # high level stuff
    QMainWindow, QDialog, QMessageBox,
    # widgets
    QWidget, QPushButton, QDateEdit, QLabel, QLineEdit, QComboBox, QFileDialog,
    QCheckBox, QDialogButtonBox, QSpinBox, QTextEdit, QSlider,
    # layout stuff
    QFrame, QSplitter, QVBoxLayout, QHBoxLayout
)

from utils.cv2       import *
from utils.dates     import infer_last_weekday, get_weekday_name
from utils.timestamp import display_timestamp
from utils.csv       import version_list

# gui-specific functions
from gui.dialogs import NewPresetDialog
from gui.worker import Worker

# Main window class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Skug Stamper v1.0")
        self.setWindowIcon(QtGui.QIcon('assets/bigband.png'))

        # One background thread for processing a video
        self.thread = None

        #######################################################################
        ### Left pane layouting (Options form)

        # Preset selection
        self.config = configparser.ConfigParser()
        self.config.read('config/presets.ini')
        self.preset_label = QLabel("Current preset")
        self.preset_combobox = QComboBox()
        self.preset_combobox.addItems(self.config.keys())
        self.preset_combobox.currentTextChanged.connect(self.populate_form_from_preset)

        # Preset management
        self.preset_save_button = QPushButton("Save current preset")
        self.preset_save_button.clicked.connect(self.save_current_preset)
        self.preset_new_button = QPushButton("New preset...")
        self.preset_new_button.clicked.connect(self.preset_new_button_dialog)
        self.preset_remove_button = QPushButton("Delete current preset")
        self.preset_remove_button.clicked.connect(self.preset_remove_button_dialog)

        self.divider1 = QFrame()
        self.divider1.setFrameStyle(QFrame.Shape.HLine)
        self.divider1.setFrameShadow(QFrame.Shadow.Sunken)

        # Input file
        self.infile_name = None
        self.capture = None
        self.total_seconds = None
        self.infile_label = QLabel("No video file selected")
        self.infile_open_button = QPushButton("Open video file...")
        self.infile_open_button.clicked.connect(self.choose_infile)
        
        # Have to define display slider early because other things depend on it
        self.display_slider = QSlider(Qt.Orientation.Horizontal)
        self.display_slider.sliderMoved.connect(self.preview_video_by_slider)
        self.display_slider.setEnabled(False)

        # Game dimensions
        self.game_x_label = QLabel("Pixels between left border and game")
        self.game_x_input = QSpinBox()
        self.game_x_input.setValue(0)
        self.game_x_input.setMinimum(0)
        self.game_x_input.setMaximum(9999)
        self.game_x_input.valueChanged.connect(self.check_start_button)
        self.game_x_input.valueChanged.connect(self.preview_video_by_slider)
        self.game_y_label = QLabel("Pixels between top border and game")
        self.game_y_input = QSpinBox()
        self.game_y_input.setValue(0)
        self.game_y_input.setMinimum(0)
        self.game_y_input.setMaximum(9999)
        self.game_y_input.valueChanged.connect(self.check_start_button)
        self.game_y_input.valueChanged.connect(self.preview_video_by_slider)
        self.game_size_label = QLabel("Horizontal width of game in pixels")
        self.game_size_input = QSpinBox()
        self.game_size_input.setValue(0)
        self.game_size_input.setMinimum(0)
        self.game_size_input.setMaximum(9999)
        self.game_size_input.valueChanged.connect(self.check_start_button)
        self.game_size_input.valueChanged.connect(self.preview_video_by_slider)

        self.divider2 = QFrame()
        self.divider2.setFrameStyle(QFrame.Shape.HLine)
        self.divider2.setFrameShadow(QFrame.Shadow.Sunken)

        # Simplify the controls greatly if not interested in making a csv
        self.outfile_checkbox = QCheckBox("Also save as a TWB csv file")
        self.outfile_checkbox.stateChanged.connect(self.outfile_checkbox_clicked)

        # Output file
        self.outfile_name = None
        self.outfile_label = QLabel("No output csv file selected")
        self.outfile_label.setEnabled(False)
        self.outfile_open_button = QPushButton("Choose output csv file...")
        self.outfile_open_button.clicked.connect(self.choose_outfile)
        self.outfile_open_button.setEnabled(False)

        # Event name
        self.event_label = QLabel("Event name")
        self.event_label.setEnabled(False)
        self.event_input = QLineEdit()
        self.event_input.setEnabled(False)
        self.event_input.textChanged.connect(self.check_start_button)

        # Date picker
        self.date_label = QLabel("Event date")
        self.date_label.setEnabled(False)
        self.date_picker = QDateEdit(
            calendarPopup=True, 
            displayFormat='yyyy-MM-dd', 
            date=QDate.currentDate()
        )
        self.date_picker.setEnabled(False)

        # Region selector
        self.region_label = QLabel("Event region")
        self.region_label.setEnabled(False)
        self.region_combobox = QComboBox()
        self.region_list = [
            "Europe", 
            "Asia", 
            "North America", 
            "Oceania", 
            "South America"
        ]
        self.region_combobox.addItems(self.region_list)
        self.region_combobox.setEnabled(False)

        # Netplay
        self.netplay_checkbox = QCheckBox("Netplay")
        self.netplay_checkbox.setEnabled(False)

        # Version
        self.version_label = QLabel("Game version")
        self.version_label.setEnabled(False)
        self.version_combobox = QComboBox()
        self.version_combobox.addItems(version_list)
        self.version_combobox.setEnabled(False)

        # URL
        self.url_label = QLabel("Vod URL")
        self.url_label.setEnabled(False)
        self.url_input = QLineEdit()
        self.url_input.setEnabled(False)
        self.url_input.textChanged.connect(self.check_start_button)

        # Start button
        self.start_button = QPushButton("Create timestamps")
        self.start_button_font = self.start_button.font()
        self.start_button_font.setBold(True)
        self.start_button.setFont(self.start_button_font)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.process_video)

        # Pre-populate fields from preset
        self.populate_form_from_preset()

        self.form_layout = QVBoxLayout()
        self.form_layout.setContentsMargins(0,0,0,0)

        # Preset stuff
        self.form_layout.addWidget(self.preset_label)
        self.form_layout.addWidget(self.preset_combobox)
        self.form_layout.addWidget(self.preset_save_button)
        self.form_layout.addWidget(self.preset_new_button)
        self.form_layout.addWidget(self.preset_remove_button)
        self.form_layout.addWidget(self.divider1)
        # Mandatory stuff
        self.form_layout.addWidget(self.infile_label)
        self.form_layout.addWidget(self.infile_open_button)
        self.form_layout.addWidget(self.game_x_label)
        self.form_layout.addWidget(self.game_x_input)
        self.form_layout.addWidget(self.game_y_label)
        self.form_layout.addWidget(self.game_y_input)
        self.form_layout.addWidget(self.game_size_label)
        self.form_layout.addWidget(self.game_size_input)
        self.form_layout.addWidget(self.divider2)
        # CSV specific options
        self.form_layout.addWidget(self.outfile_checkbox)
        self.form_layout.addWidget(self.outfile_label)
        self.form_layout.addWidget(self.outfile_open_button)
        self.form_layout.addWidget(self.event_label)
        self.form_layout.addWidget(self.event_input)
        self.form_layout.addWidget(self.date_label)
        self.form_layout.addWidget(self.date_picker)
        self.form_layout.addWidget(self.region_label)
        self.form_layout.addWidget(self.region_combobox)
        self.form_layout.addWidget(self.netplay_checkbox)
        self.form_layout.addWidget(self.version_label)
        self.form_layout.addWidget(self.version_combobox)
        self.form_layout.addWidget(self.url_label)
        self.form_layout.addWidget(self.url_input)
        # And lastly, the start button
        self.form_layout.addWidget(self.start_button)

        # Widget that encapsulates all the form controls except cancel button
        self.form_container = QWidget()
        self.form_container.setFixedSize(QSize(275,720))
        self.form_container.setLayout(self.form_layout)

        # Cancel button gets its own layout because it's a special boy
        # (want to be able to disable all the form at once, except this button)
        self.cancel_button = QPushButton("Cancel / Finish Early")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_worker)
        self.left_pane_layout = QVBoxLayout()
        self.left_pane_layout.setContentsMargins(0,0,0,0)
        self.left_pane_layout.addWidget(self.form_container)
        self.left_pane_layout.addWidget(self.cancel_button)
        self.left_pane_container = QWidget()
        self.left_pane_container.setLayout(self.left_pane_layout)

        #######################################################################
        ### Centre pane layouting (Video preview and progress bar)

        # Widget that displays frames from the video
        self.display_widget = QLabel()
        self.display_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        self.display_widget.setScaledContents(True)
        self.display_widget.setFixedSize(QSize(960,540))
        self.display_label = QLabel("0:00:00")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_label.setFixedSize(QSize(960,50))
        self.centre_pane_layout = QVBoxLayout()
        self.centre_pane_layout.setSpacing(5)
        self.centre_pane_layout.addWidget(self.display_widget)
        self.centre_pane_layout.addWidget(self.display_slider)
        self.centre_pane_layout.addWidget(self.display_label)
        self.centre_pane_container = QWidget()
        self.centre_pane_container.setLayout(self.centre_pane_layout)

        #######################################################################
        ### Right pane layouting (Output text console)

        # Widget that displays console output, timestamp results
        self.right_pane_text = QTextEdit()
        self.right_pane_text.setReadOnly(True)
        self.right_pane_text.setFixedSize(QSize(400,755))

        #######################################################################
        ### Main layout (Three side-by-side panes)

        self.main_layout = QHBoxLayout()
        self.main_layout.addWidget(self.left_pane_container)
        self.main_layout.addWidget(self.centre_pane_container)
        self.main_layout.addWidget(self.right_pane_text)
        self.main_container = QWidget()
        self.main_container.setLayout(self.main_layout)

        self.setCentralWidget(self.main_container)

    # What happens when you select a preset.
    def populate_form_from_preset(self):
        current_preset_name = self.preset_combobox.currentText()
        current_preset = self.config[current_preset_name]

        self.game_x_input.setValue(int(current_preset.get('GAME_X', 0)))
        self.game_y_input.setValue(int(current_preset.get('GAME_Y', 0)))
        self.game_size_input.setValue(int(current_preset.get('GAME_SIZE', 0)))
        self.event_input.setText(current_preset.get('EVENT', ""))

        weekday = current_preset.get('DAY', "")
        if weekday in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]:
            self.date_picker.setDate(QDate.fromString(infer_last_weekday(weekday), 'yyyy-MM-dd'))
        else:
            self.date_picker.setDate(QDate.currentDate())

        region = current_preset.get("REGION", "")
        if region in self.region_list:
            self.region_combobox.setCurrentText(region)
        else:
            self.region_combobox.setCurrentIndex(0)

        netplay = current_preset.get("NETPLAY", None)
        if netplay is not None:
            self.netplay_checkbox.setChecked(netplay == "1")

        version = current_preset.get("VERSION", "")
        if version in version_list:
            self.version_combobox.setCurrentText(version)

    # Create new preset after confirming from dialog
    def preset_new_button_dialog(self):
        dlg = NewPresetDialog(self)
        if dlg.exec():
            self.config[dlg.new_preset_name] = {}
            self.preset_combobox.insertItem(99999, dlg.new_preset_name)
            self.preset_combobox.setCurrentText(dlg.new_preset_name)

    # Save changes to a preset (write to a file at the end)
    def save_current_preset(self):
        current_preset_name = self.preset_combobox.currentText()
        current_preset = self.config[current_preset_name]

        current_preset['GAME_X'] = str(self.game_x_input.value())
        current_preset['GAME_Y'] = str(self.game_y_input.value())
        current_preset['GAME_SIZE'] = str(self.game_size_input.value())
        if self.event_input.text():
            current_preset['EVENT'] = self.event_input.text()

        current_date = self.date_picker.date()
        current_preset['DAY'] = get_weekday_name(current_date.dayOfWeek())

        current_preset['REGION'] = self.region_combobox.currentText()

        if self.netplay_checkbox.isChecked():
            current_preset['NETPLAY'] = "1"
        else:
            current_preset['NETPLAY'] = "0"

        current_preset['VERSION'] = self.version_combobox.currentText()

        self.write_presets_to_file()

    def write_presets_to_file(self):
        with open('config/presets.ini', 'w') as configfile:
            self.config.write(configfile)

    def preset_remove_button_dialog(self):
        current_preset_name = self.preset_combobox.currentText()
        button = QMessageBox.question(
            self, 
            "Remove preset", 
            f"Really remove preset \"{current_preset_name}\"?"
        )
        if button == QMessageBox.StandardButton.Yes:
            self.config.pop(current_preset_name)
            self.write_presets_to_file()
            self.preset_combobox.removeItem(self.preset_combobox.currentIndex())

    def set_slider(self, seconds):
        self.display_slider.setSliderPosition(seconds)
        self.display_label.setText(display_timestamp(seconds, self.total_seconds))

    def choose_infile(self):
        (filename, filter_info) = QFileDialog.getOpenFileName(
            self, 
            caption="Open video file",
            filter="Video Files (*.mp4 *.webm *.mkv)"
        )
        if filename:
            self.infile_name = filename
            self.infile_label.setText(os.path.basename(filename))
            self.check_start_button()
            (self.capture, self.total_seconds) = open_capture(filename)
            capture_width = int(self.capture.get(cv.CAP_PROP_FRAME_WIDTH))
            self.game_size_input.setMaximum(capture_width)
            if self.game_size_input.value() > capture_width:
                self.game_size_input.setValue(capture_width)
            self.display_slider.setEnabled(True)
            self.set_slider(0)
            self.display_slider.setRange(0, self.total_seconds)
            # Set the default csv outfile to same path but csv extension
            self.outfile_name = re.sub(
                r'\.(mp4|m4v|mov|avi|mkv|webm|wmv)$',
                '.csv',
                self.infile_name
            )
            self.outfile_label.setText(os.path.basename(self.outfile_name))
            self.preview_video_by_slider()

    def set_display_frame(self, seconds):
        if (self.capture 
            and (self.game_size_input.value() >= 480)):
            frame = get_frame_from_video(
                self.capture, 
                seconds, 
                self.game_x_input.value(),
                self.game_y_input.value(),
                self.game_size_input.value(),
                crop=False
            )
            # TODO temporary
            # self.display_widget.setScaledContents(False)
            ##
            self.display_widget.setPixmap(cv2_to_qpixmap(frame))
            self.display_label.setText(display_timestamp(seconds, self.total_seconds))

    def preview_video_by_slider(self):
        self.set_display_frame(self.display_slider.value())

    def choose_outfile(self):
        filename = QFileDialog.getSaveFileName(
            self, 
            caption='Save File',
            filter="Timestamp Files (*.csv)"
        )
        if filename[0]:
            self.outfile_name = filename[0]
            self.outfile_label.setText(os.path.basename(filename[0]))
            self.check_start_button()

    # Grey out the csv options if the user doesn't care about csv output
    def outfile_checkbox_clicked(self):
        csv_options_widgets = [
            self.outfile_label,
            self.outfile_open_button,
            self.event_label,
            self.event_input,
            self.date_label,
            self.date_picker,
            self.region_label,
            self.region_combobox,
            self.netplay_checkbox,
            self.version_label,
            self.version_combobox,
            self.url_label,
            self.url_input
        ]
        for w in csv_options_widgets:
            w.setEnabled(self.outfile_checkbox.isChecked())
        self.check_start_button()

    # Enable the start button if all required options are filled in
    def check_start_button(self):
        # Check mandatory parameters (infile, GAME_X/Y/SIZE)
        if not (self.infile_name
            and self.game_size_input.value() >= 480):
            self.start_button.setEnabled(False)
        else:
            # If the outfile checkbox is checked then there are extra requirements
            if (not self.outfile_checkbox.isChecked()) or (
                self.outfile_name
                and self.event_input.text()
                and self.url_input.text()
            ):
                self.start_button.setEnabled(True)
            else:
                self.start_button.setEnabled(False)

    def print_output_line(self, line): 
        self.right_pane_text.append(line)

    def display_frame_from_image(self, image):
        self.display_widget.setPixmap(cv2_to_qpixmap(image))

    def process_video(self):
        self.worker = Worker(
            GAME_X        = self.game_x_input.value(),
            GAME_Y        = self.game_y_input.value(),
            GAME_SIZE     = self.game_size_input.value(),
            MAKE_CSV      = self.outfile_checkbox.isChecked(),
            EVENT         = self.event_input.text(),
            DATE          = self.date_picker.date().toString(Qt.DateFormat.ISODate),
            REGION        = self.region_combobox.currentText(),
            NETPLAY       = self.netplay_checkbox.isChecked(),
            VERSION       = self.version_combobox.currentText(),
            URL           = self.url_input.text(),
            capture       = self.capture,
            start_seconds = self.display_slider.value(),
            total_seconds = self.total_seconds,
            outfile_name  = self.outfile_name
        )
        self.worker.signals.printLine.connect(self.print_output_line)
        self.worker.signals.showFrame.connect(self.display_frame_from_image)
        self.worker.signals.updateSlider.connect(self.set_slider)
        self.worker.signals.finishWork.connect(self.worker_finished)
        self.display_slider.setEnabled(False)
        self.form_container.setEnabled(False)
        self.cancel_button.setEnabled(True)
        # Start worker in another thread so it doesn't block gui execution
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    # Set a flag to signal to the worker to stop processing
    def cancel_worker(self):
        self.cancel_button.setEnabled(False)
        self.worker.signal_to_stop()

    # Clean-up actions after the worker has finished doing its thing
    def worker_finished(self):
        self.thread.quit()
        self.form_container.setEnabled(True)
        self.set_slider(0)
        self.display_slider.setEnabled(True)