//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/license202106 for the full license information.

#pragma once

// TODO: TFS#3671215 - Vision: C/C++ azac_api* files are in shared include directory, speech and vision share

#include <stdint.h>

/// <summary>
/// Type definition for Azure AI Core result codes.
/// </summary>
typedef uintptr_t AZACHR;

/// <summary>
/// Default result code indicating no error.
/// </summary>
#define AZAC_ERR_NONE                0

/// <summary>
/// Declare and initialize result code variable.
/// </summary>
#define AZAC_INIT_HR(hr)             AZACHR hr = AZAC_ERR_NONE; \
                                    (void)(hr)

/// <summary>
/// Check if result code indicates success.
/// </summary>
#define AZAC_SUCCEEDED(x)            ((x) == AZAC_ERR_NONE)

/// <summary>
/// Check if result code indicates error.
/// </summary>
#define AZAC_FAILED(x)               (!AZAC_SUCCEEDED(x))

/// <summary>
/// Base macros for all error codes.
/// </summary>
#define __AZAC_ERRCODE_FAILED(x)     (x)

/// <summary>
/// The function is not implemented.
/// </summary>
#define AZAC_ERR_NOT_IMPL             __AZAC_ERRCODE_FAILED(0xfff)

/// <summary>
/// The object has not been properly initialized.
/// </summary>
#define AZAC_ERR_UNINITIALIZED        __AZAC_ERRCODE_FAILED(0x001)

/// <summary>
/// The object has already been initialized.
/// </summary>
#define AZAC_ERR_ALREADY_INITIALIZED  __AZAC_ERRCODE_FAILED(0x002)

/// <summary>
/// An unhandled exception was detected.
/// </summary>
#define AZAC_ERR_UNHANDLED_EXCEPTION  __AZAC_ERRCODE_FAILED(0x003)

/// <summary>
/// The object or property was not found.
/// </summary>
#define AZAC_ERR_NOT_FOUND            __AZAC_ERRCODE_FAILED(0x004)

/// <summary>
/// One or more arguments are not valid.
/// </summary>
#define AZAC_ERR_INVALID_ARG          __AZAC_ERRCODE_FAILED(0x005)

/// <summary>
/// The specified timeout value has elapsed.
/// </summary>
#define AZAC_ERR_TIMEOUT              __AZAC_ERRCODE_FAILED(0x006)

/// <summary>
/// The asynchronous operation is already in progress.
/// </summary>
#define AZAC_ERR_ALREADY_IN_PROGRESS  __AZAC_ERRCODE_FAILED(0x007)

/// <summary>
/// The attempt to open the file failed.
/// </summary>
#define AZAC_ERR_FILE_OPEN_FAILED     __AZAC_ERRCODE_FAILED(0x008)

/// <summary>
/// The end of the file was reached unexpectedly.
/// </summary>
#define AZAC_ERR_UNEXPECTED_EOF       __AZAC_ERRCODE_FAILED(0x009)

/// <summary>
/// Invalid audio header encountered.
/// </summary>
#define AZAC_ERR_INVALID_HEADER       __AZAC_ERRCODE_FAILED(0x00a)

/// <summary>
/// The requested operation cannot be performed while audio is pumping
/// </summary>
#define AZAC_ERR_AUDIO_IS_PUMPING     __AZAC_ERRCODE_FAILED(0x00b)

/// <summary>
/// Unsupported audio format.
/// </summary>
#define AZAC_ERR_UNSUPPORTED_FORMAT   __AZAC_ERRCODE_FAILED(0x00c)

/// <summary>
/// Operation aborted.
/// </summary>
#define AZAC_ERR_ABORT                __AZAC_ERRCODE_FAILED(0x00d)

/// <summary>
/// Microphone is not available.
/// </summary>
#define AZAC_ERR_MIC_NOT_AVAILABLE    __AZAC_ERRCODE_FAILED(0x00e)

/// <summary>
/// An invalid state was encountered.
/// </summary>
#define AZAC_ERR_INVALID_STATE        __AZAC_ERRCODE_FAILED(0x00f)

/// <summary>
/// Attempting to create a UUID failed.
/// </summary>
#define AZAC_ERR_UUID_CREATE_FAILED   __AZAC_ERRCODE_FAILED(0x010)

/// <summary>
/// An unexpected session state transition was encountered when setting the session audio format.
/// </summary>
/// <remarks>
/// Valid transitions are:
/// * WaitForPumpSetFormatStart --> ProcessingAudio (at the beginning of stream)
/// * StoppingPump --> WaitForAdapterCompletedSetFormatStop (at the end of stream)
/// * ProcessingAudio --> WaitForAdapterCompletedSetFormatStop (when the stream runs out of data)
/// All other state transitions are invalid.
/// </remarks>
#define AZAC_ERR_SETFORMAT_UNEXPECTED_STATE_TRANSITION __AZAC_ERRCODE_FAILED(0x011)

