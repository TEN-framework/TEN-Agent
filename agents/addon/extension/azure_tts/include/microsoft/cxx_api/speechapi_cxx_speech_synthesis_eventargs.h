//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_synthesis_eventargs.h: Public API declarations for SpeechSynthesisEventArgs C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_eventargs.h>
#include <speechapi_cxx_speech_synthesis_result.h>
#include <speechapi_c_synthesizer.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Class for speech synthesis event arguments.
/// Added in version 1.4.0
/// </summary>
class SpeechSynthesisEventArgs : public EventArgs
{
private:
    SPXEVENTHANDLE m_hevent;
    std::shared_ptr<SpeechSynthesisResult> m_result;

public:

    /// <summary>
    /// Constructor.
    /// </summary>
    /// <param name="hevent">Event handle</param>
    explicit SpeechSynthesisEventArgs(SPXEVENTHANDLE hevent) :
        m_hevent(hevent),
        m_result(std::make_shared<SpeechSynthesisResult>(ResultHandleFromEventHandle(hevent))),
        Result(m_result)
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)m_hevent);
    };

    /// <inheritdoc/>
    virtual ~SpeechSynthesisEventArgs()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)m_hevent);
        SPX_THROW_ON_FAIL(synthesizer_event_handle_release(m_hevent));
    }

    /// <summary>
    /// Speech synthesis event result.
    /// </summary>
    std::shared_ptr<SpeechSynthesisResult> Result;


private:

    DISABLE_DEFAULT_CTORS(SpeechSynthesisEventArgs);

    SPXRESULTHANDLE ResultHandleFromEventHandle(SPXEVENTHANDLE hevent)
    {
        SPXRESULTHANDLE hresult = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(synthesizer_synthesis_event_get_result(hevent, &hresult));
        return hresult;
    }

};

} } } // Microsoft::CognitiveServices::Speech
