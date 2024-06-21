//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>
#include <speechapi_c_speech_config.h>
#include <speechapi_c_speech_recognition_model.h>
#include <speechapi_c_speech_translation_model.h>

SPXAPI embedded_speech_config_create(SPXSPEECHCONFIGHANDLE* hconfig);
SPXAPI embedded_speech_config_add_path(SPXSPEECHCONFIGHANDLE hconfig, const char* path);
SPXAPI embedded_speech_config_get_num_speech_reco_models(SPXSPEECHCONFIGHANDLE hconfig, uint32_t* numModels);
SPXAPI embedded_speech_config_get_speech_reco_model(SPXSPEECHCONFIGHANDLE hconfig, uint32_t index, SPXSPEECHRECOMODELHANDLE* hmodel);
SPXAPI embedded_speech_config_get_num_speech_translation_models(SPXSPEECHCONFIGHANDLE hconfig, uint32_t* numModels);
SPXAPI embedded_speech_config_get_speech_translation_model(SPXSPEECHCONFIGHANDLE hconfig, uint32_t index, SPXSPEECHRECOMODELHANDLE* hmodel);
