//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_voice_profile_client.h: Public API declarations for VoiceProfileClient C++ class
//

#pragma once
#include <string>
#include <future>

#include <speechapi_c.h>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_voice_profile.h>
#include <speechapi_cxx_voice_profile_result.h>
#include <speechapi_cxx_voice_profile_enrollment_result.h>
#include <speechapi_cxx_voice_profile_phrase_result.h>
#include <speechapi_cxx_audio_config.h>
#include <speechapi_cxx_utils.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

/// <summary>
/// Class for VoiceProfileClient.
/// This class creates voice profile client for creating, doing enrollment, deleting and reseting a voice profile.
/// Added in version 1.12.0
/// </summary>
class VoiceProfileClient : public std::enable_shared_from_this<VoiceProfileClient>
{
private:

    /*! \cond PRIVATE */

    SPXVOICEPROFILECLIENTHANDLE m_hVoiceProfileClient;

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXVOICEPROFILECLIENTHANDLE hclient) :
            PropertyCollection(
                [=]() {
                    SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                    voice_profile_client_get_property_bag(hclient, &hpropbag);
                    return hpropbag;
                }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

    /*! \endcond */

public:

    /// <summary>
    /// Create a Voice Profile Client from a speech config
    /// </summary>
    /// <param name="speechConfig">Speech configuration.</param>
    /// <returns>A smart pointer wrapped voice profile client pointer.</returns>
    static std::shared_ptr<VoiceProfileClient> FromConfig(std::shared_ptr<SpeechConfig> speechConfig)
    {
        SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient;
        SPX_THROW_ON_FAIL(::create_voice_profile_client_from_config(&hVoiceProfileClient, Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechConfig)));
        return std::shared_ptr<VoiceProfileClient>{ new VoiceProfileClient(hVoiceProfileClient)};
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    virtual ~VoiceProfileClient()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        ::voice_profile_client_release_handle(m_hVoiceProfileClient);
        m_hVoiceProfileClient = SPXHANDLE_INVALID;
    }

    /// <summary>
    /// Create a Voice Profile.
    /// </summary>
    /// <param name="profileType">a VoiceProfile type.</param>
    /// <param name="locale">a locale, e.g "en-us"</param>
    /// <returns>A smart pointer wrapped voice profile client object.</returns>
    std::future<std::shared_ptr<VoiceProfile>> CreateProfileAsync(VoiceProfileType profileType, const SPXSTRING& locale)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [profileType, locale, this, keepAlive]() -> std::shared_ptr<VoiceProfile> {
            SPXVOICEPROFILEHANDLE hVoiceProfileHandle;
            SPX_THROW_ON_FAIL(::create_voice_profile(m_hVoiceProfileClient, static_cast<int>(profileType), Utils::ToUTF8(locale).c_str(), &hVoiceProfileHandle));
            return std::shared_ptr<VoiceProfile> { new VoiceProfile(hVoiceProfileHandle) };
            });

        return future;
    }

    /// <summary>
    /// Enroll a Voice Profile.
    /// </summary>
    /// <param name="profile">a voice profile object.</param>
    /// <param name="audioInput">an audio Input.</param>
    /// <returns>A smart pointer wrapped voice profile enrollment result object.</returns>
    std::future<std::shared_ptr<VoiceProfileEnrollmentResult>> EnrollProfileAsync(std::shared_ptr<VoiceProfile> profile, std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [profile, audioInput, this, keepAlive]() -> std::shared_ptr<VoiceProfileEnrollmentResult> {
             SPXRESULTHANDLE hresult;
            SPX_THROW_ON_FAIL(::enroll_voice_profile(m_hVoiceProfileClient,
                Utils::HandleOrInvalid<SPXVOICEPROFILEHANDLE, VoiceProfile>(profile),
                Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput),
                &hresult));
            return std::make_shared<VoiceProfileEnrollmentResult>(hresult);
            });
        return future;
    }

    /// <summary>
    /// Delete a Voice Profile.
    /// </summary>
    /// <param name="profile">a voice profile object.</param>
    /// <returns>A smart pointer wrapped voice profile result object.</returns>
    std::future<std::shared_ptr<VoiceProfileResult>> DeleteProfileAsync(std::shared_ptr<VoiceProfile> profile)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [profile, this, keepAlive]() -> std::shared_ptr<VoiceProfileResult> {
            SPXRESULTHANDLE hResultHandle;
            SPX_THROW_ON_FAIL(::delete_voice_profile(m_hVoiceProfileClient,
                Utils::HandleOrInvalid<SPXVOICEPROFILEHANDLE, VoiceProfile>(profile),
                &hResultHandle));
            return std::make_shared<VoiceProfileResult>(hResultHandle);
            });
        return future;
    }

    /// <summary>
    /// Reset a Voice Profile.
    /// </summary>
    /// <param name="profile">a voice profile object.</param>
    /// <returns>A smart pointer wrapped voice profile result object.</returns>
    std::future<std::shared_ptr<VoiceProfileResult>> ResetProfileAsync(std::shared_ptr<VoiceProfile> profile)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [profile, this, keepAlive]() -> std::shared_ptr<VoiceProfileResult> {
            SPXRESULTHANDLE hResultHandle;
            SPX_THROW_ON_FAIL(::reset_voice_profile(m_hVoiceProfileClient,
                Utils::HandleOrInvalid<SPXVOICEPROFILEHANDLE, VoiceProfile>(profile),
                &hResultHandle));
            return std::make_shared<VoiceProfileResult>(hResultHandle);
           });
           return future;
    }

    /// <summary>
    ///  Retrieve an enrollment result given the id and type of the Voice Profile.
    /// </summary>
    /// <param name="voiceProfileId">The VoiceProfile Id.</param>
    /// <param name="voiceProfileType">The VoiceProfileType.</param>
    /// <returns>A future of the retrieved VoiceProfileEnrollmentResult.</returns>
    std::future<std::shared_ptr<VoiceProfileEnrollmentResult>> RetrieveEnrollmentResultAsync(const SPXSTRING& voiceProfileId, VoiceProfileType voiceProfileType)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [voiceProfileId, voiceProfileType, this, keepAlive]() -> std::shared_ptr<VoiceProfileEnrollmentResult> {
            SPXRESULTHANDLE hResultHandle;
            SPX_THROW_ON_FAIL(::retrieve_enrollment_result(m_hVoiceProfileClient, Utils::ToUTF8(voiceProfileId).c_str(), static_cast<int>(voiceProfileType), &hResultHandle));
            return std::make_shared<VoiceProfileEnrollmentResult>(hResultHandle);
            });
        return future;
    }

    /// <summary>
    ///  Retrieve an enrollment result given the Voice Profile.
    /// </summary>
    /// <param name="voiceProfile">a voice profile object.</param>
    /// <returns></returns>
    std::future<std::shared_ptr<VoiceProfileEnrollmentResult>> RetrieveEnrollmentResultAsync(const VoiceProfile& voiceProfile)
    {
        return RetrieveEnrollmentResultAsync(voiceProfile.GetId(), voiceProfile.GetType());
    }

    /// <summary>
    ///  Get all profiles having the given type.
    /// </summary>
    /// <param name="voiceProfileType">The VoiceProfileType.</param>
    /// <returns>A future of a vector of extant VoiceProfiles.</returns>
    std::future<std::vector<std::shared_ptr<VoiceProfile>>> GetAllProfilesAsync(VoiceProfileType voiceProfileType)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [voiceProfileType, this, keepAlive]() -> std::vector<std::shared_ptr<VoiceProfile>>
        {
            std::vector<std::shared_ptr<VoiceProfile>> list;

            size_t numChars = 0;
            char* json = nullptr;
            auto deleteJsonOnEixt = Utils::MakeScopeGuard([&json]() {
                ::property_bag_free_string(json);
            });

            SPX_THROW_ON_FAIL(::get_profiles_json(m_hVoiceProfileClient, static_cast<int>(voiceProfileType), &json, &numChars));

            auto profileList = Utils::Split(json, numChars, '|');
            for (auto& profile: profileList)
            {
                list.push_back(VoiceProfile::FromId(Utils::ToSPXString(profile), voiceProfileType));
            }

            return list;
        });
        return future;
    }

    std::future<std::shared_ptr<VoiceProfilePhraseResult>> GetActivationPhrasesAsync(VoiceProfileType voiceProfileType, const SPXSTRING& locale)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [voiceProfileType, locale, this, keepAlive]() -> std::shared_ptr<VoiceProfilePhraseResult> {
            SPXRESULTHANDLE hresult;
            SPX_THROW_ON_FAIL(::get_activation_phrases(m_hVoiceProfileClient,
                Utils::ToUTF8(locale).c_str(),
                static_cast<int>(voiceProfileType),
                &hresult));
            return std::make_shared<VoiceProfilePhraseResult>(hresult);
            });
        return future;
    }
    /// <summary>
    /// A collection of properties and their values defined for this <see cref="VoiceProfileClient"/>.
    /// </summary>
    PropertyCollection& Properties;

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXVOICEPROFILECLIENTHANDLE() { return m_hVoiceProfileClient; }

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hreco">Recognizer handle.</param>
    explicit VoiceProfileClient(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient) :
        m_hVoiceProfileClient(hVoiceProfileClient),
        m_properties(hVoiceProfileClient),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /*! \endcond */

private:

   DISABLE_DEFAULT_CTORS(VoiceProfileClient);
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
