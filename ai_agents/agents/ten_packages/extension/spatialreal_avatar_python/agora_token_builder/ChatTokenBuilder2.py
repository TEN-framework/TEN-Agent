# -*- coding: utf-8 -*-
__copyright__ = "Copyright (c) 2014-2017 Agora.io, Inc."


from .AccessToken2 import *


class ChatTokenBuilder:
    @staticmethod
    def build_user_token(app_id, app_certificate, user_id, expire):
        """
        Build the Chat token for user.
        :param app_id: The App ID issued to you by Agora. Apply for a new App ID from Agora Dashboard if it is missing
            from your kit. See Get an App ID.
        :param app_certificate: Certificate of the application that you registered in the Agora Dashboard.
            See Get an App Certificate.
        :param user_id: The user's unique id used in chat service.
        :param expire: represented by the number of seconds elapsed since now. If, for example, you want to access the
            Agora Service within 10 minutes after the token is generated, set expire as 600(seconds).
        :return: The Chat User token.
        """
        token = AccessToken(app_id, app_certificate, expire=expire)

        chat_service = ServiceChat(user_id)
        chat_service.add_privilege(ServiceChat.kPrivilegeUser, expire)

        token.add_service(chat_service)
        return token.build()

    @staticmethod
    def build_app_token(app_id, app_certificate, expire):
        """
        Build the Chat token for app.
        :param app_id: The App ID issued to you by Agora. Apply for a new App ID from Agora Dashboard if it is missing
            from your kit. See Get an App ID.
        :param app_certificate: Certificate of the application that you registered in the Agora Dashboard.
            See Get an App Certificate.
        :param expire: represented by the number of seconds elapsed since now. If, for example, you want to access the
            Agora Service within 10 minutes after the token is generated, set expire as 600(seconds).
        :return: The Chat App token.
        """
        token = AccessToken(app_id, app_certificate, expire=expire)

        chat_service = ServiceChat()
        chat_service.add_privilege(ServiceChat.kPrivilegeApp, expire)

        token.add_service(chat_service)
        return token.build()
