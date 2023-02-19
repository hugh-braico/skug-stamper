# native python libraries
import os
import csv
import json
import logging
from statistics import mode
import sys
from pathlib import Path
from timeit import default_timer as timer

# qt stuff
from PyQt6.QtCore import QObject, QSize, QDate, Qt, pyqtSignal, pyqtSlot, QRunnable
from PyQt6 import QtGui
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    # high level stuff
    QApplication, QMainWindow, QDialog, QMessageBox,
    # widgets
    QWidget, QPushButton, QDateEdit, QLabel, QLineEdit, QComboBox, QFileDialog,
    QCheckBox, QDialogButtonBox, QSpinBox, QTextEdit,
    # layout stuff
    QFrame, QSplitter, QVBoxLayout, QHBoxLayout
)

# other non-native python libraries
import cv2 as cv
import numpy as np
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' # Suppress annoying tensorflow logging
from keras.models import load_model
from pyperclip import copy

# custom functions
from utils.ocr   import ocr_with_fuzzy_match
from utils.cv2   import *
from utils.timestamp import display_timestamp, timestamp_url
from utils.csv   import validate_csv_fields, twb_csv_header, twb_csv_row
from utils.ml    import identify_char1, identify_char23


# The worker prints to the output console and display frames as it works
class WorkerSignals(QObject):
    printLine    = pyqtSignal(str)
    showFrame    = pyqtSignal(object)
    updateSlider = pyqtSignal(int)


