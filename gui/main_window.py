# native python libraries

import configparser
import os

# qt stuff
from PyQt6.QtCore import QSize, QDate, Qt, QThreadPool
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

from utils.cv2   import *
from utils.dates import infer_last_weekday, get_weekday_name

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
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(1)

        #######################################################################
        ### Options form

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
        self.version_list = [
            'Black Dahlia Alpha',
            'Umbrella Patch',
            'Annie Patch',
            'Annie Patch Beta',
            '2E+ Final',
            '2E+ (old UD)',
            '2E',
            'Beowulf Patch',
            'Eliza Patch',
            'Fukua Patch',
            'Big Band Patch',
            'Encore',
            'MDE',
            'SDE'
        ]
        self.version_combobox.addItems(self.version_list)
        self.version_combobox.setEnabled(False)

        # URL
        self.url_label = QLabel("Vod URL")
        self.url_label.setEnabled(False)
        self.url_input = QLineEdit()
        self.url_input.setEnabled(False)
        self.url_input.textChanged.connect(self.check_start_button)

        # Start button
        self.start_button = QPushButton("Create timestamps")
        start_button_font = self.start_button.font()
        start_button_font.setBold(True)
        self.start_button.setFont(start_button_font)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.process_video)

        # Cancel button
        self.cancel_button = QPushButton("Cancel")

        # Pre-populate fields from preset
        self.populate_form_from_preset()

        form_layout = QVBoxLayout()

        # Preset stuff
        form_layout.addWidget(self.preset_label)
        form_layout.addWidget(self.preset_combobox)
        form_layout.addWidget(self.preset_save_button)
        form_layout.addWidget(self.preset_new_button)
        form_layout.addWidget(self.preset_remove_button)
        form_layout.addWidget(self.divider1)

        # Mandatory stuff
        form_layout.addWidget(self.infile_label)
        form_layout.addWidget(self.infile_open_button)
        form_layout.addWidget(self.game_x_label)
        form_layout.addWidget(self.game_x_input)
        form_layout.addWidget(self.game_y_label)
        form_layout.addWidget(self.game_y_input)
        form_layout.addWidget(self.game_size_label)
        form_layout.addWidget(self.game_size_input)
        form_layout.addWidget(self.divider2)

        # CSV specific options
        form_layout.addWidget(self.outfile_checkbox)
        form_layout.addWidget(self.outfile_label)
        form_layout.addWidget(self.outfile_open_button)
        form_layout.addWidget(self.event_label)
        form_layout.addWidget(self.event_input)
        form_layout.addWidget(self.date_label)
        form_layout.addWidget(self.date_picker)
        form_layout.addWidget(self.region_label)
        form_layout.addWidget(self.region_combobox)
        form_layout.addWidget(self.netplay_checkbox)
        form_layout.addWidget(self.version_label)
        form_layout.addWidget(self.version_combobox)
        form_layout.addWidget(self.url_label)
        form_layout.addWidget(self.url_input)

        form_layout.addWidget(self.start_button)
        form_layout.addWidget(self.cancel_button)

        # Widget that encapsulates all the form controls
        self.form_container = QWidget()
        self.form_container.setFixedSize(QSize(275,755))
        self.form_container.setLayout(form_layout)

        #######################################################################
        ### Centre pane

        # Widget that displays frames from the video
        display_layout = QVBoxLayout()
        self.display_widget = QLabel()
        self.display_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        self.display_widget.setScaledContents(True)
        self.display_widget.setFixedSize(QSize(960,540))
        display_layout.addWidget(self.display_widget)
        display_layout.addWidget(self.display_slider)
        self.display_container = QWidget()
        self.display_container.setLayout(display_layout)

        #######################################################################
        ### Right pane

        # Widget that displays console output, timestamp results
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFixedSize(QSize(400,755))

        #######################################################################
        ### Right pane

        # Main layout has three side-by-side panes
        main_layout = QSplitter()
        main_layout.addWidget(self.form_container)
        main_layout.addWidget(self.display_container)
        main_layout.addWidget(self.output_text)

        self.setCentralWidget(main_layout)

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
        if version in self.version_list:
            self.version_combobox.setCurrentText(version)

    def preset_new_button_dialog(self):
        dlg = NewPresetDialog(self)
        if dlg.exec():
            self.config[dlg.new_preset_name] = {}
            self.preset_combobox.insertItem(99999, dlg.new_preset_name)
            self.preset_combobox.setCurrentText(dlg.new_preset_name)

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
            self.display_slider.setEnabled(True)
            self.display_slider.setSliderPosition(0)
            self.display_slider.setRange(0, self.total_seconds)
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
            self.display_widget.setPixmap(cv2_to_qpixmap(frame))

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
        self.output_text.append(line)

    def display_frame_from_image(self, image):
        self.display_widget.setPixmap(cv2_to_qpixmap(image))

    def process_video(self):
        worker = Worker(
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
            total_seconds = self.total_seconds,
            outfile_name  = self.outfile_name
        )
        worker.signals.printLine.connect(self.print_output_line)
        worker.signals.showFrame.connect(self.display_frame_from_image)
        worker.signals.updateSlider.connect(self.display_slider.setSliderPosition)
        # TODO
        self.display_slider.setEnabled(False)
        self.form_container.setEnabled(False)
        self.threadpool.start(worker)