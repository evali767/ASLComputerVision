import cv2
import mediapipe as mp
import numpy as np
import math
import time

# If mp.solutions isn't exposed, try importing the submodule and attach it
if not hasattr(mp, "solutions"):
    import mediapipe.solutions as solutions
    mp.solutions = solutions

from cvzone.HandTrackingModule import HandDetector

cap = cv2.VideoCapture(0)
detector = HandDetector(maxHands=1)

offset = 20
imgSize = 500

folder = "Data/J"
counter = 0



while True:
    success, img = cap.read()
    hands, img = detector.findHands(img)
    if hands:
        # only have one hand
        hand = hands[0]
        # give us all the values
        x, y, w, h = hand['bbox']
        # *255 to get white
        imgWhite = np.ones((imgSize, imgSize, 3), np.uint8)*255

        # give us cropped boundin gbox
        # add offset to make offset a bit bigger
        imgCrop = img[y-offset:y+h+offset, x-offset:x+w+offset]
        imgCropShape = imgCrop.shape

        

        aspectRatio = h/w
        if aspectRatio > 1:
            k = imgSize/h
            # always round up
            wCal = math.ceil(k*w)
            imgResize = cv2.resize(imgCrop, (wCal,imgSize))
            imgResizeShape = imgResize.shape
            # width gap
            wGap = math.ceil((imgSize-wCal)/2)
            # gives us height and width
            # centers in middle
            imgWhite[:, wGap:wCal+wGap] = imgResize
        else:
            k = imgSize/w
            # always round up
            hCal = math.ceil(k*h)
            imgResize = cv2.resize(imgCrop, (imgSize,hCal))
            imgResizeShape = imgResize.shape
            # width gap
            hGap = math.ceil((imgSize-hCal)/2)
            # gives us height and width
            # centers in middle
            imgWhite[hGap:hCal+hGap, :] = imgResize



        cv2.imshow("ImageCrop", imgCrop)
        cv2.imshow("ImageWhite", imgWhite)  


    cv2.imshow("Image", img)
    key = cv2.waitKey(1)
    if key == ord("s"):
        counter += 1
        cv2.imwrite(f'{folder}/Image_{time.time()}.jpg', imgWhite)
        print(counter)