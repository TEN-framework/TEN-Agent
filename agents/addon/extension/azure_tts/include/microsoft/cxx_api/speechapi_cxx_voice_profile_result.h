//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_voice_profile_result.h: Public API declarations for VoiceProfileResult C++ class
//

#pragma once
#include <string>
#include <functional>
#include <speechapi_cxx_enums.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_c_result.h>
#include <speechapi_c_common.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

/// <summary>
/// Class for VoiceProfileResult.
/// This class represents the result of processing voice profiles.
/// Added in version 1.12.0
/// </summary>
class VoiceProfileResult
{
private:

    /*! \cond PRIVATE */

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXRESULTHANDLE hresult) :
            PropertyCollection(
                [=]() {
                    SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                    result_get_property_bag(hresult, &hpropbag);
                    return hpropbag;
                }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

    /*! \endcond */

public:
    explicit VoiceProfileResult(SPXRESULTHANDLE hresult) :
        m_properties(hresult),
        ResultId(m_resultId),
        Reason(m_reason),
        Properties(m_properties),
        m_hresult(hresult)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        PopulateResultFields(hresult, &m_resultId, &m_reason);
    }

    virtual ~VoiceProfileResult()
    {
        ::recognizer_result_handle_release(m_hresult);
        m_hresult = SPXHANDLE_INVALID;
    }

    /// <summary>
    /// Unique result id.
    /// </summary>
    const SPXSTRING& ResultId;

    /// <summary>
    /// Voice profile result reason.
    /// </summary>
    const ResultReason& Reason;

    /// <summary>
    /// A collection of properties and their values defined for this <see cref="VoiceProfileResult"/>.
    /// </summary>
    PropertyCollection& Properties;

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXRESULTHANDLE() { return m_hresult; }

private:
    DISABLE_DEFAULT_CTORS(VoiceProfileResult);

    void PopulateResultFields(SPXRESULTHANDLE hresult, SPXSTRING* resultId, Speech::ResultReason* reason)
    {
        SPX_INIT_HR(hr);

        const size_t maxCharCount = 2048;
        char sz[maxCharCount + 1] = {};

        if (resultId != nullptr)
        {
            SPX_THROW_ON_FAIL(hr = result_get_result_id(hresult, sz, maxCharCount));
            *resultId = Utils::ToSPXString(sz);
        }

        if (reason != nullptr)
        {
            Result_Reason resultReason;
            SPX_THROW_ON_FAIL(hr = result_get_reason(hresult, &resultReason));
            *reason = (Speech::ResultReason)resultReason;
        }
    }

    ResultReason m_reason;
    SPXSTRING m_resultId;
    SPXRESULTHANDLE m_hresult;
};

/// <summary>
/// Class for VoiceProfileCancellationDetails.
/// This class represents error details of a voice profile result.
/// </summary>
class VoiceProfileCancellationDetails
{
private:
    CancellationErrorCode m_errorCode;

public:

    /// <summary>
    /// Creates an instance of VoiceProfileCancellationDetails object for the canceled VoiceProfile.
    /// </summary>
    /// <param name="result">The result that was canceled.</param>
    /// <returns>A shared pointer to VoiceProfileCancellationDetails.</returns>
    static std::shared_ptr<VoiceProfileCancellationDetails> FromResult(std::shared_ptr<VoiceProfileResult> result)
    {
        return std::shared_ptr<VoiceProfileCancellationDetails> { new VoiceProfileCancellationDetails(result.get()) };
    }

    /// <summary>
    /// The error code in case of an unsuccessful voice profile action(<see cref="Reason"/> is set to Error).
    /// If Reason is not Error, ErrorCode is set to NoError.
    /// </summary>
    const CancellationErrorCode& ErrorCode;

    /// <summary>
    /// The error message in case of an unsuccessful voice profile action(<see cref="Reason"/> is set to Error).
    /// </summary>
    const SPXSTRING ErrorDetails;

protected:

    /*! \cond PROTECTED */

    VoiceProfileCancellationDetails(VoiceProfileResult* result) :
        m_errorCode(GetCancellationErrorCode(result)),
        ErrorCode(m_errorCode),
        ErrorDetails(result->Properties.GetProperty(PropertyId::SpeechServiceResponse_JsonErrorDetails))
    {
    }

    /*! \endcond */

private:
    DISABLE_DEFAULT_CTORS(VoiceProfileCancellationDetails);


    CancellationErrorCode GetCancellationErrorCode(VoiceProfileResult* result)
    {
        UNUSED(result);
        Result_CancellationErrorCode errorCode = CancellationErrorCode_NoError;

        SPXRESULTHANDLE hresult = (SPXRESULTHANDLE)(*result);
        SPX_IFFAILED_THROW_HR(result_get_canceled_error_code(hresult, &errorCode));

        return (CancellationErrorCode)errorCode;
    }
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
