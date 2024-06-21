//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_pattern_matching_intent.h: Public API declarations for PatternMatchingIntent C++ struct
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Intent {

/// <summary>
/// Represents a pattern matching intent used for intent recognition.
/// </summary>
struct PatternMatchingIntent
{
    /// <summary>
    /// Phrases and patterns that will trigger this intent. At least one phrase must exist to be able to
    /// apply this intent to an IntentRecognizer.
    /// </summary> 
    std::vector<SPXSTRING> Phrases;

    /// <summary>
    /// An Id used to define this Intent if it is matched. If no Id is specified, then the first phrase in Phrases
    /// will be used.
    /// </summary>
    SPXSTRING Id;
};

} } } } // Microsoft::CognitiveServices::Speech::Intent
