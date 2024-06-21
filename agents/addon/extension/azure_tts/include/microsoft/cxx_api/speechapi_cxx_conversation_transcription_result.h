//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_conversation_transcription_result.h: Public API declarations for ConversationTranscription C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_recognition_result.h>
#include <speechapi_c.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Transcription {

/// <summary>
/// Represents the result of a conversation transcriber.
/// </summary>
class ConversationTranscriptionResult final : public RecognitionResult
{
public:

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hresult">Result handle.</param>
    explicit ConversationTranscriptionResult(SPXRESULTHANDLE hresult) :
        RecognitionResult(hresult),
        SpeakerId(m_speakerId)
    {
        PopulateSpeakerFields(hresult, &m_speakerId);
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p) -- resultid=%s; reason=0x%x; text=%s, speakerid=%s, utteranceid=%s", __FUNCTION__, (void*)this, (void*)Handle, Utils::ToUTF8(ResultId).c_str(), Reason, Utils::ToUTF8(Text).c_str(), Utils::ToUTF8(SpeakerId).c_str());
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~ConversationTranscriptionResult()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)Handle);
    }

    /// <summary>
    /// Unique Speaker id.
    /// </summary>
    const SPXSTRING& SpeakerId;

private:
    DISABLE_DEFAULT_CTORS(ConversationTranscriptionResult);

    void PopulateSpeakerFields(SPXRESULTHANDLE hresult, SPXSTRING* pspeakerId)
    {
        SPX_INIT_HR(hr);

        const size_t maxCharCount = 1024;
        char sz[maxCharCount + 1] = {};

        if (pspeakerId != nullptr && recognizer_result_handle_is_valid(hresult))
        {
            SPX_THROW_ON_FAIL(hr = conversation_transcription_result_get_speaker_id(hresult, sz, maxCharCount));
            *pspeakerId = Utils::ToSPXString(sz);
        }
    }

    SPXSTRING m_speakerId;
};

} } } }  // Microsoft::CognitiveServices::Speech::Transcription
