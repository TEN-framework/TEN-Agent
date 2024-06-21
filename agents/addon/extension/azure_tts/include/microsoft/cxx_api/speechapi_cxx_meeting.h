
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_meeting.h: Public API declarations for Meeting C++ class
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
/// Class for meeting.
/// </summary>
class Meeting : public std::enable_shared_from_this<Meeting>
{
public:

    static constexpr size_t MAX_MEETING_ID_LEN = 1024;

    /// <summary>
    /// Create a meeting using a speech config and a meeting id.
    /// </summary>
    /// <param name="speechConfig">A shared smart pointer of a speech config object.</param>
    /// <param name="meetingId">meeting Id.</param>
    /// <returns>A shared smart pointer of the created meeting object.</returns>
    static std::future<std::shared_ptr<Meeting>> CreateMeetingAsync(std::shared_ptr<SpeechConfig> speechConfig, const SPXSTRING& meetingId)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, meetingId.empty());
        auto future = std::async(std::launch::async, [meetingId, speechConfig]() -> std::shared_ptr<Meeting> {
            SPXMEETINGHANDLE hmeeting;
            SPX_THROW_ON_FAIL(meeting_create_from_config(&hmeeting, (SPXSPEECHCONFIGHANDLE)(*speechConfig), Utils::ToUTF8(meetingId).c_str()));
            return std::make_shared<Meeting>(hmeeting);
        });
        return future;
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hmeeting">Recognizer handle.</param>
    explicit Meeting(SPXMEETINGHANDLE hmeeting) :
        m_hmeeting(hmeeting),
        m_properties(hmeeting),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~Meeting()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        ::meeting_release_handle(m_hmeeting);
        m_hmeeting = SPXHANDLE_INVALID;
    }

    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXMEETINGHANDLE () const { return m_hmeeting; }

    /// <summary>
    /// Get the meeting id.
    /// </summary>
    /// <returns>Meeting id.</returns>
    SPXSTRING GetMeetingId()
    {
        char id[MAX_MEETING_ID_LEN + 1];
        std::memset(id, 0, MAX_MEETING_ID_LEN);
        SPX_THROW_ON_FAIL(meeting_get_meeting_id(m_hmeeting, id, MAX_MEETING_ID_LEN));
        return id;
    }

    /// <summary>
    /// Add a participant to a meeting using the user's id.
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
            SPX_THROW_ON_FAIL(meeting_update_participant(m_hmeeting, true, (SPXPARTICIPANTHANDLE)(*participant)));
            return participant;
        });
        return future;
    }

    /// <summary>
    /// Add a participant to a meeting using the User object.
    /// </summary>
    /// <param name="user">A shared smart pointer to a User object.</param>
    /// <returns>The passed in User object.</returns>
    std::future<std::shared_ptr<User>> AddParticipantAsync(const std::shared_ptr<User>& user)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, user]() -> std::shared_ptr<User> {
            SPX_THROW_ON_FAIL(meeting_update_participant_by_user(m_hmeeting, true, (SPXUSERHANDLE)(*user)));
            return user;
        });
        return future;
    }

    /// <summary>
    /// Add a participant to a meeting using the participant object
    /// </summary>
    /// <param name="participant">A shared smart pointer to a participant object.</param>
    /// <returns>The passed in participant object.</returns>
    std::future<std::shared_ptr<Participant>> AddParticipantAsync(const std::shared_ptr<Participant>& participant)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, participant]() -> std::shared_ptr<Participant> {
            SPX_THROW_ON_FAIL(meeting_update_participant(m_hmeeting, true, (SPXPARTICIPANTHANDLE)(*participant)));
            return participant;
        });
        return future;
    }

    /// <summary>
    /// Remove a participant from a meeting using the participant object
    /// </summary>
    /// <param name="participant">A shared smart pointer of a participant object.</param>
    /// <returns>An empty future.</returns>
    std::future<void> RemoveParticipantAsync(const std::shared_ptr<Participant>& participant)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, participant]() -> void {
            SPX_THROW_ON_FAIL(meeting_update_participant(m_hmeeting, false, (SPXPARTICIPANTHANDLE)(*participant)));
        });
        return future;
    }

    /// <summary>
    /// Remove a participant from a meeting using the User object
    /// </summary>
    /// <param name="user">A smart pointer of a User.</param>
    /// <returns>An empty future.</returns>
    std::future<void> RemoveParticipantAsync(const std::shared_ptr<User>& user)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, user]() -> void {
            SPX_THROW_ON_FAIL(meeting_update_participant_by_user(m_hmeeting, false, SPXUSERHANDLE(*user)));
        });
        return future;
    }

    /// <summary>
    /// Remove a participant from a meeting using a user id string.
    /// </summary>
    /// <param name="userId">A user id.</param>
    /// <returns>An empty future.</returns>
    std::future<void> RemoveParticipantAsync(const SPXSTRING& userId)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this, userId]() -> void {
            SPX_THROW_ON_FAIL(meeting_update_participant_by_user_id(m_hmeeting, false, Utils::ToUTF8(userId.c_str())));
        });
        return future;
    }

    /// <summary>
    /// Ends the current meeting.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> EndMeetingAsync()
    {
        return RunAsync(::meeting_end_meeting);
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
    /// Start the meeting.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> StartMeetingAsync()
    {
        return RunAsync(::meeting_start_meeting);
    }

    /// <summary>
    /// Deletes the meeting. Any participants that are still part of the meeting
    /// will be ejected after this call.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> DeleteMeetingAsync()
    {
        return RunAsync(::meeting_delete_meeting);
    }

    /// <summary>
    /// Locks the meeting. After this no new participants will be able to join.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> LockMeetingAsync()
    {
        return RunAsync(::meeting_lock_meeting);
    }

    /// <summary>
    /// Unlocks the meeting.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> UnlockMeetingAsync()
    {
        return RunAsync(::meeting_unlock_meeting);
    }

    /// <summary>
    /// Mutes all participants except for the host. This prevents others from generating
    /// transcriptions, or sending text messages.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> MuteAllParticipantsAsync()
    {
        return RunAsync(::meeting_mute_all_participants);
    }

    /// <summary>
    /// Allows other participants to generate transcriptions, or send text messages.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> UnmuteAllParticipantsAsync()
    {
        return RunAsync(::meeting_unmute_all_participants);
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
            return ::meeting_mute_participant(handle, participantId.c_str());
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
            return ::meeting_unmute_participant(handle, participantId.c_str());
        });
    }

private:

    /*! \cond PRIVATE */

    SPXMEETINGHANDLE m_hmeeting;

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXMEETINGHANDLE hmeeting) :
            PropertyCollection(
                [=]() {
            SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
            meeting_get_property_bag(hmeeting, &hpropbag);
            return hpropbag;
        }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

    inline std::future<void> RunAsync(std::function<SPXHR(SPXMEETINGHANDLE)> func)
    {
        auto keepalive = this->shared_from_this();
        return std::async(std::launch::async, [keepalive, this, func]()
        {
            SPX_THROW_ON_FAIL(func(m_hmeeting));
        });
    }

    /*! \endcond */

public:
    /// <summary>
    /// A collection of properties and their values defined for this <see cref="Meeting"/>.
    /// </summary>
    PropertyCollection& Properties;

};

}}}}
