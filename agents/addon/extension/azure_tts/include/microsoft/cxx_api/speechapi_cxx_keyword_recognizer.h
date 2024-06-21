//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_keyword_recognizer.h: Public API declarations for KeywordRecognizer C++ class
//
#pragma once

#include <future>
#include <memory>

#include <speechapi_c_common.h>
#include <speechapi_c_factory.h>
#include <speechapi_cxx_audio_config.h>
#include <speechapi_cxx_eventsignal.h>
#include <speechapi_cxx_keyword_recognition_model.h>
#include <speechapi_cxx_keyword_recognition_eventargs.h>
#include <speechapi_cxx_keyword_recognition_result.h>
#include <speechapi_cxx_utils.h>
#include <speechapi_cxx_properties.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

namespace Utils {
    template<typename T, typename U, typename F>
    std::function<void(const EventSignal<const T&>&)> Callback(U* callee, F f)
    {
        return [=](const EventSignal<const T&>& evt)
        {
            (callee->*f)(evt);
        };
    }
}

/// <summary>
/// Recognizer type that is specialized to only handle keyword activation.
/// </summary>
/// <example>
/// First, the object needs to be instantiated:
/// <code>
/// auto audioConfig = AudioConfig::FromMicrophoneInput(); // Or an alternative input
/// auto recognizer = KeywordRecognizer::FromConfig(audioConfig);
/// </code>
/// (optional) Then, the events need to be wired in order to receive notifications:
/// <code>
/// recognizer->Recognized += [](const KeywordRecognitionEventArgs& event)
/// {
///     // Your logic here...
/// };
/// </code>
/// And finally, recognition needs to be started.
/// <code>
/// auto keywordModel = KeywordRecognitionModel::FromFile(modelPath);
/// auto resultFuture = recognizer->RecognizeKeywordOnceAsync(keywordModel);
/// resultFuture.wait();
/// auto result = resultFuture.get();
/// </code>
/// <ul>
///   <li><see cref="KeywordRecognitionResult" /></li>
///   <li><see cref="KeywordRecognitionEventArgs" /><li>
///   <li><see cref="KeywordRecognitionModel" /></li>
///   <li><see cref="AudioConfig" /></li>
/// </ul>
/// </example>
class KeywordRecognizer: public std::enable_shared_from_this<KeywordRecognizer>
{
public:
    /// <summary>
    /// Creates a KeywordRecognizer from an <see cref="AudioConfig" />. The config is intended
    /// to define the audio input to be used by the recognizer object.
    /// </summary>
    /// <param name="audioConfig">Defines the audio input to be used by the recognizer.</param>
    /// <returns>A new KeywordRecognizer that will consume audio from the specified input.</returns>
    /// <remarks>
    /// If no audio config is provided, it will be equivalent to calling with a config constructed with
    /// <see cref="AudioConfig::FromDefaultMicrophoneInput" />
    /// </remarks>
    inline static std::shared_ptr<KeywordRecognizer> FromConfig(std::shared_ptr<Audio::AudioConfig> audioConfig = nullptr)
    {
           auto hreco = Utils::CallFactoryMethodLeft(
            ::recognizer_create_keyword_recognizer_from_audio_config,
            Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE>(audioConfig));
        return std::shared_ptr<KeywordRecognizer>(new KeywordRecognizer(hreco));
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~KeywordRecognizer()
    {
        Canceled.DisconnectAll();
        Recognized.DisconnectAll();
        recognizer_handle_release(m_handle);
    }

    /// <summary>
    /// Starts a keyword recognition session. This session will last until the first keyword is recognized. When this happens,
    /// a <see cref="Recognized" /> event will be raised and the session will end. To rearm the keyword, the method needs to be called
    /// again after the event is emitted.
    /// </summary>
    /// <param name="model">The <see cref="KeywordRecognitionModel" /> that describes the keyword we want to detect.</param>
    /// <returns>A future that resolves to a <see cref="KeywordRecognitionResult" /> that resolves once a keyword is detected.</returns>
    /// <remarks>
    /// Note that if no keyword is detected in the input, the task will never resolve (unless <see cref="StopRecognition" /> is called.
    /// </remarks>
    inline std::future<std::shared_ptr<KeywordRecognitionResult>> RecognizeOnceAsync(std::shared_ptr<KeywordRecognitionModel> model)
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, model, this]()
        {
            auto modelHandle = static_cast<SPXKEYWORDHANDLE>(*model);

            SPXRESULTHANDLE result = SPXHANDLE_INVALID;
            SPX_THROW_ON_FAIL(recognizer_recognize_keyword_once(m_handle, modelHandle, &result));

            return std::make_shared<KeywordRecognitionResult>(result);
        });
        return future;
    }

    /// <summary>
    /// Stops a currently active keyword recognition session.
    /// </summary>
    /// <returns>A future that resolves when the active session (if any) is stopped.</returns>
    inline std::future<void> StopRecognitionAsync()
    {
        auto keepAlive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keepAlive, this]()
        {
            SPX_THROW_ON_FAIL(recognizer_stop_keyword_recognition(m_handle));
        });
        return future;
    }

    /// <summary>
    /// Signal for events related to the recognition of keywords.
    /// </summary>
    EventSignal<const KeywordRecognitionEventArgs&> Recognized;

    /// <summary>
    /// Signal for events relating to the cancellation of an interaction. The event indicates if the reason is a direct cancellation or an error.
    /// </summary>
    EventSignal<const SpeechRecognitionCanceledEventArgs&> Canceled;

