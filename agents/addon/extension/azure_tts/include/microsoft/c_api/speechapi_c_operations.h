//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_operations.h: Public API declaration for common operation methods in the C API layer.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI speechapi_async_handle_release(SPXASYNCHANDLE h_async);
SPXAPI speechapi_async_wait_for(SPXASYNCHANDLE h_async, uint32_t milliseconds);
