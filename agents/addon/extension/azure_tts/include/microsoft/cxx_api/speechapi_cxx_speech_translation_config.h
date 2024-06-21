//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once

#include <string>
#include <sstream>

#include "speechapi_c_common.h"
#include "speechapi_c_speech_config.h"
#include "speechapi_c_speech_translation_config.h"
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_string_helpers.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Translation {

/// <summary>
/// Class that defines configurations for translation with speech input.
/// </summary>
class SpeechTranslationConfig final : public SpeechConfig
{
public:
    /// <summary>
    /// Creates an instance of the speech translation config with specified subscription key and region.
    /// </summary>
    /// <param name="subscription">The subscription key.</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>Shared pointer to the speech translation config instance.</returns>
    static std::shared_ptr<SpeechTranslationConfig> FromSubscription(const SPXSTRING& subscription, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_translation_config_from_subscription(&hconfig, Utils::ToUTF8(subscription).c_str(), Utils::ToUTF8(region).c_str()));
        return std::shared_ptr<SpeechTranslationConfig>(new SpeechTranslationConfig(hconfig));
    }

    /// <summary>
    /// Creates an instance of the speech translation config with specified authorization token and region.
    /// </summary>
    /// <param name="authToken">The authorization token.</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>Shared pointer to the speech translation config instance.</returns>
    static std::shared_ptr<SpeechTranslationConfig> FromAuthorizationToken(const SPXSTRING& authToken, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_translation_config_from_authorization_token(&hconfig, Utils::ToUTF8(authToken).c_str(), Utils::ToUTF8(region).c_str()));
        return std::shared_ptr<SpeechTranslationConfig>(new SpeechTranslationConfig(hconfig));
    }

    // <summary>
    /// Creates an instance of the speech translation config with specified endpoint and subscription.
    /// This method is intended only for users who use a non-standard service endpoint.
    /// Note: The query parameters specified in the endpoint URI are not changed, even if they are set by any other APIs.
    /// For example, if the recognition language is defined in URI as query parameter "language=de-DE", and also set by SetSpeechRecognitionLanguage("en-US"),
    /// the language setting in URI takes precedence, and the effective language is "de-DE".
    /// Only the parameters that are not specified in the endpoint URI can be set by other APIs.
    /// Note: To use an authorization token with FromEndpoint, please use FromEndpoint(const SPXSTRING&),
    /// and then call SetAuthorizationToken() on the created SpeechTranslationConfig instance.
    /// </summary>
    /// <param name="endpoint">The service endpoint to connect to.</param>
    /// <param name="subscription">The subscription key.</param>
    /// <returns>Shared pointer to the new SpeechTranslationConfig instance.</returns>
    static std::shared_ptr<SpeechTranslationConfig> FromEndpoint(const SPXSTRING& endpoint, const SPXSTRING& subscription)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_translation_config_from_endpoint(&hconfig, Utils::ToUTF8(endpoint).c_str(), Utils::ToUTF8(subscription).c_str()));
        return std::shared_ptr<SpeechTranslationConfig>(new SpeechTranslationConfig(hconfig));
    }

    /// <summary>
    /// Creates an instance of the speech translation config with specified endpoint.
    /// This method is intended only for users who use a non-standard service endpoint.
    /// Note: The query parameters specified in the endpoint URI are not changed, even if they are set by any other APIs.
    /// For example, if the recognition language is defined in URI as query parameter "language=de-DE", and also set by SetSpeechRecognitionLanguage("en-US"),
    /// the language setting in URI takes precedence, and the effective language is "de-DE".
    /// Only the parameters that are not specified in the endpoint URI can be set by other APIs.
    /// Note: if the endpoint requires a subscription key for authentication, please use FromEndpoint(const SPXSTRING&, const SPXSTRING&) to pass
    /// the subscription key as parameter.
    /// To use an authorization token with FromEndpoint, use this method to create a SpeechTranslationConfig instance, and then
    /// call SetAuthorizationToken() on the created SpeechTranslationConfig instance.
    /// Note: Added in version 1.5.0.
    /// </summary>
    /// <param name="endpoint">The service endpoint to connect to.</param>
    /// <returns>A shared pointer to the new SpeechTranslationConfig instance.</returns>
    static std::shared_ptr<SpeechTranslationConfig> FromEndpoint(const SPXSTRING& endpoint)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_translation_config_from_endpoint(&hconfig, Utils::ToUTF8(endpoint).c_str(), nullptr));
        return std::shared_ptr<SpeechTranslationConfig>(new SpeechTranslationConfig(hconfig));
    }

    /// <summary>
    /// Creates an instance of the speech translation config with specified host and subscription.
    /// This method is intended only for users who use a non-default service host. Standard resource path will be assumed.
    /// For services with a non-standard resource path or no path at all, use FromEndpoint instead.
    /// Note: Query parameters are not allowed in the host URI and must be set by other APIs.
    /// Note: To use an authorization token with FromHost, use FromHost(const SPXSTRING&),
    /// and then call SetAuthorizationToken() on the created SpeechTranslationConfig instance.
    /// Note: Added in version 1.8.0.
    /// </summary>
    /// <param name="host">The service host to connect to. Format is "protocol://host:port" where ":port" is optional.</param>
    /// <param name="subscription">The subscription key.</param>
    /// <returns>Shared pointer to the new SpeechTranslationConfig instance.</returns>
    static std::shared_ptr<SpeechTranslationConfig> FromHost(const SPXSTRING& host, const SPXSTRING& subscription)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_translation_config_from_host(&hconfig, Utils::ToUTF8(host).c_str(), Utils::ToUTF8(subscription).c_str()));
        return std::shared_ptr<SpeechTranslationConfig>(new SpeechTranslationConfig(hconfig));
    }

    /// <summary>
    /// Creates an instance of the speech translation config with specified host.
    /// This method is intended only for users who use a non-default service host. Standard resource path will be assumed.
    /// For services with a non-standard resource path or no path at all, use FromEndpoint instead.
    /// Note: Query parameters are not allowed in the host URI and must be set by other APIs.
    /// Note: If the host requires a subscription key for authentication, use FromHost(const SPXSTRING&, const SPXSTRING&) to pass
    /// the subscription key as parameter.
    /// To use an authorization token with FromHost, use this method to create a SpeechTranslationConfig instance, and then
    /// call SetAuthorizationToken() on the created SpeechTranslationConfig instance.
    /// Note: Added in version 1.8.0.
    /// </summary>
    /// <param name="host">The service host to connect to. Format is "protocol://host:port" where ":port" is optional.</param>
    /// <returns>A shared pointer to the new SpeechTranslationConfig instance.</returns>
    static std::shared_ptr<SpeechTranslationConfig> FromHost(const SPXSTRING& host)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_translation_config_from_host(&hconfig, Utils::ToUTF8(host).c_str(), nullptr));
        return std::shared_ptr<SpeechTranslationConfig>(new SpeechTranslationConfig(hconfig));
    }

    /// <summary>
    /// Adds a target language for translation.
    /// </summary>
    /// <param name="language">Translation target language to add.</param>
    void AddTargetLanguage(const SPXSTRING& language)
    {
        SPX_THROW_ON_FAIL(speech_translation_config_add_target_language(m_hconfig, Utils::ToUTF8(language).c_str()));
    }

    /// <summary>
    /// Removes a target language for translation.
    /// Added in release 1.7.0.
    /// </summary>
    /// <param name="language">Translation target language to remove.</param>
    void RemoveTargetLanguage(const SPXSTRING& language)
    {
        SPX_THROW_ON_FAIL(speech_translation_config_remove_target_language(m_hconfig, Utils::ToUTF8(language).c_str()));
    }

    /// <summary>
    /// Gets target languages for translation.
    /// </summary>
    /// <returns>Vector of translation target languages.</returns>
    std::vector<SPXSTRING> GetTargetLanguages() const
    {
        std::vector<SPXSTRING> result;
        auto targetLanguages = Utils::ToUTF8(GetProperty(PropertyId::SpeechServiceConnection_TranslationToLanguages));
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
    /// Sets output voice name.
    /// </summary>
    /// <param name="voice">Voice name to set.</param>
    void SetVoiceName(const SPXSTRING& voice)
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_TranslationVoice), nullptr, Utils::ToUTF8(voice).c_str());
    }

    /// <summary>
    /// Gets output voice name.
    /// </summary>
    /// <returns>Output voice name.</returns>
    SPXSTRING GetVoiceName() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_TranslationVoice);
    }

private:
    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    explicit SpeechTranslationConfig(SPXSPEECHCONFIGHANDLE hconfig) : SpeechConfig(hconfig) { }

    DISABLE_COPY_AND_MOVE(SpeechTranslationConfig);

};

}}}}
