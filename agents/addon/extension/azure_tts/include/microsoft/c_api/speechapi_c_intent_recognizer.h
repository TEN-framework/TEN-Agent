//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_intent_recognizer.h: Public API declarations for IntentRecognizer related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI intent_recognizer_add_intent(SPXRECOHANDLE hreco, const char* intentId, SPXTRIGGERHANDLE htrigger);
SPXAPI intent_recognizer_add_intent_with_model_id(SPXRECOHANDLE hreco, SPXTRIGGERHANDLE htrigger, const char* modelId);
SPXAPI intent_recognizer_recognize_text_once(SPXRECOHANDLE hreco, const char* text, SPXRESULTHANDLE* hresult);
SPXAPI intent_recognizer_clear_language_models(SPXRECOHANDLE hreco);
SPXAPI intent_recognizer_import_pattern_matching_model(SPXRECOHANDLE hreco, const char* jsonData);
SPXAPI intent_recognizer_add_conversational_language_understanding_model(SPXRECOHANDLE hreco, const char* languageResourceKey, const char* endpoint, const char* projectName, const char* deploymentName);
