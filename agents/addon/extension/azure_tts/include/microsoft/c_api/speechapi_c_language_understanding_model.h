//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_language_understanding_model.h: Public API declarations for LanguageUnderstandingModel related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI_(bool) language_understanding_model_handle_is_valid(SPXLUMODELHANDLE hlumodel);

SPXAPI language_understanding_model_create_from_uri(SPXLUMODELHANDLE* hlumodel, const char* uri);
SPXAPI language_understanding_model_create_from_app_id(SPXLUMODELHANDLE* hlumodel, const char* appId);
SPXAPI language_understanding_model_create_from_subscription(SPXLUMODELHANDLE* hlumodel, const char* subscriptionKey, const char* appId, const char* region);

SPXAPI language_understanding_model__handle_release(SPXLUMODELHANDLE hlumodel);
SPXAPI__(const char *) language_understanding_model_get_model_id(SPXLUMODELHANDLE hlumodel);
