//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_intent_trigger.h: Public API declarations for IntentTrigger C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_language_understanding_model.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Intent {

/// <summary>
/// Represents an intent trigger.
/// </summary>
class IntentTrigger
{
public:

    /// <summary>
    /// Creates an intent trigger using the specified phrase.
    /// </summary>
    /// <param name="simplePhrase">The simple phrase to create an intent trigger for.</param>
    /// <returns>A shared pointer to an intent trigger.</returns>
    static std::shared_ptr<IntentTrigger> From(const SPXSTRING& simplePhrase)
    {
        SPXTRIGGERHANDLE htrigger = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(intent_trigger_create_from_phrase(&htrigger, Utils::ToUTF8(simplePhrase).c_str()));
        return std::make_shared<IntentTrigger>(htrigger);
    }

    /// <summary>
    /// Creates an intent trigger using the specified LanguageUnderstandingModel.
    /// </summary>
    /// <param name="model">The LanguageUnderstandingModel to create an intent trigger for.</param>
    /// <returns>A shared pointer to an intent trigger.</returns>
    static std::shared_ptr<IntentTrigger> From(std::shared_ptr<LanguageUnderstandingModel> model)
    {
        SPXTRIGGERHANDLE htrigger = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(intent_trigger_create_from_language_understanding_model(&htrigger, (SPXLUMODELHANDLE)(*model.get()), nullptr));
        return std::make_shared<IntentTrigger>(htrigger);
    }

    /// <summary>
    /// Creates an intent trigger using the specified LanguageUnderstandingModel and an intent name.
    /// </summary>
    /// <param name="model">The LanguageUnderstandingModel to create an intent trigger for.</param>
    /// <param name="intentName">The intent name to create an intent trigger for.</param>
    /// <returns>A shared pointer to an intent trigger.</returns>
    static std::shared_ptr<IntentTrigger> From(std::shared_ptr<LanguageUnderstandingModel> model, const SPXSTRING& intentName)
    {
        SPXTRIGGERHANDLE htrigger = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(intent_trigger_create_from_language_understanding_model(&htrigger, (SPXLUMODELHANDLE)(*model.get()), Utils::ToUTF8(intentName).c_str()));
        return std::make_shared<IntentTrigger>(htrigger);
    }

    /// <summary>
    /// Virtual destructor
    /// </summary>
    virtual ~IntentTrigger() { intent_trigger_handle_release(m_htrigger); m_htrigger = SPXHANDLE_INVALID; }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="htrigger">Trigger handle.</param>
    explicit IntentTrigger(SPXTRIGGERHANDLE htrigger) : m_htrigger(htrigger) { };

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXTRIGGERHANDLE() { return m_htrigger; }

private:
    DISABLE_DEFAULT_CTORS(IntentTrigger);

    SPXTRIGGERHANDLE m_htrigger;
};


} } } } // Microsoft::CognitiveServices::Speech::Intent
