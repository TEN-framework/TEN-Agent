import sys
import os

from .AccessToken import *

Role_Rtm_User = 1


class RtmTokenBuilder:
    # appID: The App ID issued to you by Agora. Apply for a new App ID from
    #        Agora Dashboard if it is missing from your kit. See Get an App ID.
    # appCertificate:	Certificate of the application that you registered in
    #                  the Agora Dashboard. See Get an App Certificate.
    # userAccount: The user account.
    # role: Role_Rtm_User = 1
    # privilegeExpireTs: represented by the number of seconds elapsed since
    #                    1/1/1970. If, for example, you want to access the
    #                    Agora Service within 10 minutes after the token is
    #                    generated, set expireTimestamp as the current
    #                    timestamp + 600 (seconds)./
    @staticmethod
    def buildToken(
        appId, appCertificate, userAccount, role, privilegeExpiredTs
    ):
        token = AccessToken(appId, appCertificate, userAccount, "")
        token.addPrivilege(kRtmLogin, privilegeExpiredTs)
        return token.build()
