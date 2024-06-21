//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_synthesis_voices_result.h: Public API declarations for SynthesisVoicesResult C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_enums.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_voice_info.h>
#include <speechapi_c_result.h>
#include <speechapi_c_synthesizer.h>
#include <memory>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Contains information about result from voices list of speech synthesizers.
/// Added in version 1.16.0
/// </summary>
class SynthesisVoicesResult
{
private:

    /// <summary>
    /// Internal member variable that holds the voices list result handle.
    /// </summary>
    SPXRESULTHANDLE m_hresult;

    /*! \cond PRIVATE */

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXRESULTHANDLE hresult) :
            PropertyCollection(
                [=]() {
            SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
            synthesis_voices_result_get_property_bag(hresult, &hpropbag);
            return hpropbag;
        }())
        {
        }
    };

    /// <summary>
    /// Internal member variable that holds the properties associating to the voices list result.
    /// </summary>
    PrivatePropertyCollection m_properties;

    /*! \endcond */

public:

    /// <summary>
    /// Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hresult">Result handle.</param>
    explicit SynthesisVoicesResult(SPXRESULTHANDLE hresult) :
        m_hresult(hresult),
        m_properties(hresult),
        Voices(m_voices),
        ErrorDetails(m_errorDetails),
        ResultId(m_resultId),
        Reason(m_reason),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        uint32_t voiceNum;
        SPX_THROW_ON_FAIL(::synthesis_voices_result_get_voice_num(hresult, &voiceNum));
        m_voices = std::vector<std::shared_ptr<VoiceInfo>>(voiceNum);

        for (uint32_t i = 0; i < voiceNum; ++i)
        {
            SPXRESULTHANDLE hVoice = SPXHANDLE_INVALID;
            SPX_THROW_ON_FAIL(::synthesis_voices_result_get_voice_info(m_hresult, i, &hVoice));
            m_voices[i] = std::make_shared<VoiceInfo>(hVoice);
        }

        const size_t maxCharCount = 1024;
        char sz[maxCharCount + 1];
        SPX_THROW_ON_FAIL(synthesis_voices_result_get_result_id(hresult, sz, maxCharCount));
        m_resultId = Utils::ToSPXString(sz);

        Result_Reason resultReason = ResultReason_NoMatch;
        SPX_THROW_ON_FAIL(synthesis_voices_result_get_reason(hresult, &resultReason));
        m_reason = static_cast<ResultReason>(resultReason);

        m_errorDetails = m_properties.GetProperty(PropertyId::CancellationDetails_ReasonDetailedText);
    }

    /// <summary>
    /// Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXRESULTHANDLE() { return m_hresult; }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~SynthesisVoicesResult()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        synthesizer_result_handle_release(m_hresult);
    }

    /// <summary>
    /// Retrieved voices.
    /// </summary>
    const std::vector<std::shared_ptr<Microsoft::CognitiveServices::Speech::VoiceInfo>>& Voices;

    /// <summary>
    /// Error details.
    /// </summary>
    const SPXSTRING& ErrorDetails;

    /// <summary>
    /// Unique result id.
    /// </summary>
    const SPXSTRING& ResultId;

    /// <summary>
    /// Reason of the voices list result.
    /// </summary>
    const ResultReason& Reason;

    /// <summary>
    /// Collection of additional SynthesisVoicesResult properties.
    /// </summary>
    const PropertyCollection& Properties;

private:

    DISABLE_DEFAULT_CTORS(SynthesisVoicesResult);

    /// <summary>
    /// Internal member variable that holds the result ID.
    /// </summary>
    SPXSTRING m_resultId;

    /// <summary>
    /// Internal member variable that holds the result reason.
    /// </summary>
    ResultReason m_reason;

    /// <summary>
    /// Internal member variable that holds the voices list.
    /// </summary>
    std::vector<std::shared_ptr<VoiceInfo>> m_voices;

    /// <summary>
    /// Internal member variable that holds the error details.
    /// </summary>
    SPXSTRING m_errorDetails;
};


} } } // Microsoft::CognitiveServices::Speech
