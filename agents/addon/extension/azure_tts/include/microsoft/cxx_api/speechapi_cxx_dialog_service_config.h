//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
#pragma once

#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_speech_config.h>
#include <speechapi_cxx_enums.h>
#include <speechapi_c_property_bag.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Dialog {

/// <summary>
/// Class that defines base configurations for the dialog service connector object.
/// </summary>
class DialogServiceConfig
{
protected:
    /*! \cond PROTECTED */
    inline explicit DialogServiceConfig(SPXSPEECHCONFIGHANDLE h_config) : m_config{ h_config }
    {
    }
    SpeechConfig m_config;
    /*! \endcond */

public:
    /// <summary>
    /// Default destructor.
    /// </summary>
    virtual ~DialogServiceConfig() = default;

    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXSPEECHCONFIGHANDLE() const { return static_cast<SPXSPEECHCONFIGHANDLE>(m_config); }

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
    /// Sets a property value that will be passed to service using the specified channel.
    /// </summary>
    /// <param name="name">The property name.</param>
    /// <param name="value">The property value.</param>
    /// <param name="channel">The channel used to pass the specified property to service.</param>
    void SetServiceProperty(const SPXSTRING& name, const SPXSTRING& value, ServicePropertyChannel channel)
    {
        m_config.SetServiceProperty(name, value, channel);
    }


    /// <summary>
    /// Sets proxy configuration
    ///
    /// Note: Proxy functionality is not available on macOS. This function will have no effect on this platform.
    /// </summary>
    /// <param name="proxyHostName">The host name of the proxy server, without the protocol scheme (`http://`)</param>
    /// <param name="proxyPort">The port number of the proxy server</param>
    /// <param name="proxyUserName">The user name of the proxy server</param>
    /// <param name="proxyPassword">The password of the proxy server</param>
    void SetProxy(const SPXSTRING& proxyHostName, uint32_t proxyPort, const SPXSTRING& proxyUserName = SPXSTRING(), const SPXSTRING& proxyPassword = SPXSTRING())
    {
        m_config.SetProxy(proxyHostName, proxyPort, proxyUserName, proxyPassword);
    }

    /// <summary>
    /// Set the input language to the connector.
    /// </summary>
    /// <param name="lang">Specifies the name of spoken language to be recognized in BCP-47 format.</param>
    void SetLanguage(const SPXSTRING& lang)
    {
        SetProperty(PropertyId::SpeechServiceConnection_RecoLanguage, lang);
    }

    /// <summary>
    /// Gets the input language to the connector.
    /// The language is specified in BCP-47 format.
    /// </summary>
    /// <returns>The connetor language.</returns>
    SPXSTRING GetLanguage() const
    {
        return GetProperty(PropertyId::SpeechServiceConnection_RecoLanguage);
    }

};

/// <summary>
/// Class that defines configurations for the dialog service connector object for using a Bot Framework backend.
/// </summary>
class BotFrameworkConfig final : public DialogServiceConfig
{
public:
    /// <summary>
    /// Creates a bot framework service config instance with the specified subscription key and region.
    /// </summary>
    /// <param name="subscription">Subscription key associated with the bot</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>A shared pointer to the new bot framework config.</returns>
    inline static std::shared_ptr<BotFrameworkConfig> FromSubscription(const SPXSTRING& subscription, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE h_config = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(bot_framework_config_from_subscription(&h_config, Utils::ToUTF8(subscription).c_str(), Utils::ToUTF8(region).c_str(), nullptr));
        return std::shared_ptr<BotFrameworkConfig>{ new BotFrameworkConfig(h_config) };
    }

    /// <summary>
    /// Creates a bot framework service config instance with the specified subscription key and region.
    /// </summary>
    /// <param name="subscription">Subscription key associated with the bot</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <param name="bot_Id"> Identifier used to select a bot associated with this subscription.</param>
    /// <returns>A shared pointer to the new bot framework config.</returns>
    inline static std::shared_ptr<BotFrameworkConfig> FromSubscription(const SPXSTRING& subscription, const SPXSTRING& region, const SPXSTRING& bot_Id)
    {
        SPXSPEECHCONFIGHANDLE h_config = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(bot_framework_config_from_subscription(&h_config, Utils::ToUTF8(subscription).c_str(), Utils::ToUTF8(region).c_str(), Utils::ToUTF8(bot_Id).c_str()));
        return std::shared_ptr<BotFrameworkConfig>{ new BotFrameworkConfig(h_config) };
    }

