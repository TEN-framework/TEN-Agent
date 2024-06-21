//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_recognizer.h: Public API declarations for Recognizer related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>


SPXAPI_(bool) recognizer_handle_is_valid(SPXRECOHANDLE hreco);
SPXAPI recognizer_handle_release(SPXRECOHANDLE hreco);

SPXAPI_(bool) recognizer_async_handle_is_valid(SPXASYNCHANDLE hasync);
SPXAPI recognizer_async_handle_release(SPXASYNCHANDLE hasync);

SPXAPI_(bool) recognizer_result_handle_is_valid(SPXRESULTHANDLE hresult);
SPXAPI recognizer_result_handle_release(SPXRESULTHANDLE hresult);

SPXAPI_(bool) recognizer_event_handle_is_valid(SPXEVENTHANDLE hevent);
SPXAPI recognizer_event_handle_release(SPXEVENTHANDLE hevent);

SPXAPI recognizer_get_property_bag(SPXRECOHANDLE hreco, SPXPROPERTYBAGHANDLE* hpropbag);

SPXAPI recognizer_recognize_once(SPXRECOHANDLE hreco, SPXRESULTHANDLE* phresult);
SPXAPI recognizer_recognize_once_async(SPXRECOHANDLE hreco, SPXASYNCHANDLE* phasync);
SPXAPI recognizer_recognize_text_once_async(SPXRECOHANDLE hreco, const char* text, SPXASYNCHANDLE* phasync);
SPXAPI recognizer_recognize_once_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds, SPXRESULTHANDLE* phresult);

SPXAPI recognizer_start_continuous_recognition(SPXRECOHANDLE hreco);
SPXAPI recognizer_start_continuous_recognition_async(SPXRECOHANDLE hreco, SPXASYNCHANDLE* phasync);
SPXAPI recognizer_start_continuous_recognition_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds);

SPXAPI recognizer_stop_continuous_recognition(SPXRECOHANDLE hreco);
SPXAPI recognizer_stop_continuous_recognition_async(SPXRECOHANDLE hreco, SPXASYNCHANDLE* phasync);
SPXAPI recognizer_stop_continuous_recognition_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds);

SPXAPI recognizer_start_keyword_recognition(SPXRECOHANDLE hreco, SPXKEYWORDHANDLE hkeyword);
SPXAPI recognizer_start_keyword_recognition_async(SPXRECOHANDLE hreco, SPXKEYWORDHANDLE hkeyword, SPXASYNCHANDLE* phasync);
SPXAPI recognizer_start_keyword_recognition_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds);

SPXAPI recognizer_recognize_keyword_once(SPXRECOHANDLE hreco, SPXKEYWORDHANDLE hkeyword, SPXRESULTHANDLE* phresult);
SPXAPI recognizer_recognize_keyword_once_async(SPXRECOHANDLE hreco, SPXKEYWORDHANDLE hkeyword, SPXASYNCHANDLE* phasync);
SPXAPI recognizer_recognize_keyword_once_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds, SPXRESULTHANDLE* phresult);

SPXAPI recognizer_stop_keyword_recognition(SPXRECOHANDLE hreco);
SPXAPI recognizer_stop_keyword_recognition_async(SPXRECOHANDLE hreco, SPXASYNCHANDLE* phasync);
SPXAPI recognizer_stop_keyword_recognition_async_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds);

typedef void (*PSESSION_CALLBACK_FUNC)(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext);
SPXAPI recognizer_session_started_set_callback(SPXRECOHANDLE hreco, PSESSION_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI recognizer_session_stopped_set_callback(SPXRECOHANDLE hreco, PSESSION_CALLBACK_FUNC pCallback, void* pvContext);

typedef void (*PRECOGNITION_CALLBACK_FUNC)(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext);
SPXAPI recognizer_recognizing_set_callback(SPXRECOHANDLE hreco, PRECOGNITION_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI recognizer_recognized_set_callback(SPXRECOHANDLE hreco, PRECOGNITION_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI recognizer_canceled_set_callback(SPXRECOHANDLE hreco, PRECOGNITION_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI recognizer_speech_start_detected_set_callback(SPXRECOHANDLE hreco, PRECOGNITION_CALLBACK_FUNC pCallback, void* pvContext);
SPXAPI recognizer_speech_end_detected_set_callback(SPXRECOHANDLE hreco, PRECOGNITION_CALLBACK_FUNC pCallback, void* pvContext);

SPXAPI recognizer_session_event_get_session_id(SPXEVENTHANDLE hevent, char* pszSessionId, uint32_t cchSessionId);
SPXAPI recognizer_recognition_event_get_offset(SPXEVENTHANDLE hevent, uint64_t *pszOffset);
SPXAPI recognizer_recognition_event_get_result(SPXEVENTHANDLE hevent, SPXRESULTHANDLE* phresult);

SPXAPI recognizer_connection_event_get_property_bag(SPXEVENTHANDLE hevent, SPXPROPERTYBAGHANDLE* hpropbag);
