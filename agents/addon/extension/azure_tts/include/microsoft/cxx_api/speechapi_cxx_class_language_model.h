//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_class_language_model.h: Public API declarations for ClassLanguageModel C++ class
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
/// ClassLanguageModels are only usable in specific scenarios and are not generally available.
/// </remarks>
class ClassLanguageModel : public Grammar
{
public:

    /// <summary>
    /// Creates a class language model from a storage ID.
    /// </summary>
    /// <param name="storageId)">The persisted storage ID of the language model.</param>
    /// <returns>The grammar list associated with the recognizer.</returns>
    /// <remarks>
    /// Creating a ClassLanguageModel from a storage ID is only usable in specific scenarios and is not generally available.
    /// </remarks>
    static std::shared_ptr<ClassLanguageModel> FromStorageId(const SPXSTRING& storageId)
    {
        SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(class_language_model_from_storage_id(&hgrammar, Utils::ToUTF8(storageId.c_str())));

        return std::make_shared<ClassLanguageModel>(hgrammar);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hgrammar">Class Language Model handle.</param>
    explicit ClassLanguageModel(SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID) : Grammar(hgrammar) { }

    /// <summary>
    /// Assigns a grammar to a class in the language mode.
    /// </summary>
    /// <param name="className">Name of the class to assign the grammar to.</param>
    /// <param name="grammar">Grammar to assign.</param>
    template <class T>
    void AssignClass(const SPXSTRING& className, std::shared_ptr<T> grammar)
    {
        SPX_THROW_ON_FAIL(class_language_model_assign_class(m_hgrammar.get(), Utils::ToUTF8(className.c_str()), (SPXPHRASEHANDLE)(*grammar.get())));
    }

private:

    DISABLE_COPY_AND_MOVE(ClassLanguageModel);
};


} } } // Microsoft::CognitiveServices::Speech
