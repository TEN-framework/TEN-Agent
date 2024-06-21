//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_voice_info.h: Public API declarations for VoiceInfo C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_enums.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_c_result.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Contains information about synthesis voice info
/// Updated in version 1.17.0
/// </summary>
class VoiceInfo
{
private:

    /// <summary>
    /// Internal member variable that holds the voice info handle.
    /// </summary>
    SPXRESULTHANDLE m_hresult;

    /*! \cond PRIVATE */

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXRESULTHANDLE hresult) :
            PropertyCollection(
                [=]() {
            SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
            voice_info_get_property_bag(hresult, &hpropbag);
            return hpropbag;
        }())
        {
        }
    };

    /// <summary>
    /// Internal member variable that holds the properties associating to the voice info.
    /// </summary>
    PrivatePropertyCollection m_properties;

    /*! \endcond */

public:

    /// <summary>
    /// Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hresult">Result handle.</param>
    explicit VoiceInfo(SPXRESULTHANDLE hresult) :
        m_hresult(hresult),
        m_properties(hresult),
        Name(m_name),
        Locale(m_locale),
        ShortName(m_shortName),
        LocalName(m_localName),
        Gender(m_gender),
        VoiceType(m_voiceType),
        StyleList(m_styleList),
        VoicePath(m_voicePath),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        m_name = Utils::ToSPXString(Utils::CopyAndFreePropertyString(voice_info_get_name(m_hresult)));
        m_locale = Utils::ToSPXString(Utils::CopyAndFreePropertyString(voice_info_get_locale(m_hresult)));
        m_shortName = Utils::ToSPXString(Utils::CopyAndFreePropertyString(voice_info_get_short_name(m_hresult)));
        m_localName = Utils::ToSPXString(Utils::CopyAndFreePropertyString(voice_info_get_local_name(m_hresult)));
        m_styleList = Utils::Split(Utils::CopyAndFreePropertyString(voice_info_get_style_list(m_hresult)), '|');
        Synthesis_VoiceType voiceType;
        SPX_THROW_ON_FAIL(voice_info_get_voice_type(hresult, &voiceType));
        m_voiceType = static_cast<SynthesisVoiceType>(voiceType);
        m_voicePath = Utils::ToSPXString(Utils::CopyAndFreePropertyString(voice_info_get_voice_path(m_hresult)));
        auto gender = Properties.GetProperty("Gender");
        m_gender = gender == "Female" ? SynthesisVoiceGender::Female : gender == "Male" ? SynthesisVoiceGender::Male : SynthesisVoiceGender::Unknown;
    }

    /// <summary>
    /// Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXRESULTHANDLE() { return m_hresult; }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~VoiceInfo()
    {
        voice_info_handle_release(m_hresult);
    }

    /// <summary>
    /// Voice name.
    /// </summary>
    const SPXSTRING& Name;

    /// <summary>
    /// Locale of the voice.
    /// </summary>
    const SPXSTRING& Locale;

    /// <summary>
    /// Short name.
    /// </summary>
    const SPXSTRING& ShortName;

    /// <summary>
    /// Local name.
    /// </summary>
    const SPXSTRING& LocalName;

    /// <summary>
    /// Gender.
    /// Added in version 1.17.0
    /// </summary>
    const SynthesisVoiceGender& Gender;

    /// <summary>
    /// Local name.
    /// </summary>
    const SynthesisVoiceType& VoiceType;

    /// <summary>
    /// Style list
    /// </summary>
    const std::vector<SPXSTRING>& StyleList;

    /// <summary>
    /// Voice path, only valid for offline voices.
    /// </summary>
    const SPXSTRING& VoicePath;

    /// <summary>
    /// Collection of additional VoiceInfo properties.
    /// </summary>
    const PropertyCollection& Properties;

private:

    DISABLE_DEFAULT_CTORS(VoiceInfo);

    /// <summary>
    /// Internal member variable that holds the name.
    /// </summary>
    SPXSTRING m_name;

    /// <summary>
    /// Internal member variable that holds the locale.
    /// </summary>
    SPXSTRING m_locale;

    /// <summary>
    /// Internal member variable that holds the short name.
    /// </summary>
    SPXSTRING m_shortName;

    /// <summary>
    /// Internal member variable that holds the local name.
    /// </summary>
    SPXSTRING m_localName;

    /// <summary>
    /// Internal member variable that holds the gender.
    /// </summary>
    SynthesisVoiceGender m_gender;

    /// <summary>
    /// Internal member variable that holds the voice type.
    /// </summary>
    SynthesisVoiceType m_voiceType;

    /// <summary>
    /// Internal member variable that holds the style list.
    /// </summary>
    std::vector<SPXSTRING> m_styleList;

    /// <summary>
    /// Internal member variable that holds the voice path.
    /// </summary>
    SPXSTRING m_voicePath;
};


} } } // Microsoft::CognitiveServices::Speech
