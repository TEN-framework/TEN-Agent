
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_conversation_translator_events.h: Public C++ class API declarations for ConversationTranslator related events
//

#pragma once

#include <exception>
#include <future>
#include <memory>
#include <string>
#include <cstring>

#include <speechapi_c_conversation_translator.h>
#include <speechapi_c_conversation_transcription_result.h>
#include <speechapi_cxx_conversation_transcription_eventargs.h>
#include <speechapi_cxx_translation_eventargs.h>
#include <speechapi_cxx_session_eventargs.h>
#include <speechapi_cxx_participant.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Transcription {

    /// <summary>
    /// Helper class with additional methods
    /// Added in 1.9.0
    /// </summary>
    class EventHelper
    {
    protected:
        template<typename TVal, typename THandle>
        static TVal GetValue(THandle hevent, SPXHR(SPXAPI_CALLTYPE * func)(THandle hevent, TVal* ptr))
        {
            TVal value;
            SPX_THROW_ON_FAIL(func(hevent, &value));
            return value;
        }

        template<typename THandle>
        static SPXSTRING GetStringValue(THandle hevent, SPXHR(SPXAPI_CALLTYPE * func)(THandle hevent, char * psz, uint32_t cch))
        {
            const uint32_t maxCharCount = 1024;
            char sz[maxCharCount + 1];
            SPX_THROW_ON_FAIL(func(hevent, sz, maxCharCount));
            return Utils::ToSPXString(sz);
        }

        template<typename THandle>
        static SPXSTRING GetStringValue(THandle hevent, SPXHR(SPXAPI_CALLTYPE* func)(THandle hevent, char* psz, uint32_t* pcch))
        {
            // query the string length
            uint32_t length = 0;
            SPX_THROW_ON_FAIL(func(hevent, nullptr, &length));

            // retrieve the string
            std::unique_ptr<char[]> buffer(new char[length]);
            SPX_THROW_ON_FAIL(func(hevent, buffer.get(), &length));
            return Utils::ToSPXString(buffer.get());
        }
    };

    /// <summary>
    /// Represents the result of a conversation translator recognition, or text message.
    /// Added in 1.9.0
    /// </summary>
    class ConversationTranslationResult : public Translation::TranslationRecognitionResult, public EventHelper
    {
    private:
        SPXSTRING m_participantId;
        SPXSTRING m_originalLang;

    public:
        explicit ConversationTranslationResult(SPXRESULTHANDLE resultHandle) :
            Translation::TranslationRecognitionResult(resultHandle),
            m_participantId(GetStringValue(resultHandle, conversation_translator_result_get_user_id)),
            m_originalLang(GetStringValue(resultHandle, conversation_translator_result_get_original_lang)),
            ParticipantId(m_participantId),
            OriginalLanguage(m_originalLang)
        {
        }

        /// <summary>
        /// The unique participant identifier
        /// </summary>
        const SPXSTRING& ParticipantId;

        /// <summary>
        /// Gets the language that the original recognition or text message is in
        /// </summary>
        const SPXSTRING& OriginalLanguage;

    private:
        DISABLE_COPY_AND_MOVE(ConversationTranslationResult);
    };

    /// <summary>
    /// Event arguments for the ConversationExpiration event.
    /// Added in 1.9.0
    /// </summary>
    class ConversationExpirationEventArgs : public SessionEventArgs, public EventHelper
    {
    private:
        std::chrono::minutes m_expirationTime;

    public:
        /// <summary>
        /// Creates a new instance.
        /// </summary>
        /// <param name="hevent">The event handle.</param>
        explicit ConversationExpirationEventArgs(SPXEVENTHANDLE hevent) :
            SessionEventArgs(hevent),
            m_expirationTime(std::chrono::minutes(GetValue(hevent, conversation_translator_event_get_expiration_time))),
            ExpirationTime(m_expirationTime)
        {
        }

        /// <summary>
        /// How many minutes are left until the conversation expires
        /// </summary>
        const std::chrono::minutes& ExpirationTime;

    private:
        DISABLE_COPY_AND_MOVE(ConversationExpirationEventArgs);
    };

    /// <summary>
    /// Event arguments for the ParticipantsChanged event.
    /// Added in 1.9.0
    /// </summary>
    class ConversationParticipantsChangedEventArgs : public SessionEventArgs, public EventHelper
    {
    private:
        ParticipantChangedReason m_reason;
        std::vector<std::shared_ptr<Participant>> m_participants;

    public:
        /// <summary>
        /// Creates a new instance.
        /// </summary>
        /// <param name="hevent">The event handle.</param>
        explicit ConversationParticipantsChangedEventArgs(SPXEVENTHANDLE hevent) :
            SessionEventArgs(hevent),
            m_reason(GetValue(hevent, conversation_translator_event_get_participant_changed_reason)),
            m_participants(GetParticipants(hevent)),
            Reason(m_reason),
            Participants(m_participants)
        {
        }

        /// <summary>
        /// Why the participant changed event was raised (e.g. a participant joined)
        /// </summary>
        const ParticipantChangedReason& Reason;

        /// <summary>
        /// The participant(s) that joined, left, or were updated
        /// </summary>
        const std::vector<std::shared_ptr<Participant>>& Participants;

    protected:
        /*! \cond PROTECTED */

        std::vector<std::shared_ptr<Participant>> GetParticipants(SPXEVENTHANDLE hevent)
        {
            std::vector<std::shared_ptr<Participant>> list;

            SPXPARTICIPANTHANDLE hparticipant = nullptr;
            for (int i = 0; hparticipant != SPXHANDLE_INVALID; i++)
            {
                SPX_THROW_ON_FAIL(conversation_translator_event_get_participant_changed_at_index(hevent, i, &hparticipant));
                if (hparticipant != SPXHANDLE_INVALID)
                {
                    list.push_back(std::make_shared<Participant>(hparticipant));

                    // the Participant object correctly frees the handle so we don't need to do anything
                    // special here
                }
            }

            return list;
        }

        /*! \endcond */

    private:
        DISABLE_COPY_AND_MOVE(ConversationParticipantsChangedEventArgs);
    };

    /// <summary>
    /// Event arguments for the ConversationTranslator <see cref="ConversationTranslator::Transcribing"/>,
    /// <see cref="ConversationTranslator::Transcribed"/>, or <see cref="ConversationTranslator::TextMessageReceived"/>
    /// events.
    /// Added in 1.9.0
    /// </summary>
    class ConversationTranslationEventArgs : public RecognitionEventArgs, public EventHelper
    {
    private:
        std::shared_ptr<ConversationTranslationResult> m_result;

    public:
        /// <summary>
        /// Creates a new instance.
        /// </summary>
        /// <param name="hevent">The event handle returned by the C-API.</param>
        explicit ConversationTranslationEventArgs(SPXEVENTHANDLE hevent)
            : RecognitionEventArgs(hevent),
            m_result(std::make_shared<ConversationTranslationResult>(GetValue(hevent, recognizer_recognition_event_get_result))),
            Result(m_result)
        {
        }

#if defined(BINDING_OBJECTIVE_C)
    private:
#endif
        /// <summary>
        /// Contains the conversation translation result. This could be for a canceled event,
        /// a speech recognition, or a received text message.
        /// </summary>
        std::shared_ptr<const ConversationTranslationResult> Result;

#if defined(BINDING_OBJECTIVE_C)
    public:
#else
    protected:
#endif

        /*! \cond PROTECTED */

        /// <summary>
        /// Contains the conversation translation result. This could be for a canceled event,
        /// a speech recognition, or a received text message.
        /// </summary>
        std::shared_ptr<ConversationTranslationResult> GetResult() const { return m_result; }

        /*! \endcond */

    private:
        DISABLE_COPY_AND_MOVE(ConversationTranslationEventArgs);
    };


    /// <summary>
    /// Event arguments for the conversation translator canceled event.
    /// Added in 1.9.0
    /// </summary>
    class ConversationTranslationCanceledEventArgs : public ConversationTranscriptionCanceledEventArgs
    {
    public:
        /// <summary>
        /// Creates a new instance.
        /// </summary>
        /// <param name="hevent">The event handle.</param>
        explicit ConversationTranslationCanceledEventArgs(SPXEVENTHANDLE hevent) :
            ConversationTranscriptionCanceledEventArgs(hevent)
        { }
    };

}}}}
