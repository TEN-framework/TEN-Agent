//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_recognition_result.h: Public API declarations for SpeechRecognitionResult C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>
#include <speechapi_cxx_recognition_result.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Base class for speech recognition results.
/// </summary>
class SpeechRecognitionResult : public RecognitionResult
{
public:

    explicit SpeechRecognitionResult(SPXRESULTHANDLE hresult) :
        RecognitionResult(hresult)
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p) -- resultid=%s; reason=0x%x; text=%s", __FUNCTION__, (void*)this, (void*)Handle, Utils::ToUTF8(ResultId).c_str(), Reason, Utils::ToUTF8(Text).c_str());
    }

    virtual ~SpeechRecognitionResult()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)Handle);
    }


private:
    DISABLE_DEFAULT_CTORS(SpeechRecognitionResult);
};


} } } // Microsoft::CognitiveServices::Speech
