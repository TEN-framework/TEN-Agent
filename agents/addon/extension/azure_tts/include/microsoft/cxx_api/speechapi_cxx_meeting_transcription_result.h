//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_meeting_transcriber_result.h: Public API declarations for MeetingTranscription C++ class
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
/// Represents the result of a meeting transcriber.
/// </summary>
class MeetingTranscriptionResult final : public RecognitionResult
{
public:

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hresult">Result handle.</param>
    explicit MeetingTranscriptionResult(SPXRESULTHANDLE hresult) :
        RecognitionResult(hresult),
        UserId(m_userId),
        UtteranceId(m_utteranceId)
    {
        PopulateSpeakerFields(hresult, &m_userId);
        PopulateUtteranceFields(hresult, &m_utteranceId);
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p) -- resultid=%s; reason=0x%x; text=%s, userid=%s, utteranceid=%s", __FUNCTION__, (void*)this, (void*)Handle, Utils::ToUTF8(ResultId).c_str(), Reason, Utils::ToUTF8(Text).c_str(), Utils::ToUTF8(UserId).c_str(), Utils::ToUTF8(UtteranceId).c_str());
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~MeetingTranscriptionResult()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)Handle);
    }

    /// <summary>
    /// Unique Speaker id.
    /// </summary>
    const SPXSTRING& UserId;

    /// <summary>
    /// Unique id that is consistent across all the intermediates and final speech recognition result from one user.
    /// </summary>
    const SPXSTRING& UtteranceId;

private:
    DISABLE_DEFAULT_CTORS(MeetingTranscriptionResult);

    void PopulateSpeakerFields(SPXRESULTHANDLE hresult, SPXSTRING* puserId)
    {
        SPX_INIT_HR(hr);

        const size_t maxCharCount = 1024;
        char sz[maxCharCount + 1] = {};

        if (puserId != nullptr && recognizer_result_handle_is_valid(hresult))
        {
            SPX_THROW_ON_FAIL(hr = meeting_transcription_result_get_user_id(hresult, sz, maxCharCount));
            *puserId = Utils::ToSPXString(sz);
        }
    }

    void PopulateUtteranceFields(SPXRESULTHANDLE hresult, SPXSTRING* putteranceId)
    {
        SPX_INIT_HR(hr);

        const size_t maxCharCount = 1024;
        char sz[maxCharCount + 1] = {};

        if (putteranceId != nullptr && recognizer_result_handle_is_valid(hresult))
        {
            SPX_THROW_ON_FAIL(hr = meeting_transcription_result_get_utterance_id(hresult, sz, maxCharCount));
            *putteranceId = Utils::ToSPXString(sz);
        }
    }

    SPXSTRING m_userId;
    SPXSTRING m_utteranceId;
};


} } } }  // Microsoft::CognitiveServices::Speech::Transcription