/// <summary>
/// An unexpected session state was encountered in while processing audio.
/// </summary>
/// <remarks>
/// Valid states to encounter are:
/// * ProcessingAudio: We're allowed to process audio while in this state.
/// * StoppingPump: We're allowed to be called to process audio, but we'll ignore the data passed in while we're attempting to stop the pump.
/// All other states are invalid while processing audio.
/// </remarks>
#define AZAC_ERR_PROCESS_AUDIO_INVALID_STATE __AZAC_ERRCODE_FAILED(0x012)

/// <summary>
/// An unexpected state transition was encountered while attempting to start recognizing.
/// </summary>
/// <remarks>
/// A valid transition is:
/// * Idle --> WaitForPumpSetFormatStart
/// All other state transitions are invalid when attempting to start recognizing
/// </remarks>
#define AZAC_ERR_START_RECOGNIZING_INVALID_STATE_TRANSITION __AZAC_ERRCODE_FAILED(0x013)

/// <summary>
/// An unexpected error was encountered when trying to create an internal object.
/// </summary>
#define AZAC_ERR_UNEXPECTED_CREATE_OBJECT_FAILURE  __AZAC_ERRCODE_FAILED(0x014)

/// <summary>
/// An error in the audio-capturing system.
/// </summary>
#define AZAC_ERR_MIC_ERROR            __AZAC_ERRCODE_FAILED(0x015)

/// <summary>
/// The requested operation cannot be performed; there is no audio input.
/// </summary>
#define AZAC_ERR_NO_AUDIO_INPUT       __AZAC_ERRCODE_FAILED(0x016)

/// <summary>
/// An unexpected error was encountered when trying to access the USP site.
/// </summary>
#define AZAC_ERR_UNEXPECTED_USP_SITE_FAILURE  __AZAC_ERRCODE_FAILED(0x017)

/// <summary>
/// An unexpected error was encountered when trying to access the LU site.
/// </summary>
#define AZAC_ERR_UNEXPECTED_LU_SITE_FAILURE  __AZAC_ERRCODE_FAILED(0x018)

/// <summary>
/// The buffer is too small.
/// </summary>
#define AZAC_ERR_BUFFER_TOO_SMALL  __AZAC_ERRCODE_FAILED(0x019)

/// <summary>
/// A method failed to allocate memory.
/// </summary>
#define AZAC_ERR_OUT_OF_MEMORY  __AZAC_ERRCODE_FAILED(0x01A)

/// <summary>
/// An unexpected runtime error occurred.
/// </summary>
#define AZAC_ERR_RUNTIME_ERROR  __AZAC_ERRCODE_FAILED(0x01B)

/// <summary>
/// The url specified is invalid.
/// </summary>
#define AZAC_ERR_INVALID_URL  __AZAC_ERRCODE_FAILED(0x01C)

/// <summary>
/// The region specified is invalid or missing.
/// </summary>
#define AZAC_ERR_INVALID_REGION  __AZAC_ERRCODE_FAILED(0x01D)

/// <summary>
/// Switch between single shot and continuous recognition is not supported.
/// </summary>
#define AZAC_ERR_SWITCH_MODE_NOT_ALLOWED  __AZAC_ERRCODE_FAILED(0x01E)

/// <summary>
/// Changing connection status is not supported in the current recognition state.
/// </summary>
#define AZAC_ERR_CHANGE_CONNECTION_STATUS_NOT_ALLOWED __AZAC_ERRCODE_FAILED(0x01F)

/// <summary>
/// Explicit connection management is not supported by the specified recognizer.
/// </summary>
#define AZAC_ERR_EXPLICIT_CONNECTION_NOT_SUPPORTED_BY_RECOGNIZER  __AZAC_ERRCODE_FAILED(0x020)

/// <summary>
/// The handle is invalid.
/// </summary>
#define AZAC_ERR_INVALID_HANDLE  __AZAC_ERRCODE_FAILED(0x021)

/// <summary>
/// The recognizer is invalid.
/// </summary>
#define AZAC_ERR_INVALID_RECOGNIZER  __AZAC_ERRCODE_FAILED(0x022)

/// <summary>
/// The value is out of range.
/// Added in version 1.3.0.
/// </summary>
#define AZAC_ERR_OUT_OF_RANGE  __AZAC_ERRCODE_FAILED(0x023)

