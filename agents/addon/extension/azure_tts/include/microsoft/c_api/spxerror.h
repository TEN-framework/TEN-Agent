//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once

#include <azac_error.h> // must include after spxdebug.h or speechapi*.h (can NOT be included before)

#define SPXHR AZACHR
#define SPX_NOERROR AZAC_ERR_NONE
#define SPX_INIT_HR(hr) AZAC_INIT_HR(hr)
#define SPX_SUCCEEDED(x) AZAC_SUCCEEDED(x)
#define SPX_FAILED(x) AZAC_FAILED(x)
#define __SPX_ERRCODE_FAILED(x) __AZAC_ERRCODE_FAILED(x)

/// <summary>
/// The function is not implemented.
/// </summary>
#define SPXERR_NOT_IMPL \
        AZAC_ERR_NOT_IMPL

/// <summary>
/// The object has not been properly initialized.
/// </summary>
#define SPXERR_UNINITIALIZED \
        AZAC_ERR_UNINITIALIZED

/// <summary>
/// The object has already been initialized.
/// </summary>
#define SPXERR_ALREADY_INITIALIZED \
        AZAC_ERR_ALREADY_INITIALIZED

/// <summary>
/// An unhandled exception was detected.
/// </summary>
#define SPXERR_UNHANDLED_EXCEPTION \
        AZAC_ERR_UNHANDLED_EXCEPTION

/// <summary>
/// The object or property was not found.
/// </summary>
#define SPXERR_NOT_FOUND \
        AZAC_ERR_NOT_FOUND

/// <summary>
/// One or more arguments are not valid.
/// </summary>
#define SPXERR_INVALID_ARG \
        AZAC_ERR_INVALID_ARG

/// <summary>
/// The specified timeout value has elapsed.
/// </summary>
#define SPXERR_TIMEOUT \
        AZAC_ERR_TIMEOUT

/// <summary>
/// The asynchronous operation is already in progress.
/// </summary>
#define SPXERR_ALREADY_IN_PROGRESS \
        AZAC_ERR_ALREADY_IN_PROGRESS

/// <summary>
/// The attempt to open the file failed.
/// </summary>
#define SPXERR_FILE_OPEN_FAILED \
        AZAC_ERR_FILE_OPEN_FAILED

/// <summary>
/// The end of the file was reached unexpectedly.
/// </summary>
#define SPXERR_UNEXPECTED_EOF \
        AZAC_ERR_UNEXPECTED_EOF

/// <summary>
/// Invalid audio header encountered.
/// </summary>
#define SPXERR_INVALID_HEADER \
        AZAC_ERR_INVALID_HEADER

/// <summary>
/// The requested operation cannot be performed while audio is pumping
/// </summary>
#define SPXERR_AUDIO_IS_PUMPING \
        AZAC_ERR_AUDIO_IS_PUMPING

/// <summary>
/// Unsupported audio format.
/// </summary>
#define SPXERR_UNSUPPORTED_FORMAT \
        AZAC_ERR_UNSUPPORTED_FORMAT

/// <summary>
/// Operation aborted.
/// </summary>
#define SPXERR_ABORT \
        AZAC_ERR_ABORT

/// <summary>
/// Microphone is not available.
/// </summary>
#define SPXERR_MIC_NOT_AVAILABLE \
        AZAC_ERR_MIC_NOT_AVAILABLE

/// <summary>
/// An invalid state was encountered.
/// </summary>
#define SPXERR_INVALID_STATE \
        AZAC_ERR_INVALID_STATE

/// <summary>
/// Attempting to create a UUID failed.
/// </summary>
#define SPXERR_UUID_CREATE_FAILED \
        AZAC_ERR_UUID_CREATE_FAILED

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
#define SPXERR_SETFORMAT_UNEXPECTED_STATE_TRANSITION \
        AZAC_ERR_SETFORMAT_UNEXPECTED_STATE_TRANSITION

