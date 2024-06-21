//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_audio_stream.h: Public API declarations for audio stream related C methods and types
//

#pragma once
#include <speechapi_c_common.h>
#include <speechapi_c_result.h>

typedef enum
{
    StreamStatus_Unknown = 0,
    StreamStatus_NoData = 1,
    StreamStatus_PartialData = 2,
    StreamStatus_AllData = 3,
    StreamStatus_Canceled = 4
} Stream_Status;

// audio_stream
SPXAPI_(bool) audio_stream_is_handle_valid(SPXAUDIOSTREAMHANDLE haudioStream);
SPXAPI audio_stream_create_push_audio_input_stream(SPXAUDIOSTREAMHANDLE* haudioStream, SPXAUDIOSTREAMFORMATHANDLE hformat);
SPXAPI audio_stream_create_pull_audio_input_stream(SPXAUDIOSTREAMHANDLE* haudioStream, SPXAUDIOSTREAMFORMATHANDLE hformat);
SPXAPI audio_stream_create_pull_audio_output_stream(SPXAUDIOSTREAMHANDLE* haudioStream);
SPXAPI audio_stream_create_push_audio_output_stream(SPXAUDIOSTREAMHANDLE* haudioStream);
SPXAPI audio_stream_release(SPXAUDIOSTREAMHANDLE haudioStream);

// pull_audio_input_stream
typedef int (*CUSTOM_AUDIO_PULL_STREAM_READ_CALLBACK)(void* pvContext, uint8_t* buffer, uint32_t size);
typedef void (*CUSTOM_AUDIO_PULL_STREAM_CLOSE_CALLBACK)(void* pvContext);
typedef void (*CUSTOM_AUDIO_PULL_STREAM_GET_PROPERTY_CALLBACK)(void* pvContext, int id, uint8_t* value, uint32_t size);
SPXAPI pull_audio_input_stream_set_callbacks(SPXAUDIOSTREAMHANDLE haudioStream, void* pvContext, CUSTOM_AUDIO_PULL_STREAM_READ_CALLBACK readCallback, CUSTOM_AUDIO_PULL_STREAM_CLOSE_CALLBACK closeCallback);
SPXAPI pull_audio_input_stream_set_getproperty_callback(SPXAUDIOSTREAMHANDLE haudioStream, void* pvContext, CUSTOM_AUDIO_PULL_STREAM_GET_PROPERTY_CALLBACK getPropertyCallback);

// push_audio_input_stream
SPXAPI push_audio_input_stream_write(SPXAUDIOSTREAMHANDLE haudioStream, uint8_t* buffer, uint32_t size);
SPXAPI push_audio_input_stream_close(SPXAUDIOSTREAMHANDLE haudioStream);
SPXAPI push_audio_input_stream_set_property_by_id(SPXAUDIOSTREAMHANDLE haudioStream, int id, const char* value);
SPXAPI push_audio_input_stream_set_property_by_name(SPXAUDIOSTREAMHANDLE haudioStream, const char* name, const char* value);

// pull audio output stream
SPXAPI pull_audio_output_stream_read(SPXAUDIOSTREAMHANDLE haudioStream, uint8_t* buffer, uint32_t bufferSize, uint32_t* pfilledSize);

// push_audio_output_stream
typedef int(*CUSTOM_AUDIO_PUSH_STREAM_WRITE_CALLBACK)(void* pvContext, uint8_t* buffer, uint32_t size);
typedef void(*CUSTOM_AUDIO_PUSH_STREAM_CLOSE_CALLBACK)(void* pvContext);
SPXAPI push_audio_output_stream_set_callbacks(SPXAUDIOSTREAMHANDLE haudioStream, void* pvContext, CUSTOM_AUDIO_PUSH_STREAM_WRITE_CALLBACK writeCallback, CUSTOM_AUDIO_PUSH_STREAM_CLOSE_CALLBACK closeCallback);

// audio data stream
SPXAPI_(bool) audio_data_stream_is_handle_valid(SPXAUDIOSTREAMHANDLE haudioStream);
SPXAPI audio_data_stream_create_from_file(SPXAUDIOSTREAMHANDLE* haudioStream, const char* fileName);
SPXAPI audio_data_stream_create_from_result(SPXAUDIOSTREAMHANDLE* haudioStream, SPXRESULTHANDLE hresult);
SPXAPI audio_data_stream_create_from_keyword_result(SPXAUDIOSTREAMHANDLE* audioStreamHandle, SPXRESULTHANDLE resultHandle);
SPXAPI audio_data_stream_get_status(SPXAUDIOSTREAMHANDLE haudioStream, Stream_Status* status);
SPXAPI audio_data_stream_get_reason_canceled(SPXAUDIOSTREAMHANDLE haudioStream, Result_CancellationReason* reason);
SPXAPI audio_data_stream_get_canceled_error_code(SPXAUDIOSTREAMHANDLE haudioStream, Result_CancellationErrorCode* errorCode);
SPXAPI_(bool) audio_data_stream_can_read_data(SPXAUDIOSTREAMHANDLE haudioStream, uint32_t requestedSize);
SPXAPI_(bool) audio_data_stream_can_read_data_from_position(SPXAUDIOSTREAMHANDLE haudioStream, uint32_t requestedSize, uint32_t position);
SPXAPI audio_data_stream_read(SPXAUDIOSTREAMHANDLE haudioStream, uint8_t* buffer, uint32_t bufferSize, uint32_t* pfilledSize);
SPXAPI audio_data_stream_read_from_position(SPXAUDIOSTREAMHANDLE haudioStream, uint8_t* buffer, uint32_t bufferSize, uint32_t position, uint32_t* pfilledSize);
SPXAPI audio_data_stream_save_to_wave_file(SPXAUDIOSTREAMHANDLE haudioStream, const char* fileName);
SPXAPI audio_data_stream_get_position(SPXAUDIOSTREAMHANDLE haudioStream, uint32_t* position);
SPXAPI audio_data_stream_set_position(SPXAUDIOSTREAMHANDLE haudioStream, uint32_t position);
SPXAPI audio_data_stream_detach_input(SPXAUDIOSTREAMHANDLE audioStreamHandle);
SPXAPI audio_data_stream_get_property_bag(SPXAUDIOSTREAMHANDLE haudioStream, SPXPROPERTYBAGHANDLE* hpropbag);
SPXAPI audio_data_stream_release(SPXAUDIOSTREAMHANDLE haudioStream);