/// <summary>
/// Extension library not found.
/// Added in version 1.3.0.
/// </summary>
#define AZAC_ERR_EXTENSION_LIBRARY_NOT_FOUND    __AZAC_ERRCODE_FAILED(0x024)

/// <summary>
/// An unexpected error was encountered when trying to access the TTS engine site.
/// Added in version 1.4.0.
/// </summary>
#define AZAC_ERR_UNEXPECTED_TTS_ENGINE_SITE_FAILURE  __AZAC_ERRCODE_FAILED(0x025)

/// <summary>
/// An unexpected error was encountered when trying to access the audio output stream.
/// Added in version 1.4.0.
/// </summary>
#define AZAC_ERR_UNEXPECTED_AUDIO_OUTPUT_FAILURE  __AZAC_ERRCODE_FAILED(0x026)

/// <summary>
/// Gstreamer internal error.
/// Added in version 1.4.0.
/// </summary>
#define AZAC_ERR_GSTREAMER_INTERNAL_ERROR    __AZAC_ERRCODE_FAILED(0x027)

/// <summary>
/// Compressed container format not supported.
/// Added in version 1.4.0.
/// </summary>
#define AZAC_ERR_CONTAINER_FORMAT_NOT_SUPPORTED_ERROR    __AZAC_ERRCODE_FAILED(0x028)

/// <summary>
/// Codec extension or gstreamer not found.
/// Added in version 1.4.0.
/// </summary>
#define AZAC_ERR_GSTREAMER_NOT_FOUND_ERROR    __AZAC_ERRCODE_FAILED(0x029)

/// <summary>
/// The language specified is missing.
/// Added in version 1.5.0.
/// </summary>
#define AZAC_ERR_INVALID_LANGUAGE  __AZAC_ERRCODE_FAILED(0x02A)

/// <summary>
/// The API is not applicable.
/// Added in version 1.5.0.
/// </summary>
#define AZAC_ERR_UNSUPPORTED_API_ERROR  __AZAC_ERRCODE_FAILED(0x02B)

/// <summary>
/// The ring buffer is unavailable.
/// Added in version 1.8.0.
/// </summary>
#define AZAC_ERR_RINGBUFFER_DATA_UNAVAILABLE  __AZAC_ERRCODE_FAILED(0x02C)

/// <summary>
/// An unexpected error was encountered when trying to access the Conversation site.
/// Added in version 1.5.0.
/// </summary>
#define AZAC_ERR_UNEXPECTED_CONVERSATION_SITE_FAILURE  __AZAC_ERRCODE_FAILED(0x030)

/// <summary>
/// An unexpected error was encountered when trying to access the Conversation site.
/// Added in version 1.8.0.
/// </summary>
#define AZAC_ERR_UNEXPECTED_CONVERSATION_TRANSLATOR_SITE_FAILURE  __AZAC_ERRCODE_FAILED(0x031)

/// <summary>
/// An asynchronous operation was canceled before it was executed.
/// Added in version 1.8.0.
/// </summary>
#define AZAC_ERR_CANCELED  __AZAC_ERRCODE_FAILED(0x032)

/// <summary>
/// Codec for compression could not be initialized.
/// Added in version 1.10.0.
/// </summary>
#define AZAC_ERR_COMPRESS_AUDIO_CODEC_INITIFAILED    __AZAC_ERRCODE_FAILED(0x033)

/// <summary>
/// Data not available.
/// Added in version 1.10.0.
/// </summary>
#define AZAC_ERR_DATA_NOT_AVAILABLE    __AZAC_ERRCODE_FAILED(0x034)

/// <summary>
/// Invalid result reason.
/// Added in version 1.12.0
/// </summary>
#define AZAC_ERR_INVALID_RESULT_REASON   __AZAC_ERRCODE_FAILED(0x035)

/// <summary>
/// An unexpected error was encountered when trying to access the RNN-T site.
/// </summary>
#define AZAC_ERR_UNEXPECTED_RNNT_SITE_FAILURE  __AZAC_ERRCODE_FAILED(0x036)

/// <summary>
/// Sending of a network message failed.
/// </summary>
#define AZAC_ERR_NETWORK_SEND_FAILED  __AZAC_ERRCODE_FAILED(0x037)

/// <summary>
/// Audio extension library not found.
/// Added in version 1.16.0.
/// </summary>
#define AZAC_ERR_AUDIO_SYS_LIBRARY_NOT_FOUND  __AZAC_ERRCODE_FAILED(0x038)

