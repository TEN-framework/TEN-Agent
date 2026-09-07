# -*- coding: utf-8 -*-
__copyright__ = "Copyright (c) 2014-2017 Agora.io, Inc."


import hmac
import ctypes
import warnings
from hashlib import sha1


warnings.warn("The DynamicKey module is deprecated", DeprecationWarning)


def generateSignaure(appID, appCertificate, channelName, unixTs, randomInt):
    key = "\x00" * (32 - len(appID)) + appID
    content = (
        key
        + "{:0>10}".format(unixTs)
        + "%.8x" % (int(randomInt) & 0xFFFFFFFF)
        + str(channelName)
    )
    signature = hmac.new(
        appCertificate.encode("utf-8"), content.encode("utf-8"), sha1
    ).hexdigest()
    return signature


def generate(appID, appCertificate, channelName, unixTs, randomInt):
    randomInt = ctypes.c_uint(randomInt).value
    signature = generateSignaure(
        appID, appCertificate, channelName, unixTs, randomInt
    )
    ret = (
        str(signature)
        + appID
        + "{0:0>10}".format(unixTs)
        + "%.8x" % (int(randomInt) & 0xFFFFFFFF)
    )
    return ret
