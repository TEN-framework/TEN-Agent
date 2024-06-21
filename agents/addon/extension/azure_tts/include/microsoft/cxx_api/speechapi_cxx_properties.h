#pragma once

#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_enums.h>
#include <speechapi_c_session.h>
#include <speechapi_c_property_bag.h>
#include <speechapi_cxx_speech_config.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

class KeywordRecognizer;

/// <summary>
/// Class to retrieve or set a property value from a property collection.
/// </summary>
class PropertyCollection
{
public:

    /// <summary>
    /// Destructor.
    /// </summary>
    ~PropertyCollection()
    {
        if (property_bag_is_valid(m_propbag))
        {
            property_bag_release(m_propbag);
            m_propbag = SPXHANDLE_INVALID;
        }
    }

    /// <summary>
    /// Set value of a property.
    /// </summary>
    /// <param name="propertyID">The id of the property. See <see cref="PropertyId"/></param>
    /// <param name="value">value to set</param>
    void SetProperty(PropertyId propertyID, const SPXSTRING& value)
    {
        property_bag_set_string(m_propbag, (int)propertyID, NULL, Utils::ToUTF8(value).c_str());
    }

    /// <summary>
    /// Set value of a property.
    /// </summary>
    /// <param name="propertyName">The name of property.</param>
    /// <param name="value">value to set</param>
    void SetProperty(const SPXSTRING& propertyName, const SPXSTRING& value)
    {
        property_bag_set_string(m_propbag, -1, Utils::ToUTF8(propertyName).c_str(), Utils::ToUTF8(value).c_str());
    }

    /// <summary>
    /// Returns value of a property.
    /// If the property value is not defined, the specified default value is returned.
    /// </summary>
    /// <param name="propertyID">The id of the property. See <see cref="PropertyId"/></param>
    /// <param name="defaultValue">The default value which is returned if no value is defined for the property (empty string by default).</param>
    /// <returns>value of the property.</returns>
    SPXSTRING GetProperty(PropertyId propertyID, const SPXSTRING& defaultValue = SPXSTRING()) const
    {
        const char* propCch = property_bag_get_string(m_propbag, static_cast<int>(propertyID), nullptr, Utils::ToUTF8(defaultValue).c_str());
        return Utils::ToSPXString(Utils::CopyAndFreePropertyString(propCch));
    }

    /// <summary>
    /// Returns value of a property.
    /// If the property value is not defined, the specified default value is returned.
    /// </summary>
    /// <param name="propertyName">The name of the property.</param>
    /// <param name="defaultValue">The default value which is returned if no value is defined for the property (empty string by default).</param>
    /// <returns>value of the property.</returns>
    SPXSTRING GetProperty(const SPXSTRING& propertyName, const SPXSTRING& defaultValue = SPXSTRING()) const
    {
        const char* propCch = property_bag_get_string(m_propbag, -1, Utils::ToUTF8(propertyName).c_str(), Utils::ToUTF8(defaultValue).c_str());
        return Utils::ToSPXString(Utils::CopyAndFreePropertyString(propCch));
    }

protected:
    friend class KeywordRecognizer;

    /*! \cond PROTECTED */

    PropertyCollection(SPXPROPERTYBAGHANDLE propbag) : m_propbag(propbag) {}

    /*! \endcond */

private:

    DISABLE_COPY_AND_MOVE(PropertyCollection);

    SPXPROPERTYBAGHANDLE m_propbag;
};


} } } // Microsoft::CognitiveServices::Speech
