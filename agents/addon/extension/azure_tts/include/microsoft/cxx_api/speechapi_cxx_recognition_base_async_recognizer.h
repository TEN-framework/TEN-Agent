//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_recognition_base_async_recognizer.h: Public API declarations for BaseAsyncRecognizer C++ class
//

#pragma once
#include <future>
#include <memory>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_eventsignal.h>
#include <speechapi_cxx_recognition_result.h>
#include <speechapi_cxx_session_eventargs.h>
#include <speechapi_cxx_recognition_base_async_recognizer.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// BaseAsyncRecognizer class.
/// </summary>
class BaseAsyncRecognizer : public AsyncRecognizer<RecognitionResult, RecognitionEventArgs, RecognitionEventArgs>
{
protected:

    /*! \cond PROTECTED */

    using BaseType = AsyncRecognizer<RecognitionResult, RecognitionEventArgs, RecognitionEventArgs>;

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    explicit BaseAsyncRecognizer(SPXRECOHANDLE hreco) :
        BaseType(hreco)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    ~BaseAsyncRecognizer()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
        TermRecognizer();
    }

    DISABLE_DEFAULT_CTORS(BaseAsyncRecognizer);

    /*! \endcond */
};


} } } // Microsoft::CognitiveServices::Speech
