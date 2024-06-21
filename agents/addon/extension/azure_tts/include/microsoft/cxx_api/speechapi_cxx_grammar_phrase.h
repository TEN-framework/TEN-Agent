//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_phrase_grammar.h: Public API declarations for GrammarPhrase C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_smart_handle.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Represents a phrase that may be spoken by the user.
/// Added in version 1.5.0.
/// </summary>
class GrammarPhrase
{
public:

    /// <summary>
    /// Creates a grammar phrase using the specified phrase text.
    /// </summary>
    /// <param name="text">The text representing a phrase that may be spoken by the user.</param>
    /// <returns>A shared pointer to a grammar phrase.</returns>
    static std::shared_ptr<GrammarPhrase> From(const SPXSTRING& text)
    {
        SPXPHRASEHANDLE hphrase = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(grammar_phrase_create_from_text(&hphrase, Utils::ToUTF8(text).c_str()));
        return std::make_shared<GrammarPhrase>(hphrase);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hphrase">Grammar phrase handle.</param>
    explicit GrammarPhrase(SPXPHRASEHANDLE hphrase) : m_hphrase(hphrase) { };

    /// <summary>
    /// Virtual destructor
    /// </summary>
    virtual ~GrammarPhrase() { }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXPHRASEHANDLE() { return m_hphrase; }

private:

    DISABLE_DEFAULT_CTORS(GrammarPhrase);

    SmartHandle<SPXPHRASEHANDLE, &grammar_phrase_handle_release> m_hphrase;
};


} } } // Microsoft::CognitiveServices::Speech
