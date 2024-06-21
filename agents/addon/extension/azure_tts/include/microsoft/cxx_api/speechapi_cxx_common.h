//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_common.h: Public API declarations for global C++ APIs/namespaces
//

#pragma once

#include <speechapi_c_common.h>
#include <speechapi_c_error.h>
#include <spxerror.h>
#include <azac_api_cxx_common.h> // must include after spxdebug.h or speechapi*.h (can NOT be included before)

#define DISABLE_COPY_AND_MOVE(T)    AZAC_DISABLE_COPY_AND_MOVE(T)
#define DISABLE_DEFAULT_CTORS(T)    AZAC_DISABLE_DEFAULT_CTORS(T)