private:
    /*! \cond PROTECTED */

    static void FireEvent_Recognized(SPXRECOHANDLE, SPXEVENTHANDLE h_event, void* pv_context)
    {
        auto keep_alive = static_cast<KeywordRecognizer*>(pv_context)->shared_from_this();
        KeywordRecognitionEventArgs event{ h_event };
        keep_alive->Recognized.Signal(event);
    }

    static void FireEvent_Canceled(SPXRECOHANDLE, SPXEVENTHANDLE h_event, void* pv_context)
    {
        auto keep_alive = static_cast<KeywordRecognizer*>(pv_context)->shared_from_this();
        SpeechRecognitionCanceledEventArgs event{ h_event };
        keep_alive->Canceled.Signal(event);
    }

    void RecognizerEventConnectionChanged(const EventSignal<const KeywordRecognitionEventArgs&>& reco_event)
    {
        if (m_handle != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_handle=0x%8p", __FUNCTION__, (void*)m_handle);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_handle), "%s: m_handle is INVALID!!!", __FUNCTION__);

            if (&reco_event== &Recognized)
            {
                ::recognizer_recognized_set_callback(m_handle, Recognized.IsConnected() ? KeywordRecognizer::FireEvent_Recognized : nullptr, this);
            }
        }
    }

    void CanceledEventConnectionChanged(const EventSignal<const SpeechRecognitionCanceledEventArgs&>& canceled_event)
    {
        if (m_handle != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_handle=0x%8p", __FUNCTION__, (void*)m_handle);
            SPX_DBG_TRACE_VERBOSE_IF(!::recognizer_handle_is_valid(m_handle), "%s: m_handle is INVALID!!!", __FUNCTION__);

            if (&canceled_event == &Canceled)
            {
                ::recognizer_canceled_set_callback(m_handle, Canceled.IsConnected() ? KeywordRecognizer::FireEvent_Canceled : nullptr, this);
            }
        }
    }

    inline explicit KeywordRecognizer(SPXRECOHANDLE handle):
        Recognized{ Utils::Callback<KeywordRecognitionEventArgs>(this, &KeywordRecognizer::RecognizerEventConnectionChanged) },
        Canceled{ Utils::Callback<SpeechRecognitionCanceledEventArgs>(this, &KeywordRecognizer::CanceledEventConnectionChanged) },
        m_properties{ Utils::CallFactoryMethodRight(recognizer_get_property_bag, handle) },
        m_handle{ handle },
        Properties { m_properties }
    {
    }

    PropertyCollection m_properties;
    SPXRECOHANDLE m_handle;
    /*! \endcond */

public:
    /// <summary>
    /// A collection of properties and their values defined for this <see cref="KeywordRecognizer"/>.
    /// </summary>
    const PropertyCollection& Properties;
};


} } }
