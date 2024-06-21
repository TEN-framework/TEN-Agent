//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_hybrid_speech_config.h: Public API declarations for HybridSpeechConfig C++ class
//
#pragma once

#include <string>

#include <speechapi_c_common.h>
#include <speechapi_c_hybrid_speech_config.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_utils.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Class that defines hybrid (cloud and embedded) configurations for speech recognition or speech synthesis.
/// </summary>
class HybridSpeechConfig
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
    /// Creates an instance of the hybrid speech config with specified cloud and embedded speech configs.
    /// </summary>
    /// <param name="cloudSpeechConfig">A shared smart pointer of a cloud speech config.</param>
    /// <param name="embeddedSpeechConfig">A shared smart pointer of an embedded speech config.</param>
    /// <returns>A shared pointer to the new hybrid speech config instance.</returns>
    static std::shared_ptr<HybridSpeechConfig> FromConfigs(
        std::shared_ptr<SpeechConfig> cloudSpeechConfig,
        std::shared_ptr<EmbeddedSpeechConfig> embeddedSpeechConfig)
    {
        SPXSPEECHCONFIGHANDLE hconfig = SPXHANDLE_INVALID;

        SPX_THROW_ON_FAIL(hybrid_speech_config_create(
            &hconfig,
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE,SpeechConfig>(cloudSpeechConfig),
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE,EmbeddedSpeechConfig>(embeddedSpeechConfig)));

        auto ptr = new HybridSpeechConfig(hconfig);
        return std::shared_ptr<HybridSpeechConfig>(ptr);
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
    virtual ~HybridSpeechConfig() = default;

protected:
    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    inline explicit HybridSpeechConfig(SPXSPEECHCONFIGHANDLE hconfig) : m_config(hconfig)
    {
    }

    /*! \endcond */

private:
    DISABLE_COPY_AND_MOVE(HybridSpeechConfig);

    };

}}}
