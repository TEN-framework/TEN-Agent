//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_voice_profile.h: Public API declarations for VoiceProfile C++ class
//

#pragma once
#include <string>

#include <speechapi_c.h>
#include <speechapi_c_speaker_recognition.h>
#include <speechapi_cxx_common.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

// Forward declaration for friends.
class VoiceProfileClient;

/// <summary>
/// Class for VoiceProfile.
/// Added in version 1.12.0
/// </summary>
class VoiceProfile : public std::enable_shared_from_this<VoiceProfile>
{
public:

    static std::shared_ptr<VoiceProfile> FromId(const SPXSTRING& Id, VoiceProfileType voiceProfileType = VoiceProfileType::TextIndependentIdentification)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        SPXVOICEPROFILEHANDLE hVoiceProfile;
        SPX_THROW_ON_FAIL(::create_voice_profile_from_id_and_type(&hVoiceProfile,Utils::ToUTF8(Id).c_str(), static_cast<int>(voiceProfileType)));
        return std::shared_ptr<VoiceProfile> { new VoiceProfile(hVoiceProfile) };
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    virtual ~VoiceProfile()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        ::voice_profile_release_handle(m_hVoiceProfile);
        m_hVoiceProfile = SPXHANDLE_INVALID;
    }

    /// <summary>
    /// Get a voice profile id.
    /// </summary>
    /// <returns> the voice profile id.</returns>
    const SPXSTRING GetId() const
    {
        // query the string length
        uint32_t length = 0;
        SPX_THROW_ON_FAIL(voice_profile_get_id(m_hVoiceProfile, nullptr, &length));

        // retrieve the string
        std::unique_ptr<char[]> buffer(new char[length]);
        SPX_THROW_ON_FAIL(voice_profile_get_id(m_hVoiceProfile, buffer.get(), &length));
        return Utils::ToSPXString(buffer.get());
    }

    /// <summary>
    /// Get the VoiceProfileType from the VoiceProfile.
    /// </summary>
    /// <returns></returns>
    VoiceProfileType GetType() const
    {
        int type = -1;
        SPX_THROW_ON_FAIL(voice_profile_get_type(m_hVoiceProfile, &type));
        return static_cast<VoiceProfileType>(type);
    }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXVOICEPROFILEHANDLE() { return m_hVoiceProfile; }

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hVoiceProfile">Voice Profile handle.</param>
    explicit VoiceProfile(SPXVOICEPROFILEHANDLE hVoiceProfile) :
        m_hVoiceProfile(hVoiceProfile)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /*! \endcond */

private:

    /*! \cond PRIVATE */
    friend Microsoft::CognitiveServices::Speech::Speaker::VoiceProfileClient;
    DISABLE_DEFAULT_CTORS(VoiceProfile);

    SPXVOICEPROFILEHANDLE m_hVoiceProfile;

    /*! \endcond */
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
