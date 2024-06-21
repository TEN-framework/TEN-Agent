//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once

#include <string>
#include <sstream>
#include <set>

#include "speechapi_cxx_properties.h"
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c_source_lang_config.h>
#include "speechapi_c_common.h"

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Class that defines source language configuration, added in 1.8.0
/// </summary>
class SourceLanguageConfig
{
public:
    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXSOURCELANGCONFIGHANDLE() const { return m_hconfig; }

    /// <summary>
    /// Creates an instance of the SourceLanguageConfig with source language
    /// </summary>
    /// <param name="language">The source language</param>
    /// <returns>A shared pointer to the new SourceLanguageConfig instance.</returns>
    static std::shared_ptr<SourceLanguageConfig> FromLanguage(const SPXSTRING& language)
    {
        SPXSOURCELANGCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(source_lang_config_from_language(&hconfig, language.c_str()));
        auto ptr = new SourceLanguageConfig(hconfig);
        return std::shared_ptr<SourceLanguageConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of the SourceLanguageConfig with source language and custom endpoint id. A custom endpoint id corresponds to custom models. 
    /// </summary>
    /// <param name="language">The source language</param>
    /// <param name="endpointId">The custom endpoint id</param>
    /// <returns>A shared pointer to the new SourceLanguageConfig instance.</returns>
    static std::shared_ptr<SourceLanguageConfig> FromLanguage(const SPXSTRING& language, const SPXSTRING& endpointId)
    {
        SPXSOURCELANGCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(source_lang_config_from_language_and_endpointId(&hconfig, language.c_str(), endpointId.c_str()));
        auto ptr = new SourceLanguageConfig(hconfig);
        return std::shared_ptr<SourceLanguageConfig>(ptr);
    }

    /// <summary>
    /// Destructs the object.
    /// </summary>
    virtual ~SourceLanguageConfig()
    {
        source_lang_config_release(m_hconfig);
        property_bag_release(m_propertybag);
    }

private:
    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    explicit SourceLanguageConfig(SPXSOURCELANGCONFIGHANDLE hconfig)
        :m_hconfig(hconfig)
        {
            SPX_THROW_ON_FAIL(source_lang_config_get_property_bag(hconfig, &m_propertybag));
        }

    /// <summary>
    /// Internal member variable that holds the config
    /// </summary>
    SPXSOURCELANGCONFIGHANDLE m_hconfig;

    /// <summary>
    /// Internal member variable that holds the properties of the config
    /// </summary>
    SPXPROPERTYBAGHANDLE m_propertybag;

    DISABLE_COPY_AND_MOVE(SourceLanguageConfig);
};
}}}
