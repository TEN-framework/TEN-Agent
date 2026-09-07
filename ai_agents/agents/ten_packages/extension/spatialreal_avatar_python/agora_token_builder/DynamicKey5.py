# -*- coding: utf-8 -*-
__copyright__ = "Copyright (c) 2014-2017 Agora.io, Inc."


import hmac
import ctypes
import base64
import warnings
from hashlib import sha1

from .Packer import *


warnings.warn("The DynamicKey5 module is deprecated", DeprecationWarning)


# service type
MEDIA_CHANNEL_SERVICE = 1
RECORDING_SERVICE = 2
PUBLIC_SHARING_SERVICE = 3
IN_CHANNEL_PERMISSION = 4

# extra key
ALLOW_UPLOAD_IN_CHANNEL = 1

# permision
NoUpload = b"0"
AudioVideoUpload = b"3"


def generatePublicSharingKey(
    appID, appCertificate, channelName, unixTs, randomInt, uid, expiredTs
):
    return generateDynamicKey(
        PUBLIC_SHARING_SERVICE,
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        {},
    )


def generateRecordingKey(
    appID, appCertificate, channelName, unixTs, randomInt, uid, expiredTs
):
    return generateDynamicKey(
        RECORDING_SERVICE,
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        {},
    )


def generateMediaChannelKey(
    appID, appCertificate, channelName, unixTs, randomInt, uid, expiredTs
):
    return generateDynamicKey(
        MEDIA_CHANNEL_SERVICE,
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        {},
    )


def generateInChannelPermissionKey(
    appID,
    appCertificate,
    channelName,
    unixTs,
    randomInt,
    uid,
    expiredTs,
    permission,
):
    extra = {}
    extra[ALLOW_UPLOAD_IN_CHANNEL] = permission
    return generateDynamicKey(
        IN_CHANNEL_PERMISSION,
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        extra,
    )


def generateDynamicKey(
    servicetype,
    appID,
    appCertificate,
    channelName,
    unixTs,
    randomInt,
    uid,
    expiredTs,
    extra,
):
    uid = ctypes.c_uint(uid).value
    randomInt = ctypes.c_uint(randomInt).value
    signature = generateSignature(
        servicetype,
        appID,
        appCertificate,
        channelName,
        unixTs,
        randomInt,
        uid,
        expiredTs,
        extra,
    )
    version = "{0:0>3}".format(5)
    content = (
        pack_uint16(servicetype)
        + pack_string(signature)
        + pack_string(bytes.fromhex(appID))
        + pack_uint32(unixTs)
        + pack_uint32(randomInt)
        + pack_uint32(expiredTs)
        + pack_map_string(extra)
    )
    return version + base64.b64encode(content).decode("utf-8")


def generateSignature(
    servicetype,
    appID,
    appCertificate,
    channelName,
    unixTs,
    randomInt,
    uid,
    expiredTs,
    extra,
):
    content = (
        pack_uint16(servicetype)
        + pack_string(bytes.fromhex(appID))
        + pack_uint32(unixTs)
        + pack_uint32(randomInt)
        + pack_string(channelName)
        + pack_uint32(uid)
        + pack_uint32(expiredTs)
        + pack_map_string(extra)
    )
    signature = hmac.new(
        bytes.fromhex(appCertificate), content, sha1
    ).hexdigest()
    return signature.upper()
