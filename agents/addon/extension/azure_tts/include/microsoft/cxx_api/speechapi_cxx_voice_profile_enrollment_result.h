//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_voice_profile_enrollment_result.h: Public API declarations for VoiceProfileEnrollmentResult C++ class
//

#pragma once
#include <string>
#include <functional>
#include <speechapi_cxx_enums.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_recognition_result.h>
#include <speechapi_c_result.h>
#include <speechapi_c_common.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

/// <summary>
/// A enum that represents the timing information of an enrollment.
/// Added in version 1.12.0.
/// </summary>
enum class EnrollmentInfoType
{
    /// <summary>
    ///  Number of enrollment audios accepted for this profile.
    /// </summary>
    EnrollmentsCount = 0,

    /// <summary>
    ///  Total length of enrollment audios accepted for this profile.
    /// </summary>
    EnrollmentsLength = 1,

    /// <summary>
    ///  Summation of pure speech(which is the amount of audio after removing silence and non - speech segments) across all profile enrollments.
    /// </summary>
    EnrollmentsSpeechLength = 2,

    /// <summary>
    ///  Amount of pure speech (which is the amount of audio after removing silence and non-speech segments) needed to complete profile enrollment.
    /// </summary>
    RemainingEnrollmentsSpeechLength = 3,

    /// <summary>
    /// Number of enrollment audios needed to complete profile enrollment.
    /// </summary>
    RemainingEnrollmentsCount = 4,

    /// <summary>
    ///  This enrollment audio length in hundred nanoseconds.
    /// </summary>
    AudioLength = 5,

    /// <summary>
    ///  This enrollment audio pure speech(which is the amount of audio after removing silence and non - speech segments) length in hundred nanoseconds.
    /// </summary>
    AudioSpeechLength = 6
};

/// <summary>
/// Represents the result of an enrollment.
/// Added in version 1.12.0.
/// </summary>
class VoiceProfileEnrollmentResult final : public RecognitionResult
{
private:

    SPXSTRING m_profileId;
    const int enrollmentsCount;
    const uint64_t enrollmentsLength;
    const uint64_t enrollmentsSpeechLength;
    const int remainingEnrollmentsCount;
    const uint64_t remainingEnrollmentsSpeechLength;
    const uint64_t audioLength;
    const uint64_t audioSpeechLength;
    const SPXSTRING createdDateTime;
    const SPXSTRING lastUpdatedDateTime;

public:

    /// <summary>
    /// Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hresult">Result handle.</param>
    explicit VoiceProfileEnrollmentResult(SPXRESULTHANDLE hresult) :
        RecognitionResult(hresult),
        m_profileId(Properties.GetProperty("enrollment.profileId", "")),
        enrollmentsCount(std::stoi(Properties.GetProperty("enrollment.enrollmentsCount", "0"))),
        enrollmentsLength(static_cast<uint64_t>(std::stoll(Properties.GetProperty("enrollment.enrollmentsLengthInSec", "0")))),
        enrollmentsSpeechLength(static_cast<uint64_t>(std::stoll(Properties.GetProperty("enrollment.enrollmentsSpeechLengthInSec", "0")))),
        remainingEnrollmentsCount(std::stoi(Properties.GetProperty("enrollment.remainingEnrollmentsCount", "0"))),
        remainingEnrollmentsSpeechLength(std::stoll(Properties.GetProperty("enrollment.remainingEnrollmentsSpeechLengthInSec", "0"))),
        audioLength(static_cast<uint64_t>(std::stoll(Properties.GetProperty("enrollment.audioLengthInSec", "0")))),
        audioSpeechLength(static_cast<uint64_t>(std::stoll(Properties.GetProperty("enrollment.audioSpeechLengthInSec", "0")))),
        createdDateTime(Properties.GetProperty("enrollment.createdDateTime", "")),
        lastUpdatedDateTime(Properties.GetProperty("enrollment.lastUpdatedDateTime", "")),
        ProfileId(m_profileId)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    virtual ~VoiceProfileEnrollmentResult()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// The profile id of the speaker in the enrollment.
    /// </summary>
    const SPXSTRING& ProfileId;

