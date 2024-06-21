//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_participant.h: Public API declarations for Participant C++ class
//

#pragma once
#include <speechapi_c.h>
#include <speechapi_c_conversation_translator.h>
#include <speechapi_cxx_properties.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Transcription {

/// <summary>
/// Represents a participant in a conversation.
/// Added in version 1.5.0.
/// </summary>
class Participant
{
private:
    SPXPARTICIPANTHANDLE m_hparticipant;
    SPXSTRING m_avatar;
    SPXSTRING m_id;
    SPXSTRING m_displayName;
    bool m_isTts;
    bool m_isMuted;
    bool m_isHost;

public:
    /// <summary>
    /// Create a participant using user id, her/his preferred language and her/his voice signature.
    /// If voice signature is empty then user will not be identified.
    /// </summary>
    /// <param name="userId">A user ids.</param>
    /// <param name="preferredLanguage">The preferred languages of the user. It can be optional.</param>
    /// <param name="voiceSignature">The voice signature of the user. It can be optional.</param>
    /// <returns>A smart pointer of Participant </returns>
    static std::shared_ptr<Participant> From(const SPXSTRING& userId, const SPXSTRING& preferredLanguage = {}, const SPXSTRING& voiceSignature = {})
    {
        SPXPARTICIPANTHANDLE hparticipant = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(participant_create_handle(&hparticipant, Utils::ToUTF8(userId.c_str()), Utils::ToUTF8(preferredLanguage.c_str()), Utils::ToUTF8(voiceSignature.c_str())));
        return std::make_shared<Participant>(hparticipant);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hparticipant">participant handle.</param>
    explicit Participant(SPXPARTICIPANTHANDLE hparticipant = SPXHANDLE_INVALID) :
        m_hparticipant(hparticipant),
        m_avatar(),
        m_id(),
        m_displayName(),
        m_isTts(false),
        m_isMuted(false),
        m_isHost(false),
        Id(m_id),
        Avatar(m_avatar),
        DisplayName(m_displayName),
        IsUsingTts(m_isTts),
        IsMuted(m_isMuted),
        IsHost(m_isHost),
        m_properties(hparticipant),
        Properties(m_properties)
    {
        LoadConversationParticipantProperties(hparticipant);
    }

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~Participant() { participant_release_handle(m_hparticipant); }

    /// <summary>
    /// Get the identifier for the participant.
    /// </summary>
    const SPXSTRING& Id;

    /// <summary>
    /// Gets the colour of the user's avatar as an HTML hex string (e.g. FF0000 for red).
    /// </summary>
    const SPXSTRING& Avatar;

    /// <summary>
    /// The participant's display name. Please note that each participant within the same conversation must
    /// have a different display name. Duplicate names within the same conversation are not allowed. You can
    /// use the Id property as another way to refer to each participant.
    /// </summary>
    const SPXSTRING& DisplayName;

    /// <summary>
    /// Gets whether or not the participant is using Text To Speech (TTS).
    /// </summary>
    const bool& IsUsingTts;

    /// <summary>
    /// Gets whether or not this participant is muted.
    /// </summary>
    const bool& IsMuted;

    /// <summary>
    /// Gets whether or not this participant is the host.
    /// </summary>
    const bool& IsHost;

    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXPARTICIPANTHANDLE() const { return m_hparticipant; }

    /// <summary>
    /// Set preferred language.
    /// </summary>
    /// <param name="preferredLanguage">The preferred language, such as "en-us".</param>
    void SetPreferredLanguage(const std::string& preferredLanguage)
    {
        SPX_THROW_ON_FAIL(participant_set_preferred_langugage(m_hparticipant, Utils::ToUTF8(preferredLanguage.c_str())));
    }

    /// <summary>
    /// Set voice signature.
    /// If voice signature is empty then user will not be identified.
    /// </summary>
    /// <param name="voiceSignature">The participant's voice signature."</param>
    void SetVoiceSignature(const std::string& voiceSignature)
    {
        SPX_THROW_ON_FAIL(participant_set_voice_signature(m_hparticipant, Utils::ToUTF8(voiceSignature.c_str())));
    }

private:

    /*! \cond PRIVATE */

    DISABLE_COPY_AND_MOVE(Participant);

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXPARTICIPANTHANDLE hparticipant) :
            PropertyCollection(
                [=]() {
            SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
            participant_get_property_bag(hparticipant, &hpropbag);
            return hpropbag;
        }())
        {
        }
    };

    PrivatePropertyCollection m_properties;
    
    SPXSTRING TryLoadString(SPXEVENTHANDLE hevent, SPXHR(SPXAPI_CALLTYPE * func)(SPXEVENTHANDLE, char*, uint32_t *))
    {
        std::unique_ptr<char[]> psz;
        try
        {
            // query the string length
            uint32_t length = 0;

            // don't use SPX_THROW_ON_FAIL since that creates a handle for exceptions that will leak
            // since we don't care about them.
            SPXHR hr = func(hevent, nullptr, &length);
            if (SPX_FAILED(hr) || length == 0)
            {
                return SPXSTRING{};
            }

            psz = std::unique_ptr<char[]>(new char[length]);
            hr = func(hevent, psz.get(), &length);
            if (SPX_FAILED(hr))
            {
                return SPXSTRING{};
            }

            return Utils::ToSPXString(psz.get());
        }
        catch (...)
        {
            // ignore errors since not all participants have the properties we need
            return SPXSTRING{};
        }
    }

    void LoadConversationParticipantProperties(SPXPARTICIPANTHANDLE hParticipant)
    {
        m_id = TryLoadString(hParticipant, conversation_translator_participant_get_id);
        m_avatar = TryLoadString(hParticipant, conversation_translator_participant_get_avatar);
        m_displayName = TryLoadString(hParticipant, conversation_translator_participant_get_displayname);

        bool val;
        if (SPX_SUCCEEDED(conversation_translator_participant_get_is_using_tts(hParticipant, &val)))
        {
            m_isTts = val;
        }

        if (SPX_SUCCEEDED(conversation_translator_participant_get_is_muted(hParticipant, &val)))
        {
            m_isMuted = val;
        }

        if (SPX_SUCCEEDED(conversation_translator_participant_get_is_host(hParticipant, &val)))
        {
            m_isHost = val;
        }
    }

    /*! \endcond */

public:

    /// <summary>
    /// Collection of additional participant properties.
    /// </summary>
    PropertyCollection& Properties;
};

}}}}
