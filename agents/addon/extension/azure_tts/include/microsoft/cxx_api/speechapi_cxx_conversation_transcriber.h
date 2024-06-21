//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_conversation_transcriber.h: Public API declarations for ConversationTranscriber C++ class
//

#pragma once
#include <exception>
#include <future>
#include <memory>
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>
#include <speechapi_cxx_recognizer.h>
#include <speechapi_cxx_conversation_transcription_eventargs.h>
#include <speechapi_cxx_conversation_transcription_result.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_speech_config.h>
#include <speechapi_cxx_audio_stream.h>
#include <speechapi_cxx_auto_detect_source_lang_config.h>
#include <speechapi_cxx_source_lang_config.h>
#include <speechapi_cxx_audio_config.h>
#include <speechapi_cxx_utils.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Transcription {

class Session;

/// <summary>
/// Class for ConversationTranscribers.
/// </summary>
class ConversationTranscriber final : public Recognizer
{
public:
    /// <summary>
    /// Create a conversation transcriber from a speech config
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <returns>A smart pointer wrapped conversation transcriber pointer.</returns>
    static std::shared_ptr<ConversationTranscriber> FromConfig(std::shared_ptr<SpeechConfig> speechconfig, std::nullptr_t)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_conversation_transcriber_from_config(
            &hreco,
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(nullptr)));
        return std::make_shared<ConversationTranscriber>(hreco);
    }

    /// <summary>
    /// Create a conversation transcriber from a speech config and audio config.
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped conversation transcriber pointer.</returns>
    static std::shared_ptr<ConversationTranscriber> FromConfig(std::shared_ptr<SpeechConfig> speechconfig, std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_conversation_transcriber_from_config(
            &hreco,
            Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE,SpeechConfig>(speechconfig),
            Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<ConversationTranscriber>(hreco);
    }

    /// <summary>
    /// Create a conversation transcriber from a speech config, auto detection source language config and audio config
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="autoDetectSourceLangConfig">Auto detection source language config.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped conversation trasncriber pointer.</returns>
    static std::shared_ptr<ConversationTranscriber> FromConfig(
        std::shared_ptr<SpeechConfig> speechconfig,
        std::shared_ptr<AutoDetectSourceLanguageConfig> autoDetectSourceLangConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_conversation_transcriber_from_auto_detect_source_lang_config(
            &hreco,
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            Utils::HandleOrInvalid<SPXAUTODETECTSOURCELANGCONFIGHANDLE, AutoDetectSourceLanguageConfig>(autoDetectSourceLangConfig),
            Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<ConversationTranscriber>(hreco);
    }

    /// <summary>
    /// Create a conversation transcriber from a speech config, source language config and audio config
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="sourceLanguageConfig">Source language config.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped conversation transcriber pointer.</returns>
    static std::shared_ptr<ConversationTranscriber> FromConfig(
        std::shared_ptr<SpeechConfig> speechconfig,
        std::shared_ptr<SourceLanguageConfig> sourceLanguageConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_conversation_transcriber_from_source_lang_config(
            &hreco,
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            Utils::HandleOrInvalid<SPXSOURCELANGCONFIGHANDLE, SourceLanguageConfig>(sourceLanguageConfig),
            Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<ConversationTranscriber>(hreco);
    }

    /// <summary>
    /// Create a conversation transcriber from a speech config, source language and audio config
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="sourceLanguage">Source language.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped conversation transcriber pointer.</returns>
    static std::shared_ptr<ConversationTranscriber> FromConfig(
        std::shared_ptr<SpeechConfig> speechconfig,
        const SPXSTRING& sourceLanguage,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        return FromConfig(speechconfig, SourceLanguageConfig::FromLanguage(sourceLanguage), audioInput);
    }

    /// <summary>
    /// Asynchronously starts a conversation transcribing.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> StartTranscribingAsync()
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this]() -> void {
            SPX_INIT_HR(hr);
        SPX_THROW_ON_FAIL(hr = recognizer_async_handle_release(m_hasyncStartContinuous)); // close any unfinished previous attempt

        SPX_EXITFN_ON_FAIL(hr = recognizer_start_continuous_recognition_async(m_hreco, &m_hasyncStartContinuous));
        SPX_EXITFN_ON_FAIL(hr = recognizer_start_continuous_recognition_async_wait_for(m_hasyncStartContinuous, UINT32_MAX));

    SPX_EXITFN_CLEANUP:
        auto releaseHr = recognizer_async_handle_release(m_hasyncStartContinuous);
        SPX_REPORT_ON_FAIL(releaseHr);
        m_hasyncStartContinuous = SPXHANDLE_INVALID;

        SPX_THROW_ON_FAIL(hr);
            });

        return future;
    }

    /// <summary>
    /// Asynchronously stops a conversation transcribing.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> StopTranscribingAsync()
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this]() -> void {
            SPX_INIT_HR(hr);
            SPX_THROW_ON_FAIL(hr = recognizer_async_handle_release(m_hasyncStopContinuous)); // close any unfinished previous attempt

            SPX_EXITFN_ON_FAIL(hr = recognizer_stop_continuous_recognition_async(m_hreco, &m_hasyncStopContinuous));
            SPX_EXITFN_ON_FAIL(hr = recognizer_stop_continuous_recognition_async_wait_for(m_hasyncStopContinuous, UINT32_MAX));

        SPX_EXITFN_CLEANUP:
            auto releaseHr = recognizer_async_handle_release(m_hasyncStopContinuous);
            SPX_REPORT_ON_FAIL(releaseHr);
            m_hasyncStopContinuous = SPXHANDLE_INVALID;

            SPX_THROW_ON_FAIL(hr);
        });

        return future;
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hreco">Recognizer handle.</param>
    explicit ConversationTranscriber(SPXRECOHANDLE hreco) throw() :
        Recognizer(hreco),
        SessionStarted(GetSessionEventConnectionsChangedCallback()),
        SessionStopped(GetSessionEventConnectionsChangedCallback()),
        SpeechStartDetected(GetRecognitionEventConnectionsChangedCallback()),
        SpeechEndDetected(GetRecognitionEventConnectionsChangedCallback()),
        Transcribing(GetRecoEventConnectionsChangedCallback()),
        Transcribed(GetRecoEventConnectionsChangedCallback()),
        Canceled(GetRecoCanceledEventConnectionsChangedCallback()),
        m_hasyncStartContinuous(SPXHANDLE_INVALID),
        m_hasyncStopContinuous(SPXHANDLE_INVALID),
        m_properties(hreco),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~ConversationTranscriber()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        TermRecognizer();
    }

    /// <summary>
    /// Signal for events indicating the start of a recognition session (operation).
    /// </summary>
    EventSignal<const SessionEventArgs&> SessionStarted;

    /// <summary>
    /// Signal for events indicating the end of a recognition session (operation).
    /// </summary>
    EventSignal<const SessionEventArgs&> SessionStopped;

    /// <summary>
    /// Signal for events indicating the start of speech.
    /// </summary>
    EventSignal<const RecognitionEventArgs&> SpeechStartDetected;

    /// <summary>
    /// Signal for events indicating the end of speech.
    /// </summary>
    EventSignal<const RecognitionEventArgs&> SpeechEndDetected;

    /// <summary>
    /// Signal for events containing intermediate recognition results.
    /// </summary>
    EventSignal<const ConversationTranscriptionEventArgs&> Transcribing;

    /// <summary>
    /// Signal for events containing final recognition results.
    /// (indicating a successful recognition attempt).
    /// </summary>
    EventSignal<const ConversationTranscriptionEventArgs&> Transcribed;

    /// <summary>
    /// Signal for events containing canceled recognition results
    /// (indicating a recognition attempt that was canceled as a result or a direct cancellation request
    /// or, alternatively, a transport or protocol failure).
    /// </summary>
    EventSignal<const ConversationTranscriptionCanceledEventArgs&> Canceled;

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

 protected:
    /*! \cond PROTECTED */

     /// <summary>
     /// Internal constructor. Creates a new instance using the provided handle.
     /// </summary>
     /// <param name="hreco">Recognizer handle.</param>
    virtual void TermRecognizer() override
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        // Disconnect the event signals in reverse construction order
        Canceled.DisconnectAll();
        Transcribed.DisconnectAll();
        Transcribing.DisconnectAll();
        SpeechEndDetected.DisconnectAll();
        SpeechStartDetected.DisconnectAll();
        SessionStopped.DisconnectAll();
        SessionStarted.DisconnectAll();

        // Close the async handles we have open for Recognize, StartContinuous, and StopContinuous
        for (auto handle : { &m_hasyncStartContinuous, &m_hasyncStopContinuous })
        {
            if (*handle != SPXHANDLE_INVALID && ::recognizer_async_handle_is_valid(*handle))
            {
                ::recognizer_async_handle_release(*handle);
                *handle = SPXHANDLE_INVALID;
            }
        }

        // Ask the base to term
        Recognizer::TermRecognizer();
    }

    void RecoEventConnectionsChanged(const EventSignal<const ConversationTranscriptionEventArgs&>& recoEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&recoEvent == &Transcribing)
            {
                recognizer_recognizing_set_callback(m_hreco, Transcribing.IsConnected() ? FireEvent_Transcribing : nullptr, this);
            }
            else if (&recoEvent == &Transcribed)
            {
                recognizer_recognized_set_callback(m_hreco, Transcribed.IsConnected() ? FireEvent_Transcribed : nullptr, this);
            }
        }
    }

    static void FireEvent_Transcribing(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<ConversationTranscriptionEventArgs> recoEvent{ new ConversationTranscriptionEventArgs(hevent) };

        auto pThis = static_cast<ConversationTranscriber*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->Transcribing.Signal(*recoEvent.get());
    }

    static void FireEvent_Transcribed(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<ConversationTranscriptionEventArgs> recoEvent{ new ConversationTranscriptionEventArgs(hevent) };

        auto pThis = static_cast<ConversationTranscriber*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->Transcribed.Signal(*recoEvent.get());
    }

    void RecoCanceledEventConnectionsChanged(const EventSignal<const ConversationTranscriptionCanceledEventArgs&>& recoEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&recoEvent == &Canceled)
            {
                recognizer_canceled_set_callback(m_hreco, Canceled.IsConnected() ? FireEvent_Canceled : nullptr, this);
            }
        }
    }

    static void FireEvent_Canceled(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);

        auto ptr = new ConversationTranscriptionCanceledEventArgs(hevent);
        std::shared_ptr<ConversationTranscriptionCanceledEventArgs> recoEvent(ptr);

        auto pThis = static_cast<ConversationTranscriber*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->Canceled.Signal(*ptr);
    }

    void SessionEventConnectionsChanged(const EventSignal<const SessionEventArgs&>& sessionEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&sessionEvent == &SessionStarted)
            {
                recognizer_session_started_set_callback(m_hreco, SessionStarted.IsConnected() ? FireEvent_SessionStarted : nullptr, this);
            }
            else if (&sessionEvent == &SessionStopped)
            {
                recognizer_session_stopped_set_callback(m_hreco, SessionStopped.IsConnected() ? FireEvent_SessionStopped : nullptr, this);
            }
        }
    }

    static void FireEvent_SessionStarted(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<SessionEventArgs> sessionEvent{ new SessionEventArgs(hevent) };

        auto pThis = static_cast<ConversationTranscriber*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->SessionStarted.Signal(*sessionEvent.get());

        // SessionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(hevent));
        recognizer_event_handle_release(hevent);
    }

    static void FireEvent_SessionStopped(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<SessionEventArgs> sessionEvent{ new SessionEventArgs(hevent) };

        auto pThis = static_cast<ConversationTranscriber*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->SessionStopped.Signal(*sessionEvent.get());

        // SessionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(hevent));
        recognizer_event_handle_release(hevent);
    }

    void RecognitionEventConnectionsChanged(const EventSignal<const RecognitionEventArgs&>& recognitionEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&recognitionEvent == &SpeechStartDetected)
            {
                recognizer_speech_start_detected_set_callback(m_hreco, SpeechStartDetected.IsConnected() ? FireEvent_SpeechStartDetected : nullptr, this);
            }
            else if (&recognitionEvent == &SpeechEndDetected)
            {
                recognizer_speech_end_detected_set_callback(m_hreco, SpeechEndDetected.IsConnected() ? FireEvent_SpeechEndDetected : nullptr, this);
            }
        }
    }

    static void FireEvent_SpeechStartDetected(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<RecognitionEventArgs> recoEvent{ new RecognitionEventArgs(hevent) };

        auto pThis = static_cast<ConversationTranscriber*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->SpeechStartDetected.Signal(*recoEvent.get());

        // RecognitionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(hevent));
        recognizer_event_handle_release(hevent);
    }

    static void FireEvent_SpeechEndDetected(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<RecognitionEventArgs> recoEvent{ new RecognitionEventArgs(hevent) };

        auto pThis = static_cast<ConversationTranscriber*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->SpeechEndDetected.Signal(*recoEvent.get());

        // RecognitionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(hevent));
        recognizer_event_handle_release(hevent);
    }

    /*! \endcond */

