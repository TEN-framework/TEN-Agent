//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_recognition_async_recognizer.h: Public API declarations for AsyncRecognizer<RecoResult, RecoEventArgs> C++ template class
//

#pragma once
#include <future>
#include <memory>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_eventsignal.h>
#include <speechapi_cxx_recognizer.h>
#include <speechapi_cxx_session_eventargs.h>
#include <speechapi_cxx_recognition_eventargs.h>
#include <speechapi_cxx_keyword_recognition_model.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// AsyncRecognizer abstract base class.
/// </summary>
template <class RecoResult, class RecoEventArgs, class RecoCanceledEventArgs>
class AsyncRecognizer : public Recognizer
{
public:

    /// <summary>
    /// Performs recognition in a non-blocking (asynchronous) mode.
    /// </summary>
    /// <returns>Future containing result value (a shared pointer to RecoResult)
    /// of the asynchronous recognition.
    /// </returns>
    virtual std::future<std::shared_ptr<RecoResult>> RecognizeOnceAsync() = 0;

    /// <summary>
    /// Asynchronously initiates continuous recognition operation.
    /// </summary>
    /// <returns>An empty future.</returns>
    virtual std::future<void> StartContinuousRecognitionAsync() = 0;

    /// <summary>
    /// Asynchronously terminates ongoing continuous recognition operation.
    /// </summary>
    /// <returns>An empty future.</returns>
    virtual std::future<void> StopContinuousRecognitionAsync() = 0;

    /// <summary>
    /// Asynchronously initiates keyword recognition operation.
    /// </summary>
    /// <param name="model">The keyword recognition model that specifies the keyword to be recognized.</param>
    /// <returns>An asynchronous operation that starts the keyword recognition.</returns>
    virtual std::future<void> StartKeywordRecognitionAsync(std::shared_ptr<KeywordRecognitionModel> model) = 0;

    /// <summary>
    /// Asynchronously terminates ongoing keyword recognition operation.
    /// </summary>
    /// <returns>An empty future.</returns>
    virtual std::future<void> StopKeywordRecognitionAsync() = 0;

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
    EventSignal<const RecoEventArgs&> Recognizing;

    /// <summary>
    /// Signal for events containing final recognition results.
    /// (indicating a successful recognition attempt).
    /// </summary>
    EventSignal<const RecoEventArgs&> Recognized;

    /// <summary>
    /// Signal for events containing canceled recognition results
    /// (indicating a recognition attempt that was canceled as a result or a direct cancellation request
    /// or, alternatively, a transport or protocol failure).
    /// </summary>
    EventSignal<const RecoCanceledEventArgs&> Canceled;

protected:

    /*! \cond PROTECTED */

