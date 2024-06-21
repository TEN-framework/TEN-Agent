//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_session_eventargs.h: Public API declarations for SessionEventArgs C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c_recognizer.h>
#include <speechapi_cxx_eventargs.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Base class for session event arguments.
/// </summary>
class SessionEventArgs : public EventArgs
{
public:

    /// <summary>
    /// Constructor.
    /// </summary>
    /// <param name="hevent">Event handle</param>
    explicit SessionEventArgs(SPXEVENTHANDLE hevent) :
        SessionId(m_sessionId),
        m_sessionId(GetSessionId(hevent))
    {
    };

    /// <inheritdoc/>
    virtual ~SessionEventArgs() {}

    /// <summary>
    /// Session identifier (a GUID in string format).
    /// </summary>
    const SPXSTRING& SessionId;


protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Extract session identifier from given event handle <paramref name="hevent"/>
    /// </summary>
    static const SPXSTRING GetSessionId(SPXEVENTHANDLE hevent)
    {
        static const auto cchMaxUUID = 36;
        static const auto cchMaxSessionId = cchMaxUUID + 1;
        char sessionId[cchMaxSessionId] = {};

        SPX_THROW_ON_FAIL(recognizer_session_event_get_session_id(hevent, sessionId, cchMaxSessionId));
        return Utils::ToSPXString(sessionId);
    };

    /*! \endcond */

private:

    DISABLE_DEFAULT_CTORS(SessionEventArgs);

    SPXSTRING m_sessionId;
};


} } } // Microsoft::CognitiveServices::Speech
