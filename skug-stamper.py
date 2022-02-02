# native python libraries
import argparse
import configparser
import csv
import json
import logging
import os
from statistics import mode
import sys
from pathlib import Path
from timeit import default_timer as timer

# non-native python libraries
import cv2 as cv
import numpy as np
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' # Suppress annoying tensorflow logging
from keras.models import load_model
from pyperclip import copy

# helper scripts
from utils.ocr import ocr_with_fuzzy_match
from utils.cv2 import get_frame_from_video, is_round_start, get_char_imgs, get_name_imgs
from utils.timestamp import display_timestamp, timestamp_url
from utils.csv import validate_csv_fields, twb_csv_header, twb_csv_row
from utils.ml  import identify_char1, identify_char23


def main():
    start_time = timer()

    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', type=str, required=True, help='Input video filename')
    parser.add_argument('--output', '-o', type=str, default='out.csv', help='Output csv file (default: out.csv)')
    parser.add_argument('--preset', '-p', type=str, default='DEFAULT', help='Which presets.ini preset to use (default: DEFAULT)')
    parser.add_argument('--url', '-u', type=str, default='', help='YouTube URL of your video')
    parser.add_argument('--date', '-d', type=str, default='', help='Date the video was recorded (YYYY-MM-DD or DD/MM/YYYY)')
    parser.add_argument('--event', '-e', type=str, default='', help='Name of the event (overrides presets.ini)')
    parser.add_argument('--no-csv', '-n', action='store_true', help="Don't output a csv file, don't warn about missing parameters")
    parser.add_argument('--only-sets', '-s', action='store_true', help="Do not timestamp individual games, only sets of >=2 games")
    parser.add_argument('--debug', action='store_true', help="verbose logging, may output images to a debug/ folder")
    args = parser.parse_args()

    # Set logging level
    logging_format = '%(levelname)s: %(message)s'
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format=logging_format)
    else:
        logging.basicConfig(level=logging.INFO, format=logging_format)

    # Load config (see presets.ini for more info)
    config = configparser.ConfigParser()
    config.read('config/presets.ini')
    GAME_X    = config.getint(args.preset, 'GAME_X')
    GAME_Y    = config.getint(args.preset, 'GAME_Y')
    GAME_SIZE = config.getint(args.preset, 'GAME_SIZE')
    VERSION   = config.get(args.preset, 'VERSION', fallback="")
    REGION    = config.get(args.preset, 'REGION', fallback="")
    NETPLAY   = config.getint(args.preset, 'NETPLAY', fallback=1)
    # Event can be set in either presets/args, but args take precedence
    if args.event:
        EVENT = args.event
    else:
        EVENT = config.get(args.preset, 'EVENT', fallback="")

    # Abort immediately if any of the game dimensions are not supplied
    if GAME_X is None or GAME_X < 0:
        sys.exit("Missing or invalid required value: GAME_X. Check your presets.ini.")
    if GAME_Y is None or GAME_Y < 0:
        sys.exit("Missing or invalid required value: GAME_Y. Check your presets.ini.")
    if GAME_SIZE is None or GAME_SIZE < 0:
        sys.exit("Missing or invalid required value: GAME_SIZE. Check your presets.ini.")

    # From experimentation, this seems to work well as a brightness threshold
    PNAME_THRESHOLD = 190

    # Issue some warnings for missing or invalid csv data
    if not args.no_csv:
        validate_csv_fields(EVENT, args.date, REGION, NETPLAY, VERSION, args.url)

    # Open a dictionary of known usernames and aliases
    with open("config/usernames.json", "r") as f:
        usernames_dict = json.load(f)

    # Open a dictionary that maps character names to their TWB shorthand
    with open("config/characters.json", "r") as f:
        characters_dict = json.load(f)

    # Load tensorflow models for identifying characters
    char1_model  = load_model('models/char1_model.h5')
    char23_model = load_model('models/char23_model.h5')

    # Open video file and get its total length
    if not os.path.isfile(args.input):
        sys.exit(f"ERROR: file {args.input} doesn't exist!")
    capture = cv.VideoCapture(args.input)
    fps = capture.get(cv.CAP_PROP_FPS)
    frame_count = int(capture.get(cv.CAP_PROP_FRAME_COUNT))
    total_seconds = int(frame_count / fps)

    # Set up a bunch of counting/tracking variables
    start_hours, start_minutes, start_seconds = 0, 0, 0
    seconds = start_hours*3600 + start_minutes*60 + start_seconds
    prev_p1name = None
    prev_p2name = None
    set_length  = 1
    csv_list = [twb_csv_header()]
    timestamp_list = []

    # Showtime. Try to find round starts and guess who's playing and what team
    print("\nProcessing video...")
    while seconds < total_seconds:
        image = get_frame_from_video(capture, seconds, GAME_X, GAME_Y, GAME_SIZE)
        timestamp = display_timestamp(seconds, total_seconds)

        if is_round_start(image, GAME_SIZE):

            timestamp = display_timestamp(seconds, total_seconds)
            filename_safe_timestamp = timestamp.replace(':','-')

            logging.debug(f"{timestamp} Found round start")

            cv.imwrite(f"""green_bars_samples/{filename_safe_timestamp}.jpg""", image)
            
            # Try to guess the player names.
            p1name_img, p2name_img = get_name_imgs(image, GAME_SIZE)
            p1name = ocr_with_fuzzy_match(p1name_img, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp}_p1")
            p2name = ocr_with_fuzzy_match(p2name_img, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp}_p2")

            # If any of the guesses are ???, just keep trying for a bit
            # This can wait out some intro animations that cover up player names,
            # and also moving around the stage background during gameplay can
            # produce something more favorable. 
            retry_seconds = seconds + 1
            while retry_seconds < seconds + 20 and \
                  retry_seconds < total_seconds and \
                  (p1name == "???" or p2name == "???"):
                timestamp2 = display_timestamp(retry_seconds, total_seconds)
                filename_safe_timestamp2 = timestamp2.replace(':','-')
                logging.debug(f"{timestamp2} Retrying due to OCR failure...")
                image2 = get_frame_from_video(capture, retry_seconds, GAME_X, GAME_Y, GAME_SIZE)
                p1name_img2, p2name_img2 = get_name_imgs(image2, GAME_SIZE)
                if p1name == "???":
                    p1name = ocr_with_fuzzy_match(p1name_img2, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp2}_p1")
                if p2name == "???":
                    p2name = ocr_with_fuzzy_match(p2name_img2, usernames_dict, PNAME_THRESHOLD, debug_name=f"{filename_safe_timestamp2}_p2")
                retry_seconds += 1

            # Save an image of this frame if something went wrong
            if args.debug and (p1name == "???" or p2name == "???"):
                debug_path = "debug/failure_screenshots"
                Path(debug_path).mkdir(parents=True, exist_ok=True)
                cv.imwrite(f"""{debug_path}/{filename_safe_timestamp}.jpg""", image)

            # Ignore this timestamp if it looks like it's just another game in
            # a set (ie. the previous game had the same two players)
            # If any name is ???, always make a timestamp since we can't be sure
            if p1name != "???" and p2name != "???" and \
               ((p1name == prev_p1name and p2name == prev_p2name) or \
                (p1name == prev_p2name and p2name == prev_p1name)):
                print(f"{timestamp} (next game in set)")
                set_length += 1
            else:
                # If the previous set was only 1 game in length and --only-sets
                # was supplied, then it doesn't actually get timestamped. 
                # Retroactively remove it from the list
                if args.only_sets and timestamp_list and set_length == 1:
                    csv_list.pop()
                    timestamp_list.pop()
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
                      retry_seconds < total_seconds:
                    p1char1_img, p2char1_img = get_char_imgs(image2, 1, GAME_SIZE)
                    p1char2_img, p2char2_img = get_char_imgs(image2, 2, GAME_SIZE)
                    p1char3_img, p2char3_img = get_char_imgs(image2, 3, GAME_SIZE)
                    p1char1_guesses.append(identify_char1(p1char1_img, char1_model))
                    p2char1_guesses.append(identify_char1(p2char1_img, char1_model))
                    p1char2_guesses.append(identify_char23(p1char2_img, char23_model))
                    p2char2_guesses.append(identify_char23(p2char2_img, char23_model))
                    p1char3_guesses.append(identify_char23(p1char3_img, char23_model))
                    p2char3_guesses.append(identify_char23(p2char3_img, char23_model))
                    retry_seconds += 1
                    image2 = get_frame_from_video(capture, retry_seconds, GAME_X, GAME_Y, GAME_SIZE)
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
                print(timestamp_line)
                timestamp_list.append(timestamp_line)
                if not args.no_csv:
                    csv_list.append(
                        twb_csv_row(
                            EVENT, args.date, REGION, NETPLAY, VERSION,
                            p1name, p1char1, p1char2, p1char3,
                            p2name, p2char1, p2char2, p2char3,
                            timestamp_url(args.url, seconds)
                        )
                    )
            prev_p1name = p1name
            prev_p2name = p2name

            # Assume no single game of SG is going to take less than 20 seconds
            seconds += 20
        else:
            seconds += 2
    print("Finished!")
    # Save the csv at the very end after all data is collected
    if not args.no_csv:
        with open(args.output, "w") as f:
            f.write("\n".join(csv_list))
        print(f"CSV data written to {args.output}.")
    timestamp_data = "\n".join(timestamp_list)
    print("\nSummary:\n" + timestamp_data)
    copy(timestamp_data)
    print("Timestamps copied to clipboard.")
    end_time = timer()
    logging.debug(f"Total execution time: {(end_time - start_time):.2f}s")


if __name__ == '__main__':
    main()