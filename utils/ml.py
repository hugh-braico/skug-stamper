import numpy as np
from numpy import argmax
from keras.models import load_model
from glob import glob
import cv2 as cv
from pathlib import Path
import logging

char1_list  = ["AN","BB","BD","BW","CE","DB","EL","FI","FU","MF",    "PC","PS","PW","RF","SQ","UM","VA"]
char23_list = ["AN","BB","BD","BW","CE","DB","EL","FI","FU","MF","N","PC","PS","PW","RF","SQ","UM","VA"]


# Identify a point character by its big portrait
def identify_char1(image, model):
    height, width = 80, 120
    image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    # Resize to the correct size so it can be accepted by the model
    image = cv.resize(image, (width, height), interpolation=cv.INTER_CUBIC)
    img_array = np.array(image)
    img_array = img_array.astype('float32')
    img_array = img_array / 255.0
    img_array = img_array.reshape(1,height,width,1)
    output_labels = model.predict(img_array)[0]
    return char1_list[argmax(output_labels)]


# Identify a mid or anchor character by its mini portrait
def identify_char23(image, model, debug_name="guess"):
    if logging.DEBUG >= logging.root.level:
        debug_path = f"debug/identify_char23/{debug_name}"
        Path(debug_path).mkdir(parents=True, exist_ok=True)
        cv.imwrite(f"{debug_path}/1.jpg", image)

    height, width = 12, 48
    image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
    # Resize to the correct size so it can be accepted by the model
    image = cv.resize(image, (width, height), interpolation=cv.INTER_CUBIC)
    img_array = np.array(image)
    img_array = img_array.astype('float32')
    img_array = img_array / 255.0
    img_array = img_array.reshape(1,height,width,3)
    output_labels = model.predict(img_array)[0]
    return char23_list[argmax(output_labels)]