    /// <summary>
    ///  Retrieve a textual representation of the created time of the voice profile.
    /// </summary>
    /// <returns></returns>
    const SPXSTRING& GetCreatedTime() const
    {
        return createdDateTime;
    }

    /// <summary>
    ///  Retrieve a textual representation of the last updated time of the voice profile.
    /// </summary>
    /// <returns></returns>
    const SPXSTRING& GetLastUpdatedDateTime() const
    {
        return lastUpdatedDateTime;
    }

    /// <summary>
    /// Enrollment information in ticks.
    /// A single tick represents one hundred nanoseconds or one ten-millionth of a second.
    /// </summary>
    /// <param name="type">an enum of EnrollmentInfoType.</param>
    /// <returns>Duration of recognized speech in ticks.</returns>
    uint64_t GetEnrollmentInfo(EnrollmentInfoType type) const
    {
        switch (type)
        {
        case EnrollmentInfoType::EnrollmentsCount:
            return static_cast<uint64_t>(enrollmentsCount);

        case EnrollmentInfoType::EnrollmentsLength:
            return enrollmentsLength;

        case EnrollmentInfoType::EnrollmentsSpeechLength:
            return enrollmentsSpeechLength;

        case EnrollmentInfoType::RemainingEnrollmentsCount:
            return static_cast<uint64_t>(remainingEnrollmentsCount);

        case EnrollmentInfoType::RemainingEnrollmentsSpeechLength:
            return remainingEnrollmentsSpeechLength;

        case EnrollmentInfoType::AudioLength:
            return audioLength;

        case EnrollmentInfoType::AudioSpeechLength:
            return audioSpeechLength;

        default:
            throw std::runtime_error("Invalid enrollmentInfoType!");
        }
    }

private:

    DISABLE_DEFAULT_CTORS(VoiceProfileEnrollmentResult);

};

/// <summary>
/// Represents the cancellation details of a result of an enrollment.
/// Added in version 1.12.0.
/// </summary>
class VoiceProfileEnrollmentCancellationDetails
{
private:

    CancellationErrorCode m_errorCode;

public:

    /// <summary>
    /// Create an object that represents the details of a canceled enrollment result.
    /// </summary>
    /// <param name="result">a voice profile enrollment result object.</param>
    /// <returns>a smart pointer of voice profile enrollment cancellation details object.</returns>
    static std::shared_ptr<VoiceProfileEnrollmentCancellationDetails> FromResult(std::shared_ptr<VoiceProfileEnrollmentResult> result)
    {
        return std::shared_ptr<VoiceProfileEnrollmentCancellationDetails> { new VoiceProfileEnrollmentCancellationDetails(result.get()) };
    }

    /// <summary>
    /// The error code in case of an unsuccessful enrollment (<see cref="Reason"/> is set to Error).
    /// </summary>
    const CancellationErrorCode& ErrorCode;

    /// <summary>
    /// The error message in case of an unsuccessful enrollment (<see cref="Reason"/> is set to Error).
    /// </summary>
    const SPXSTRING ErrorDetails;

protected:

    /*! \cond PROTECTED */

    VoiceProfileEnrollmentCancellationDetails(VoiceProfileEnrollmentResult* result) :
        m_errorCode(GetCancellationErrorCode(result)),
        ErrorCode(m_errorCode),
        ErrorDetails(result->Properties.GetProperty(PropertyId::SpeechServiceResponse_JsonErrorDetails))
    {
    }

    /*! \endcond */

private:
    DISABLE_DEFAULT_CTORS(VoiceProfileEnrollmentCancellationDetails);

    /*! \cond PRIVATE */

    CancellationErrorCode GetCancellationErrorCode(VoiceProfileEnrollmentResult* result)
    {
        Result_CancellationErrorCode errorCode = CancellationErrorCode_NoError;

        SPXRESULTHANDLE hresult = (SPXRESULTHANDLE)(*result);
        SPX_IFFAILED_THROW_HR(result_get_canceled_error_code(hresult, &errorCode));

        return static_cast<CancellationErrorCode>(errorCode);
    }

    /*! \endcond */
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
