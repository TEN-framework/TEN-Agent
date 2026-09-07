# -*- coding: utf-8 -*-
__copyright__ = "Copyright (c) 2014-2017 Agora.io, Inc."

from .AccessToken2 import *


class FpaTokenBuilder:
    @staticmethod
    def build_token(app_id, app_certificate):
        """
        Build the FPA token.
        :param app_id: The App ID issued to you by Agora. Apply for a new App ID from Agora Dashboard if it is missing
            from your kit. See Get an App ID.
        :param app_certificate: Certificate of the application that you registered in the Agora Dashboard.
            See Get an App Certificate.
        :return: The FPA token.
        """
        token = AccessToken(app_id, app_certificate, expire=24 * 3600)

        service_fpa = ServiceFpa()
        service_fpa.add_privilege(ServiceFpa.kPrivilegeLogin, 0)
        token.add_service(service_fpa)

        return token.build()
