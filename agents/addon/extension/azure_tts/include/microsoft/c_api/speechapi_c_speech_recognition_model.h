//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI speech_recognition_model_handle_release(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_recognition_model_get_name(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_recognition_model_get_locales(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_recognition_model_get_path(SPXSPEECHRECOMODELHANDLE hmodel);
SPXAPI__(const char*) speech_recognition_model_get_version(SPXSPEECHRECOMODELHANDLE hmodel);
