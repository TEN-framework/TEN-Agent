//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speaker_identification_model.h: Public API declarations for SpeakerIdentificationModel C++ class
//

#pragma once
#include <string>
#include <vector>
#include <speechapi_cxx_common.h>

#include <speechapi_c.h>
#include <speechapi_cxx_voice_profile.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

/// <summary>
/// Represents speaker identification model used with speaker recognition class.
/// Added in version 1.12.0
/// </summary>
class SpeakerIdentificationModel : public std::enable_shared_from_this<SpeakerIdentificationModel>
{
public:

    /// <summary>
    /// Creates a speaker identification model using the voice profiles.
    /// </summary>
    /// <param name="profiles">a vector of voice profiles.</param>
    /// <returns>A shared pointer to speaker identification model.</returns>
    static std::shared_ptr<SpeakerIdentificationModel> FromProfiles(const std::vector<std::shared_ptr<VoiceProfile>>& profiles)
    {
        SPXSIMODELHANDLE hsimodel = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speaker_identification_model_create(&hsimodel));
        for (auto& profile : profiles)
        {
            SPX_THROW_ON_FAIL(speaker_identification_model_add_profile(hsimodel, (SPXVOICEPROFILEHANDLE)(*profile)));
        }

        return std::shared_ptr<SpeakerIdentificationModel>{ new SpeakerIdentificationModel(hsimodel) };
    }

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~SpeakerIdentificationModel() { speaker_identification_model_release_handle(m_simodel); }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXSIMODELHANDLE() { return m_simodel; }

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a speaker identification model using the provided handle.
    /// </summary>
    /// <param name="hsimodel">speaker identification handle.</param>
    explicit SpeakerIdentificationModel(SPXSIMODELHANDLE hsimodel = SPXHANDLE_INVALID) : m_simodel(hsimodel) { }


    /*! \endcond */

private:

    DISABLE_COPY_AND_MOVE(SpeakerIdentificationModel);

    SPXSIMODELHANDLE m_simodel;
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
