//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_meeting.h: Public API declarations for meeting related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI meeting_create_from_config(SPXMEETINGHANDLE* phmeeting, SPXSPEECHCONFIGHANDLE hspeechconfig, const char* id);
SPXAPI meeting_update_participant_by_user_id(SPXMEETINGHANDLE hconv, bool add, const char* userId);
SPXAPI meeting_update_participant_by_user(SPXMEETINGHANDLE hconv, bool add, SPXUSERHANDLE huser);
SPXAPI meeting_update_participant(SPXMEETINGHANDLE hconv, bool add, SPXPARTICIPANTHANDLE hparticipant);
SPXAPI meeting_get_meeting_id(SPXMEETINGHANDLE hconv, char* id, size_t size);
SPXAPI meeting_end_meeting(SPXMEETINGHANDLE hconv);
SPXAPI meeting_get_property_bag(SPXMEETINGHANDLE hconv, SPXPROPERTYBAGHANDLE* phpropbag);
SPXAPI meeting_release_handle(SPXHANDLE handle);

SPXAPI meeting_start_meeting(SPXMEETINGHANDLE hconv);
SPXAPI meeting_delete_meeting(SPXMEETINGHANDLE hconv);
SPXAPI meeting_lock_meeting(SPXMEETINGHANDLE hconv);
SPXAPI meeting_unlock_meeting(SPXMEETINGHANDLE hconv);
SPXAPI meeting_mute_all_participants(SPXMEETINGHANDLE hconv);
SPXAPI meeting_unmute_all_participants(SPXMEETINGHANDLE hconv);
SPXAPI meeting_mute_participant(SPXMEETINGHANDLE hconv, const char * participantId);
SPXAPI meeting_unmute_participant(SPXMEETINGHANDLE hconv, const char * participantId);

