
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_conversation.h: Public API declarations for Conversation C++ class
//

#pragma once
#include <exception>
#include <future>
#include <memory>
#include <string>
#include <cstring>

#include <speechapi_c.h>

#include <speechapi_cxx_speech_config.h>
#include <speechapi_cxx_utils.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_user.h>
#include <speechapi_cxx_participant.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Transcription {

/// <summary>
/// Class for conversation.
/// Added in version 1.8.0
/// </summary>
class Conversation : public std::enable_shared_from_this<Conversation>
{
public:

    static constexpr size_t MAX_CONVERSATION_ID_LEN = 1024;

    /// <summary>
    /// Create a conversation using a speech config and an optional conversation id.
    /// </summary>
    /// <param name="speechConfig">A shared smart pointer of a speech config object.</param>
    /// <param name="conversationId">Conversation Id.</param>
    /// <returns>A shared smart pointer of the created conversation object.</returns>
    static std::future<std::shared_ptr<Conversation>> CreateConversationAsync(std::shared_ptr<SpeechConfig> speechConfig, const SPXSTRING& conversationId = SPXSTRING())
    {
        auto future = std::async(std::launch::async, [conversationId, speechConfig]() -> std::shared_ptr<Conversation> {
            SPXCONVERSATIONHANDLE hconversation;
            SPX_THROW_ON_FAIL(conversation_create_from_config(&hconversation, (SPXSPEECHCONFIGHANDLE)(*speechConfig), Utils::ToUTF8(conversationId).c_str()));
            return std::make_shared<Conversation>(hconversation);
        });
        return future;
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hconversation">Recognizer handle.</param>
    explicit Conversation(SPXCONVERSATIONHANDLE hconversation) :
        m_hconversation(hconversation),
        m_properties(hconversation),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~Conversation()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        ::conversation_release_handle(m_hconversation);
        m_hconversation = SPXHANDLE_INVALID;
    }

    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXCONVERSATIONHANDLE () const { return m_hconversation; }

    /// <summary>
    /// Get the conversation id.
    /// </summary>
    /// <returns>Conversation id.</returns>
    SPXSTRING GetConversationId()
    {
        char id[MAX_CONVERSATION_ID_LEN + 1];
        std::memset(id, 0, MAX_CONVERSATION_ID_LEN);
        SPX_THROW_ON_FAIL(conversation_get_conversation_id(m_hconversation, id, MAX_CONVERSATION_ID_LEN));
        return id;
    }

