//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_meeting_transcriber_result.h: Public API declarations for MeetingTranscriberResult related C methods and enumerations
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI meeting_transcription_result_get_user_id(SPXRESULTHANDLE hresult, char* pszUserId, uint32_t cchUserId);
SPXAPI meeting_transcription_result_get_utterance_id(SPXRESULTHANDLE hresult, char* pszUtteranceId, uint32_t cchUtteranceId);
