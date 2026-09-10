#
# Copyright © 2025 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
import numpy as np
import cv2


def pHash(img):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = img.shape[:2]
    vis0 = np.zeros((h, w), np.float32)
    vis0[:h, :w] = img

    vis1 = cv2.dct(cv2.dct(vis0))
    vis1 = vis1[:8, :8]

    img_list = vis1.flatten().tolist()

    avg = sum(img_list) * 1.0 / 64
    avg_list = [0 if i < avg else 1 for i in img_list]
    return avg_list


def hanming_dist(s1, s2):
    return sum([ch1 != ch2 for ch1, ch2 in zip(s1, s2)])


def compare(
    video1: cv2.VideoCapture = None, video2: cv2.VideoCapture = None
) -> bool:
    # compare frame count.
    if video1.get(cv2.CAP_PROP_FRAME_COUNT) != video2.get(
        cv2.CAP_PROP_FRAME_COUNT
    ):
        return False

    frame_count = int(video1.get(cv2.CAP_PROP_FRAME_COUNT))

    similar = 0
    grab_failure_cnt = 0

    # grab frame and compare.
    for _ in range(frame_count):
        retval1 = video1.grab()
        retval2 = video2.grab()

        if not retval1 or not retval2:
            grab_failure_cnt += 1
            if grab_failure_cnt >= 10:
                raise Exception(
                    "Grab failed too much >= {} times, could be endless loop.".format(
                        10
                    )
                )
        else:
            grab_failure_cnt = 0

        flag1, frame1 = video1.retrieve()
        flag2, frame2 = video2.retrieve()

        if flag1 & flag2:
            phash1 = pHash(frame1)
            phash2 = pHash(frame2)

            if hanming_dist(phash1, phash2) < 12:
                similar += 1

    print("similar:", similar / frame_count, " frame_count:", frame_count)
    return similar / frame_count == 1


def compareVideo(srcVideo, dstVideo):
    video1 = cv2.VideoCapture(srcVideo)
    video2 = cv2.VideoCapture(dstVideo)
    return compare(video1, video2)
