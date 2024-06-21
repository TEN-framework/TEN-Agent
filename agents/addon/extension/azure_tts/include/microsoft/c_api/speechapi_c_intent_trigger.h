//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_intent_trigger.h: Public API declarations for IntentTrigger related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>


SPXAPI_(bool) intent_trigger_handle_is_valid(SPXTRIGGERHANDLE htrigger);

SPXAPI intent_trigger_create_from_phrase(SPXTRIGGERHANDLE* htrigger, const char* phrase);
SPXAPI intent_trigger_create_from_language_understanding_model(SPXTRIGGERHANDLE* htrigger, SPXLUMODELHANDLE hlumodel, const char* intentName);

SPXAPI intent_trigger_handle_release(SPXTRIGGERHANDLE htrigger);
