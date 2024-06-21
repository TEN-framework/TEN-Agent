//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>
#include <speechapi_cxx_speech_recognition_result.h>
#include <speechapi_cxx_conversation_transcription_result.h>
#include <speechapi_cxx_translation_result.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Contains auto detected source language result
/// Added in 1.8.0
/// </summary>
class AutoDetectSourceLanguageResult
{
public:

    /// <summary>
    /// Creates an instance of AutoDetectSourceLanguageResult object for the speech recognition result.
    /// </summary>
    /// <param name="result">The speech recognition result.</param>
    /// <returns>A shared pointer to AutoDetectSourceLanguageResult.</returns>
    static std::shared_ptr<AutoDetectSourceLanguageResult> FromResult(std::shared_ptr<SpeechRecognitionResult> result)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, result == nullptr);
        auto ptr = new AutoDetectSourceLanguageResult(result);
        return std::shared_ptr<AutoDetectSourceLanguageResult>(ptr);
    }

    /// <summary>
    /// Creates an instance of AutoDetectSourceLanguageResult object for the speech translation result.
    /// </summary>
    /// <param name="result">The speech translation result.</param>
    /// <returns>A shared pointer to AutoDetectSourceLanguageResult.</returns>
    static std::shared_ptr<AutoDetectSourceLanguageResult> FromResult(std::shared_ptr<Translation::TranslationRecognitionResult> result)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, result == nullptr);
        auto ptr = new AutoDetectSourceLanguageResult(result);
        return std::shared_ptr<AutoDetectSourceLanguageResult>(ptr);
    }

    /// <summary>
    /// Creates an instance of AutoDetectSourceLanguageResult object for the convesation transcription result.
    /// </summary>
    /// <param name="result">The conversation transcription result.</param>
    /// <returns>A shared pointer to AutoDetectSourceLanguageResult.</returns>
    static std::shared_ptr<AutoDetectSourceLanguageResult> FromResult(std::shared_ptr<Microsoft::CognitiveServices::Speech::Transcription::ConversationTranscriptionResult> result)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, result == nullptr);
        auto ptr = new AutoDetectSourceLanguageResult(result);
        return std::shared_ptr<AutoDetectSourceLanguageResult>(ptr);
    }

    /// <summary>
    /// The language value
    /// If this is empty, it means the system fails to detect the source language automatically
    /// </summary>
    const SPXSTRING Language;

protected:

    /*! \cond PROTECTED */
    // Using RecognitionResult pointer, so this can cover all classes that inherit from RecognitionResult
    AutoDetectSourceLanguageResult(std::shared_ptr<RecognitionResult> result) :
        Language(result->Properties.GetProperty(PropertyId::SpeechServiceConnection_AutoDetectSourceLanguageResult))
    {
    }

    /*! \endcond */

private:

    DISABLE_DEFAULT_CTORS(AutoDetectSourceLanguageResult);
};

} } } // Microsoft::CognitiveServices::Speech
