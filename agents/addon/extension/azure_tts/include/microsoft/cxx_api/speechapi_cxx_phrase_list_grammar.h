//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_phrase_list_grammar.h: Public API declarations for PhraseListGrammar C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_smart_handle.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_grammar.h>
#include <speechapi_cxx_grammar_phrase.h>
#include <speechapi_c.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Represents a phrase list grammar for dynamic grammar scenarios.
/// Added in version 1.5.0.
/// </summary>
class PhraseListGrammar : public Grammar
{
public:

    /// <summary>
    /// Creates a phrase list grammar for the specified recognizer.
    /// </summary>
    /// <param name="recognizer">The recognizer from which to obtain the phrase list grammar.</param>
    /// <returns>A shared pointer to phrase list grammar.</returns>
    template <class T>
    static std::shared_ptr<PhraseListGrammar> FromRecognizer(std::shared_ptr<T> recognizer)
    {
        return FromRecognizer(recognizer, Utils::ToSPXString(nullptr));
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hgrammar">Phrase list grammar handle.</param>
    explicit PhraseListGrammar(SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID) : Grammar(hgrammar) { }

    /// <summary>
    /// Adds a simple phrase that may be spoken by the user.
    /// </summary>
    /// <param name="text">The phrase to be added.</param>
    void AddPhrase(const SPXSTRING& text)
    {
        auto phrase = GrammarPhrase::From(text);
        SPX_THROW_ON_FAIL(phrase_list_grammar_add_phrase(m_hgrammar.get(), (SPXPHRASEHANDLE)(*phrase.get())));
    }

    /// <summary>
    /// Clears all phrases from the phrase list grammar.
    /// </summary>
    void Clear()
    {
        SPX_THROW_ON_FAIL(phrase_list_grammar_clear(m_hgrammar.get()));
    }

protected:

    /// <summary>
    /// Internal. Creates a phrase list grammar for the specified recognizer, with the specified name.
    /// </summary>
    /// <param name="recognizer">The recognizer from which to obtain the phrase list grammar.</param>
    /// <param name="name">The name of the phrase list grammar to create.</param>
    /// <returns>A shared pointer to phrase list grammar.</returns>
    template <class T>
    static std::shared_ptr<PhraseListGrammar> FromRecognizer(std::shared_ptr<T> recognizer, const SPXSTRING& name)
    {
        SPXRECOHANDLE hreco = recognizer != nullptr
            ? (SPXRECOHANDLE)(*recognizer.get())
            : SPXHANDLE_INVALID;

        SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(phrase_list_grammar_from_recognizer_by_name(&hgrammar, hreco, Utils::ToUTF8(name.c_str())));

        return std::make_shared<PhraseListGrammar>(hgrammar);
    }


private:

    DISABLE_COPY_AND_MOVE(PhraseListGrammar);
};


} } } // Microsoft::CognitiveServices::Speech
