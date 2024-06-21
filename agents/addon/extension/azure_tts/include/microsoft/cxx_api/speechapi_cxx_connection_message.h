//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_connection_message.h: Public API declarations for ConnectionMessage C++ class
//

#pragma once
#include <string>
#include <vector>
#include <speechapi_c_connection.h>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_session_eventargs.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// ConnectionMessage represents implementation specific messages sent to and received from
/// the speech service. These messages are provided for debugging purposes and should not
/// be used for production use cases with the Azure Cognitive Services Speech Service.
/// Messages sent to and received from the Speech Service are subject to change without
/// notice. This includes message contents, headers, payloads, ordering, etc.
/// Added in version 1.10.0.
/// </summary>
class ConnectionMessage
{
private:

    /*! \cond PRIVATE */

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXCONNECTIONMESSAGEHANDLE hcm) :
            PropertyCollection(
                [=]() {
                SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                ::connection_message_get_property_bag(hcm, &hpropbag);
                return hpropbag;
            }())
        {
        }
    };

    SPXCONNECTIONMESSAGEHANDLE m_hcm;
    PrivatePropertyCollection m_properties;

    /*! \endcond */

public:

    /// <summary>
    /// Constructor.
    /// </summary>
    /// <param name="hcm">Event handle.</param>
    explicit ConnectionMessage(SPXCONNECTIONMESSAGEHANDLE hcm) :
        m_hcm(hcm),
        m_properties(hcm),
        Properties(m_properties)
    {
    };

    /// <summary>
    /// Destructor.
    /// </summary>
    virtual ~ConnectionMessage()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)m_hcm);
        SPX_THROW_ON_FAIL(::connection_message_handle_release(m_hcm));
    }

    /// <summary>
    /// Gets the message path.
    /// </summary>
    /// <returns>An std::string containing the message path.</returns>
    std::string GetPath() const
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_hcm == SPXHANDLE_INVALID);
        return m_properties.GetProperty("connection.message.path");
    }

    /// <summary>
    /// Checks to see if the ConnectionMessage is a text message.
    /// See also IsBinaryMessage().
    /// </summary>
    /// <returns>A bool indicated if the message payload is text.</returns>
    bool IsTextMessage() const
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_hcm == SPXHANDLE_INVALID);
        return m_properties.GetProperty("connection.message.type") == "text";
    }

    /// <summary>
    /// Checks to see if the ConnectionMessage is a binary message.
    /// See also GetBinaryMessage().
    /// </summary>
    /// <returns>A bool indicated if the message payload is binary.</returns>
    bool IsBinaryMessage() const
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_hcm == SPXHANDLE_INVALID);
        return m_properties.GetProperty("connection.message.type") == "binary";
    }

    /// <summary>
    /// Gets the text message payload. Typically the text message content-type is
    /// application/json. To determine other content-types use
    /// Properties.GetProperty("Content-Type").
    /// </summary>
    /// <returns>An std::string containing the text message.</returns>
    std::string GetTextMessage() const
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_hcm == SPXHANDLE_INVALID);
        return m_properties.GetProperty("connection.message.text.message");
    }

    /// <summary>
    /// Gets the binary message payload.
    /// </summary>
    /// <returns>An std::vector<uint8_t> containing the binary message.</returns>
    std::vector<uint8_t> GetBinaryMessage() const
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_hcm == SPXHANDLE_INVALID);
        auto size = ::connection_message_get_data_size(m_hcm);

        std::vector<uint8_t> message(size);
        SPX_THROW_ON_FAIL(::connection_message_get_data(m_hcm, message.data(), size));

        return message;
    }

    /// <summary>
    /// A collection of properties and their values defined for this <see cref="ConnectionMessage"/>.
    /// Message headers can be accessed via this collection (e.g. "Content-Type").
    /// </summary>
    PropertyCollection& Properties;

private:

    /*! \cond PRIVATE */

    DISABLE_COPY_AND_MOVE(ConnectionMessage);

    /*! \endcond */
};


} } } // Microsoft::CognitiveServices::Speech
