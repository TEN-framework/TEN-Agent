//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_embedded_speech_config.h: Public API declarations for EmbeddedSpeechConfig C++ class
//

#pragma once

#include <string>

#include <speechapi_c_common.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_speech_recognition_model.h>
#include <speechapi_cxx_speech_translation_model.h>
#include <speechapi_c_embedded_speech_config.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Class that defines embedded (offline) speech configuration.
/// </summary>
class EmbeddedSpeechConfig
{
protected:
    /*! \cond PROTECTED */

    SpeechConfig m_config;

    /*! \endcond */

public:
    /// <summary>
    /// Internal operator used to get the underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXSPEECHCONFIGHANDLE() const
    {
        return static_cast<SPXSPEECHCONFIGHANDLE>(m_config);
    }

    /// <summary>
    /// Creates an instance of the embedded speech config with a specified offline model path.
    /// </summary>
    /// <param name="path">The folder path to search for offline models.
    /// This can be a root path under which several models are located in subfolders,
    /// or a direct path to a specific model folder.
    /// </param>
    /// <returns>A shared pointer to the new embedded speech config instance.</returns>
    static std::shared_ptr<EmbeddedSpeechConfig> FromPath(const SPXSTRING& path)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, path.empty());
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;

        SPX_THROW_ON_FAIL(embedded_speech_config_create(&hconfig));
        SPX_THROW_ON_FAIL(embedded_speech_config_add_path(hconfig, Utils::ToUTF8(path).c_str()));

        auto ptr = new EmbeddedSpeechConfig(hconfig);
        return std::shared_ptr<EmbeddedSpeechConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of the embedded speech config with specified offline model paths.
    /// </summary>
    /// <param name="paths">The folder paths to search for offline models.
    /// These can be root paths under which several models are located in subfolders,
    /// or direct paths to specific model folders.
    /// </param>
    /// <returns>A shared pointer to the new embedded speech config instance.</returns>
    static std::shared_ptr<EmbeddedSpeechConfig> FromPaths(const std::vector<SPXSTRING>& paths)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, paths.empty());
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;

        SPX_THROW_ON_FAIL(embedded_speech_config_create(&hconfig));
        for (const SPXSTRING& path : paths)
        {
            SPX_THROW_HR_IF(SPXERR_INVALID_ARG, path.empty());
            SPX_THROW_ON_FAIL(embedded_speech_config_add_path(hconfig, Utils::ToUTF8(path).c_str()));
        }

        auto ptr = new EmbeddedSpeechConfig(hconfig);
        return std::shared_ptr<EmbeddedSpeechConfig>(ptr);
    }

    /// <summary>
    /// Gets a list of available speech recognition models.
    /// </summary>
    /// <returns>Speech recognition model info.</returns>
    std::vector<std::shared_ptr<SpeechRecognitionModel>> GetSpeechRecognitionModels()
    {
        std::vector<std::shared_ptr<SpeechRecognitionModel>> models;

        uint32_t numModels = 0;
        SPX_THROW_ON_FAIL(embedded_speech_config_get_num_speech_reco_models(static_cast<SPXSPEECHCONFIGHANDLE>(m_config), &numModels));

        for (uint32_t i = 0; i < numModels; i++)
        {
            SPXSPEECHRECOMODELHANDLE hmodel = SPXHANDLE_INVALID;
            SPX_THROW_ON_FAIL(embedded_speech_config_get_speech_reco_model(static_cast<SPXSPEECHCONFIGHANDLE>(m_config), i, &hmodel));

            auto model = std::make_shared<SpeechRecognitionModel>(hmodel);
            models.push_back(model);
        }

        return models;
    }

    /// <summary>
    /// Sets the model for speech recognition.
    /// </summary>
    /// <param name="name">The model name.</param>
    /// <param name="key">The model decryption key.</param>
    void SetSpeechRecognitionModel(const SPXSTRING& name, const SPXSTRING& key)
    {
        SetProperty(PropertyId::SpeechServiceConnection_RecoModelName, name);
        SetProperty(PropertyId::SpeechServiceConnection_RecoModelKey, key);
    }

    /// <summary>
    /// Gets the model name for speech recognition.
    /// </summary>
    /// <returns>The speech recognition model name.</returns>
    SPXSTRING GetSpeechRecognitionModelName() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_RecoModelName);
    }

    /// <summary>
    /// Sets the speech recognition output format.
    /// </summary>
    /// <param name="format">Speech recognition output format (simple or detailed).</param>
    void SetSpeechRecognitionOutputFormat(OutputFormat format)
    {
        m_config.SetOutputFormat(format);
    }

    /// <summary>
    /// Gets the speech recognition output format.
    /// </summary>
    /// <returns>Speech recognition output format (simple or detailed).</returns>
    OutputFormat GetSpeechRecognitionOutputFormat() const
    {
        return m_config.GetOutputFormat();
    }

    /// <summary>
    /// Sets the profanity option. This can be used to remove profane words or mask them.
    /// </summary>
    /// <param name="profanity">Profanity option value.</param>
    void SetProfanity(ProfanityOption profanity)
    {
        m_config.SetProfanity(profanity);
    }

    /// <summary>
    /// Sets the voice for embedded speech synthesis.
    /// </summary>
    /// <param name="name">The voice name of the embedded speech synthesis.</param>
    /// <param name="key">The decryption key.</param>
    void SetSpeechSynthesisVoice(const SPXSTRING& name, const SPXSTRING& key)
    {
        SetProperty(PropertyId::SpeechServiceConnection_SynthOfflineVoice, name);
        SetProperty(PropertyId::SpeechServiceConnection_SynthModelKey, key);
    }

    /// <summary>
    /// Gets the voice name for embedded speech synthesis.
    /// </summary>
    /// <returns>The speech synthesis model name, i.e. the voice name.</returns>
    SPXSTRING GetSpeechSynthesisVoiceName() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_SynthOfflineVoice);
    }

    /// <summary>
    /// Sets the speech synthesis output format (e.g. Riff16Khz16BitMonoPcm).
    /// </summary>
    /// <param name="formatId">Specifies the output format ID</param>
    void SetSpeechSynthesisOutputFormat(SpeechSynthesisOutputFormat formatId)
    {
        m_config.SetSpeechSynthesisOutputFormat(formatId);
    }

    /// <summary>
    /// Gets the speech synthesis output format.
    /// </summary>
    /// <returns>The speech synthesis output format.</returns>
    SPXSTRING GetSpeechSynthesisOutputFormat() const
    {
        return m_config.GetSpeechSynthesisOutputFormat();
    }

    /// <summary>
    /// Gets a list of available speech translation models.
    /// </summary>
    /// <returns>Speech translation model info.</returns>
    std::vector<std::shared_ptr<SpeechTranslationModel>> GetSpeechTranslationModels()
    {
        std::vector<std::shared_ptr<SpeechTranslationModel>> models;

        uint32_t numModels = 0;
        SPX_THROW_ON_FAIL(embedded_speech_config_get_num_speech_translation_models(static_cast<SPXSPEECHCONFIGHANDLE>(m_config), &numModels));

        for (uint32_t i = 0; i < numModels; i++)
        {
            SPXSPEECHRECOMODELHANDLE hmodel = SPXHANDLE_INVALID;
            SPX_THROW_ON_FAIL(embedded_speech_config_get_speech_translation_model(static_cast<SPXSPEECHCONFIGHANDLE>(m_config), i, &hmodel));

            auto model = std::make_shared<SpeechTranslationModel>(hmodel);
            models.push_back(model);
        }

        return models;
    }

    /// <summary>
    /// Sets the model for speech translation.
    /// </summary>
    /// <param name="name">Model name.</param>
    /// <param name="key">Model decryption key.</param>
    void SetSpeechTranslationModel(const SPXSTRING& name, const SPXSTRING& key)
    {
        SetProperty(PropertyId::SpeechTranslation_ModelName, name);
        SetProperty(PropertyId::SpeechTranslation_ModelKey, key);
    }

    /// <summary>
    /// Gets the model name for speech translation.
    /// </summary>
    /// <returns>The speech translation model name.</returns>
    SPXSTRING GetSpeechTranslationModelName() const
    {
        return GetProperty(PropertyId::SpeechTranslation_ModelName);
    }

    /// <summary>
    /// Sets the model for keyword recognition.
    /// This is for customer specific models that are tailored for detecting
    /// wake words and direct commands.
    /// </summary>
    /// <param name="name">Model name.</param>
    /// <param name="key">Model decryption key.</param>
    void SetKeywordRecognitionModel(const SPXSTRING& name, const SPXSTRING& key)
    {
        SetProperty(PropertyId::KeywordRecognition_ModelName, name);
        SetProperty(PropertyId::KeywordRecognition_ModelKey, key);
    }

    /// <summary>
    /// Gets the model name for keyword recognition.
    /// </summary>
    /// <returns>The keyword recognition model name.</returns>
    SPXSTRING GetKeywordRecognitionModelName() const
    {
        return GetProperty(PropertyId::KeywordRecognition_ModelName);
    }

    /// <summary>
    /// Sets a property value by name.
    /// </summary>
    /// <param name="name">The property name.</param>
    /// <param name="value">The property value.</param>
    void SetProperty(const SPXSTRING& name, const SPXSTRING& value)
    {
        m_config.SetProperty(name, value);
    }

    /// <summary>
    /// Sets a property value by ID.
    /// </summary>
    /// <param name="id">The property id.</param>
    /// <param name="value">The property value.</param>
    void SetProperty(PropertyId id, const SPXSTRING& value)
    {
        m_config.SetProperty(id, value);
    }

    /// <summary>
    /// Gets a property value by name.
    /// </summary>
    /// <param name="name">The parameter name.</param>
    /// <returns>The property value.</returns>
    SPXSTRING GetProperty(const SPXSTRING& name) const
    {
        return m_config.GetProperty(name);
    }

    /// <summary>
    /// Gets a property value by ID.
    /// </summary>
    /// <param name="id">The parameter id.</param>
    /// <returns>The property value.</returns>
    SPXSTRING GetProperty(PropertyId id) const
    {
        return m_config.GetProperty(id);
    }

    /// <summary>
    /// Destructs the object.
    /// </summary>
    virtual ~EmbeddedSpeechConfig() = default;

protected:
    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    inline explicit EmbeddedSpeechConfig(SPXSPEECHCONFIGHANDLE hconfig) : m_config(hconfig)
    {
    }

    /*! \endcond */

private:
    DISABLE_COPY_AND_MOVE(EmbeddedSpeechConfig);

    };

}}}
