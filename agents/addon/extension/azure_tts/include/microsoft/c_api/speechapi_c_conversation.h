//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_conversation.h: Public API declarations for conversation related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI conversation_create_from_config(SPXCONVERSATIONHANDLE* phconv, SPXSPEECHCONFIGHANDLE hspeechconfig, const char* id);
SPXAPI conversation_update_participant_by_user_id(SPXCONVERSATIONHANDLE hconv, bool add, const char* userId);
SPXAPI conversation_update_participant_by_user(SPXCONVERSATIONHANDLE hconv, bool add, SPXUSERHANDLE huser);
SPXAPI conversation_update_participant(SPXCONVERSATIONHANDLE hconv, bool add, SPXPARTICIPANTHANDLE hparticipant);
SPXAPI conversation_get_conversation_id(SPXCONVERSATIONHANDLE hconv, char* id, size_t size);
SPXAPI conversation_end_conversation(SPXCONVERSATIONHANDLE hconv);
SPXAPI conversation_get_property_bag(SPXCONVERSATIONHANDLE hconv, SPXPROPERTYBAGHANDLE* phpropbag);
SPXAPI conversation_release_handle(SPXHANDLE handle);

SPXAPI conversation_start_conversation(SPXCONVERSATIONHANDLE hconv);
SPXAPI conversation_delete_conversation(SPXCONVERSATIONHANDLE hconv);
SPXAPI conversation_lock_conversation(SPXCONVERSATIONHANDLE hconv);
SPXAPI conversation_unlock_conversation(SPXCONVERSATIONHANDLE hconv);
SPXAPI conversation_mute_all_participants(SPXCONVERSATIONHANDLE hconv);
SPXAPI conversation_unmute_all_participants(SPXCONVERSATIONHANDLE hconv);
SPXAPI conversation_mute_participant(SPXCONVERSATIONHANDLE hconv, const char * participantId);
SPXAPI conversation_unmute_participant(SPXCONVERSATIONHANDLE hconv, const char * participantId);

