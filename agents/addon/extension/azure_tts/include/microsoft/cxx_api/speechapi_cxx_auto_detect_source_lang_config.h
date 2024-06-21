//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once

#include <string>
#include <sstream>

#include <speechapi_cxx_common.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_utils.h>
#include <speechapi_c_auto_detect_source_lang_config.h>
#include <speechapi_cxx_source_lang_config.h>
#include <stdarg.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Class that defines auto detection source configuration
/// Updated in 1.13.0
/// </summary>
class AutoDetectSourceLanguageConfig
{
public:
    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXAUTODETECTSOURCELANGCONFIGHANDLE() const { return m_hconfig; }

    /// <summary>
    /// Creates an instance of the AutoDetectSourceLanguageConfig with open range as source languages
    /// Note: only <see cref="SpeechSynthesizer"/>, embedded speech translation and multilingual <see cref="TranslationRecognizer"/> support source language auto detection from open range,
    /// for <see cref="Recognizer"/>, please use AutoDetectSourceLanguageConfig with specific source languages.
    /// Added in 1.13.0
    /// </summary>
    /// <returns>A shared pointer to the new AutoDetectSourceLanguageConfig instance.</returns>
    static std::shared_ptr<AutoDetectSourceLanguageConfig> FromOpenRange()
    {
        SPXAUTODETECTSOURCELANGCONFIGHANDLE hconfig = SPXHANDLE_INVALID;

        SPX_THROW_ON_FAIL(create_auto_detect_source_lang_config_from_open_range(&hconfig));
        auto ptr = new AutoDetectSourceLanguageConfig(hconfig);
        return std::shared_ptr<AutoDetectSourceLanguageConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of the AutoDetectSourceLanguageConfig with source languages
    /// </summary>
    /// <param name="languages">The list of source languages.</param>
    /// <returns>A shared pointer to the new AutoDetectSourceLanguageConfig instance.</returns>
    static std::shared_ptr<AutoDetectSourceLanguageConfig> FromLanguages(const std::vector<SPXSTRING>& languages)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, languages.empty());
        SPXAUTODETECTSOURCELANGCONFIGHANDLE hconfig = SPXHANDLE_INVALID;

        std::string languagesStr;
        bool isFirst = true;
        for (const SPXSTRING& language : languages)
        {
            SPX_THROW_HR_IF(SPXERR_INVALID_ARG, language.empty());
            if (!isFirst)
            {
                languagesStr += ",";
            }
            isFirst = false;
            languagesStr += Utils::ToUTF8(language);
        }
        SPX_THROW_ON_FAIL(create_auto_detect_source_lang_config_from_languages(&hconfig, languagesStr.c_str()));
        auto ptr = new AutoDetectSourceLanguageConfig(hconfig);
        return std::shared_ptr<AutoDetectSourceLanguageConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of the AutoDetectSourceLanguageConfig with a list of source language config
    /// </summary>
    /// <param name="configList">The list of source languages config</param>
    /// <returns>A shared pointer to the new AutoDetectSourceLanguageConfig instance.</returns>
    static std::shared_ptr<AutoDetectSourceLanguageConfig> FromSourceLanguageConfigs(std::vector<std::shared_ptr<Microsoft::CognitiveServices::Speech::SourceLanguageConfig>> configList)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, configList.empty());
        SPXAUTODETECTSOURCELANGCONFIGHANDLE hconfig = SPXHANDLE_INVALID;

        bool isFirst = true;
        for (const auto& config : configList)
        {
           SPX_THROW_HR_IF(SPXERR_INVALID_ARG, config == nullptr);
           if (isFirst)
           {
               SPX_THROW_ON_FAIL(create_auto_detect_source_lang_config_from_source_lang_config(&hconfig, Utils::HandleOrInvalid<SPXSOURCELANGCONFIGHANDLE, SourceLanguageConfig>(config)));
               isFirst = false;
           }
           else
           {
               SPX_THROW_ON_FAIL(add_source_lang_config_to_auto_detect_source_lang_config(hconfig, Utils::HandleOrInvalid<SPXSOURCELANGCONFIGHANDLE, SourceLanguageConfig>(config)));
           }
        }
        auto ptr = new AutoDetectSourceLanguageConfig(hconfig);
        return std::shared_ptr<AutoDetectSourceLanguageConfig>(ptr);
    }

    /// <summary>
    /// Destructs the object.
    /// </summary>
    virtual ~AutoDetectSourceLanguageConfig()
    {
        auto_detect_source_lang_config_release(m_hconfig);
        property_bag_release(m_propertybag);
    }

private:

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    explicit AutoDetectSourceLanguageConfig(SPXAUTODETECTSOURCELANGCONFIGHANDLE hconfig)
        :m_hconfig(hconfig)
        {
            SPX_THROW_ON_FAIL(auto_detect_source_lang_config_get_property_bag(hconfig, &m_propertybag));
        }

    /// <summary>
    /// Internal member variable that holds the config
    /// </summary>
    SPXAUTODETECTSOURCELANGCONFIGHANDLE m_hconfig;

    /// <summary>
    /// Internal member variable that holds the properties of the speech config
    /// </summary>
    SPXPROPERTYBAGHANDLE m_propertybag;

    DISABLE_COPY_AND_MOVE(AutoDetectSourceLanguageConfig);
};

}}}

