//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_grammar_list.h: Public API declarations for GrammarList C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_smart_handle.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_grammar.h>
#include <speechapi_c.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


/// <summary>
/// Represents a list of grammars for dynamic grammar scenarios.
/// Added in version 1.7.0.
/// </summary>
/// <remarks>
/// GrammarLists are only usable in specific scenarios and are not generally available.
/// </remarks>
class GrammarList : public Grammar
{
public:

    /// <summary>
    /// Creates a grammar lsit for the specified recognizer.
    /// </summary>
    /// <param name="recognizer">The recognizer from which to obtain the grammar list.</param>
    /// <returns>The grammar list associated with the recognizer.</returns>
    /// <remarks>
    /// Creating a grammar list from a recognizer is only usable in specific scenarios and is not generally available.
    /// </remarks>
    template <class T>
    static std::shared_ptr<GrammarList> FromRecognizer(std::shared_ptr<T> recognizer)
    {
        SPXRECOHANDLE hreco = recognizer != nullptr
            ? (SPXRECOHANDLE)(*recognizer.get())
            : SPXHANDLE_INVALID;

        SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(grammar_list_from_recognizer(&hgrammar, hreco));

        return std::make_shared<GrammarList>(hgrammar);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hgrammar">GrammarList handle.</param>
    explicit GrammarList(SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID) : Grammar(hgrammar) { }

    /// <summary>
    /// Adds a single grammar to the current grammar list
    /// </summary>
    /// <param name="grammar">The grammar to add</param>
    /// <remarks>
    /// Currently Class Language Models are the only support grammars to add.
    /// </remarks>
    template <class T>
    void Add(std::shared_ptr<T> grammar)
    {
        SPX_THROW_ON_FAIL(grammar_list_add_grammar(m_hgrammar.get(), (SPXGRAMMARHANDLE)(*grammar.get())));
    }

    /// <summary>
    /// Sets the Recognition Factor applied to all grammars in a recognizer's GrammarList
    /// </summary>
    /// <param name="factor">The RecognitionFactor to apply</param>
    /// <param name="scope">The scope for the Recognition Factor being set</param>
    /// <remarks>
    /// The Recognition Factor is a numerical value greater than 0 modifies the default weight applied to supplied grammars.
    /// Setting the Recognition Factor to 0 will disable the supplied grammars.
    /// The default Recognition Factor is 1.
    /// </remarks>
    void SetRecognitionFactor(double factor, RecognitionFactorScope scope)
    {
        SPX_THROW_ON_FAIL(grammar_list_set_recognition_factor(m_hgrammar.get(), factor, (GrammarList_RecognitionFactorScope)scope));
    }

private:
    DISABLE_COPY_AND_MOVE(GrammarList);
};

} } } // Microsoft::CognitiveServices::Speech
