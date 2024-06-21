//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_keyword_recognition_result.h: Public API declarations for the KeywordRecognitionResult C++ class
//

#pragma once

#include <speechapi_cxx_common.h>
#include <speechapi_cxx_recognition_result.h>
#include <speechapi_cxx_audio_data_stream.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Class that defines the results emitted by the <see cref="KeywordRecognizer" />.
/// </summary>
class KeywordRecognitionResult : public RecognitionResult
{
public:

    explicit KeywordRecognitionResult(SPXRESULTHANDLE hresult) :
        RecognitionResult(hresult)
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p) -- resultid=%s; reason=0x%x; text=%s", __FUNCTION__, (void*)this, (void*)Handle, Utils::ToUTF8(ResultId).c_str(), Reason, Utils::ToUTF8(Text).c_str());
    }

    virtual ~KeywordRecognitionResult() = default;

private:
    DISABLE_DEFAULT_CTORS(KeywordRecognitionResult);
};

inline std::shared_ptr<AudioDataStream> AudioDataStream::FromResult(std::shared_ptr<KeywordRecognitionResult> result)
{
    auto resultHandle = result != nullptr ? static_cast<SPXRESULTHANDLE>(*result) : SPXHANDLE_INVALID;
    auto streamHandle = Utils::CallFactoryMethodLeft(audio_data_stream_create_from_keyword_result, resultHandle);
    return std::shared_ptr<AudioDataStream>{ new AudioDataStream(streamHandle) };
}

} } } // Microsoft::CognitiveServices::Speech
