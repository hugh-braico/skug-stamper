import numpy as np
from numpy import argmax
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
import logging
from keras.models import load_model
from glob import glob
import cv2 as cv
from pathlib import Path

char1_list  = ["AN","BB","BD","BW","CE","DB","EL","FI","FU","MA","MF",    "PC","PS","PW","RF","SQ","UM","VA"]
char23_list = ["AN","BB","BD","BW","CE","DB","EL","FI","FU","MA","MF","N","PC","PS","PW","RF","SQ","UM","VA"]


# Identify a point character by its big portrait
def identify_char1(image, model, debug_name="guess"):
    height, width = 80, 120
    greyscale_image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    # Resize to the correct size so it can be accepted by the model
    resized_image = cv.resize(greyscale_image, (width, height), interpolation=cv.INTER_CUBIC)
    img_array = np.array(resized_image)
    img_array = img_array.astype('float32')
    img_array = img_array / 255.0
    img_array = img_array.reshape(1,height,width,1)
    output_labels = model.predict(img_array, verbose=None)[0]
    guess = char1_list[argmax(output_labels)]
    if logging.DEBUG >= logging.root.level:
        debug_path = f"debug/ml/{debug_name}"
        Path(debug_path).mkdir(parents=True, exist_ok=True)
        cv.imwrite(f"{debug_path}/1_original.jpg", image)
        cv.imwrite(f"{debug_path}/2_greyscale.jpg", greyscale_image)
        cv.imwrite(f"{debug_path}/3_resized_{guess}.jpg", resized_image)
    return guess


# Identify a mid or anchor character by its mini portrait
def identify_char23(image, model, debug_name="guess"):
    height, width = 12, 48
    rgb_image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
    # Resize to the correct size so it can be accepted by the model
    resized_image = cv.resize(rgb_image, (width, height), interpolation=cv.INTER_CUBIC)
    img_array = np.array(resized_image)
    img_array = img_array.astype('float32')
    img_array = img_array / 255.0
    img_array = img_array.reshape(1,height,width,3)
    output_labels = model.predict(img_array, verbose=None)[0]
    guess = char23_list[argmax(output_labels)]
    if logging.DEBUG >= logging.root.level:
        debug_path = f"debug/ml/{debug_name}"
        Path(debug_path).mkdir(parents=True, exist_ok=True)
        cv.imwrite(f"{debug_path}/1_original.jpg", image)
        cv.imwrite(f"{debug_path}/2_rgb.jpg", rgb_image)
        cv.imwrite(f"{debug_path}/3_resized_{guess}.jpg", resized_image)
    return guess
