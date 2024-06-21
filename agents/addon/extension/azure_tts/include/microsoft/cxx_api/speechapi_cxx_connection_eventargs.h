//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_session_eventargs.h>
#include <speechapi_cxx_properties.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Provides data for the ConnectionEvent.
/// Added in version 1.2.0.
/// </summary>
class ConnectionEventArgs : public SessionEventArgs
{
protected:
    /*! \cond PRIVATE */
    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXEVENTHANDLE hevent) :
            PropertyCollection([=]()
            {
                SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                recognizer_connection_event_get_property_bag(hevent, &hpropbag);
                return hpropbag;
            }())
        {}
    };

    PrivatePropertyCollection m_properties;
    /*! \endcond */

public:

    /// <summary>
    /// Constructor.
    /// </summary>
    /// <param name="hevent">Event handle.</param>
    explicit ConnectionEventArgs(SPXEVENTHANDLE hevent) :
        SessionEventArgs(hevent),
        m_properties(hevent),
        Properties(m_properties)
    {
    };

    /// <inheritdoc/>
    virtual ~ConnectionEventArgs() {}

    /// <summary>
    /// Collection of additional properties.
    /// </summary>
    const PropertyCollection& Properties;

private:

    DISABLE_COPY_AND_MOVE(ConnectionEventArgs);
};


} } } // Microsoft::CognitiveServices::Speech
