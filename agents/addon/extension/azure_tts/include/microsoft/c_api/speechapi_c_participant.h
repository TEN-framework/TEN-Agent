//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_participant.h: Public API declarations for conversation transcriber participant related C methods and enumerations
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI participant_create_handle(SPXPARTICIPANTHANDLE* hparticipant, const char* userId, const char* preferred_language, const char* voice_signature);
SPXAPI participant_release_handle(SPXPARTICIPANTHANDLE hparticipant);
SPXAPI participant_set_preferred_langugage(SPXPARTICIPANTHANDLE hparticipant, const char* preferred_language);
SPXAPI participant_set_voice_signature(SPXPARTICIPANTHANDLE hparticipant, const char* voice_signature);
SPXAPI participant_get_property_bag(SPXPARTICIPANTHANDLE hparticipant, SPXPROPERTYBAGHANDLE* hpropbag);
