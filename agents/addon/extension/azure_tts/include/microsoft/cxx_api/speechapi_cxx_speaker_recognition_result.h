//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speaker_recognition_result.h: Public API declarations for SpeakerRecognitionResult C++ class
//

#pragma once
#include <string>
#include <vector>
#include <speechapi_cxx_common.h>

#include <speechapi_c.h>
#include <speechapi_c_result.h>
#include <speechapi_cxx_properties.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

/// <summary>
/// Represents speaker recognition result.
/// Added in 1.12.0
/// </summary>
class SpeakerRecognitionResult
{

private:

    /// Internal member variable that holds the speakerRecognition result handle.
    /// </summary>
    SPXRESULTHANDLE m_hresult;

    /*! \cond PRIVATE */

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXRESULTHANDLE hresult) :
            PropertyCollection(
                [hresult]() {
                    SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                    result_get_property_bag(hresult, &hpropbag);
                    return hpropbag;
                }())
        {
        }
    };

    /// <summary>
    /// Internal member variable that holds the properties associating to the speaker recognition result.
    /// </summary>
    PrivatePropertyCollection m_properties;

    /*! \endcond */

public:

    /// <summary>
    /// Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hresult">Result handle.</param>
    explicit SpeakerRecognitionResult(SPXRESULTHANDLE hresult) :
        m_hresult(hresult),
        m_properties(hresult),
        ResultId(m_resultId),
        Reason(m_reason),
        ProfileId(m_profileId),
        Properties(m_properties),
        m_profileId(Properties.GetProperty("speakerrecognition.profileid","")),
        m_score(std::stof(Properties.GetProperty("speakerrecognition.score", "0.0")))
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        PopulateResultFields(hresult, &m_resultId, &m_reason);
    }

    /// <summary>
    /// Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXRESULTHANDLE() { return m_hresult; }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~SpeakerRecognitionResult()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        recognizer_result_handle_release(m_hresult);
    }

    /// <summary>
    /// Unique result id.
    /// </summary>
    const SPXSTRING& ResultId;

    /// <summary>
    /// Reason of the speaker recognition result.
    /// </summary>
    const ResultReason& Reason;

    /// <summary>
    /// The profile id of the first verified/identified speaker. The rest of recognized speakers can be retrieved by parsing the json result string in the Properties.
    /// </summary>
    const SPXSTRING& ProfileId;

    /// <summary>
    /// Collection of additional properties.
    /// </summary>
    const PropertyCollection& Properties;

    /// <summary>
    /// Returns a similarity score.
    /// </summary>
    /// <returns> A float number indicating the similarity between input audio and targeted voice profile.This number is between 0 and 1. A higher number means higher similarity.< / returns>
    double GetScore() const
    {
        return m_score;
    }

private:

    /*! \cond PRIVATE */

    DISABLE_DEFAULT_CTORS(SpeakerRecognitionResult);

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

    SPXSTRING m_resultId;
    ResultReason m_reason;
    SPXSTRING m_profileId;
    float m_score;

    /*! \endcond */
};

/// <summary>
/// Represents the details of a canceled speaker recognition result.
/// </summary>
class SpeakerRecognitionCancellationDetails
{
private:

    CancellationReason m_reason;
    CancellationErrorCode m_errorCode;

public:

    /// <summary>
    /// Creates an instance of SpeakerRecognitionCancellationDetails object for the canceled speaker recognition result.
    /// </summary>
    /// <param name="result">The result that was canceled.</param>
    /// <returns>A shared pointer to SpeakerRecognitionCancellationDetails.</returns>
    static std::shared_ptr<SpeakerRecognitionCancellationDetails> FromResult(std::shared_ptr<SpeakerRecognitionResult> result)
    {
        return std::shared_ptr<SpeakerRecognitionCancellationDetails> { new SpeakerRecognitionCancellationDetails(result.get()) };
    }

    /// <summary>
    /// The reason the result was canceled.
    /// </summary>
    const CancellationReason& Reason;

    /// <summary>
    /// The error code in case of an unsuccessful speaker recognition (<see cref="Reason"/> is set to Error).
    /// If Reason is not Error, ErrorCode is set to NoError.
    /// </summary>
    const CancellationErrorCode& ErrorCode;

    /// <summary>
    /// The error message in case of an unsuccessful speaker recognition (<see cref="Reason"/> is set to Error).
    /// </summary>
    const SPXSTRING ErrorDetails;

protected:

    /*! \cond PROTECTED */

    SpeakerRecognitionCancellationDetails(SpeakerRecognitionResult* result) :
        m_reason(GetCancellationReason(result)),
        m_errorCode(GetCancellationErrorCode(result)),
        Reason(m_reason),
        ErrorCode(m_errorCode),
        ErrorDetails(result->Properties.GetProperty(PropertyId::SpeechServiceResponse_JsonErrorDetails))
    {
    }

    /*! \endcond */

private:

    DISABLE_DEFAULT_CTORS(SpeakerRecognitionCancellationDetails);


    CancellationReason GetCancellationReason(SpeakerRecognitionResult* result)
    {
        Result_CancellationReason reason = CancellationReason_Error;

        SPXRESULTHANDLE hresult = (SPXRESULTHANDLE)(*result);
        SPX_IFFAILED_THROW_HR(result_get_reason_canceled(hresult, &reason));

        return static_cast<Speech::CancellationReason>(reason);
    }

    CancellationErrorCode GetCancellationErrorCode(SpeakerRecognitionResult* result)
    {
        Result_CancellationErrorCode errorCode = CancellationErrorCode_NoError;

        SPXRESULTHANDLE hresult = (SPXRESULTHANDLE)(*result);
        SPX_IFFAILED_THROW_HR(result_get_canceled_error_code(hresult, &errorCode));

        return static_cast<CancellationErrorCode>(errorCode);
    }
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
