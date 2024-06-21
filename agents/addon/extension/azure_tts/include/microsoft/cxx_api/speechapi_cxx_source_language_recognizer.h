//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_source_language_recognizer.h: Public API declarations for SourceLanguageRecognizer C++ class
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

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

class Session;

/// <summary>
/// Class for source language recognizers.
/// You can use this class for standalone language detection.
/// Added in version 1.17.0
/// </summary>
class SourceLanguageRecognizer final : public AsyncRecognizer<SpeechRecognitionResult, SpeechRecognitionEventArgs, SpeechRecognitionCanceledEventArgs>
{
public:

    using BaseType = AsyncRecognizer<SpeechRecognitionResult, SpeechRecognitionEventArgs, SpeechRecognitionCanceledEventArgs>;

    /// <summary>
    /// Create a source language recognizer from a speech config, auto detection source language config and audio config
    /// </summary>
    /// <param name="speechconfig">Speech configuration</param>
    /// <param name="autoDetectSourceLangConfig">Auto detection source language config</param>
    /// <param name="audioInput">Audio configuration</param>
    /// <returns>A smart pointer wrapped source language recognizer pointer.</returns>
    static std::shared_ptr<SourceLanguageRecognizer> FromConfig(
        std::shared_ptr<SpeechConfig> speechconfig,
        std::shared_ptr<AutoDetectSourceLanguageConfig> autoDetectSourceLangConfig,
        std::shared_ptr<Audio::AudioConfig> audioInput = nullptr)
    {
        SPXRECOHANDLE hreco;
        SPX_THROW_ON_FAIL(::recognizer_create_source_language_recognizer_from_auto_detect_source_lang_config(
            &hreco,
            HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            HandleOrInvalid<SPXAUTODETECTSOURCELANGCONFIGHANDLE, AutoDetectSourceLanguageConfig>(autoDetectSourceLangConfig),
            HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::make_shared<SourceLanguageRecognizer>(hreco);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hreco">Recognizer handle.</param>
    explicit SourceLanguageRecognizer(SPXRECOHANDLE hreco) : BaseType(hreco), Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~SourceLanguageRecognizer()
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
    /// A collection of properties and their values defined for this <see cref="SourceLanguageRecognizer"/>.
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
    DISABLE_DEFAULT_CTORS(SourceLanguageRecognizer);
    friend class Microsoft::CognitiveServices::Speech::Session;
};
} } } // Microsoft::CognitiveServices::Speech
