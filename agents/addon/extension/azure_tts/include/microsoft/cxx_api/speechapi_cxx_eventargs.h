//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_eventargs.h: Public API declarations for EventArgs C++ base class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Base class for event arguments.
/// </summary>
class EventArgs
{
public:

    /// <summary>
    /// Destructor.
    /// </summary>
    virtual ~EventArgs() {}

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Constructor.
    /// </summary>
    EventArgs() {};

    /*! \endcond */

private:

    DISABLE_COPY_AND_MOVE(EventArgs);
};


} } } // Microsoft::CognitiveServices::Speech