class Worker(QRunnable):
    def __init__(self, *args, **kwargs):
        super(Worker, self).__init__()

        self.signals = WorkerSignals()

        # Unpack arguments
        self.GAME_X        = kwargs['GAME_X']
        self.GAME_Y        = kwargs['GAME_Y']
        self.GAME_SIZE     = kwargs['GAME_SIZE']
        self.MAKE_CSV      = kwargs['MAKE_CSV']
        self.EVENT         = kwargs['EVENT']
        self.DATE          = kwargs['DATE']
        self.REGION        = kwargs['REGION']
        if kwargs['NETPLAY'] == True:
            self.NETPLAY   = 1
        else:
            self.NETPLAY   = 0
        self.VERSION       = kwargs['VERSION']
        self.URL           = kwargs['URL']
        self.capture       = kwargs['capture']
        self.total_seconds = kwargs['total_seconds']
        self.outfile_name  = kwargs['outfile_name']

    @pyqtSlot()
    def run(self):
        # Load tensorflow models for identifying characters
        char1_model  = load_model('models/char1_model.h5')
        char23_model = load_model('models/char23_model.h5')

        # Open a dictionary of known usernames and aliases
        with open("config/usernames.json", "r") as f:
            usernames_dict = json.load(f)

        # From experimentation, this seems to work well as a brightness threshold
        PNAME_THRESHOLD = 190

        # Set up a bunch of counting/tracking variables
        start_hours, start_minutes, start_seconds = 0, 0, 0
        seconds = start_hours*3600 + start_minutes*60 + start_seconds
        prev_p1name = None
        prev_p2name = None
        set_length  = 1
        csv_list = [twb_csv_header()]
        timestamp_list = []

        # Showtime. Try to find round starts and guess who's playing and what team
        self.signals.printLine.emit("\nProcessing video...")
        while seconds < self.total_seconds:
            image = get_frame_from_video(self.capture, seconds, self.GAME_X, self.GAME_Y, self.GAME_SIZE, crop=False)
            self.signals.updateSlider.emit(seconds)

            if is_round_start(image, self.GAME_SIZE):

                self.signals.showFrame.emit(np.copy(image))

                timestamp = display_timestamp(seconds, self.total_seconds)
                filename_safe_timestamp = timestamp.replace(':','-')

                # logging.debug(f"{timestamp} Found round start")

                # cv.imwrite(f"""green_bars_samples/{filename_safe_timestamp}.jpg""", image)
                
                # Try to guess the player names. Don't even try for offline games.
                if self.NETPLAY == 1:
                    # Initial guess
                    p1name_img, p2name_img = get_name_imgs(image, self.GAME_SIZE)
                    p1name = ocr_with_fuzzy_match(p1name_img, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp}_p1")
                    p2name = ocr_with_fuzzy_match(p2name_img, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp}_p2")

                    # If any of the guesses are _, just keep trying for a bit
                    # This can wait out some intro animations that cover up player names,
                    # and also moving around the stage background during gameplay can
                    # produce something more favorable. 
                    retry_seconds = seconds + 1
                    while retry_seconds < seconds + 20 and \
                          retry_seconds < self.total_seconds and \
                          (p1name == "_" or p2name == "_"):
                        timestamp2 = display_timestamp(retry_seconds, self.total_seconds)
                        filename_safe_timestamp2 = timestamp2.replace(':','-')
                        # logging.debug(f"{timestamp2} Retrying due to OCR failure...")
                        image2 = get_frame_from_video(self.capture, retry_seconds, self.GAME_X, self.GAME_Y, self.GAME_SIZE)
                        p1name_img2, p2name_img2 = get_name_imgs(image2, self.GAME_SIZE)
                        if p1name == "_":
                            p1name = ocr_with_fuzzy_match(p1name_img2, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp2}_p1")
                        if p2name == "_":
                            p2name = ocr_with_fuzzy_match(p2name_img2, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp2}_p2")
                        retry_seconds += 1
                else:
                    # Offline games won't have player tags
                    p1name = "_"
                    p2name = "_"

                # Save an image of this frame if something went wrong
                # if args.debug and (p1name == "_" or p2name == "_"):
                #     debug_path = "debug/failure_screenshots"
                #     Path(debug_path).mkdir(parents=True, exist_ok=True)
                #     cv.imwrite(f"""{debug_path}/{filename_safe_timestamp}.jpg""", image)

                # Ignore this timestamp if it looks like it's just another game in
                # a set (ie. the previous game had the same two players)
                # If any name is _, always make a timestamp since we can't be sure
                if self.NETPLAY == 1 and p1name != "_" and p2name != "_" and \
                   ((p1name == prev_p1name and p2name == prev_p2name) or \
                    (p1name == prev_p2name and p2name == prev_p1name)):
                    self.signals.printLine.emit(f"{timestamp} (next game in set)")
                    set_length += 1
                else:
                    # If the previous set was only 1 game in length and --only-sets
                    # was supplied, then it doesn't actually get timestamped. 
                    # Retroactively remove it from the list

                    # if args.only_sets and timestamp_list and set_length == 1:
                    #     csv_list.pop()
                    #     timestamp_list.pop()

                    set_length = 1
                    # Guess team characters if this looks like a fresh set
                    # Do a few attempts and pick the most common result
                    # This code is pretty ugly, but oh well. 
                    p1char1_guesses = []
                    p2char1_guesses = []
                    p1char2_guesses = []
                    p2char2_guesses = []
                    p1char3_guesses = []
                    p2char3_guesses = []
                    retry_seconds = seconds
                    image2 = image
                    while retry_seconds < seconds + 5 and \
                          retry_seconds < self.total_seconds:
                        p1char1_img, p2char1_img = get_char_imgs(image2, 1, self.GAME_SIZE)
                        p1char2_img, p2char2_img = get_char_imgs(image2, 2, self.GAME_SIZE)
                        p1char3_img, p2char3_img = get_char_imgs(image2, 3, self.GAME_SIZE)
                        p1char1_guesses.append(identify_char1(p1char1_img, char1_model))
                        p2char1_guesses.append(identify_char1(p2char1_img, char1_model))
                        p1char2_guesses.append(identify_char23(p1char2_img, char23_model, debug_name=f"{retry_seconds}/p1char2"))
                        p2char2_guesses.append(identify_char23(p2char2_img, char23_model, debug_name=f"{retry_seconds}/p2char2"))
                        p1char3_guesses.append(identify_char23(p1char3_img, char23_model, debug_name=f"{retry_seconds}/p1char3"))
                        p2char3_guesses.append(identify_char23(p2char3_img, char23_model, debug_name=f"{retry_seconds}/p2char3"))
                        retry_seconds += 1
                        image2 = get_frame_from_video(self.capture, retry_seconds, self.GAME_X, self.GAME_Y, self.GAME_SIZE)
                    p1char1 = mode(p1char1_guesses)
                    p2char1 = mode(p2char1_guesses)
                    p1char2 = mode(p1char2_guesses)
                    p2char2 = mode(p2char2_guesses)
                    p1char3 = mode(p1char3_guesses)
                    p2char3 = mode(p2char3_guesses)

                    # Construct a team display string for each player
                    p1team = p1char1
                    if p1char2 != "N":
                        p1team += f"/{p1char2}"
                        if p1char3 != "N":
                            p1team += f"/{p1char3}"

                    p2team = p2char1
                    if p2char2 != "N":
                        p2team += f"/{p2char2}"
                        if p2char3 != "N":
                            p2team += f"/{p2char3}"

                    # Create a timestamp and CSV row for this game
                    timestamp_line = f"{timestamp} {p1name} ({p1team}) vs {p2name} ({p2team})"
                    self.signals.printLine.emit(timestamp_line)
                    timestamp_list.append(timestamp_line)
                    if self.MAKE_CSV:
                        csv_list.append(
                            twb_csv_row(
                                self.EVENT, self.DATE, self.REGION, self.NETPLAY, self.VERSION,
                                p1name, p1char1, p1char2, p1char3,
                                p2name, p2char1, p2char2, p2char3,
                                timestamp_url(self.URL, seconds)
                            )
                        )

                    # Look for invalid things and issue warnings in the output
                    if (p1char1 == 'N'
                    or p1char1 == p1char2 
                    or p1char1 == p1char3 
                    or (p1char2 != 'N' and p1char2 == p1char3)
                    or (p1char2 == 'N' and p1char3 != 'N')):
                        self.signals.printLine.emit(f"### WARNING! Invalid team {p1team}, please correct manually")
                    if (p2char1 == 'N'
                    or p2char1 == p2char2 
                    or p2char1 == p2char3 
                    or (p2char2 != 'N' and p2char2 == p2char3)
                    or (p2char2 == 'N' and p2char3 != 'N')):
                        self.signals.printLine.emit(f"### WARNING! Invalid team {p2team}, please correct manually")
                    if p1name == p2name and p1name != "_":
                        self.signals.printLine.emit(f"### WARNING! Duplicate names detected, please correct manually")

                prev_p1name = p1name
                prev_p2name = p2name

                # No single game of SG is going to take less than 20 seconds
                seconds += 20
            else:
                seconds += 1
        self.signals.printLine.emit("Finished!")
        # Save the csv at the very end after all data is collected
        if self.MAKE_CSV:
            with open(self.outfile_name, "w") as f:
                f.write("\n".join(csv_list))
            self.signals.printLine.emit(f"CSV data written to {self.outfile_name}.")
        timestamp_data = "\n".join(timestamp_list)
        self.signals.printLine.emit("\nSummary:\n" + timestamp_data)
        copy(timestamp_data)