//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_conversation_transcriber_result.h: Public API declarations for ConversationTranscriberResult related C methods and enumerations
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI conversation_transcription_result_get_speaker_id(SPXRESULTHANDLE hresult, char* pszSpeakerId, uint32_t cchSpeakerId);
