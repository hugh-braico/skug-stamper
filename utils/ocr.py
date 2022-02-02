import pytesseract
from fuzzywuzzy import process
import cv2 as cv
import numpy as np
import logging
from pathlib import Path


# Guesses the text contained within an image
def ocr_with_fuzzy_match(image, aliases_dict, brightness_threshold, debug_name="guess"):
    # Set up debug logging
    if logging.DEBUG >= logging.root.level:
        debug_path = f"debug/ocr/{debug_name}"
        Path(debug_path).mkdir(parents=True, exist_ok=True)
        cv.imwrite(f"{debug_path}/1_crop.jpg", image)

    # Perform a series of black flood fills starting from the edge of
    # the canvas.
    image = floodfill_edges_black(image, brightness_threshold)
    if logging.DEBUG >= logging.root.level:
        cv.imwrite(f"{debug_path}/2_floodfill.jpg", image)

    # Remove pixels that are too tinted, since text is (pretty) monochrome
    # image = remove_coloured_pixels(image)
    # if logging.DEBUG >= logging.root.level:
    #     cv.imwrite(f"{debug_path}/3_removecolor.jpg", image)

    # Grayscale, threshold to remove dark areas, and invert
    image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    ret, image = cv.threshold(image, brightness_threshold, 255, cv.THRESH_BINARY_INV)
    if logging.DEBUG >= logging.root.level:
        cv.imwrite(f"{debug_path}/4_threshold.jpg", image)

    # Finally, perform a series of white flood fills starting from the edge of
    # the canvas. This will clean up the parts that were not caught by the 
    # first pass of flood fills.
    image = floodfill_edges_white(image)
    if logging.DEBUG >= logging.root.level:
        cv.imwrite(f"{debug_path}/5_floodfill.jpg", image)

    # Use OCR to guess the text
    guess = pytesseract.image_to_string(image).strip().replace("\n","")

    # Use fuzzy string matching against a list of known aliases
    guess = fuzzymatch(guess, aliases_dict)

    return guess


# Perform black flood fills around the edge of an RGB image
# Intended to be used before thresholding
def floodfill_edges_black(image, brightness_threshold):
    h, w = image.shape[:2]
    new_val = (0,0,0)
    diff = 30

    # How different pixels can be from the edge and still be filled
    lo_diff = (diff, diff, diff, diff)
    up_diff = (diff, diff, diff, diff)

    # If we fill pixels that are too bright then they can potentially "eat" into
    # vulnerable parts of the text (such as through the top of "e"s)
    max_brightness = (brightness_threshold - diff) * 3 - 1

    for row in range(h):
        left_brightness  = sum(image[row, 0])
        right_brightness = sum(image[row, w-1])
        # if left_brightness > min_brightness and left_brightness < max_brightness:
        if left_brightness < max_brightness:
            cv.floodFill(image, None, (0, row), newVal=new_val, loDiff=lo_diff, upDiff=up_diff)
        # if right_brightness > min_brightness and right_brightness < max_brightness:
        if right_brightness < max_brightness:
            cv.floodFill(image, None, (w-1, row), newVal=new_val, loDiff=lo_diff, upDiff=up_diff)
    for col in range(w):
        top_brightness  = sum(image[0, col])
        bottom_brightness = sum(image[h-1, col])
        # if top_brightness > min_brightness and top_brightness < max_brightness:
        if top_brightness < max_brightness:
            cv.floodFill(image, None, (col, 0), newVal=new_val, loDiff=lo_diff, upDiff=up_diff)
        # if bottom_brightness > min_brightness and bottom_brightness < max_brightness:
        if bottom_brightness < max_brightness:
            cv.floodFill(image, None, (col, h-1), newVal=new_val, loDiff=lo_diff, upDiff=up_diff)
    return image  


# Perform white flood fills around the edge of a monochrome image
# Intended to be used after thresholding
def floodfill_edges_white(image):
    h, w = image.shape[:2]
    for row in range(h):
        if image[row, 0] == 0:
            cv.floodFill(image, None, (0, row), 255)
        if image[row, w-1] == 0:
            cv.floodFill(image, None, (w-1, row), 255)
    for col in range(w):
        if image[0, col] == 0:
            cv.floodFill(image, None, (col, 0), 255)
        if image[h-1, col] == 0:
            cv.floodFill(image, None, (col, h-1), 255)
    return image  


# The text we care about is (mostly) monochrome and the stage tends to have
# color, so we can improve filtering somewhat by removing non-mono pixels.
# Not currently used.
def remove_coloured_pixels(image):
    h, w = image.shape[:2]
    max_diff = 34 # maximum allowable difference between R G and B components
    for y in range(0,h):
        for x in range(0,w):
            pixel = image[y,x]
            r = int(pixel[0])
            g = int(pixel[1])
            b = int(pixel[2])
            if abs(r - g) > max_diff or \
               abs(r - b) > max_diff or \
               abs(b - g) > max_diff:
                image[y,x] = np.array([0, 0, 0])
    return image


# Fuzzy matches a name against a dictionary of known aliases, returns real name
def fuzzymatch(name, aliases_dict):
    minimum_confidence = 65
    if name:
        choice = process.extractOne(name, aliases_dict.keys())
        if choice[1] >= minimum_confidence:
            # Debug logging
            if choice[1] < 100:
                if choice[0] == aliases_dict[choice[0]]:
                    logging.debug(f"{name} -> {choice[0]}")
                else:
                    logging.debug(f"{name} -> {choice[0]} -> {aliases_dict[choice[0]]}")
            else:
                if choice[0] == aliases_dict[choice[0]]:
                    logging.debug(f"Exact match {choice[0]}")
                else:
                    logging.debug(f"Exact match {choice[0]} -> {aliases_dict[choice[0]]}")
            return aliases_dict[choice[0]]
        else:
            logging.debug(f"Can't find good enough match for {name} (best option was {choice[0]})")
            return "???"
    else:
        logging.debug(f"Can't find any text in this image at all!")
        return "???"