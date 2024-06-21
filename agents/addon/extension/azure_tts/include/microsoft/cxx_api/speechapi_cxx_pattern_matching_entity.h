//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_pattern_matching_entity.h: Public API declarations for PatternMatchingEntity C++ struct
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
/// Represents a pattern matching entity used for intent recognition.
/// </summary>
struct PatternMatchingEntity
{
    /// <summary>
    /// An Id used to define this Entity if it is matched. This id must appear in an intent phrase
    /// or it will never be matched.
    /// </summary>
    SPXSTRING Id;

    /// <summary>
    /// The Type of this Entity.
    /// </summary>
    EntityType Type;

    /// <summary>
    /// The EntityMatchMode of this Entity.
    /// </summary>
    EntityMatchMode Mode;

    /// <summary>
    /// If the Type is List these phrases will be used as the list.
    /// </summary>
    std::vector<SPXSTRING> Phrases;
    
};

} } } } // Microsoft::CognitiveServices::Speech::Intent
