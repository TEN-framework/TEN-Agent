import os
import sys
from collections import OrderedDict

from .AccessToken import *

Role_Attendee = 0  # depreated, same as publisher
Role_Publisher = 1  # for live broadcaster
Role_Subscriber = 2  # default, for live audience
Role_Admin = 101  # deprecated, same as publisher


class RtcTokenBuilder:
    # appID: The App ID issued to you by Agora. Apply for a new App ID from
    #        Agora Dashboard if it is missing from your kit. See Get an App ID.
    # appCertificate:	Certificate of the application that you registered in
    #                  the Agora Dashboard. See Get an App Certificate.
    # channelName:Unique channel name for the AgoraRTC session in the string format
    # uid: User ID. A 32-bit unsigned integer with a value ranging from
    #      1 to (2^32-1). uid must be unique.
    # role: Role_Publisher = 1: A broadcaster (host) in a live-broadcast profile.
    #       Role_Subscriber = 2: (Default) A audience in a live-broadcast profile.
    # privilegeExpireTs: represented by the number of seconds elapsed since
    #                    1/1/1970. If, for example, you want to access the
    #                    Agora Service within 10 minutes after the token is
    #                    generated, set expireTimestamp as the current
    #                    timestamp + 600 (seconds)./
    @staticmethod
    def buildTokenWithUid(
        appId, appCertificate, channelName, uid, role, privilegeExpiredTs
    ):
        return RtcTokenBuilder.buildTokenWithAccount(
            appId, appCertificate, channelName, uid, role, privilegeExpiredTs
        )

    # appID: The App ID issued to you by Agora. Apply for a new App ID from
    #        Agora Dashboard if it is missing from your kit. See Get an App ID.
    # appCertificate:	Certificate of the application that you registered in
    #                  the Agora Dashboard. See Get an App Certificate.
    # channelName:Unique channel name for the AgoraRTC session in the string format
    # userAccount: The user account.
    # role: Role_Publisher = 1: A broadcaster (host) in a live-broadcast profile.
    #       Role_Subscriber = 2: (Default) A audience in a live-broadcast profile.
    # privilegeExpireTs: represented by the number of seconds elapsed since
    #                    1/1/1970. If, for example, you want to access the
    #                    Agora Service within 10 minutes after the token is
    #                    generated, set expireTimestamp as the current
    @staticmethod
    def buildTokenWithAccount(
        appId, appCertificate, channelName, account, role, privilegeExpiredTs
    ):
        token = AccessToken(appId, appCertificate, channelName, account)
        token.addPrivilege(kJoinChannel, privilegeExpiredTs)
        if (
            (role == Role_Attendee)
            | (role == Role_Admin)
            | (role == Role_Publisher)
        ):
            token.addPrivilege(kPublishVideoStream, privilegeExpiredTs)
            token.addPrivilege(kPublishAudioStream, privilegeExpiredTs)
            token.addPrivilege(kPublishDataStream, privilegeExpiredTs)
        return token.build()
