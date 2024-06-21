//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_translation_result.h: Public API declarations for TranslationResult C++ class
//

#pragma once
#include <string>
#include <vector>
#include <map>
#include <new>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_enums.h>
#include <speechapi_c.h>
#include <speechapi_cxx_speech_recognition_result.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Translation {

/// <summary>
/// Defines the translation text result.
/// </summary>
class TranslationRecognitionResult : public RecognitionResult
{
private:

    std::map<SPXSTRING, SPXSTRING> m_translations;

public:
    /// <summary>
    /// It is intended for internal use only. It creates an instance of <see cref="TranslationRecognitionResult"/>.
    /// </summary>
    /// <param name="resultHandle">The handle of the result returned by recognizer in C-API.</param>
    explicit TranslationRecognitionResult(SPXRESULTHANDLE resultHandle) :
        RecognitionResult(resultHandle),
        Translations(m_translations)
    {
        PopulateResultFields(resultHandle);
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p) -- resultid=%s.", __FUNCTION__, (void*)this, (void*)Handle, ResultId.c_str());
    };

    /// <summary>
    /// Destructs the instance.
    /// </summary>
    virtual ~TranslationRecognitionResult()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)Handle);
    }

    /// <summary>
    /// Presents the translation results. Each item in the map is a key value pair, where key is the language tag of the translated text,
    /// and value is the translation text in that language.
    /// </summary>
    const std::map<SPXSTRING, SPXSTRING>& Translations;

private:
    void PopulateResultFields(SPXRESULTHANDLE resultHandle)
    {
        SPX_INIT_HR(hr);

        size_t count = 0;
        hr = translation_text_result_get_translation_count(resultHandle, &count);
        SPX_THROW_ON_FAIL(hr);

        size_t maxLanguageSize = 0;
        size_t maxTextSize = 0;

        for (size_t i = 0; i < count; i++)
        {
            size_t languageSize = 0;
            size_t textSize = 0;

            hr = translation_text_result_get_translation(resultHandle, i, nullptr, nullptr, &languageSize, &textSize);
            SPX_THROW_ON_FAIL(hr);

            maxLanguageSize = (std::max)(maxLanguageSize, languageSize);
            maxTextSize = (std::max)(maxTextSize, textSize);
        }

        auto targetLanguage = std::make_unique<char[]>(maxLanguageSize);
        auto translationText = std::make_unique<char[]>(maxTextSize);
        for (size_t i = 0; i < count; i++)
        {
            hr = translation_text_result_get_translation(resultHandle, i, targetLanguage.get(), translationText.get(), &maxLanguageSize, &maxTextSize);
            SPX_THROW_ON_FAIL(hr);
            m_translations[Utils::ToSPXString(targetLanguage.get())] = Utils::ToSPXString(translationText.get());
        }

        SPX_DBG_TRACE_VERBOSE("Translation phrases: numberentries: %d", (int)m_translations.size());
#ifdef _DEBUG
        for (const auto& cf : m_translations)
        {
            (void)(cf); // prevent warning for cf when compiling release builds
            SPX_DBG_TRACE_VERBOSE(" phrase for %s: %s", cf.first.c_str(), cf.second.c_str());
        }
#endif
    };

    DISABLE_DEFAULT_CTORS(TranslationRecognitionResult);
};


/// <summary>
/// Defines the translation synthesis result, i.e. the voice output of the translated text in the target language.
/// </summary>
class TranslationSynthesisResult
{
private:

    ResultReason m_reason;
    std::vector<uint8_t> m_audioData;

public:
    /// <summary>
    /// It is intended for internal use only. It creates an instance of <see cref="TranslationSynthesisResult"/>
    /// </summary>
    /// <param name="resultHandle">The handle of the result returned by recognizer in C-API.</param>
    explicit TranslationSynthesisResult(SPXRESULTHANDLE resultHandle) :
        Reason(m_reason),
        Audio(m_audioData)
    {
        PopulateResultFields(resultHandle);
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p) reason=0x%x", __FUNCTION__, (void*)this, (void*)resultHandle, Reason);
    };

    /// <summary>
    /// Destructs the instance.
    /// </summary>
    virtual ~TranslationSynthesisResult()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p)", __FUNCTION__, (void*)this);
    };

    /// <summary>
    /// Recognition reason.
    /// </summary>
    const ResultReason& Reason;

    /// <summary>
    /// The voice output of the translated text in the target language.
    /// </summary>
    const std::vector<uint8_t>& Audio;


private:

    DISABLE_DEFAULT_CTORS(TranslationSynthesisResult);

    void PopulateResultFields(SPXRESULTHANDLE resultHandle)
    {
        SPX_INIT_HR(hr);

        Result_Reason resultReason = ResultReason_NoMatch;
        SPX_THROW_ON_FAIL(hr = result_get_reason(resultHandle, &resultReason));
        m_reason = (ResultReason)resultReason;

        size_t bufLen = 0;
        hr = translation_synthesis_result_get_audio_data(resultHandle, nullptr, &bufLen);
        if (hr == SPXERR_BUFFER_TOO_SMALL)
        {
            m_audioData.resize(bufLen);
            hr = translation_synthesis_result_get_audio_data(resultHandle, m_audioData.data(), &bufLen);
        }
        SPX_THROW_ON_FAIL(hr);

        SPX_DBG_TRACE_VERBOSE("Translation synthesis: audio length: %zu, vector size: %zu", bufLen, m_audioData.size());
    };
};


} } } } // Microsoft::CognitiveServices::Speech::Translation