/// <summary>
/// An unexpected session state was encountered in while processing audio.
/// </summary>
/// <remarks>
/// Valid states to encounter are:
/// * ProcessingAudio: We're allowed to process audio while in this state.
/// * StoppingPump: We're allowed to be called to process audio, but we'll ignore the data passed in while we're attempting to stop the pump.
/// All other states are invalid while processing audio.
/// </remarks>
#define SPXERR_PROCESS_AUDIO_INVALID_STATE \
        AZAC_ERR_PROCESS_AUDIO_INVALID_STATE

/// <summary>
/// An unexpected state transition was encountered while attempting to start recognizing.
/// </summary>
/// <remarks>
/// A valid transition is:
/// * Idle --> WaitForPumpSetFormatStart
/// All other state transitions are invalid when attempting to start recognizing
/// </remarks>
#define SPXERR_START_RECOGNIZING_INVALID_STATE_TRANSITION \
        AZAC_ERR_START_RECOGNIZING_INVALID_STATE_TRANSITION

/// <summary>
/// An unexpected error was encountered when trying to create an internal object.
/// </summary>
#define SPXERR_UNEXPECTED_CREATE_OBJECT_FAILURE \
        AZAC_ERR_UNEXPECTED_CREATE_OBJECT_FAILURE

/// <summary>
/// An error in the audio-capturing system.
/// </summary>
#define SPXERR_MIC_ERROR \
        AZAC_ERR_MIC_ERROR

/// <summary>
/// The requested operation cannot be performed; there is no audio input.
/// </summary>
#define SPXERR_NO_AUDIO_INPUT \
        AZAC_ERR_NO_AUDIO_INPUT

/// <summary>
/// An unexpected error was encountered when trying to access the USP site.
/// </summary>
#define SPXERR_UNEXPECTED_USP_SITE_FAILURE \
        AZAC_ERR_UNEXPECTED_USP_SITE_FAILURE

/// <summary>
/// An unexpected error was encountered when trying to access the LuAdapterSite site.
/// </summary>
#define SPXERR_UNEXPECTED_LU_SITE_FAILURE \
        AZAC_ERR_UNEXPECTED_LU_SITE_FAILURE

/// <summary>
/// The buffer is too small.
/// </summary>
#define SPXERR_BUFFER_TOO_SMALL \
        AZAC_ERR_BUFFER_TOO_SMALL

/// <summary>
/// A method failed to allocate memory.
/// </summary>
#define SPXERR_OUT_OF_MEMORY \
        AZAC_ERR_OUT_OF_MEMORY

/// <summary>
/// An unexpected runtime error occurred.
/// </summary>
#define SPXERR_RUNTIME_ERROR \
        AZAC_ERR_RUNTIME_ERROR

/// <summary>
/// The url specified is invalid.
/// </summary>
#define SPXERR_INVALID_URL \
        AZAC_ERR_INVALID_URL

/// <summary>
/// The region specified is invalid or missing.
/// </summary>
#define SPXERR_INVALID_REGION \
        AZAC_ERR_INVALID_REGION

/// <summary>
/// Switch between single shot and continuous recognition is not supported.
/// </summary>
#define SPXERR_SWITCH_MODE_NOT_ALLOWED \
        AZAC_ERR_SWITCH_MODE_NOT_ALLOWED

/// <summary>
/// Changing connection status is not supported in the current recognition state.
/// </summary>
#define SPXERR_CHANGE_CONNECTION_STATUS_NOT_ALLOWED \
        AZAC_ERR_CHANGE_CONNECTION_STATUS_NOT_ALLOWED

/// <summary>
/// Explicit connection management is not supported by the specified recognizer.
/// </summary>
#define SPXERR_EXPLICIT_CONNECTION_NOT_SUPPORTED_BY_RECOGNIZER \
        AZAC_ERR_EXPLICIT_CONNECTION_NOT_SUPPORTED_BY_RECOGNIZER

/// <summary>
/// The handle is invalid.
/// </summary>
#define SPXERR_INVALID_HANDLE \
        AZAC_ERR_INVALID_HANDLE

