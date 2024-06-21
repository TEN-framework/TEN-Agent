//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_dialog_service_config.h: Public API declarations for dialog service connector configuration related C methods and types
//
#pragma once

#include <speechapi_c_common.h>

SPXAPI bot_framework_config_from_subscription(SPXSPEECHCONFIGHANDLE* ph_config, const char* subscription, const char* region, const char *bot_Id);
SPXAPI bot_framework_config_from_authorization_token(SPXSPEECHCONFIGHANDLE* ph_config, const char* auth_token, const char* region, const char* bot_Id);

SPXAPI custom_commands_config_from_subscription(SPXSPEECHCONFIGHANDLE* ph_dialog_service_config, const char* app_id, const char *subscription, const char* region);
SPXAPI custom_commands_config_from_authorization_token(SPXSPEECHCONFIGHANDLE* ph_dialog_service_config, const char* app_id, const char *auth_token, const char* region);
