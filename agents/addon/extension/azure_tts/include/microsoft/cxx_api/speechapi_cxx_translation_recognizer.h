//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_translation_recognizer.h: Public API declarations for translation recognizer in C++.
//

#pragma once
#include <exception>
#include <future>
#include <memory>
#include <string>
#include <map>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>
#include <speechapi_cxx_recognition_async_recognizer.h>
#include <speechapi_cxx_translation_result.h>
#include <speechapi_cxx_translation_eventargs.h>
#include <speechapi_cxx_speech_translation_config.h>
#include <speechapi_cxx_auto_detect_source_lang_config.h>
#include <speechapi_cxx_audio_stream.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Translation {

/// <summary>
/// Performs translation on the speech input.
/// </summary>
class TranslationRecognizer final : public AsyncRecognizer<TranslationRecognitionResult, TranslationRecognitionEventArgs, TranslationRecognitionCanceledEventArgs>
{
public:
    /// <summary>
    /// Create a translation recognizer from a speech config
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(std::shared_ptr<SpeechTranslationConfig> speechconfig, std::nullptr_t)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechTranslationConfig>(speechconfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(nullptr)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    /// <summary>
    /// Create a translation recognizer from an embedded speech config
    /// </summary>
    /// <param name="speechConfig">Embedded speech configuration.</param>
    /// <returns>A smart pointer wrapped translation recognizer pointer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(std::shared_ptr<EmbeddedSpeechConfig> speechConfig, std::nullptr_t)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(nullptr)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    /// <summary>
    /// Create a translation recognizer from a hybrid speech config
    /// </summary>
    /// <param name="speechConfig">Hybrid speech configuration.</param>
    /// <returns>A smart pointer wrapped translation recognizer pointer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(std::shared_ptr<HybridSpeechConfig> speechConfig, std::nullptr_t)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, HybridSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(nullptr)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    /// <summary>
    /// Create a translation recognizer from a translation config and an audio config.
    /// Users should use this function to create a translation recognizer.
    /// </summary>
    /// <param name="speechconfig">Speech translation config.</param>
    /// <param name="audioInput">Audio config.</param>
    /// <returns>The shared smart pointer of the created translation recognizer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(std::shared_ptr<SpeechTranslationConfig> speechconfig, std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco { SPXHANDLE_INVALID };
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechTranslationConfig>(speechconfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    /// <summary>
    /// Create a translation recognizer from an embedded speech config and audio config.
    /// </summary>
    /// <param name="speechConfig">Embedded speech config.</param>
    /// <param name="audioConfig">Audio config.</param>
    /// <returns>A smart pointer wrapped translation recognizer pointer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(std::shared_ptr<EmbeddedSpeechConfig> speechConfig, std::shared_ptr<Audio::AudioConfig> audioConfig = nullptr)
    {
        SPXRECOHANDLE hreco{ SPXHANDLE_INVALID };
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioConfig)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    /// <summary>
    /// Create a translation recognizer from a hybrid speech config and audio config.
    /// </summary>
    /// <param name="speechConfig">Hybrid speech config.</param>
    /// <param name="audioConfig">Audio config.</param>
    /// <returns>A smart pointer wrapped translation recognizer pointer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(std::shared_ptr<HybridSpeechConfig> speechConfig, std::shared_ptr<Audio::AudioConfig> audioConfig = nullptr)
    {
        SPXRECOHANDLE hreco{ SPXHANDLE_INVALID };
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, HybridSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioConfig)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    /// <summary>
    /// Create a translation recognizer from a translation config, auto detection source language config and an audio config.
    /// Users should use this function to create a translation recognizer.
    /// </summary>
    /// <param name="speechconfig">Speech translation config.</param>
    /// <param name="autoDetectSourceLangConfig">Auto detection source language config.</param>
    /// <param name="audioInput">Audio config.</param>
    /// <returns>The shared smart pointer of the created translation recognizer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(
            std::shared_ptr<SpeechTranslationConfig> speechconfig,
            std::shared_ptr<AutoDetectSourceLanguageConfig> autoDetectSourceLangConfig,
            std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco { SPXHANDLE_INVALID };
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_auto_detect_source_lang_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechTranslationConfig>(speechconfig),
            HandleOrInvalid<SPXAUTODETECTSOURCELANGCONFIGHANDLE, AutoDetectSourceLanguageConfig>(autoDetectSourceLangConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    /// <summary>
    /// Create a translation recognizer from an embedded speech config, auto detection source language config and audio config.
    /// </summary>
    /// <param name="speechConfig">Embedded speech config.</param>
    /// <param name="autoDetectSourceLangConfig">Auto detection source language config.</param>
    /// <param name="audioInput">Audio config.</param>
    /// <returns>The shared smart pointer of the created translation recognizer.</returns>
    static std::shared_ptr<TranslationRecognizer> FromConfig(
        std::shared_ptr<EmbeddedSpeechConfig> speechConfig,
        std::shared_ptr<AutoDetectSourceLanguageConfig> autoDetectSourceLangConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco{ SPXHANDLE_INVALID };
        SPX_THROW_ON_FAIL(::recognizer_create_translation_recognizer_from_auto_detect_source_lang_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUTODETECTSOURCELANGCONFIGHANDLE, AutoDetectSourceLanguageConfig>(autoDetectSourceLangConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<TranslationRecognizer>(hreco);
    }

    // The AsyncRecognizer only deals with events for translation text result. The audio output event
    // is managed by OnTranslationSynthesisResult.
    using BaseType = AsyncRecognizer<TranslationRecognitionResult, TranslationRecognitionEventArgs, TranslationRecognitionCanceledEventArgs>;

    /// <summary>
    /// It is intended for internal use only. It creates an instance of <see cref="TranslationRecognizer"/>.
    /// </summary>
    /// <remarks>
    /// It is recommended to use SpeechTranslationConfig to create an instance of <see cref="TranslationRecognizer"/>. This method is mainly
    /// used in case where a recognizer handle has been created by methods via C-API.
    /// </remarks>
    /// <param name="hreco">The handle of the recognizer that is returned by C-API.</param>
    explicit TranslationRecognizer(SPXRECOHANDLE hreco) :
        BaseType(hreco),
        Properties(m_properties),
        Synthesizing(GetTranslationAudioEventConnectionsChangedCallback())
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// Deconstruct the instance.
    /// </summary>
    ~TranslationRecognizer()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        Synthesizing.DisconnectAll();
        TermRecognizer();
    }

    /// <summary>
    /// Starts translation recognition, and returns after a single utterance is recognized. The end of a
    /// single utterance is determined by listening for silence at the end or until a maximum of 15
    /// seconds of audio is processed.  The task returns the recognized text as well as the translation.
    /// Note: Since RecognizeOnceAsync() returns only a single utterance, it is suitable only for single
    /// shot recognition like command or query.
    /// For long-running multi-utterance recognition, use StartContinuousRecognitionAsync() instead.
    /// </summary>
    /// <returns>An asynchronous operation representing the recognition. It returns a value of <see cref="TranslationRecognitionResult"/> as result.</returns>
    std::future<std::shared_ptr<TranslationRecognitionResult>> RecognizeOnceAsync() override
    {
        return BaseType::RecognizeOnceAsyncInternal();
    }

    /// <summary>
    /// Starts translation on a continous audio stream, until StopContinuousRecognitionAsync() is called.
    /// User must subscribe to events to receive recognition results.
    /// </summary>
    /// <returns>An asynchronous operation that starts the translation.</returns>
    std::future<void> StartContinuousRecognitionAsync() override
    {
        return BaseType::StartContinuousRecognitionAsyncInternal();
    }

    /// <summary>
    /// Stops continuous translation.
    /// </summary>
    /// <returns>A task representing the asynchronous operation that stops the translation.</returns>
    std::future<void> StopContinuousRecognitionAsync() override { return BaseType::StopContinuousRecognitionAsyncInternal(); }

    /// <summary>
    /// Starts keyword recognition on a continuous audio stream, until StopKeywordRecognitionAsync() is called.
    /// </summary>
    /// <param name="model">Specifies the keyword model to be used.</param>
    /// <returns>An asynchronous operation that starts the keyword recognition.</returns>
    std::future<void> StartKeywordRecognitionAsync(std::shared_ptr<KeywordRecognitionModel> model) override
    {
        return BaseType::StartKeywordRecognitionAsyncInternal(model);
    };

    /// <summary>
    /// Stops continuous keyword recognition.
    /// </summary>
    /// <returns>A task representing the asynchronous operation that stops the keyword recognition.</returns>
    std::future<void> StopKeywordRecognitionAsync() override
    {
        return BaseType::StopKeywordRecognitionAsyncInternal();
    };

    /// <summary>
    /// Sets the authorization token that will be used for connecting to the service.
    /// Note: The caller needs to ensure that the authorization token is valid. Before the authorization token
    /// expires, the caller needs to refresh it by calling this setter with a new valid token.
    /// Otherwise, the recognizer will encounter errors during recognition.
    /// </summary>
    /// <param name="token">A string that represents the endpoint id.</param>
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
    /// Adds a target language for translation.
    /// Added in version 1.7.0.
    /// </summary>
    /// <param name="language">Translation target language to add.</param>
    void AddTargetLanguage(const SPXSTRING& language)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_hreco == SPXHANDLE_INVALID);
        SPX_THROW_ON_FAIL(::translator_add_target_language(m_hreco, Utils::ToUTF8(language).c_str()));
    }

    /// <summary>
    /// Removes a target language for translation.
    /// Added in version 1.7.0.
    /// </summary>
    /// <param name="language">Translation target language to remove.</param>
    void RemoveTargetLanguage(const SPXSTRING& language)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_hreco == SPXHANDLE_INVALID);
        SPX_THROW_ON_FAIL(::translator_remove_target_language(m_hreco, Utils::ToUTF8(language).c_str()));
    }

