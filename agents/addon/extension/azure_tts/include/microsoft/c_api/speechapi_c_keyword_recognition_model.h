//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_keyword_recognition_model.h: Public API declarations for KeywordRecognitionModel related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>


SPXAPI_(bool) keyword_recognition_model_handle_is_valid(SPXKEYWORDHANDLE hkeyword);
SPXAPI keyword_recognition_model_handle_release(SPXKEYWORDHANDLE hkeyword);

SPXAPI keyword_recognition_model_create_from_file(const char* fileName, SPXKEYWORDHANDLE* phkwmodel);
SPXAPI keyword_recognition_model_create_from_config(SPXSPEECHCONFIGHANDLE hconfig, SPXKEYWORDHANDLE* phkwmodel);
SPXAPI keyword_recognition_model_add_user_defined_wake_word(SPXKEYWORDHANDLE hkwmodel, const char* wakeWord);
