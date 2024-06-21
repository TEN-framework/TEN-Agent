//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_connection_message_eventargs.h: Public API declarations for ConnectionMessageEventArgs C++ base class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_eventargs.h>
#include <speechapi_cxx_connection_message.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Provides data for the ConnectionMessageEvent
/// </summary>
class ConnectionMessageEventArgs : public EventArgs
{
private:

    /*! \cond PRIVATE */

    SPXEVENTHANDLE m_hevent;
    std::shared_ptr<ConnectionMessage> m_message;

    /*! \endcond */

public:

    /// <summary>
    /// Constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hevent">Event handle.</param>
    explicit ConnectionMessageEventArgs(SPXEVENTHANDLE hevent) :
        m_hevent(hevent),
        m_message(std::make_shared<ConnectionMessage>(MessageHandleFromEventHandle(hevent)))
    {
    };

    /// <summary>
    /// Destructor.
    /// </summary>
    virtual ~ConnectionMessageEventArgs()
    {
        SPX_THROW_ON_FAIL(::connection_message_received_event_handle_release(m_hevent));
    }

    /// <summary>
    /// Gets the <see cref="ConnectionMessage"/> associated with this <see cref="ConnectionMessageEventArgs"/>.
    /// </summary>
    /// <returns>An `std::shared<ConnectionMessage>` containing the message.</returns>
    std::shared_ptr<ConnectionMessage> GetMessage() const { return m_message; }

private:

    /*! \cond PRIVATE */

    DISABLE_COPY_AND_MOVE(ConnectionMessageEventArgs);

    SPXCONNECTIONMESSAGEHANDLE MessageHandleFromEventHandle(SPXEVENTHANDLE hevent)
    {
        SPXCONNECTIONMESSAGEHANDLE hcm = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(::connection_message_received_event_get_message(hevent, &hcm));
        return hcm;
    }

    /*! \endcond */

};


} } } // Microsoft::CognitiveServices::Speech
