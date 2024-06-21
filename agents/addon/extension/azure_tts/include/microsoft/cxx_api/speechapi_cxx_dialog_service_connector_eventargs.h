//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once

#include <memory>
#include <vector>

#include <speechapi_cxx_audio_stream.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Dialog {

// Forward declarations
class DialogServiceConnector;

/// <summary>
/// Class for activity received event arguments.
/// </summary>
class ActivityReceivedEventArgs: public std::enable_shared_from_this<ActivityReceivedEventArgs>
{
public:
    friend DialogServiceConnector;
    /// <summary>
    /// Releases the event.
    /// </summary>
    inline ~ActivityReceivedEventArgs()
    {
        SPX_THROW_ON_FAIL(::dialog_service_connector_activity_received_event_release(m_handle));
    }

    /// <summary>
    /// Gets the activity associated with the event.
    /// </summary>
    /// <returns>The serialized activity activity.</returns>
    inline std::string GetActivity() const
    {
        size_t size;
        SPX_THROW_ON_FAIL(::dialog_service_connector_activity_received_event_get_activity_size(m_handle, &size));
        auto ptr = std::make_unique<char[]>(size + 1);
        SPX_THROW_ON_FAIL(::dialog_service_connector_activity_received_event_get_activity(m_handle, ptr.get(), size + 1));
        return std::string{ ptr.get() };
    }

    /// <summary>
    /// Gets the audio associated with the event.
    /// </summary>
    /// <returns>The audio.</returns>
    inline std::shared_ptr<Audio::PullAudioOutputStream> GetAudio() const
    {
        SPXAUDIOSTREAMHANDLE h_audio{ SPXHANDLE_INVALID };
        SPX_THROW_ON_FAIL(::dialog_service_connector_activity_received_event_get_audio(m_handle, &h_audio));
        if (h_audio == SPXHANDLE_INVALID)
        {
            return nullptr;
        }
        return std::shared_ptr<Audio::PullAudioOutputStream>(new Audio::PullAudioOutputStream(h_audio) );
    }

    /// <summary>
    /// Checks if the event contains audio.
    /// </summary>
    /// <returns>True if the event contains audio, false otherwise.</returns>
    inline bool HasAudio() const
    {
        return ::dialog_service_connector_activity_received_event_has_audio(m_handle);
    }
private:
    /*! \cond PROTECTED */
    inline ActivityReceivedEventArgs(SPXEVENTHANDLE h_event) : m_handle{ h_event }
    {
    }

    SPXEVENTHANDLE m_handle;
    /*! \endcond */
};

/// <summary>
/// Class for turn status event arguments.
/// </summary>
class TurnStatusReceivedEventArgs : public std::enable_shared_from_this<TurnStatusReceivedEventArgs>
{
public:
    friend DialogServiceConnector;
    /// <summary>
    /// Releases the event.
    /// </summary>
    inline ~TurnStatusReceivedEventArgs()
    {
        SPX_THROW_ON_FAIL(::dialog_service_connector_turn_status_received_release(m_handle));
    }

    /// <summary>
    /// Retrieves the interaction ID associated with this turn status event. Interaction generally correspond
    /// to a single input signal (e.g. voice utterance) or data/activity transaction and will correlate to
    /// 'replyToId' fields in Bot Framework activities.
    /// </summary>
    /// <returns> The interaction ID associated with the turn status. </returns>
    inline std::string GetInteractionId() const
    {
        size_t size = 0;
        SPX_THROW_ON_FAIL(::dialog_service_connector_turn_status_received_get_interaction_id_size(m_handle, &size));
        auto ptr = std::make_unique<char[]>(size + 1);
        SPX_THROW_ON_FAIL(::dialog_service_connector_turn_status_received_get_interaction_id(m_handle, ptr.get(), size + 1));
        return std::string{ ptr.get() };
    }

    /// <summary>
    /// Retrieves the conversation ID associated with this turn status event. Conversations may span multiple
    /// interactions and are the unit which a client may request resume/retry upon.
    /// </summary>
    /// <returns> The conversation ID associated with the turn status. </returns>
    inline std::string GetConversationId() const
    {
        size_t size = 0;
        SPX_THROW_ON_FAIL(::dialog_service_connector_turn_status_received_get_conversation_id_size(m_handle, &size));
        auto ptr = std::make_unique<char[]>(size + 1);
        SPX_THROW_ON_FAIL(::dialog_service_connector_turn_status_received_get_conversation_id(m_handle, ptr.get(), size + 1));
        return std::string{ ptr.get() };
    }

    /// <summary>
    /// Retrieves the numeric status code associated with this turn status event. These generally correspond to
    /// standard HTTP status codes such as 200 (OK), 400 (Failure/Bad Request), and 429 (Timeout/Throttled).
    /// </summary>
    /// <returns> The status code associated with this event, analolgous to standard HTTP codes. </returns>
    inline int GetStatusCode() const
    {
        int cApiStatus = 404;
        SPX_THROW_ON_FAIL(::dialog_service_connector_turn_status_received_get_status(m_handle, &cApiStatus));
        return cApiStatus;
    }

private:
    /*! \cond PROTECTED */
    inline TurnStatusReceivedEventArgs(SPXEVENTHANDLE h_event) : m_handle{ h_event }
    {
    }

    SPXEVENTHANDLE m_handle;
    /*! \endcond */
};

} } } }
