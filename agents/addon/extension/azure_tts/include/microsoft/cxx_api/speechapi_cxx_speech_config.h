//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_config.h: Public API declarations for SpeechConfig C++ class
//
#pragma once

#include <string>

#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c_common.h>
#include <speechapi_c_speech_config.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

namespace Dialog { class DialogServiceConfig; }
class EmbeddedSpeechConfig;
class HybridSpeechConfig;

/// <summary>
/// Class that defines configurations for speech / intent recognition, or speech synthesis.
/// </summary>
class SpeechConfig
{
public:
    friend Dialog::DialogServiceConfig;
    friend EmbeddedSpeechConfig;
    friend HybridSpeechConfig;

    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXSPEECHCONFIGHANDLE() const { return m_hconfig; }

    /// <summary>
    /// Creates an instance of the speech config with specified subscription key and region.
    /// </summary>
    /// <param name="subscription">The subscription key.</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>A shared pointer to the new speech config instance.</returns>
    static std::shared_ptr<SpeechConfig> FromSubscription(const SPXSTRING& subscription, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_config_from_subscription(&hconfig, Utils::ToUTF8(subscription).c_str(), Utils::ToUTF8(region).c_str()));

        auto ptr = new SpeechConfig(hconfig);
        return std::shared_ptr<SpeechConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of the speech config with specified authorization token and region.
    /// Note: The caller needs to ensure that the authorization token is valid. Before the authorization token
    /// expires, the caller needs to refresh it by calling this setter with a new valid token.
    /// As configuration values are copied when creating a new recognizer, the new token value will not apply to recognizers that have already been created.
    /// For recognizers that have been created before, you need to set authorization token of the corresponding recognizer
    /// to refresh the token. Otherwise, the recognizers will encounter errors during recognition.
    /// </summary>
    /// <param name="authToken">The authorization token.</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>A shared pointer to the new speech config instance.</returns>
    static std::shared_ptr<SpeechConfig> FromAuthorizationToken(const SPXSTRING& authToken, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_config_from_authorization_token(&hconfig, Utils::ToUTF8(authToken).c_str(), Utils::ToUTF8(region).c_str()));

