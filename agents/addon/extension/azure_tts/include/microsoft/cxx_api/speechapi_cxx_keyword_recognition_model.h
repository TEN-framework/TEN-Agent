//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_keyword_recognition_model.h: Public API declarations for KeywordRecognitionModel C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_utils.h>
#include <speechapi_c_keyword_recognition_model.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Represents keyword recognition model used with StartKeywordRecognitionAsync methods.
/// </summary>
class KeywordRecognitionModel
{
public:

    /// <summary>
    /// Creates a keyword recognition model using the specified file.
    /// </summary>
    /// <param name="fileName">The file name of the keyword recognition model.</param>
    /// <returns>A shared pointer to keyword recognition model.</returns>
    static std::shared_ptr<KeywordRecognitionModel> FromFile(const SPXSTRING& fileName)
    {
        SPXKEYWORDHANDLE hkeyword = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(keyword_recognition_model_create_from_file(Utils::ToUTF8(fileName).c_str(), &hkeyword));
        return std::make_shared<KeywordRecognitionModel>(hkeyword);
    }

    /// <summary>
    /// Creates a keyword recognition model using the specified embedded speech config.
    /// </summary>
    /// <param name="embeddedSpeechConfig">Embedded speech config.</param>
    /// <returns>A shared pointer to keyword recognition model.</returns>
    static std::shared_ptr<KeywordRecognitionModel> FromConfig(std::shared_ptr<EmbeddedSpeechConfig> embeddedSpeechConfig)
    {
        SPXKEYWORDHANDLE hkeyword = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(keyword_recognition_model_create_from_config(
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(embeddedSpeechConfig), &hkeyword));

        return std::make_shared<KeywordRecognitionModel>(hkeyword);
    }

    /// <summary>
    /// Creates a keyword recognition model using the specified embedded speech config
    /// and user-defined wake words.
    /// </summary>
    /// <param name="embeddedSpeechConfig">Embedded speech config.</param>
    /// <param name="userDefinedWakeWords">User-defined wake words.</param>
    /// <returns>A shared pointer to keyword recognition model.</returns>
    static std::shared_ptr<KeywordRecognitionModel> FromConfig(
        std::shared_ptr<EmbeddedSpeechConfig> embeddedSpeechConfig, const std::vector<SPXSTRING>& userDefinedWakeWords)
    {
        SPXKEYWORDHANDLE hkeyword = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(keyword_recognition_model_create_from_config(
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE, EmbeddedSpeechConfig>(embeddedSpeechConfig), &hkeyword));

        for (const SPXSTRING& wakeWord : userDefinedWakeWords)
        {
            SPX_THROW_HR_IF(SPXERR_INVALID_ARG, wakeWord.empty());
            SPX_THROW_ON_FAIL(keyword_recognition_model_add_user_defined_wake_word(
                static_cast<SPXKEYWORDHANDLE>(hkeyword), Utils::ToUTF8(wakeWord).c_str()));
        }

        return std::make_shared<KeywordRecognitionModel>(hkeyword);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hkeyword">Keyword handle.</param>
    explicit KeywordRecognitionModel(SPXKEYWORDHANDLE hkeyword = SPXHANDLE_INVALID) : m_hkwmodel(hkeyword) { }

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~KeywordRecognitionModel() { keyword_recognition_model_handle_release(m_hkwmodel); }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXKEYWORDHANDLE() { return m_hkwmodel; }

private:

    DISABLE_COPY_AND_MOVE(KeywordRecognitionModel);

    SPXKEYWORDHANDLE m_hkwmodel;
};


} } } // Microsoft::CognitiveServices::Speech
