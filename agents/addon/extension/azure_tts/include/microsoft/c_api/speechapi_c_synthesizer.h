//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_synthesizer.h: Public API declarations for Synthesizer related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>
#include <speechapi_c_connection.h>
#include <speechapi_c_synthesis_request.h>


enum SpeechSynthesis_BoundaryType
{
    SpeechSynthesis_BoundaryType_Word = 0,
    SpeechSynthesis_BoundaryType_Punctuation = 1,
    SpeechSynthesis_BoundaryType_Sentence = 2
};
typedef enum SpeechSynthesis_BoundaryType SpeechSynthesis_BoundaryType;

SPXAPI_(bool) synthesizer_handle_is_valid(SPXSYNTHHANDLE hsynth);
SPXAPI synthesizer_handle_release(SPXSYNTHHANDLE hsynth);

SPXAPI_(bool) synthesizer_async_handle_is_valid(SPXASYNCHANDLE hasync);
SPXAPI synthesizer_async_handle_release(SPXASYNCHANDLE hasync);

SPXAPI_(bool) synthesizer_result_handle_is_valid(SPXRESULTHANDLE hresult);
SPXAPI synthesizer_result_handle_release(SPXRESULTHANDLE hresult);

SPXAPI_(bool) synthesizer_event_handle_is_valid(SPXEVENTHANDLE hevent);
SPXAPI synthesizer_event_handle_release(SPXEVENTHANDLE hevent);

SPXAPI synthesizer_get_property_bag(SPXSYNTHHANDLE hsynth, SPXPROPERTYBAGHANDLE* hpropbag);

SPXAPI synthesizer_speak_text(SPXSYNTHHANDLE hsynth, const char* text, uint32_t textLength, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_speak_ssml(SPXSYNTHHANDLE hsynth, const char* ssml, uint32_t ssmlLength, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_speak_request(SPXSYNTHHANDLE hsynth, SPXREQUESTHANDLE hrequest, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_speak_text_async(SPXSYNTHHANDLE hsynth, const char* text, uint32_t textLength, SPXASYNCHANDLE* phasync);
SPXAPI synthesizer_speak_ssml_async(SPXSYNTHHANDLE hsynth, const char* ssml, uint32_t ssmlLength, SPXASYNCHANDLE* phasync);
SPXAPI synthesizer_speak_request_async(SPXSYNTHHANDLE hsynth, SPXREQUESTHANDLE hrequest, SPXASYNCHANDLE* phasync);
SPXAPI synthesizer_start_speaking_text(SPXSYNTHHANDLE hsynth, const char* text, uint32_t textLength, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_start_speaking_ssml(SPXSYNTHHANDLE hsynth, const char* ssml, uint32_t ssmlLength, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_start_speaking_request(SPXSYNTHHANDLE hsynth, SPXREQUESTHANDLE hrequest, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_start_speaking_text_async(SPXSYNTHHANDLE hsynth, const char* text, uint32_t textLength, SPXASYNCHANDLE* phasync);
SPXAPI synthesizer_start_speaking_ssml_async(SPXSYNTHHANDLE hsynth, const char* ssml, uint32_t ssmlLength, SPXASYNCHANDLE* phasync);
SPXAPI synthesizer_speak_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_stop_speaking(SPXSYNTHHANDLE hsynth);
SPXAPI synthesizer_stop_speaking_async(SPXSYNTHHANDLE hsynth, SPXASYNCHANDLE* phasync);
SPXAPI synthesizer_stop_speaking_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds);

SPXAPI synthesizer_get_voices_list(SPXSYNTHHANDLE hsynth, const char* locale, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_get_voices_list_async(SPXSYNTHHANDLE hsynth, const char* locale, SPXASYNCHANDLE* phasync);
SPXAPI synthesizer_get_voices_list_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds, SPXRESULTHANDLE* phresult);

typedef void(*PSYNTHESIS_CALLBACK_FUNC)(SPXSYNTHHANDLE hsynth, SPXEVENTHANDLE hevent, void* pvContext);
SPXAPI synthesizer_started_set_callback(SPXSYNTHHANDLE hsynth, PSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI synthesizer_synthesizing_set_callback(SPXSYNTHHANDLE hsynth, PSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI synthesizer_completed_set_callback(SPXSYNTHHANDLE hsynth, PSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI synthesizer_canceled_set_callback(SPXSYNTHHANDLE hsynth, PSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI synthesizer_word_boundary_set_callback(SPXSYNTHHANDLE hsynth, PSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI synthesizer_viseme_received_set_callback(SPXSYNTHHANDLE hsynth, PSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI synthesizer_bookmark_reached_set_callback(SPXSYNTHHANDLE hsynth, PSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI synthesizer_connection_connected_set_callback(SPXCONNECTIONHANDLE hConnection, CONNECTION_CALLBACK_FUNC pCallback, void * pvContext);
SPXAPI synthesizer_connection_disconnected_set_callback(SPXCONNECTIONHANDLE hConnection, CONNECTION_CALLBACK_FUNC pCallback, void * pvContext);

SPXAPI synthesizer_synthesis_event_get_result(SPXEVENTHANDLE hevent, SPXRESULTHANDLE* phresult);
SPXAPI synthesizer_word_boundary_event_get_values(SPXEVENTHANDLE hevent, uint64_t *pAudioOffset, uint64_t *pDuration,
                                                  uint32_t *pTextOffset, uint32_t *pWordLength, SpeechSynthesis_BoundaryType *pBoundaryType);
SPXAPI synthesizer_event_get_result_id(SPXEVENTHANDLE hEvent, char* resultId, uint32_t resultIdLength);
SPXAPI__(const char*) synthesizer_event_get_text(SPXEVENTHANDLE hEvent);
SPXAPI synthesizer_viseme_event_get_values(SPXEVENTHANDLE hevent, uint64_t* pAudioOffset, uint32_t* pVisemeId);
SPXAPI__(const char*) synthesizer_viseme_event_get_animation(SPXEVENTHANDLE hEvent);
SPXAPI synthesizer_bookmark_event_get_values(SPXEVENTHANDLE hevent, uint64_t* pAudioOffset);