/// <summary>
/// An error in the audio-rendering system.
/// Added in version 1.20.0
/// </summary>
#define AZAC_ERR_LOUDSPEAKER_ERROR        __AZAC_ERRCODE_FAILED(0x039)

/// <summary>
/// An unexpected error was encountered when trying to access the Vision site.
/// Added in version 1.15.0.
/// </summary>
#define AZAC_ERR_VISION_SITE_FAILURE __AZAC_ERRCODE_FAILED(0x050)

/// <summary>
/// Stream number provided was invalid in the current context.
/// Added in version 1.15.0.
/// </summary>
#define AZAC_ERR_MEDIA_INVALID_STREAM __AZAC_ERRCODE_FAILED(0x060)

/// <summary>
/// Offset required is invalid in the current context.
/// Added in version 1.15.0.
/// </summary>
#define AZAC_ERR_MEDIA_INVALID_OFFSET __AZAC_ERRCODE_FAILED(0x061)

/// <summary>
/// No more data is available in source.
/// Added in version 1.15.0.
/// </summary>
#define AZAC_ERR_MEDIA_NO_MORE_DATA __AZAC_ERRCODE_FAILED(0x062)

/// <summary>
/// Source has not been started.
/// Added in version 1.15.0.
/// </summary>
#define AZAC_ERR_MEDIA_NOT_STARTED __AZAC_ERRCODE_FAILED(0x063)

/// <summary>
/// Source has already been started.
/// Added in version 1.15.0.
/// </summary>
#define AZAC_ERR_MEDIA_ALREADY_STARTED __AZAC_ERRCODE_FAILED(0x064)

/// <summary>
/// Media device creation failed.
/// Added in version 1.18.0.
/// </summary>
#define AZAC_ERR_MEDIA_DEVICE_CREATION_FAILED __AZAC_ERRCODE_FAILED(0x065)

/// <summary>
/// No devices of the selected category are available.
/// Added in version 1.18.0.
/// </summary>
#define AZAC_ERR_MEDIA_NO_DEVICE_AVAILABLE __AZAC_ERRCODE_FAILED(0x066)

/// <summary>
/// Enabled Voice Activity Detection while using keyword recognition is not allowed.
/// </summary>
#define AZAC_ERR_VAD_COULD_NOT_USE_WITH_KEYWORD_RECOGNIZER __AZAC_ERRCODE_FAILED(0x067)

/// <summary>
/// The specified RecoEngineAdapter could not be created.
/// </summary>
#define AZAC_ERR_COULD_NOT_CREATE_ENGINE_ADAPTER __AZAC_ERRCODE_FAILED(0x070)

/// <summary>
/// The input file has a size of 0 bytes.
/// </summary>
#define AZAC_ERR_INPUT_FILE_SIZE_IS_ZERO_BYTES __AZAC_ERRCODE_FAILED(0x072)

/// <summary>
/// Cannot open the input media file for reading. Does it exist?
/// </summary>
#define AZAC_ERR_FAILED_TO_OPEN_INPUT_FILE_FOR_READING __AZAC_ERRCODE_FAILED(0x073)

/// <summary>
/// Failed to read from the input media file.
/// </summary>
#define AZAC_ERR_FAILED_TO_READ_FROM_INPUT_FILE __AZAC_ERRCODE_FAILED(0x074)

/// <summary>
/// Input media file is too large.
/// </summary>
#define AZAC_ERR_INPUT_FILE_TOO_LARGE __AZAC_ERRCODE_FAILED(0x075)

/// <summary>
/// The input URL is unsupported. It should start with `http://`, `https://` or `rtsp://`.
/// </summary>
#define AZAC_ERR_UNSUPPORTED_URL_PROTOCOL __AZAC_ERRCODE_FAILED(0x076)

/// <summary>
/// The Nullable value is empty. Check HasValue() before getting the value.
/// </summary>
#define AZAC_ERR_EMPTY_NULLABLE __AZAC_ERRCODE_FAILED(0x077)

/// <summary>
/// The given model version string is not in the expected format. The format
/// is specified by the regular expression `^(latest|\d{4}-\d{2}-\d{2})(-preview)?$`.
/// </summary>
#define AZAC_ERR_INVALID_MODEL_VERSION_FORMAT __AZAC_ERRCODE_FAILED(0x078)

/// <summary>
/// Malformed network message
/// </summary>
#define AZAC_ERR_NETWORK_MALFORMED __AZAC_ERRCODE_FAILED(0x090)

/// <summary>
/// Unexpected message received
/// </summary>
#define AZAC_ERR_NETWORK_PROTOCOL_VIOLATION __AZAC_ERRCODE_FAILED(0x091)
