//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_pattern_matching_model.h: Public API declarations for PatternMatchingModel related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI_(bool) pattern_matching_model_handle_is_valid(SPXLUMODELHANDLE hlumodel);

SPXAPI pattern_matching_model_create(SPXLUMODELHANDLE* hlumodel, SPXRECOHANDLE hIntentReco, const char* id);
SPXAPI pattern_matching_model_create_from_id(SPXLUMODELHANDLE* hlumodel, const char* id);

typedef SPXAPI_RESULTTYPE(SPXAPI_CALLTYPE* PATTERN_MATCHING_MODEL_GET_STR_FROM_INDEX)(void* context, size_t index, const char** str, size_t* size);

SPXAPI pattern_matching_model_add_entity(
    SPXLUMODELHANDLE hlumodel,
    const char* id,
    int32_t type,
    int32_t mode,
    size_t numPhrases,
    void* phraseContext,
    PATTERN_MATCHING_MODEL_GET_STR_FROM_INDEX phraseGetter);

SPXAPI pattern_matching_model_add_intent(
    SPXLUMODELHANDLE hlumodel,
    const char* id,
    uint32_t priority,
    size_t numPhrases,
    void* phraseContext,
    PATTERN_MATCHING_MODEL_GET_STR_FROM_INDEX phraseGetter);
