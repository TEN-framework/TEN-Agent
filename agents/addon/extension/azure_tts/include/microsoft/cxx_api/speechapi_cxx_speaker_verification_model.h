//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speaker_verification_model.h: Public API declarations for SpeakerVerificationModel C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>

#include <speechapi_c.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_voice_profile.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

/// <summary>
/// Represents speaker verification model used with speaker recognition class.
/// Added in version 1.12.0
/// </summary>
class SpeakerVerificationModel : public std::enable_shared_from_this<SpeakerVerificationModel>
{
public:

    /// <summary>
    /// Creates a speaker verification model using the voice profile.
    /// </summary>
    /// <param name="profile">The voice profile.</param>
    /// <returns>A shared pointer to speaker verification model.</returns>
    static std::shared_ptr<SpeakerVerificationModel> FromProfile(std::shared_ptr<VoiceProfile> profile)
    {
        SPXSVMODELHANDLE hsvmodel = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speaker_verification_model_create(&hsvmodel, (SPXVOICEPROFILEHANDLE)(*profile)));
        return std::shared_ptr<SpeakerVerificationModel>{ new SpeakerVerificationModel(hsvmodel) };
    }

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~SpeakerVerificationModel() { speaker_verification_model_release_handle(m_svmodel); }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXSVMODELHANDLE() { return m_svmodel; }

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance of speaker verification model using the provided handle.
    /// </summary>
    /// <param name="hsvmodel">speaker verification model handle.</param>
    explicit SpeakerVerificationModel(SPXSIMODELHANDLE hsvmodel = SPXHANDLE_INVALID) : m_svmodel(hsvmodel) { }

    /*! \endcond */

private:

    DISABLE_COPY_AND_MOVE(SpeakerVerificationModel);

    SPXSVMODELHANDLE m_svmodel;
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
