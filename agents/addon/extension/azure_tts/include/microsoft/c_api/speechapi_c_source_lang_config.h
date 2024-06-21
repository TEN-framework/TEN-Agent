//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI source_lang_config_from_language(SPXSOURCELANGCONFIGHANDLE* hconfig, const char* language);
SPXAPI source_lang_config_from_language_and_endpointId(SPXSOURCELANGCONFIGHANDLE* hconfig, const char* language, const char* endpointId);
SPXAPI_(bool) source_lang_config_is_handle_valid(SPXSOURCELANGCONFIGHANDLE hconfig);
SPXAPI source_lang_config_release(SPXSOURCELANGCONFIGHANDLE hconfig);
SPXAPI source_lang_config_get_property_bag(SPXSOURCELANGCONFIGHANDLE hconfig, SPXPROPERTYBAGHANDLE* hpropbag);
