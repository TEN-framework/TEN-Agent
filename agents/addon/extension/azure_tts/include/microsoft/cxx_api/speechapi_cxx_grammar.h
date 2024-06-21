//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_grammar.h: Public API declarations for Grammar C++ class
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
/// Represents base class grammar for customizing speech recognition.
/// Added in version 1.5.0.
/// </summary>
class Grammar
{
public:

    /// <summary>
    /// Creates a grammar from a storage ID.
    /// Added in version 1.7.0.
    /// </summary>
    /// <param name="storageId)">The persisted storage ID of the language model.</param>
    /// <returns>The grammar.</returns>
    /// <remarks>
    /// Creating a grammar from a storage ID is only usable in specific scenarios and is not generally possible.
    /// </remarks>
    static std::shared_ptr<Grammar> FromStorageId(const SPXSTRING& storageId)
    {
        SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(grammar_create_from_storage_id(&hgrammar, Utils::ToUTF8(storageId.c_str())));

        return std::make_shared<Grammar>(hgrammar);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hgrammar">Grammar handle.</param>
    explicit Grammar(SPXGRAMMARHANDLE hgrammar = SPXHANDLE_INVALID) : m_hgrammar(hgrammar) { }

    /// <summary>
    /// Destructor, does nothing.
    /// </summary>
    virtual ~Grammar() { }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXGRAMMARHANDLE() { return m_hgrammar; }

protected:
    /*! \cond PROTECTED */
    DISABLE_COPY_AND_MOVE(Grammar);

    SmartHandle<SPXGRAMMARHANDLE, &grammar_handle_release> m_hgrammar;
    /*! \endcond */
};


} } } // Microsoft::CognitiveServices::Speech
