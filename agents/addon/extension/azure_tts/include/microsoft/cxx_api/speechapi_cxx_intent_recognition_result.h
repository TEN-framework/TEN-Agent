//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_intent_recognition_result.h: Public API declarations for IntentRecognitionResult C++ class
//

#pragma once
#include <string>
#include <map>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_recognition_result.h>
#include <speechapi_c.h>
#include <speechapi_cxx_utils.h>

#include "speechapi_c_json.h"

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Intent {

/// <summary>
/// Represents the result of an intent recognition.
/// </summary>
class IntentRecognitionResult final : public RecognitionResult
{
public:

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hresult">Result handle.</param>
    explicit IntentRecognitionResult(SPXRESULTHANDLE hresult) :
        RecognitionResult(hresult),
        IntentId(m_intentId)
    {
        PopulateIntentFields(hresult, &m_intentId);
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p) -- resultid=%s; reason=0x%x; text=%s", __FUNCTION__, (void*)this, (void*)Handle, Utils::ToUTF8(ResultId).c_str(), Reason, Utils::ToUTF8(Text).c_str());
    }

    /// <summary>
    /// A call to return a map of the entities found in the utterance.
    /// </summary>
    /// <returns>
    /// A map with the entity name as a key and containing the value of the entity found in the utterance.
    /// </returns>
    /// <remarks>
    /// This currently does not report LUIS entities.
    /// </remarks>
    const std::map<SPXSTRING, SPXSTRING>& GetEntities() const
    {
        return m_entities;
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~IntentRecognitionResult()
    {
        SPX_DBG_TRACE_VERBOSE("%s (this=0x%p, handle=0x%p)", __FUNCTION__, (void*)this, (void*)Handle);
    }

    /// <summary>
    /// Unique intent id.
    /// </summary>
    const SPXSTRING& IntentId;

private:
    DISABLE_DEFAULT_CTORS(IntentRecognitionResult);

    void PopulateIntentFields(SPXRESULTHANDLE hresult, SPXSTRING* pintentId)
    {
        SPX_INIT_HR(hr);

        const size_t maxCharCount = 1024;
        char sz[maxCharCount+1] = {};

        if (pintentId != nullptr && recognizer_result_handle_is_valid(hresult))
        {
            SPX_THROW_ON_FAIL(hr = intent_result_get_intent_id(hresult, sz, maxCharCount));
            *pintentId = Utils::ToSPXString(sz);
        }

        auto jsonSLE = Properties.GetProperty("LanguageUnderstandingSLE_JsonResult");
        SPXHANDLE parserHandle = SPXHANDLE_INVALID;
        auto scopeGuard = Utils::MakeScopeGuard([&parserHandle]()
        {
            if (parserHandle != SPXHANDLE_INVALID)
            {
                ai_core_json_parser_handle_release(parserHandle);
            }
        });

        auto root = ai_core_json_parser_create(&parserHandle, jsonSLE.c_str(), jsonSLE.size());
        int count = ai_core_json_item_count(parserHandle, root);
        for (int i = 0; i < count; i++)
        {
            auto itemInt = ai_core_json_item_at(parserHandle, root, i, nullptr);
            auto nameInt = ai_core_json_item_name(parserHandle, itemInt);

            // Need to use string copy here to force the ajv json parser to convert back to utf8.
            auto name = ai_core_json_value_as_string_copy(parserHandle, nameInt, "");
            auto value = ai_core_json_value_as_string_copy(parserHandle, itemInt, "");
            if (value != nullptr && name != nullptr)
            {
                m_entities[name] = value;
            }
        }
         
    }

    SPXSTRING m_intentId;
    std::map<SPXSTRING, SPXSTRING> m_entities;
};


} } } } // Microsoft::CognitiveServices::Speech::Recognition::Intent
