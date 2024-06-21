//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_recognizer.h: Public API declarations for SpeechRecognizer C++ class
//

#pragma once
#include <exception>
#include <future>
#include <memory>
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>
#include <speechapi_cxx_recognition_async_recognizer.h>
#include <speechapi_cxx_speech_recognition_eventargs.h>
#include <speechapi_cxx_speech_recognition_result.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_speech_config.h>
#include <speechapi_cxx_audio_stream.h>
#include <speechapi_cxx_auto_detect_source_lang_config.h>
#include <speechapi_cxx_source_lang_config.h>
#include <speechapi_cxx_audio_config.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

class Session;

/// <summary>
/// Class for speech recognizers.
/// </summary>
class SpeechRecognizer final : public AsyncRecognizer<SpeechRecognitionResult, SpeechRecognitionEventArgs, SpeechRecognitionCanceledEventArgs>
{
public:

    using BaseType = AsyncRecognizer<SpeechRecognitionResult, SpeechRecognitionEventArgs, SpeechRecognitionCanceledEventArgs>;

    /// <summary>
    /// Create a speech recognizer from a speech config
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(std::shared_ptr<SpeechConfig> speechconfig, std::nullptr_t)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(nullptr)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from an embedded speech config.
    /// Added in version 1.19.0
    /// </summary>
    /// <param name="speechConfig">Embedded speech configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(std::shared_ptr<EmbeddedSpeechConfig> speechConfig, std::nullptr_t)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(nullptr)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from a hybrid speech config.
    /// </summary>
    /// <param name="speechConfig">Hybrid speech configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(std::shared_ptr<HybridSpeechConfig> speechConfig, std::nullptr_t)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, HybridSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(nullptr)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from a speech config and audio config.
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(std::shared_ptr<SpeechConfig> speechconfig, std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE,SpeechConfig>(speechconfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from an embedded speech config and audio config.
    /// Added in version 1.19.0
    /// </summary>
    /// <param name="speechConfig">Embedded speech configuration.</param>
    /// <param name="audioConfig">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(std::shared_ptr<EmbeddedSpeechConfig> speechConfig, std::shared_ptr<Audio::AudioConfig> audioConfig = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioConfig)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from a hybrid speech config and audio config.
    /// </summary>
    /// <param name="speechConfig">Hybrid speech configuration.</param>
    /// <param name="audioConfig">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(std::shared_ptr<HybridSpeechConfig> speechConfig, std::shared_ptr<Audio::AudioConfig> audioConfig = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, HybridSpeechConfig>(speechConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioConfig)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from a speech config, auto detection source language config and audio config
    /// Added in 1.8.0
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="autoDetectSourceLangConfig">Auto detection source language config.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(
        std::shared_ptr<SpeechConfig> speechconfig,
        std::shared_ptr<AutoDetectSourceLanguageConfig> autoDetectSourceLangConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_auto_detect_source_lang_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            HandleOrInvalid<SPXAUTODETECTSOURCELANGCONFIGHANDLE, AutoDetectSourceLanguageConfig>(autoDetectSourceLangConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from an embedded speech config, auto detection source language config and audio config
    /// Added in 1.20.0
    /// </summary>
    /// <param name="speechconfig">Embedded speech configuration.</param>
    /// <param name="autoDetectSourceLangConfig">Auto detection source language config.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(
        std::shared_ptr<EmbeddedSpeechConfig> speechconfig,
        std::shared_ptr<AutoDetectSourceLanguageConfig> autoDetectSourceLangConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_auto_detect_source_lang_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(speechconfig),
            HandleOrInvalid<SPXAUTODETECTSOURCELANGCONFIGHANDLE, AutoDetectSourceLanguageConfig>(autoDetectSourceLangConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from a hybrid speech config, auto detection source language config and audio config
    /// </summary>
    /// <param name="speechconfig">Hybrid speech configuration.</param>
    /// <param name="autoDetectSourceLangConfig">Auto detection source language config.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(
        std::shared_ptr<HybridSpeechConfig> speechconfig,
        std::shared_ptr<AutoDetectSourceLanguageConfig> autoDetectSourceLangConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_auto_detect_source_lang_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, HybridSpeechConfig>(speechconfig),
            HandleOrInvalid<SPXAUTODETECTSOURCELANGCONFIGHANDLE, AutoDetectSourceLanguageConfig>(autoDetectSourceLangConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from a speech config, source language config and audio config
    /// Added in 1.8.0
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="sourceLanguageConfig">Source language config.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(
        std::shared_ptr<SpeechConfig> speechconfig,
        std::shared_ptr<SourceLanguageConfig> sourceLanguageConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_speech_recognizer_from_source_lang_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            HandleOrInvalid<SPXSOURCELANGCONFIGHANDLE, SourceLanguageConfig>(sourceLanguageConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<SpeechRecognizer>(hreco);
    }

    /// <summary>
    /// Create a speech recognizer from a speech config, source language and audio config
    /// Added in 1.8.0
    /// </summary>
    /// <param name="speechconfig">Speech configuration.</param>
    /// <param name="sourceLanguage">Source language.</param>
    /// <param name="audioInput">Audio configuration.</param>
    /// <returns>A smart pointer wrapped speech recognizer pointer.</returns>
    static std::shared_ptr<SpeechRecognizer> FromConfig(
        std::shared_ptr<SpeechConfig> speechconfig,
        const SPXSTRING& sourceLanguage,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        return FromConfig(speechconfig, SourceLanguageConfig::FromLanguage(sourceLanguage), audioInput);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hreco">Recognizer handle.</param>
    explicit SpeechRecognizer(SPXRECOHANDLE hreco) : BaseType(hreco), Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~SpeechRecognizer()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        TermRecognizer();
    }

    /// <summary>
    /// Starts speech recognition, and returns after a single utterance is recognized. The end of a
    /// single utterance is determined by listening for silence at the end or until a maximum of 15
    /// seconds of audio is processed.  The task returns the recognition text as result.
    /// Note: Since RecognizeOnceAsync() returns only a single utterance, it is suitable only for single
    /// shot recognition like command or query.
    /// For long-running multi-utterance recognition, use StartContinuousRecognitionAsync() instead.
    /// </summary>
    /// <returns>Future containing result value (a shared pointer to SpeechRecognitionResult)
    /// of the asynchronous speech recognition.
    /// </returns>
    std::future<std::shared_ptr<SpeechRecognitionResult>> RecognizeOnceAsync() override
    {
        return BaseType::RecognizeOnceAsyncInternal();
    }

    /// <summary>
    /// Asynchronously initiates continuous speech recognition operation.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> StartContinuousRecognitionAsync() override
    {
        return BaseType::StartContinuousRecognitionAsyncInternal();
    }

    /// <summary>
    /// Asynchronously terminates ongoing continuous speech recognition operation.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> StopContinuousRecognitionAsync() override
    {
        return BaseType::StopContinuousRecognitionAsyncInternal();
    }

    /// <summary>
    /// Asynchronously initiates keyword recognition operation.
    /// </summary>
    /// <param name="model">Specifies the keyword model to be used.</param>
    /// <returns>An empty future.</returns>
    std::future<void> StartKeywordRecognitionAsync(std::shared_ptr<KeywordRecognitionModel> model) override
    {
        return BaseType::StartKeywordRecognitionAsyncInternal(model);
    }

    /// <summary>
    /// Asynchronously terminates keyword recognition operation.
    /// </summary>
    /// <returns>An empty future.</returns>
    std::future<void> StopKeywordRecognitionAsync() override
    {
        return BaseType::StopKeywordRecognitionAsyncInternal();
    }

    /// <summary>
    /// A collection of properties and their values defined for this <see cref="SpeechRecognizer"/>.
    /// </summary>
    PropertyCollection& Properties;

    /// <summary>
    /// Gets the endpoint ID of a customized speech model that is used for speech recognition.
    /// </summary>
    /// <returns>the endpoint ID of a customized speech model that is used for speech recognition</returns>
    SPXSTRING GetEndpointId()
    {
        return Properties.GetProperty(PropertyId::SpeechServiceConnection_EndpointId, SPXSTRING());
    }

    /// <summary>
    /// Sets the authorization token that will be used for connecting to the service.
    /// Note: The caller needs to ensure that the authorization token is valid. Before the authorization token
    /// expires, the caller needs to refresh it by calling this setter with a new valid token.
    /// Otherwise, the recognizer will encounter errors during recognition.
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

private:
    DISABLE_DEFAULT_CTORS(SpeechRecognizer);
    friend class Microsoft::CognitiveServices::Speech::Session;
};


} } } // Microsoft::CognitiveServices::Speech
