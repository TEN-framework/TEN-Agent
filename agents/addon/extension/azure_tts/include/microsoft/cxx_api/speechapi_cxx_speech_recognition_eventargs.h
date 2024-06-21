//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_recognition_eventargs.h: Public API declarations for SpeechRecognitionEventArgs C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_recognition_eventargs.h>
#include <speechapi_cxx_speech_recognition_result.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Class for speech recognition event arguments.
/// </summary>
class SpeechRecognitionEventArgs : public RecognitionEventArgs
{
private:

    SPXEVENTHANDLE m_hevent;
    std::shared_ptr<SpeechRecognitionResult> m_result;

public:

    /// <summary>
    /// Constructor.
    /// </summary>
    /// <param name="hevent">Event handle</param>
    explicit SpeechRecognitionEventArgs(SPXEVENTHANDLE hevent) :
        RecognitionEventArgs(hevent),
        m_hevent(hevent),
        m_result(std::make_shared<SpeechRecognitionResult>(ResultHandleFromEventHandle(hevent))),
        Result(m_result)
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)m_hevent);
    };

    /// <inheritdoc/>
    virtual ~SpeechRecognitionEventArgs()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)m_hevent);
        SPX_THROW_ON_FAIL(recognizer_event_handle_release(m_hevent));
    };

#if defined(BINDING_OBJECTIVE_C)
private:
#endif
    /// <summary>
    /// Speech recognition event result.
    /// </summary>
    std::shared_ptr<SpeechRecognitionResult> Result;

#if defined(BINDING_OBJECTIVE_C)
public:
#else
protected:
#endif

    /*! \cond PROTECTED */

    /// <summary>
    /// Speech recognition event result.
    /// </summary>
    std::shared_ptr<SpeechRecognitionResult> GetResult() const { return m_result; }

    /*! \endcond */

private:

    DISABLE_DEFAULT_CTORS(SpeechRecognitionEventArgs);

    SPXRESULTHANDLE ResultHandleFromEventHandle(SPXEVENTHANDLE hevent)
    {
        SPXRESULTHANDLE hresult = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(recognizer_recognition_event_get_result(hevent, &hresult));
        return hresult;
    }
};


/// <summary>
/// Class for speech recognition canceled event arguments.
/// </summary>
class SpeechRecognitionCanceledEventArgs final : public SpeechRecognitionEventArgs
{
private:

    std::shared_ptr<CancellationDetails> m_cancellation;
    CancellationReason m_cancellationReason;
    CancellationErrorCode m_errorCode;

public:

    /// <summary>
    /// Constructor.
    /// </summary>
    /// <param name="hevent">Event handle</param>
    explicit SpeechRecognitionCanceledEventArgs(SPXEVENTHANDLE hevent) :
        SpeechRecognitionEventArgs(hevent),
        m_cancellation(CancellationDetails::FromResult(GetResult())),
        m_cancellationReason(m_cancellation->Reason),
        m_errorCode(m_cancellation->ErrorCode),
        Reason(m_cancellationReason),
        ErrorCode(m_errorCode),
        ErrorDetails(m_cancellation->ErrorDetails)
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p)", __FUNCTION__, (void*)this);
    };

    /// <inheritdoc/>
    virtual ~SpeechRecognitionCanceledEventArgs()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p)", __FUNCTION__, (void*)this);
    };

#if defined(BINDING_OBJECTIVE_C)
private:
#endif

#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-private-field"
#endif
    /// <summary>
    /// The reason the result was canceled.
    /// </summary>
    const CancellationReason& Reason;

    /// <summary>
    /// The error code in case of an unsuccessful recognition (<see cref="Reason"/> is set to Error).
    /// If Reason is not Error, ErrorCode is set to NoError.
    /// Added in version 1.1.0.
    /// </summary>
    const CancellationErrorCode& ErrorCode;

#ifdef __clang__
#pragma clang diagnostic pop
#endif

    /// <summary>
    /// The error message in case of an unsuccessful recognition (<see cref="Reason"/> is set to Error).
    /// </summary>
    const SPXSTRING ErrorDetails;

#if defined(BINDING_OBJECTIVE_C)
public:
#else
private:
#endif
    /// <summary>
    /// CancellationDetails.
    /// </summary>
    std::shared_ptr<CancellationDetails> GetCancellationDetails() const { return m_cancellation; }

private:

    DISABLE_DEFAULT_CTORS(SpeechRecognitionCanceledEventArgs);
};


} } } // Microsoft::CognitiveServices::Speech
