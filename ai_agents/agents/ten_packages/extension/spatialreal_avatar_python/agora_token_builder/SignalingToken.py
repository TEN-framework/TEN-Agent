# -*- coding: utf-8 -*-
__copyright__ = "Copyright (c) 2014-2017 Agora.io, Inc."


import hashlib
import warnings


warnings.warn("The SignalingToken module is deprecated", DeprecationWarning)


def generateSignalingToken(account, appID, appCertificate, expiredTsInSeconds):
    version = "1"
    expired = str(expiredTsInSeconds)
    content = account + appID + appCertificate + expired
    md5sum = hashlib.md5(content.encode("utf-8")).hexdigest()
    result = "%s:%s:%s:%s" % (version, appID, expired, md5sum)
    return result
