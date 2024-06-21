//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_conversation_translator.h: Public API declarations for conversation translator related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>
#include <speechapi_c_connection.h>

#ifdef __cplusplus
#include <speechapi_cxx_enums.h>
typedef Microsoft::CognitiveServices::Speech::Transcription::ParticipantChangedReason ParticipantChangedReason;
#else
#include <speechapi_c_property_bag.h>
#endif

typedef void(*PCONV_TRANS_CALLBACK)(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, SPXEVENTHANDLE hEvent, void* pvContext);

SPXAPI conversation_translator_create_from_config(SPXCONVERSATIONTRANSLATORHANDLE* phandle, SPXAUDIOCONFIGHANDLE haudioinput);
SPXAPI conversation_translator_get_property_bag(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator, SPXPROPERTYBAGHANDLE* phpropertyBag);

SPXAPI conversation_translator_join(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator, SPXCONVERSATIONHANDLE hconv, const char* psznickname);
SPXAPI conversation_translator_join_with_id(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator, const char *pszconversationid, const char* psznickname, const char * pszlang);
SPXAPI conversation_translator_start_transcribing(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator);
SPXAPI conversation_translator_stop_transcribing(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator);
SPXAPI conversation_translator_send_text_message(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator, const char *pszmessage);
SPXAPI conversation_translator_leave(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator);
SPXAPI conversation_translator_set_authorization_token(SPXCONVERSATIONTRANSLATORHANDLE hconvtranslator, const char* pszAuthToken, const char* pszRegion);

SPXAPI_(bool) conversation_translator_handle_is_valid(SPXCONVERSATIONTRANSLATORHANDLE handle);
SPXAPI conversation_translator_handle_release(SPXHANDLE handle);

SPXAPI conversation_translator_session_started_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);
SPXAPI conversation_translator_session_stopped_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);
SPXAPI conversation_translator_canceled_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);
SPXAPI conversation_translator_participants_changed_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);
SPXAPI conversation_translator_conversation_expiration_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);
SPXAPI conversation_translator_transcribing_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);
SPXAPI conversation_translator_transcribed_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);
SPXAPI conversation_translator_text_message_recevied_set_callback(SPXCONVERSATIONTRANSLATORHANDLE hConvTrans, PCONV_TRANS_CALLBACK pCallback, void* pvContext);

SPXAPI conversation_translator_connection_connected_set_callback(SPXCONNECTIONHANDLE hConnection, CONNECTION_CALLBACK_FUNC pCallback, void * pvContext);
SPXAPI conversation_translator_connection_disconnected_set_callback(SPXCONNECTIONHANDLE hConnection, CONNECTION_CALLBACK_FUNC pCallback, void * pvContext);

SPXAPI_(bool) conversation_translator_event_handle_is_valid(SPXCONVERSATIONTRANSLATORHANDLE handle);
SPXAPI conversation_translator_event_handle_release(SPXHANDLE handle);

SPXAPI conversation_translator_event_get_expiration_time(SPXEVENTHANDLE hevent, int32_t* pexpirationminutes);
SPXAPI conversation_translator_event_get_participant_changed_reason(SPXEVENTHANDLE hevent, ParticipantChangedReason* preason);
SPXAPI conversation_translator_event_get_participant_changed_at_index(SPXEVENTHANDLE hevent, int index, SPXPARTICIPANTHANDLE* phparticipant);

SPXAPI conversation_translator_result_get_user_id(SPXRESULTHANDLE hresult, char* pszUserId, uint32_t cchUserId);

SPXAPI conversation_translator_result_get_original_lang(SPXRESULTHANDLE hresult, char * psz, uint32_t * pcch);

SPXAPI conversation_translator_participant_get_avatar(SPXEVENTHANDLE hevent, char * psz, uint32_t * pcch);
SPXAPI conversation_translator_participant_get_displayname(SPXEVENTHANDLE hevent, char * psz, uint32_t * pcch);
SPXAPI conversation_translator_participant_get_id(SPXEVENTHANDLE hevent, char * psz, uint32_t * pcch);
SPXAPI conversation_translator_participant_get_is_muted(SPXEVENTHANDLE hevent, bool * pMuted);
SPXAPI conversation_translator_participant_get_is_host(SPXEVENTHANDLE hevent, bool * pIsHost);
SPXAPI conversation_translator_participant_get_is_using_tts(SPXEVENTHANDLE hevent, bool * ptts);
