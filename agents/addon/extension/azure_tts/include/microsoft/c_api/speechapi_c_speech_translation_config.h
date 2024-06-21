//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI speech_translation_config_from_subscription(SPXSPEECHCONFIGHANDLE* configHandle, const char* subscription, const char* region);
SPXAPI speech_translation_config_from_authorization_token(SPXSPEECHCONFIGHANDLE* configHandle, const char* authToken, const char* region);
SPXAPI speech_translation_config_from_endpoint(SPXSPEECHCONFIGHANDLE* configHandle, const char* endpoint, const char* subscription);
SPXAPI speech_translation_config_from_host(SPXSPEECHCONFIGHANDLE* configHandle, const char* host, const char* subscription);

SPXAPI speech_translation_config_add_target_language(SPXSPEECHCONFIGHANDLE configHandle, const char* language);
SPXAPI speech_translation_config_remove_target_language(SPXSPEECHCONFIGHANDLE configHandle, const char* language);