    /// <summary>
    /// Creates a bot framework service config instance with the specified authorization token and region.
    /// Note: The caller needs to ensure that the authorization token is valid. Before the authorization token
    /// expires, the caller needs to refresh it by calling this setter with a new valid token.
    /// As configuration values are copied when creating a new connector, the new token value will not apply to connectors that have already been created.
    /// For connectors that have been created before, you need to set authorization token of the corresponding connector
    /// to refresh the token. Otherwise, the connectors will encounter errors during operation.
    /// </summary>
    /// <param name="authToken">The authorization token.</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>A shared pointer to the new bot framework config.</returns>
    inline static std::shared_ptr<BotFrameworkConfig> FromAuthorizationToken(const SPXSTRING& authToken, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE h_config = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(bot_framework_config_from_authorization_token(&h_config, Utils::ToUTF8(authToken).c_str(), Utils::ToUTF8(region).c_str(), nullptr));
        return std::shared_ptr<BotFrameworkConfig>{ new BotFrameworkConfig(h_config) };
    }

    /// <summary>
    /// Creates a bot framework service config instance with the specified authorization token and region.
    /// Note: The caller needs to ensure that the authorization token is valid. Before the authorization token
    /// expires, the caller needs to refresh it by calling this setter with a new valid token.
    /// As configuration values are copied when creating a new connector, the new token value will not apply to connectors that have already been created.
    /// For connectors that have been created before, you need to set authorization token of the corresponding connector
    /// to refresh the token. Otherwise, the connectors will encounter errors during operation.
    /// </summary>
    /// <param name="authToken">The authorization token.</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <param name="bot_Id"> Identifier used to select a bot associated with this subscription.</param>
    /// <returns>A shared pointer to the new bot framework config.</returns>
    inline static std::shared_ptr<BotFrameworkConfig> FromAuthorizationToken(const SPXSTRING& authToken, const SPXSTRING& region, const SPXSTRING& bot_Id)
    {
        SPXSPEECHCONFIGHANDLE h_config = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(bot_framework_config_from_authorization_token(&h_config, Utils::ToUTF8(authToken).c_str(), Utils::ToUTF8(region).c_str(), Utils::ToUTF8(bot_Id).c_str()));
        return std::shared_ptr<BotFrameworkConfig>{ new BotFrameworkConfig(h_config) };
    }
private:
    inline explicit BotFrameworkConfig(SPXSPEECHCONFIGHANDLE h_config): DialogServiceConfig{ h_config }
    {
    }
};

/// <summary>
/// Class that defines configurations for the dialog service connector object for using a CustomCommands backend.
/// </summary>
class CustomCommandsConfig: public DialogServiceConfig
{
public:
    /// <summary>
    /// Creates a Custom Commands config instance with the specified application id, subscription key and region.
    /// </summary>
    /// <param name="appId">Custom Commands application id.</param>
    /// <param name="subscription">Subscription key associated with the bot</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>A shared pointer to the new bot framework config.</returns>
    inline static std::shared_ptr<CustomCommandsConfig> FromSubscription(const SPXSTRING& appId, const SPXSTRING& subscription, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE h_config = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(custom_commands_config_from_subscription(&h_config, Utils::ToUTF8(appId).c_str(), Utils::ToUTF8(subscription).c_str(), Utils::ToUTF8(region).c_str()));
        return std::shared_ptr<CustomCommandsConfig>{ new CustomCommandsConfig(h_config) };
    }

    /// <summary>
    /// Creates a Custom Commands config instance with the specified application id authorization token and region.
    /// Note: The caller needs to ensure that the authorization token is valid. Before the authorization token
    /// expires, the caller needs to refresh it by calling this setter with a new valid token.
    /// As configuration values are copied when creating a new connector, the new token value will not apply to connectors that have already been created.
    /// For connectors that have been created before, you need to set authorization token of the corresponding connector
    /// to refresh the token. Otherwise, the connectors will encounter errors during operation.
    /// </summary>
    /// <param name="appId">Custom Commands application id.</param>
    /// <param name="authToken">The authorization token.</param>
    /// <param name="region">The region name (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>A shared pointer to the new bot framework config.</returns>
    inline static std::shared_ptr<CustomCommandsConfig> FromAuthorizationToken(const SPXSTRING& appId, const SPXSTRING& authToken, const SPXSTRING& region)
    {
        SPXSPEECHCONFIGHANDLE h_config = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(custom_commands_config_from_authorization_token(&h_config, Utils::ToUTF8(appId).c_str(), Utils::ToUTF8(authToken).c_str(), Utils::ToUTF8(region).c_str()));
        return std::shared_ptr<CustomCommandsConfig>{ new CustomCommandsConfig(h_config) };
    }

    /// <summary>
    /// Sets the corresponding backend application identifier.
    /// </summary>
    /// <param name="applicationId">Application identifier.</param>
    inline void SetApplicationId(const SPXSTRING& applicationId)
    {
        SetProperty(PropertyId::Conversation_ApplicationId, applicationId);
    }

    /// <summary>
    /// Gets the application identifier.
    /// </summary>
    /// <returns>Speech Channel Secret Key.</returns>
    inline SPXSTRING GetApplicationId() const
    {
        return GetProperty(PropertyId::Conversation_ApplicationId);
    }

private:
    inline explicit CustomCommandsConfig(SPXSPEECHCONFIGHANDLE h_config): DialogServiceConfig{ h_config }
    {
    }
};

} } } }
