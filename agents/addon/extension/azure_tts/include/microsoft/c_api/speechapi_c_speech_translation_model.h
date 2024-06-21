//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI speech_translation_model_handle_release(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_translation_model_get_name(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_translation_model_get_source_languages(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_translation_model_get_target_languages(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_translation_model_get_path(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_translation_model_get_version(SPXSPEECHRECOMODELHANDLE hmodel);