    /// <summary>
    /// Add a participant to a conversation using the user's id.
    ///
    /// Note: The returned participant can be used to remove. If the client changes the participant's attributes,
    /// the changed attributes are passed on to the service only when the participant is added again.
    /// </summary>
    /// <param name="userId">A user id.</param>
    /// <returns>a shared smart pointer of the participant.</returns>
    std::future<std::shared_ptr<Participant>> AddParticipantAsync(const SPXSTRING& userId)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, userId]() -> std::shared_ptr<Participant> {
            const auto participant = Participant::From(userId);
            SPX_THROW_ON_FAIL(conversation_update_participant(m_hconversation, true, (SPXPARTICIPANTHANDLE)(*participant)));
            return participant;
        });
        return future;
    }

    /// <summary>
    /// Add a participant to a conversation using the User object.
    /// </summary>
    /// <param name="user">A shared smart pointer to a User object.</param>
    /// <returns>The passed in User object.</returns>
    std::future<std::shared_ptr<User>> AddParticipantAsync(const std::shared_ptr<User>& user)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, user]() -> std::shared_ptr<User> {
            SPX_THROW_ON_FAIL(conversation_update_participant_by_user(m_hconversation, true, (SPXUSERHANDLE)(*user)));
            return user;
        });
        return future;
    }

    /// <summary>
    /// Add a participant to a conversation using the participant object
    /// </summary>
    /// <param name="participant">A shared smart pointer to a participant object.</param>
    /// <returns>The passed in participant object.</returns>
    std::future<std::shared_ptr<Participant>> AddParticipantAsync(const std::shared_ptr<Participant>& participant)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, participant]() -> std::shared_ptr<Participant> {
            SPX_THROW_ON_FAIL(conversation_update_participant(m_hconversation, true, (SPXPARTICIPANTHANDLE)(*participant)));
            return participant;
        });
        return future;
    }

    /// <summary>
    /// Remove a participant from a conversation using the participant object
    /// </summary>
    /// <param name="participant">A shared smart pointer of a participant object.</param>
    /// <returns>An empty future.</returns>
    std::future<void> RemoveParticipantAsync(const std::shared_ptr<Participant>& participant)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, participant]() -> void {
            SPX_THROW_ON_FAIL(conversation_update_participant(m_hconversation, false, (SPXPARTICIPANTHANDLE)(*participant)));
        });
        return future;
    }

    /// <summary>
    /// Remove a participant from a conversation using the User object
    /// </summary>
    /// <param name="user">A smart pointer of a User.</param>
    /// <returns>An empty future.</returns>
    std::future<void> RemoveParticipantAsync(const std::shared_ptr<User>& user)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, user]() -> void {
            SPX_THROW_ON_FAIL(conversation_update_participant_by_user(m_hconversation, false, SPXUSERHANDLE(*user)));
        });
        return future;
    }

    /// <summary>
    /// Remove a participant from a conversation using a user id string.
    /// </summary>
    /// <param name="userId">A user id.</param>
    /// <returns>An empty future.</returns>
    std::future<void> RemoveParticipantAsync(const SPXSTRING& userId)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, userId]() -> void {
            SPX_THROW_ON_FAIL(conversation_update_participant_by_user_id(m_hconversation, false, Utils::ToUTF8(userId.c_str())));
        });
        return future;
    }

    /// <summary>
    /// Ends the current conversation.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> EndConversationAsync()
    {
        return RunAsync(::conversation_end_conversation);
    }

    /// <summary>
    /// Sets the authorization token that will be used for connecting the server.
    /// </summary>
    /// <param name="token">The authorization token.</param>
    void SetAuthorizationToken(const SPXSTRING& token)
    {
        Properties.SetProperty(PropertyId::SpeechServiceAuthorization_Token, token);
    }

    /// <summary>
    /// Gets the authorization token.
    /// </summary>
    /// <returns>Authorization token</returns>
    SPXSTRING GetAuthorizationToken()
    {
        return Properties.GetProperty(PropertyId::SpeechServiceAuthorization_Token, SPXSTRING());
    }

    /// <summary>
    /// Start the conversation.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> StartConversationAsync()
    {
        return RunAsync(::conversation_start_conversation);
    }

    /// <summary>
    /// Deletes the conversation. Any participants that are still part of the converation
    /// will be ejected after this call.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> DeleteConversationAsync()
    {
        return RunAsync(::conversation_delete_conversation);
    }

    /// <summary>
    /// Locks the conversation. After this no new participants will be able to join.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> LockConversationAsync()
    {
        return RunAsync(::conversation_lock_conversation);
    }

    /// <summary>
    /// Unlocks the conversation.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> UnlockConversationAsync()
    {
        return RunAsync(::conversation_unlock_conversation);
    }

    /// <summary>
    /// Mutes all participants except for the host. This prevents others from generating
    /// transcriptions, or sending text messages.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> MuteAllParticipantsAsync()
    {
        return RunAsync(::conversation_mute_all_participants);
    }

    /// <summary>
    /// Allows other participants to generate transcriptions, or send text messages.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> UnmuteAllParticipantsAsync()
    {
        return RunAsync(::conversation_unmute_all_participants);
    }

    /// <summary>
    /// Mutes a particular participant. This will prevent them generating new transcriptions,
    /// or sending text messages.
    /// </summary>
    /// <param name="participantId">The identifier for the participant.</param>
    /// <returns>An empty future.</returns>
    std::future<void> MuteParticipantAsync(const SPXSTRING& participantId)
    {
        return RunAsync([participantId = Utils::ToUTF8(participantId)](auto handle)
        {
            return ::conversation_mute_participant(handle, participantId.c_str());
        });
    }

    /// <summary>
    /// Unmutes a particular participant.
    /// </summary>
    /// <param name="participantId">The identifier for the participant.</param>
    /// <returns>An empty future.</returns>
    std::future<void> UnmuteParticipantAsync(const SPXSTRING& participantId)
    {
        return RunAsync([participantId = Utils::ToUTF8(participantId)](auto handle)
        {
            return ::conversation_unmute_participant(handle, participantId.c_str());
        });
    }

private:

    /*! \cond PRIVATE */

    SPXCONVERSATIONHANDLE m_hconversation;

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXCONVERSATIONHANDLE hconv) :
            PropertyCollection(
                [=]() {
            SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
            conversation_get_property_bag(hconv, &hpropbag);
            return hpropbag;
        }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

    inline std::future<void> RunAsync(std::function<SPXHR(SPXCONVERSATIONHANDLE)> func)
    {
        auto keepalive = this->shared_from_this();
        return std::async(std::launch::async, [keepalive, this, func]()
        {
            SPX_THROW_ON_FAIL(func(m_hconversation));
        });
    }

    /*! \endcond */

public:
    /// <summary>
    /// A collection of properties and their values defined for this <see cref="Conversation"/>.
    /// </summary>
    PropertyCollection& Properties;

};

}}}}
