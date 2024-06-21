//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_user.h: Public API declarations for user related C methods and enumerations
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI user_create_from_id(const char* user_id, SPXUSERHANDLE* huser);
SPXAPI user_release_handle(SPXUSERHANDLE huser);
SPXAPI user_get_id(SPXUSERHANDLE huser, char* user_id, size_t user_id_size);
