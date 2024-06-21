//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//


#pragma once
#include <speechapi_c_common.h>


// Todo: Translation recognizer management API.

typedef void(*PTRANSLATIONSYNTHESIS_CALLBACK_FUNC)(SPXRECOHANDLE hreco, SPXEVENTHANDLE hevent, void* pvContext);
SPXAPI translator_synthesizing_audio_set_callback(SPXRECOHANDLE hreco, PTRANSLATIONSYNTHESIS_CALLBACK_FUNC pCallback, void* pvContext);

SPXAPI translator_add_target_language(SPXRECOHANDLE hreco, const char* language);
SPXAPI translator_remove_target_language(SPXRECOHANDLE hreco, const char* language);
