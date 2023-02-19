import cv2 as cv
import numpy as np
import sys
import os
import logging
from pathlib import Path
from PyQt6.QtGui import QPixmap, QImage

# Open a video file, returning a capture object and some other data
def open_capture(filename: str):
    if not os.path.isfile(filename):
        sys.exit(f"ERROR: file {filename} doesn't exist!")
    capture = cv.VideoCapture(filename)
    fps = capture.get(cv.CAP_PROP_FPS)
    frame_count = int(capture.get(cv.CAP_PROP_FRAME_COUNT))
    total_seconds = int(frame_count / fps)
    return (capture, total_seconds)


# Read a frame at a specific time from a video
def get_frame_from_video(capture, seconds, GAME_X, GAME_Y, GAME_SIZE, crop=True):
    capture.set(cv.CAP_PROP_POS_MSEC,(seconds*1000))   
    success, image = capture.read()
    if not success:
        sys.exit(f"Failed to read frame at t = {seconds} from capture!")
    # Cut down to only the relevant part we're interested in
    # This means passing around a smaller array, and also all calculations
    # from this point forward can be independent of GAME_X and GAME_Y
    y1 = GAME_Y
    if crop:
        y2 = GAME_Y + int(GAME_SIZE*0.15)
    else:
        y2 = GAME_Y + int(GAME_SIZE*0.562)
    x1 = GAME_X
    x2 = GAME_X + GAME_SIZE - 1
    return image[y1:y2, x1:x2]


def cv2_to_qpixmap(image):
    height, width, channel = image.shape
    bytesPerLine = 3 * width
    image2 = np.require(image, np.uint8, 'C')
    qimg = QImage(image2, width, height, bytesPerLine, QImage.Format.Format_BGR888)
    return QPixmap(qimg)


def avg_colour_of_area(image, y1, y2, x1, x2):
    area = image[y1:y2, x1:x2]
    return area.mean(axis=0).mean(axis=0)


# Determines whether a frame is near the start of a round by looking for the
# presence of a green health bar on both P1 and P2's point characters.
def is_round_start(image, GAME_SIZE):

    # Take two slices from each health bar, take the average colour, and then
    # compare to an "expected" green value. 
    # Needs to be two because stuff like Band's saxophone and Bella's hoop 
    # intro like to cut through the middle. Very annoying
    y1   = int(GAME_SIZE*0.0734)
    y2   = y1 + 1

    # Correct/"expected" green colours + max allowable error
    correct_outer_green = np.array([128.9, 221.8, 218.9])
    correct_inner_green = np.array([ 69.7, 126.3,  56.6])
    threshold = 10

    # P1 outer slice
    p1x1_outer = int(GAME_SIZE*0.146)
    p1x2_outer = int(GAME_SIZE*0.225)
    p1_outer_avg = avg_colour_of_area(image, y1, y2, p1x1_outer, p1x2_outer)
    if np.linalg.norm(p1_outer_avg - correct_outer_green) > threshold:
        return False

    # P2 outer slice
    p2x1_outer = GAME_SIZE - p1x2_outer
    p2x2_outer = GAME_SIZE - p1x1_outer
    p2_outer_avg = avg_colour_of_area(image, y1, y2, p2x1_outer, p2x2_outer)
    if np.linalg.norm(p2_outer_avg - correct_outer_green) > threshold:
        return False

    # P1 inner slice
    p1x1_inner = int(GAME_SIZE*0.330)
    p1x2_inner = int(GAME_SIZE*0.409)
    p1_inner_avg = avg_colour_of_area(image, y1, y2, p1x1_inner, p1x2_inner)
    if np.linalg.norm(p1_inner_avg - correct_inner_green) > threshold:
        return False

    # P2 inner slice
    p2x1_inner = GAME_SIZE - p1x2_inner
    p2x2_inner = GAME_SIZE - p1x1_inner
    p2_inner_avg = avg_colour_of_area(image, y1, y2, p2x1_inner, p2x2_inner)
    if np.linalg.norm(p2_inner_avg - correct_inner_green) > threshold:
        return False

    return True


# Get character portraits from a frame
def get_char_imgs(image, char_num, GAME_SIZE):
    # funny magic numbers for each portrait's position
    if char_num == 1:
        y1   = int(GAME_SIZE*0.015625)
        y2   = int(GAME_SIZE*0.078125)
        p1x1 = int(GAME_SIZE*0.023438)
        p1x2 = int(GAME_SIZE*0.117188)
    elif char_num == 2:
        y1   = int(GAME_SIZE*0.054688)
        y2   = int(GAME_SIZE*0.064063)
        p1x1 = int(GAME_SIZE*0.134375)
        p1x2 = int(GAME_SIZE*0.171875)
    else:
        y1   = int(GAME_SIZE*0.043750)
        y2   = int(GAME_SIZE*0.053125)
        p1x1 = int(GAME_SIZE*0.128906)
        p1x2 = int(GAME_SIZE*0.166406)
    # horizontal flip for player 2
    p2x1 = GAME_SIZE - p1x2
    p2x2 = GAME_SIZE - p1x1
    # crop the image and return
    return image[y1:y2, p1x1:p1x2], image[y1:y2, p2x1:p2x2]


# Get the player's names from a frame
def get_name_imgs(image, GAME_SIZE):
    # funny magic numbers for each name's position
    y1   = int(GAME_SIZE*0.1)
    y2   = int(GAME_SIZE*0.1234)
    p1x1 = int(GAME_SIZE*0.164)
    p1x2 = int(GAME_SIZE*0.352)
    # horizontal flip for player 2
    p2x1 = GAME_SIZE - p1x2
    p2x2 = GAME_SIZE - p1x1
    # crop the image and return
    return image[y1:y2, p1x1:p1x2], image[y1:y2, p2x1:p2x2]