        auto ptr = new SpeechConfig(hconfig);
        return std::shared_ptr<SpeechConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of the speech config with specified endpoint and subscription.
    /// This method is intended only for users who use a non-standard service endpoint.
    /// Note: The query parameters specified in the endpoint URI are not changed, even if they are set by any other APIs.
    /// For example, if the recognition language is defined in URI as query parameter "language=de-DE", and also set by SetSpeechRecognitionLanguage("en-US"),
    /// the language setting in URI takes precedence, and the effective language is "de-DE".
    /// Only the parameters that are not specified in the endpoint URI can be set by other APIs.
    /// Note: To use an authorization token with FromEndpoint, use FromEndpoint(const SPXSTRING&),
    /// and then call SetAuthorizationToken() on the created SpeechConfig instance.
    /// </summary>
    /// <param name="endpoint">The service endpoint to connect to.</param>
    /// <param name="subscription">The subscription key.</param>
    /// <returns>A shared pointer to the new speech config instance.</returns>
    static std::shared_ptr<SpeechConfig> FromEndpoint(const SPXSTRING& endpoint, const SPXSTRING& subscription)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_config_from_endpoint(&hconfig, Utils::ToUTF8(endpoint).c_str(), Utils::ToUTF8(subscription).c_str()));

        auto ptr = new SpeechConfig(hconfig);
        return std::shared_ptr<SpeechConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of SpeechConfig with specified endpoint.
    /// This method is intended only for users who use a non-standard service endpoint.
    /// Note: The query parameters specified in the endpoint URI are not changed, even if they are set by any other APIs.
    /// Whether a specific query parameter is supported or not, depends on the endpoint and scenario.
    /// For example, if the recognition language is defined in URI as query parameter "language=de-DE", and also set by SetSpeechRecognitionLanguage("en-US"),
    /// the language setting in URI takes precedence, and the effective language is "de-DE".
    /// The example only applies when the endpoint and scenario combination supports language as a query parameter.
    /// Only the parameters that are not specified in the endpoint URI can be set by other APIs.
    /// Note: If the endpoint requires a subscription key for authentication, use FromEndpoint(const SPXSTRING&, const SPXSTRING&) to pass
    /// the subscription key as parameter.
    /// To use an authorization token with FromEndpoint, use this method to create a SpeechConfig instance, and then
    /// call SetAuthorizationToken() on the created SpeechConfig instance.
    /// Note: Added in version 1.5.0.
    /// </summary>
    /// <param name="endpoint">The service endpoint URI to connect to.</param>
    /// <returns>A shared pointer to the new speech config instance.</returns>
    static std::shared_ptr<SpeechConfig> FromEndpoint(const SPXSTRING& endpoint)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_config_from_endpoint(&hconfig, Utils::ToUTF8(endpoint).c_str(), nullptr));

        auto ptr = new SpeechConfig(hconfig);
        return std::shared_ptr<SpeechConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of the speech config with specified host and subscription.
    /// This method is intended only for users who use a non-default service host. Standard resource path will be assumed.
    /// For services with a non-standard resource path or no path at all, use FromEndpoint instead.
    /// Note: Query parameters are not allowed in the host URI and must be set by other APIs.
    /// Note: To use an authorization token with FromHost, use FromHost(const SPXSTRING&),
    /// and then call SetAuthorizationToken() on the created SpeechConfig instance.
    /// Note: Added in version 1.8.0.
    /// </summary>
    /// <param name="host">The service host to connect to. Format is "protocol://host:port" where ":port" is optional.</param>
    /// <param name="subscription">The subscription key.</param>
    /// <returns>A shared pointer to the new speech config instance.</returns>
    static std::shared_ptr<SpeechConfig> FromHost(const SPXSTRING& host, const SPXSTRING& subscription)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_config_from_host(&hconfig, Utils::ToUTF8(host).c_str(), Utils::ToUTF8(subscription).c_str()));

        auto ptr = new SpeechConfig(hconfig);
        return std::shared_ptr<SpeechConfig>(ptr);
    }

    /// <summary>
    /// Creates an instance of SpeechConfig with specified host.
    /// This method is intended only for users who use a non-default service host. Standard resource path will be assumed.
    /// For services with a non-standard resource path or no path at all, use FromEndpoint instead.
    /// Note: Query parameters are not allowed in the host URI and must be set by other APIs.
    /// Note: If the host requires a subscription key for authentication, use FromHost(const SPXSTRING&, const SPXSTRING&) to pass
    /// the subscription key as parameter.
    /// To use an authorization token with FromHost, use this method to create a SpeechConfig instance, and then
    /// call SetAuthorizationToken() on the created SpeechConfig instance.
    /// Note: Added in version 1.8.0.
    /// </summary>
    /// <param name="host">The service host URI to connect to. Format is "protocol://host:port" where ":port" is optional.</param>
    /// <returns>A shared pointer to the new speech config instance.</returns>
    static std::shared_ptr<SpeechConfig> FromHost(const SPXSTRING& host)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_config_from_host(&hconfig, Utils::ToUTF8(host).c_str(), nullptr));

        auto ptr = new SpeechConfig(hconfig);
        return std::shared_ptr<SpeechConfig>(ptr);
    }

    /// <summary>
    /// Set the input language to the speech recognizer.
    /// </summary>
    /// <param name="lang">Specifies the name of spoken language to be recognized in BCP-47 format.</param>
    void SetSpeechRecognitionLanguage(const SPXSTRING& lang)
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_RecoLanguage), nullptr, Utils::ToUTF8(lang).c_str());
    }

    /// <summary>
    /// Gets the input language to the speech recognition.
    /// The language is specified in BCP-47 format.
    /// </summary>
    /// <returns>The speech recognition language.</returns>
    SPXSTRING GetSpeechRecognitionLanguage() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_RecoLanguage);
    }

    /// <summary>
    /// Sets the language of the speech synthesizer.
    /// Added in version 1.4.0
    /// </summary>
    /// <param name="lang">Specifies the name of language (e.g. en-US)</param>
    void SetSpeechSynthesisLanguage(const SPXSTRING& lang)
    {
        SPX_THROW_ON_FAIL(property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_SynthLanguage), nullptr, Utils::ToUTF8(lang).c_str()));
    }

    /// <summary>
    /// Gets the language of the speech synthesizer.
    /// Added in version 1.4.0
    /// </summary>
    /// <returns>The speech synthesis language.</returns>
    SPXSTRING GetSpeechSynthesisLanguage() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_SynthLanguage);
    }

    /// <summary>
    /// Set the voice of the speech synthesizer.
    /// Added in version 1.4.0
    /// </summary>
    /// <param name="voiceName">Specifies the name of voice</param>
    void SetSpeechSynthesisVoiceName(const SPXSTRING& voiceName)
    {
        SPX_THROW_ON_FAIL(property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_SynthVoice), nullptr, Utils::ToUTF8(voiceName).c_str()));
    }

    /// <summary>
    /// Gets the voice of the speech synthesizer.
    /// Added in version 1.4.0
    /// </summary>
    /// <returns>The speech synthesis voice name.</returns>
    SPXSTRING GetSpeechSynthesisVoiceName() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_SynthVoice);
    }

    /// <summary>
    /// Sets the speech synthesis output format (e.g. Riff16Khz16BitMonoPcm).
    /// Added in version 1.4.0
    /// </summary>
    /// <param name="formatId">Specifies the output format ID</param>
    void SetSpeechSynthesisOutputFormat(SpeechSynthesisOutputFormat formatId)
    {
        SPX_THROW_ON_FAIL(speech_config_set_audio_output_format(m_hconfig, static_cast<Speech_Synthesis_Output_Format>(formatId)));
    }

    /// <summary>
    /// Gets the speech synthesis output format.
    /// Added in version 1.4.0
    /// </summary>
    /// <returns>The speech synthesis output format.</returns>
    SPXSTRING GetSpeechSynthesisOutputFormat() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_SynthOutputFormat);
    }

    /// <summary>
    /// Sets the endpoint ID of Custom Speech or Custom Voice.
    /// </summary>
    /// <param name="endpointId">Endpoint ID.</param>
    void SetEndpointId(const SPXSTRING& endpointId)
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_EndpointId), nullptr, Utils::ToUTF8(endpointId).c_str());
    }

    /// <summary>
    /// Gets the endpoint ID of Custom Speech or Custom Voice.
    /// </summary>
    /// <returns>Endpoint ID.</returns>
    SPXSTRING GetEndpointId() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_EndpointId);
    }

    /// <summary>
    /// Sets the authorization token to connect to the service.
    /// Note: The caller needs to ensure that the authorization token is valid. Before the authorization token
    /// expires, the caller needs to refresh it by calling this setter with a new valid token.
    /// As configuration values are copied when creating a new recognizer, the new token value will not apply to recognizers that have already been created.
    /// For recognizers that have been created before, you need to set authorization token of the corresponding recognizer
    /// to refresh the token. Otherwise, the recognizers will encounter errors during recognition.
    /// </summary>
    /// <param name="token">The authorization token.</param>
    void SetAuthorizationToken(const SPXSTRING& token)
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceAuthorization_Token), nullptr, Utils::ToUTF8(token).c_str());
    }

    /// <summary>
    /// Gets the authorization token to connect to the service.
    /// </summary>
    /// <returns>The authorization token.</returns>
    SPXSTRING GetAuthorizationToken() const
    {
        return GetProperty(PropertyId::SpeechServiceAuthorization_Token);
    }

    /// <summary>
    /// Gets the subscription key that is used to create Speech Recognizer or Intent Recognizer or Translation Recognizer or Speech Synthesizer.
    /// </summary>
    /// <returns>The subscription key.</returns>
    SPXSTRING GetSubscriptionKey() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_Key);
    }

    /// <summary>
    /// Gets the region key that used to create Speech Recognizer or Intent Recognizer or Translation Recognizer or speech Synthesizer.
    /// </summary>
    /// <returns>Region.</returns>
    SPXSTRING GetRegion() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_Region);
    }

    /// <summary>
    /// Gets speech recognition output format (simple or detailed).
    /// Note: This output format is for speech recognition result, use <see cref="SpeechConfig::GetSpeechSynthesisOutputFormat"/> to get synthesized audio output format.
    /// </summary>
    /// <returns>Speech recognition output format.</returns>
    OutputFormat GetOutputFormat() const
    {
        auto result = GetProperty(PropertyId::SpeechServiceResponse_RequestDetailedResultTrueFalse);
        return result == Utils::ToSPXString(TrueString) ? OutputFormat::Detailed : OutputFormat::Simple;
    }

    /// <summary>
    /// Sets speech recognition output format (simple or detailed).
    /// Note: This output format is for speech recognition result, use <see cref="SpeechConfig::SetSpeechSynthesisOutputFormat"/> to set synthesized audio output format.
    /// </summary>
    /// <param name="format">Speech recognition output format</param>
    void SetOutputFormat(OutputFormat format)
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceResponse_RequestDetailedResultTrueFalse), nullptr,
            format == OutputFormat::Detailed ? Utils::ToUTF8(TrueString) : Utils::ToUTF8(FalseString));
    }

    /// <summary>
    /// Sets profanity option.
    /// Added in version 1.5.0.
    /// </summary>
    /// <param name="profanity">Profanity option value.</param>
    void SetProfanity(ProfanityOption profanity)
    {
        SPX_THROW_ON_FAIL(speech_config_set_profanity(m_hconfig, (SpeechConfig_ProfanityOption)profanity));
    }

    /// <summary>
    /// Enables audio logging in service.
    /// Added in version 1.5.0.
    /// </summary>
    /// <remarks>
    /// Audio and content logs are stored either in Microsoft-owned storage, or in your own storage account linked
    /// to your Cognitive Services subscription (Bring Your Own Storage (BYOS) enabled Speech resource).
    /// </remarks>
    void EnableAudioLogging()
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_EnableAudioLogging), nullptr, TrueString);
    }

    /// <summary>
    /// Includes word-level timestamps in response result.
    /// Added in version 1.5.0.
    /// </summary>
    void RequestWordLevelTimestamps()
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceResponse_RequestWordLevelTimestamps), nullptr, TrueString);
    }

    /// <summary>
    /// Enables dictation mode. Only supported in speech continuous recognition.
    /// Added in version 1.5.0.
    /// </summary>
    void EnableDictation()
    {
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_RecoMode), nullptr, "DICTATION");
    }

    /// <summary>
    /// Sets proxy configuration
    /// Added in version 1.1.0
    ///
    /// Note: Proxy functionality is not available on macOS. This function will have no effect on this platform.
    /// </summary>
    /// <param name="proxyHostName">The host name of the proxy server, without the protocol scheme (`http://`)</param>
    /// <param name="proxyPort">The port number of the proxy server</param>
    /// <param name="proxyUserName">The user name of the proxy server</param>
    /// <param name="proxyPassword">The password of the proxy server</param>
    void SetProxy(const SPXSTRING& proxyHostName, uint32_t proxyPort, const SPXSTRING& proxyUserName = SPXSTRING(), const SPXSTRING& proxyPassword = SPXSTRING())
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, proxyHostName.empty());
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, proxyPort == 0);

        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_ProxyHostName), nullptr,
            Utils::ToUTF8(proxyHostName).c_str());
        property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_ProxyPort), nullptr,
            std::to_string(proxyPort).c_str());
        if (!proxyUserName.empty())
        {
            property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_ProxyUserName), nullptr,
                Utils::ToUTF8(proxyUserName).c_str());
        }
        if (!proxyPassword.empty())
        {
            property_bag_set_string(m_propertybag, static_cast<int>(PropertyId::SpeechServiceConnection_ProxyPassword), nullptr,
                Utils::ToUTF8(proxyPassword).c_str());
        }
    }

    /// <summary>
    /// Sets a property value by name.
    /// </summary>
    /// <param name="name">The property name.</param>
    /// <param name="value">The property value.</param>
    void SetProperty(const SPXSTRING& name, const SPXSTRING& value)
    {
        property_bag_set_string(m_propertybag, -1, Utils::ToUTF8(name).c_str(), Utils::ToUTF8(value).c_str());
    }

    /// <summary>
    /// Gets a property value by name.
    /// </summary>
    /// <param name="name">The parameter name.</param>
    /// <returns>The property value.</returns>
    SPXSTRING GetProperty(const SPXSTRING& name) const
    {
        const char* value = property_bag_get_string(m_propertybag, -1, Utils::ToUTF8(name).c_str(), "");
        return Utils::ToSPXString(Utils::CopyAndFreePropertyString(value));
    }

    /// <summary>
    /// Gets a property value by ID.
    /// </summary>
    /// <param name="id">The parameter id.</param>
    /// <returns>The property value.</returns>
    SPXSTRING GetProperty(PropertyId id) const
    {
        const char* value = property_bag_get_string(m_propertybag, static_cast<int>(id), nullptr, "");
        return Utils::ToSPXString(Utils::CopyAndFreePropertyString(value));
    }

    /// <summary>
    /// Sets a property value by ID.
    /// </summary>
    /// <param name="id">The property id.</param>
    /// <param name="value">The property value.</param>
    void SetProperty(PropertyId id, const SPXSTRING& value)
    {
        property_bag_set_string(m_propertybag, static_cast<int>(id), nullptr, Utils::ToUTF8(value).c_str());
    }

    /// <summary>
    /// Sets a property value that will be passed to service using the specified channel.
    /// Added in version 1.5.0.
    /// </summary>
    /// <param name="name">The property name.</param>
    /// <param name="value">The property value.</param>
    /// <param name="channel">The channel used to pass the specified property to service.</param>
    void SetServiceProperty(const SPXSTRING& name, const SPXSTRING& value, ServicePropertyChannel channel)
    {
        SPX_THROW_ON_FAIL(speech_config_set_service_property(m_hconfig, Utils::ToUTF8(name).c_str(), Utils::ToUTF8(value).c_str(), (SpeechConfig_ServicePropertyChannel)channel));
    }

    /// <summary>
    /// Destructs the object.
    /// </summary>
    virtual ~SpeechConfig()
    {
        speech_config_release(m_hconfig);
        property_bag_release(m_propertybag);
    }

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    explicit SpeechConfig(SPXSPEECHCONFIGHANDLE hconfig)
        :m_hconfig(hconfig)
        {
            SPX_THROW_ON_FAIL(speech_config_get_property_bag(hconfig, &m_propertybag));
        }

    /// <summary>
    /// Internal member variable that holds the speech config
    /// </summary>
    SPXSPEECHCONFIGHANDLE m_hconfig;

    /// <summary>
    /// Internal member variable that holds the properties of the speech config
    /// </summary>
    SPXPROPERTYBAGHANDLE m_propertybag;

    /*! \endcond */

private:
    DISABLE_COPY_AND_MOVE(SpeechConfig);

    };

}}}
