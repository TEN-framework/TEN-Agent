# -*- coding: utf-8 -*-
__copyright__ = "Copyright (c) 2014-2024 Agora.io, Inc."

from .AccessToken2 import *
from .utils import *


class ApaasTokenBuilder:
    @staticmethod
    def build_room_user_token(
        app_id, app_certificate, room_uuid, user_uuid, role, expire
    ):
        """
        Build user room token
        :param app_id: The App ID issued to you by Agora. Apply for a new App ID from Agora Dashboard if it is missing
            from your kit. See Get an App ID.
        :param app_certificate: Certificate of the application that you registered in the Agora Dashboard.
            See Get an App Certificate.
        :param room_uuid: The room's id, must be unique.
        :param user_uuid: The user's id, must be unique.
        :param role: The user's role.
        :param expire: represented by the number of seconds elapsed since now. If, for example, you want to access the
            Agora Service within 10 minutes after the token is generated, set expire as 600(seconds).
        :return: The user room token.
        """
        token = AccessToken(app_id, app_certificate, expire=expire)

        chat_user_id = get_md5(user_uuid)
        apaas_service = ServiceApaas(room_uuid, user_uuid, role)
        apaas_service.add_privilege(ServiceApaas.kPrivilegeRoomUser, expire)
        token.add_service(apaas_service)

        rtm_service = ServiceRtm(user_uuid)
        rtm_service.add_privilege(ServiceRtm.kPrivilegeLogin, expire)
        token.add_service(rtm_service)

        chat_service = ServiceChat(chat_user_id)
        chat_service.add_privilege(ServiceChat.kPrivilegeUser, expire)
        token.add_service(chat_service)

        return token.build()

    @staticmethod
    def build_user_token(app_id, app_certificate, user_uuid, expire):
        """
        Build user token
        :param app_id: The App ID issued to you by Agora. Apply for a new App ID from Agora Dashboard if it is missing
            from your kit. See Get an App ID.
        :param app_certificate: Certificate of the application that you registered in the Agora Dashboard.
            See Get an App Certificate.
        :param user_uuid: The user's id, must be unique.
        :param expire: represented by the number of seconds elapsed since now. If, for example, you want to access the
            Agora Service within 10 minutes after the token is generated, set expire as 600(seconds).
        :return: The user token.
        """
        token = AccessToken(app_id, app_certificate, expire=expire)
        apaas_service = ServiceApaas(user_uuid=user_uuid)

        apaas_service.add_privilege(ServiceApaas.kPrivilegeUser, expire)
        token.add_service(apaas_service)

        return token.build()

    @staticmethod
    def build_app_token(app_id, app_certificate, expire):
        """
        Build app token
        :param app_id: The App ID issued to you by Agora. Apply for a new App ID from Agora Dashboard if it is missing
            from your kit. See Get an App ID.
        :param app_certificate: Certificate of the application that you registered in the Agora Dashboard.
            See Get an App Certificate.
        :param expire: represented by the number of seconds elapsed since now. If, for example, you want to access the
            Agora Service within 10 minutes after the token is generated, set expire as 600(seconds).
        :return: The app token.
        """
        token = AccessToken(app_id, app_certificate, expire=expire)
        apaas_service = ServiceApaas()

        apaas_service.add_privilege(ServiceApaas.kPrivilegeApp, expire)
        token.add_service(apaas_service)

        return token.build()
