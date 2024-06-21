//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_synthesis_word_boundary_eventargs.h: Public API declarations for SpeechSynthesisWordBoundaryEventArgs C++ class
//

#pragma once
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_eventargs.h>
#include <speechapi_c_synthesizer.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Class for speech synthesis word boundary event arguments.
/// Added in version 1.7.0
/// </summary>
class SpeechSynthesisWordBoundaryEventArgs : public EventArgs
{
private:

    SPXEVENTHANDLE m_hEvent;

public:

    /// <summary>
    /// Constructor.
    /// </summary>
    /// <param name="hevent">Event handle</param>
    explicit SpeechSynthesisWordBoundaryEventArgs(SPXEVENTHANDLE hevent) :
    m_hEvent(hevent),
    ResultId(m_resultId),
    Duration(m_duration),
    Text(m_text),
    BoundaryType(m_boundaryType)
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)m_hEvent);
        uint64_t durationTicks;
        SpeechSynthesis_BoundaryType boundaryType = SpeechSynthesis_BoundaryType_Word;
        synthesizer_word_boundary_event_get_values(hevent, &m_audioOffset, &durationTicks, &m_textOffset, &m_wordLength, &boundaryType);
        m_duration = std::chrono::milliseconds(durationTicks / static_cast<uint64_t>(10000));
        m_boundaryType = static_cast<SpeechSynthesisBoundaryType>(boundaryType);
        AudioOffset = m_audioOffset;
        TextOffset = m_textOffset;
        WordLength = m_wordLength;
        m_text = Utils::ToSPXString(Utils::CopyAndFreePropertyString(synthesizer_event_get_text(hevent)));

        const size_t maxCharCount = 256;
        char sz[maxCharCount + 1];
        SPX_THROW_ON_FAIL(synthesizer_event_get_result_id(hevent, sz, maxCharCount));
        m_resultId = Utils::ToSPXString(sz);
    };

    /// <inheritdoc/>
    virtual ~SpeechSynthesisWordBoundaryEventArgs()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)m_hEvent);
        SPX_THROW_ON_FAIL(synthesizer_event_handle_release(m_hEvent));
    }

    /// <summary>
    /// Unique result id.
    /// Added in version 1.25.0
    /// </summary>
    const SPXSTRING& ResultId;

    /// <summary>
    /// Word boundary audio offset.
    /// </summary>
    uint64_t AudioOffset;

    /// <summary>
    /// Time duration of the audio.
    /// Added in version 1.21.0
    /// </summary>
    const std::chrono::milliseconds& Duration;

    /// <summary>
    /// Word boundary text offset.
    /// </summary>
    uint32_t TextOffset;

    /// <summary>
    /// Word boundary word length.
    /// </summary>
    uint32_t WordLength;

    /// <summary>
    /// The text.
    /// Added in version 1.21.0
    /// </summary>
    const SPXSTRING& Text;

    /// <summary>
    /// Word boundary type.
    /// Added in version 1.21.0
    /// </summary>
    const SpeechSynthesisBoundaryType& BoundaryType;

private:

    DISABLE_DEFAULT_CTORS(SpeechSynthesisWordBoundaryEventArgs);

    SPXSTRING m_resultId;
    uint64_t m_audioOffset{ 0 };
    std::chrono::milliseconds m_duration{ 0 };
    uint32_t m_textOffset{ 0 };
    uint32_t m_wordLength{ 0 };
    SPXSTRING m_text;
    SpeechSynthesisBoundaryType m_boundaryType{ SpeechSynthesisBoundaryType::Word };
};


} } } // Microsoft::CognitiveServices::Speech
