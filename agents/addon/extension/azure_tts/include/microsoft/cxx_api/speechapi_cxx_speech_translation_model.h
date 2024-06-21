//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_translation_model.h: Public API declarations for SpeechTranslationModel C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_c_speech_translation_model.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Speech translation model information.
/// </summary>
class SpeechTranslationModel
{
private:

    /// <summary>
    /// Internal member variable that holds the model handle.
    /// </summary>
    SPXSPEECHRECOMODELHANDLE m_hmodel;

public:

    /// <summary>
    /// Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hmodel">Model handle.</param>
    explicit SpeechTranslationModel(SPXSPEECHRECOMODELHANDLE hmodel) :
        m_hmodel(hmodel),
        Name(m_name),
        SourceLanguages(m_sourceLanguages),
        TargetLanguages(m_targetLanguages),
        Path(m_path),
        Version(m_version)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        m_name = Utils::ToSPXString(Utils::CopyAndFreePropertyString(speech_translation_model_get_name(m_hmodel)));
        m_sourceLanguages = Utils::Split(Utils::CopyAndFreePropertyString(speech_translation_model_get_source_languages(m_hmodel)), '|');
        m_targetLanguages = Utils::Split(Utils::CopyAndFreePropertyString(speech_translation_model_get_target_languages(m_hmodel)), '|');
        m_path = Utils::ToSPXString(Utils::CopyAndFreePropertyString(speech_translation_model_get_path(m_hmodel)));
        m_version = Utils::ToSPXString(Utils::CopyAndFreePropertyString(speech_translation_model_get_version(m_hmodel)));
    }

    /// <summary>
    /// Explicit conversion operator.
    /// </summary>
    /// <returns>Model handle.</returns>
    explicit operator SPXSPEECHRECOMODELHANDLE() { return m_hmodel; }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~SpeechTranslationModel()
    {
        speech_translation_model_handle_release(m_hmodel);
    }

    /// <summary>
    /// Model name.
    /// </summary>
    const SPXSTRING& Name;

    /// <summary>
    /// Source languages that the model supports.
    /// </summary>
    const std::vector<SPXSTRING>& SourceLanguages;

    /// <summary>
    /// Target languages that the model supports.
    /// </summary>
    const std::vector<SPXSTRING>& TargetLanguages;

    /// <summary>
    /// Model path (only valid for offline models).
    /// </summary>
    const SPXSTRING& Path;

    /// <summary>
    /// Model version.
    /// </summary>
    const SPXSTRING& Version;

private:

    DISABLE_DEFAULT_CTORS(SpeechTranslationModel);

    /// <summary>
    /// Internal member variable that holds the model name.
    /// </summary>
    SPXSTRING m_name;

    /// <summary>
    /// Internal member variable that holds the model source languages.
    /// </summary>
    std::vector<SPXSTRING> m_sourceLanguages;

    /// <summary>
    /// Internal member variable that holds the model target languages.
    /// </summary>
    std::vector<SPXSTRING> m_targetLanguages;

    /// <summary>
    /// Internal member variable that holds the model path.
    /// </summary>
    SPXSTRING m_path;

    /// <summary>
    /// Internal member variable that holds the model version.
    /// </summary>
    SPXSTRING m_version;
};

} } } // Microsoft::CognitiveServices::Speech