    /// <summary>
    /// Gets target languages for translation.
    /// Added in version 1.7.0.
    /// </summary>
    /// <returns>Vector of translation target languages.</returns>
    std::vector<SPXSTRING> GetTargetLanguages() const
    {
        std::vector<SPXSTRING> result;
        auto targetLanguages = Utils::ToUTF8(Properties.GetProperty(PropertyId::SpeechServiceConnection_TranslationToLanguages));
        if (targetLanguages.empty())
            return result;

        // Getting languages one by one.
        std::stringstream languageStream(targetLanguages);
        std::string token;
        while (std::getline(languageStream, token, CommaDelim))
        {
            result.push_back(Utils::ToSPXString(token));
        }
        return result;
    }

    /// <summary>
    /// The collection of properties and their values defined for this <see cref="TranslationRecognizer"/>.
    /// </summary>
    PropertyCollection& Properties;

    /// <summary>
    /// The event signals that a translation synthesis result is received.
    /// </summary>
    EventSignal<const TranslationSynthesisEventArgs&> Synthesizing;

private:

    DISABLE_DEFAULT_CTORS(TranslationRecognizer);

    friend class Microsoft::CognitiveServices::Speech::Session;

    std::function<void(const EventSignal<const TranslationSynthesisEventArgs&>&)> GetTranslationAudioEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const TranslationSynthesisEventArgs&>& audioEvent) {
            if (&audioEvent == &Synthesizing)
            {
                translator_synthesizing_audio_set_callback(m_hreco, Synthesizing.IsConnected() ? FireEvent_TranslationSynthesisResult : nullptr, this);
            }
        };
    }

    static void FireEvent_TranslationSynthesisResult(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext)
    {
        UNUSED(hreco);
        std::unique_ptr<TranslationSynthesisEventArgs> recoEvent{ new TranslationSynthesisEventArgs(hevent) };

        auto pThis = static_cast<TranslationRecognizer*>(pvContext);
        auto keepAlive = pThis->shared_from_this();
        pThis->Synthesizing.Signal(*recoEvent.get());
    }
};
} } } } // Microsoft::CognitiveServices::Speech::Translation