    explicit AsyncRecognizer(SPXRECOHANDLE hreco) throw() :
        Recognizer(hreco),
        SessionStarted(GetSessionEventConnectionsChangedCallback()),
        SessionStopped(GetSessionEventConnectionsChangedCallback()),
        SpeechStartDetected(GetRecognitionEventConnectionsChangedCallback()),
        SpeechEndDetected(GetRecognitionEventConnectionsChangedCallback()),
        Recognizing(GetRecoEventConnectionsChangedCallback()),
        Recognized(GetRecoEventConnectionsChangedCallback()),
        Canceled(GetRecoCanceledEventConnectionsChangedCallback()),
        m_properties(hreco),
        m_hasyncRecognize(SPXHANDLE_INVALID),
        m_hasyncStartContinuous(SPXHANDLE_INVALID),
        m_hasyncStopContinuous(SPXHANDLE_INVALID),
        m_hasyncStartKeyword(SPXHANDLE_INVALID),
        m_hasyncStopKeyword(SPXHANDLE_INVALID)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    };

    virtual ~AsyncRecognizer()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        TermRecognizer();
    };

    virtual void TermRecognizer() override
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        // Disconnect the event signals in reverse construction order
        Canceled.DisconnectAll();
        Recognized.DisconnectAll();
        Recognizing.DisconnectAll();
        SpeechEndDetected.DisconnectAll();
        SpeechStartDetected.DisconnectAll();
        SessionStopped.DisconnectAll();
        SessionStarted.DisconnectAll();

        // Close the async handles we have open for Recognize, StartContinuous, and StopContinuous
        for (auto handle : { &m_hasyncRecognize, &m_hasyncStartContinuous, &m_hasyncStopContinuous })
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

    std::future<std::shared_ptr<RecoResult>> RecognizeOnceAsyncInternal()
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this]() -> std::shared_ptr<RecoResult> {
            SPX_INIT_HR(hr);

            SPXRESULTHANDLE hresult = SPXHANDLE_INVALID;
            SPX_THROW_ON_FAIL(hr = recognizer_recognize_once(m_hreco, &hresult));

            return std::make_shared<RecoResult>(hresult);
        });

        return future;
    };

    std::future<void> StartContinuousRecognitionAsyncInternal()
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
    };

    std::future<void> StopContinuousRecognitionAsyncInternal()
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

    std::future<void> StartKeywordRecognitionAsyncInternal(std::shared_ptr<KeywordRecognitionModel> model)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, model, this]() -> void {
            SPX_INIT_HR(hr);
            SPX_THROW_ON_FAIL(hr = recognizer_async_handle_release(m_hasyncStartKeyword)); // close any unfinished previous attempt

            auto hkeyword = (SPXKEYWORDHANDLE)(*model.get());
            SPX_EXITFN_ON_FAIL(hr = recognizer_start_keyword_recognition_async(m_hreco, hkeyword, &m_hasyncStartKeyword));
            SPX_EXITFN_ON_FAIL(hr = recognizer_start_keyword_recognition_async_wait_for(m_hasyncStartKeyword, UINT32_MAX));

            SPX_EXITFN_CLEANUP:
            auto releaseHr = recognizer_async_handle_release(m_hasyncStartKeyword);
            SPX_REPORT_ON_FAIL(releaseHr);
            m_hasyncStartKeyword = SPXHANDLE_INVALID;

            SPX_THROW_ON_FAIL(hr);
        });

        return future;
    };

    std::future<void> StopKeywordRecognitionAsyncInternal()
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this]() -> void {
            SPX_INIT_HR(hr);
            SPX_THROW_ON_FAIL(hr = recognizer_async_handle_release(m_hasyncStopKeyword)); // close any unfinished previous attempt

            SPX_EXITFN_ON_FAIL(hr = recognizer_stop_keyword_recognition_async(m_hreco, &m_hasyncStopKeyword));
            SPX_EXITFN_ON_FAIL(hr = recognizer_stop_keyword_recognition_async_wait_for(m_hasyncStopKeyword, UINT32_MAX));

            SPX_EXITFN_CLEANUP:
            auto releaseHr = recognizer_async_handle_release(m_hasyncStopKeyword);
            SPX_REPORT_ON_FAIL(releaseHr);
            m_hasyncStartKeyword = SPXHANDLE_INVALID;

            SPX_THROW_ON_FAIL(hr);
        });

        return future;
    };

    virtual void RecoEventConnectionsChanged(const EventSignal<const RecoEventArgs&>& recoEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&recoEvent == &Recognizing)
            {
                recognizer_recognizing_set_callback(m_hreco, Recognizing.IsConnected() ? AsyncRecognizer::FireEvent_Recognizing: nullptr, this);
            }
            else if (&recoEvent == &Recognized)
            {
                recognizer_recognized_set_callback(m_hreco, Recognized.IsConnected() ? AsyncRecognizer::FireEvent_Recognized: nullptr, this);
            }
        }
    }

    virtual void RecoCanceledEventConnectionsChanged(const EventSignal<const RecoCanceledEventArgs&>& recoEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&recoEvent == &Canceled)
            {
                recognizer_canceled_set_callback(m_hreco, Canceled.IsConnected() ? AsyncRecognizer::FireEvent_Canceled : nullptr, this);
            }
        }
    }

    virtual void RecognitionEventConnectionsChanged(const EventSignal<const RecognitionEventArgs&>& recognitionEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&recognitionEvent == &SpeechStartDetected)
            {
                recognizer_speech_start_detected_set_callback(m_hreco, SpeechStartDetected.IsConnected() ? AsyncRecognizer::FireEvent_SpeechStartDetected : nullptr, this);
            }
            else if (&recognitionEvent == &SpeechEndDetected)
            {
                recognizer_speech_end_detected_set_callback(m_hreco, SpeechEndDetected.IsConnected() ? AsyncRecognizer::FireEvent_SpeechEndDetected : nullptr, this);
            }
        }
    }

    virtual void SessionEventConnectionsChanged(const EventSignal<const SessionEventArgs&>& sessionEvent)
    {
        if (m_hreco != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_hreco=0x%8p", __FUNCTION__, (void*)m_hreco);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_hreco), "%s: m_hreco is INVALID!!!", __FUNCTION__);

            if (&sessionEvent == &SessionStarted)
            {
                recognizer_session_started_set_callback(m_hreco, SessionStarted.IsConnected() ? AsyncRecognizer::FireEvent_SessionStarted: nullptr, this);
            }
            else if (&sessionEvent == &SessionStopped)
            {
                recognizer_session_stopped_set_callback(m_hreco, SessionStopped.IsConnected() ? AsyncRecognizer::FireEvent_SessionStopped : nullptr, this);
            }
        }
    }

    static void FireEvent_SessionStarted(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<SessionEventArgs> sessionEvent { new SessionEventArgs(hevent) };

        auto pThis = static_cast<AsyncRecognizer*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->SessionStarted.Signal(*sessionEvent.get());

        // SessionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(hevent));
        recognizer_event_handle_release(hevent);
    }

    static void FireEvent_SessionStopped(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<SessionEventArgs> sessionEvent { new SessionEventArgs(hevent) };

        auto pThis = static_cast<AsyncRecognizer*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->SessionStopped.Signal(*sessionEvent.get());

        // SessionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(hevent));
        recognizer_event_handle_release(hevent);
    }

    static void FireEvent_SpeechStartDetected(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<RecognitionEventArgs> recoEvent{ new RecognitionEventArgs(hevent) };

        auto pThis = static_cast<AsyncRecognizer*>(pvContext);
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

        auto pThis = static_cast<AsyncRecognizer*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->SpeechEndDetected.Signal(*recoEvent.get());

        // RecognitionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(hevent));
        recognizer_event_handle_release(hevent);
    }

    static void FireEvent_Recognizing(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<RecoEventArgs> recoEvent { new RecoEventArgs(hevent) };

        auto pThis = static_cast<AsyncRecognizer*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->Recognizing.Signal(*recoEvent.get());
    }

    static void FireEvent_Recognized(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<RecoEventArgs> recoEvent { new RecoEventArgs(hevent) };

        auto pThis = static_cast<AsyncRecognizer*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->Recognized.Signal(*recoEvent.get());
    }

    static void FireEvent_Canceled(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);

        auto ptr = new RecoCanceledEventArgs(hevent);
        std::shared_ptr<RecoCanceledEventArgs> recoEvent(ptr);

        auto pThis = static_cast<AsyncRecognizer*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->Canceled.Signal(*ptr);
    }

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXRECOHANDLE hreco) :
            PropertyCollection(
                [=](){
                SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                recognizer_get_property_bag(hreco, &hpropbag);
                return hpropbag;
            }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

    SPXASYNCHANDLE m_hasyncRecognize;
    SPXASYNCHANDLE m_hasyncStartContinuous;
    SPXASYNCHANDLE m_hasyncStopContinuous;
    SPXASYNCHANDLE m_hasyncStartKeyword;
    SPXASYNCHANDLE m_hasyncStopKeyword;

    template <typename Handle, typename Config>
    static Handle HandleOrInvalid(std::shared_ptr<Config> audioInput)
    {
        return audioInput == nullptr
            ? (Handle)SPXHANDLE_INVALID
            : (Handle)(*audioInput.get());
    }

    /*! \endcond */

private:

    DISABLE_DEFAULT_CTORS(AsyncRecognizer);

    inline std::function<void(const EventSignal<const SessionEventArgs&>&)> GetSessionEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const SessionEventArgs&>& sessionEvent) { this->SessionEventConnectionsChanged(sessionEvent); };
    }

    inline std::function<void(const EventSignal<const RecoEventArgs&>&)> GetRecoEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const RecoEventArgs&>& recoEvent) { this->RecoEventConnectionsChanged(recoEvent); };
    }

    inline std::function<void(const EventSignal<const RecoCanceledEventArgs&>&)> GetRecoCanceledEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const RecoCanceledEventArgs&>& recoEvent) { this->RecoCanceledEventConnectionsChanged(recoEvent); };
    }

    inline std::function<void(const EventSignal<const RecognitionEventArgs&>&)> GetRecognitionEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const RecognitionEventArgs&>& recoEvent) { this->RecognitionEventConnectionsChanged(recoEvent); };
    }
};


} } } // Microsoft::CognitiveServices::Speech