private:

    SPXASYNCHANDLE m_hasyncStartContinuous;
    SPXASYNCHANDLE m_hasyncStopContinuous;

    DISABLE_DEFAULT_CTORS(ConversationTranscriber);
    friend class Microsoft::CognitiveServices::Speech::Session;

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXRECOHANDLE hreco) :
            PropertyCollection(
                [=]() {
                    SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
        recognizer_get_property_bag(hreco, &hpropbag);
        return hpropbag;
                }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

    inline std::function<void(const EventSignal<const SessionEventArgs&>&)> GetSessionEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const SessionEventArgs&>& sessionEvent) { this->SessionEventConnectionsChanged(sessionEvent); };
    }

    inline std::function<void(const EventSignal<const ConversationTranscriptionEventArgs&>&)> GetRecoEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const ConversationTranscriptionEventArgs&>& recoEvent) { this->RecoEventConnectionsChanged(recoEvent); };
    }

    inline std::function<void(const EventSignal<const ConversationTranscriptionCanceledEventArgs&>&)> GetRecoCanceledEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const ConversationTranscriptionCanceledEventArgs&>& recoEvent) { this->RecoCanceledEventConnectionsChanged(recoEvent); };
    }

    inline std::function<void(const EventSignal<const RecognitionEventArgs&>&)> GetRecognitionEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const RecognitionEventArgs&>& recoEvent) { this->RecognitionEventConnectionsChanged(recoEvent); };
    }

public:
    /// <summary>
    /// A collection of properties and their values defined for this <see cref="ConversationTranscriber"/>.
    /// </summary>
    PropertyCollection& Properties;
};


} } } } // Microsoft::CognitiveServices::Speech::Transcription