/// <summary>
/// The recognizer is invalid.
/// </summary>
#define SPXERR_INVALID_RECOGNIZER \
        AZAC_ERR_INVALID_RECOGNIZER

/// <summary>
/// The value is out of range.
/// Added in version 1.3.0.
/// </summary>
#define SPXERR_OUT_OF_RANGE \
        AZAC_ERR_OUT_OF_RANGE

/// <summary>
/// Extension library not found.
/// Added in version 1.3.0.
/// </summary>
#define SPXERR_EXTENSION_LIBRARY_NOT_FOUND \
        AZAC_ERR_EXTENSION_LIBRARY_NOT_FOUND

/// <summary>
/// An unexpected error was encountered when trying to access the TTS engine site.
/// Added in version 1.4.0.
/// </summary>
#define SPXERR_UNEXPECTED_TTS_ENGINE_SITE_FAILURE \
        AZAC_ERR_UNEXPECTED_TTS_ENGINE_SITE_FAILURE

/// <summary>
/// An unexpected error was encountered when trying to access the audio output stream.
/// Added in version 1.4.0.
/// </summary>
#define SPXERR_UNEXPECTED_AUDIO_OUTPUT_FAILURE \
        AZAC_ERR_UNEXPECTED_AUDIO_OUTPUT_FAILURE

/// <summary>
/// Gstreamer internal error.
/// Added in version 1.4.0.
/// </summary>
#define SPXERR_GSTREAMER_INTERNAL_ERROR \
        AZAC_ERR_GSTREAMER_INTERNAL_ERROR

/// <summary>
/// Compressed container format not supported.
/// Added in version 1.4.0.
/// </summary>
#define SPXERR_CONTAINER_FORMAT_NOT_SUPPORTED_ERROR \
        AZAC_ERR_CONTAINER_FORMAT_NOT_SUPPORTED_ERROR

/// <summary>
/// Codec extension or gstreamer not found.
/// Added in version 1.4.0.
/// </summary>
#define SPXERR_GSTREAMER_NOT_FOUND_ERROR \
        AZAC_ERR_GSTREAMER_NOT_FOUND_ERROR

/// <summary>
/// The language specified is missing.
/// Added in version 1.5.0.
/// </summary>
#define SPXERR_INVALID_LANGUAGE \
        AZAC_ERR_INVALID_LANGUAGE

/// <summary>
/// The API is not applicable.
/// Added in version 1.5.0.
/// </summary>
#define SPXERR_UNSUPPORTED_API_ERROR \
        AZAC_ERR_UNSUPPORTED_API_ERROR

/// <summary>
/// The ring buffer is unavailable.
/// Added in version 1.8.0.
/// </summary>
#define SPXERR_RINGBUFFER_DATA_UNAVAILABLE \
        AZAC_ERR_RINGBUFFER_DATA_UNAVAILABLE

/// <summary>
/// An unexpected error was encountered when trying to access the Conversation site.
/// Added in version 1.5.0.
/// </summary>
#define SPXERR_UNEXPECTED_CONVERSATION_SITE_FAILURE \
        AZAC_ERR_UNEXPECTED_CONVERSATION_SITE_FAILURE

/// <summary>
/// An unexpected error was encountered when trying to access the Conversation site.
/// Added in version 1.8.0.
/// </summary>
#define SPXERR_UNEXPECTED_CONVERSATION_TRANSLATOR_SITE_FAILURE \
        AZAC_ERR_UNEXPECTED_CONVERSATION_TRANSLATOR_SITE_FAILURE

/// <summary>
/// An asynchronous operation was canceled before it was executed.
/// Added in version 1.8.0.
/// </summary>
#define SPXERR_CANCELED \
        AZAC_ERR_CANCELED

/// <summary>
/// Codec for compression could not be initialized.
/// Added in version 1.10.0.
/// </summary>
#define SPXERR_COMPRESS_AUDIO_CODEC_INITIFAILED \
        AZAC_ERR_COMPRESS_AUDIO_CODEC_INITIFAILED

