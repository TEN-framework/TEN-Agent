# -*- coding: utf-8 -*-
__copyright__ = "Copyright (c) 2014-2017 Agora.io, Inc."


import hmac
import ctypes
import warnings
from hashlib import sha1


warnings.warn("The DynamicKey4 module is deprecated", DeprecationWarning)


def generatePublicSharingKey(
    appID, appCertificate, channelName, unixTs, randomInt, uid, expiredTs
):
    return generateDynamicKey(
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        "APSS",
    )


def generateRecordingKey(
    appID, appCertificate, channelName, unixTs, randomInt, uid, expiredTs
):
    return generateDynamicKey(
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        "ARS",
    )


def generateMediaChannelKey(
    appID, appCertificate, channelName, unixTs, randomInt, uid, expiredTs
):
    return generateDynamicKey(
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        "ACS",
    )


def generateDynamicKey(
    appID,
    appCertificate,
    channelName,
    unixTs,
    randomInt,
    uid,
    expiredTs,
    servicetype,
):
    uid = ctypes.c_uint(uid).value
    randomInt = ctypes.c_uint(randomInt).value
    signature = generateSignature(
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        servicetype,
    )
    version = "{0:0>3}".format(4)
    ret = (
        version
        + str(signature)
        + appID
        + "{0:0>10}".format(unixTs)
        + "%.8x" % (int(randomInt) & 0xFFFFFFFF)
        + "{:0>10}".format(expiredTs)
    )
    return ret


def generateSignature(
    appID,
    appCertificate,
    channelName,
    unixTs,
    randomInt,
    uid,
    expiredTs,
    servicetype,
):
    key = "\x00" * (32 - len(appID)) + appID
    content = (
        servicetype
        + key
        + "{:0>10}".format(unixTs)
        + "%.8x" % (int(randomInt) & 0xFFFFFFFF)
        + str(channelName)
        + "{:0>10}".format(uid)
        + "{:0>10}".format(expiredTs)
    )
    signature = hmac.new(
        appCertificate.encode("utf-8"), content.encode("utf-8"), sha1
    ).hexdigest()
    return signature