/// <summary>
/// Data not available.
/// Added in version 1.10.0.
/// </summary>
#define SPXERR_DATA_NOT_AVAILABLE \
        AZAC_ERR_DATA_NOT_AVAILABLE

/// <summary>
/// Invalid result reason.
/// Added in version 1.12.0
/// </summary>
#define SPXERR_INVALID_RESULT_REASON \
        AZAC_ERR_INVALID_RESULT_REASON

/// <summary>
/// An unexpected error was encountered when trying to access the RNN-T site.
/// </summary>
#define SPXERR_UNEXPECTED_RNNT_SITE_FAILURE \
        AZAC_ERR_UNEXPECTED_RNNT_SITE_FAILURE

/// <summary>
/// Sending of a network message failed.
/// </summary>
#define SPXERR_NETWORK_SEND_FAILED \
        AZAC_ERR_NETWORK_SEND_FAILED

/// <summary>
/// Audio extension library not found.
/// Added in version 1.16.0.
/// </summary>
#define SPXERR_AUDIO_SYS_LIBRARY_NOT_FOUND \
        AZAC_ERR_AUDIO_SYS_LIBRARY_NOT_FOUND

/// <summary>
/// An error in the audio-rendering system.
/// Added in version 1.20.0
/// </summary>
#define SPXERR_LOUDSPEAKER_ERROR \
        AZAC_ERR_LOUDSPEAKER_ERROR

/// <summary>
/// An unexpected error was encountered when trying to access the Vision site.
/// Added in version 1.15.0.
/// </summary>
#define SPXERR_VISION_SITE_FAILURE \
        AZAC_ERR_VISION_SITE_FAILURE

/// <summary>
/// Stream number provided was invalid in the current context.
/// Added in version 1.15.0.
/// </summary>
#define SPXERR_MEDIA_INVALID_STREAM \
        AZAC_ERR_MEDIA_INVALID_STREAM

/// <summary>
/// Offset required is invalid in the current context.
/// Added in version 1.15.0.
/// </summary>
#define SPXERR_MEDIA_INVALID_OFFSET \
        AZAC_ERR_MEDIA_INVALID_OFFSET

/// <summary>
/// No more data is available in source.
/// Added in version 1.15.0.
/// </summary>
#define SPXERR_MEDIA_NO_MORE_DATA \
        AZAC_ERR_MEDIA_NO_MORE_DATA

/// <summary>
/// Source has not been started.
/// Added in version 1.15.0.
/// </summary>
#define SPXERR_MEDIA_NOT_STARTED \
        AZAC_ERR_MEDIA_NOT_STARTED

/// <summary>
/// Source has already been started.
/// Added in version 1.15.0.
/// </summary>
#define SPXERR_MEDIA_ALREADY_STARTED \
        AZAC_ERR_MEDIA_ALREADY_STARTED

/// <summary>
/// Media device creation failed.
/// Added in version 1.18.0.
/// </summary>
#define SPXERR_MEDIA_DEVICE_CREATION_FAILED \
        AZAC_ERR_MEDIA_DEVICE_CREATION_FAILED

/// <summary>
/// No devices of the selected category are available.
/// Added in version 1.18.0.
/// </summary>
#define SPXERR_MEDIA_NO_DEVICE_AVAILABLE \
    AZAC_ERR_MEDIA_NO_DEVICE_AVAILABLE

/// <summary>
/// Enabled Voice Activity Detection while using keyword recognition is not allowed.
/// </summary>
#define SPXERR_VAD_COULD_NOT_USE_WITH_KEYWORD_RECOGNIZER \
    AZAC_ERR_VAD_COULD_NOT_USE_WITH_KEYWORD_RECOGNIZER

/// <summary>
/// The specified RecoEngineAdapter could not be created.
/// </summary>
#define SPXERR_COULD_NOT_CREATE_ENGINE_ADAPTER \
        AZAC_ERR_COULD_NOT_CREATE_ENGINE_ADAPTER
