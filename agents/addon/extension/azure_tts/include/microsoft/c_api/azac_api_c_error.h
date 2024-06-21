//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/vision/license for the full license information.
//

#pragma once

// TODO: TFS#3671215 - Vision: C/C++ azac_api* files are in shared include directory, speech and vision share

#ifndef AZAC_SUPPRESS_COMMON_INCLUDE_FROM_ERROR
#define AZAC_SUPPRESS_ERROR_INCLUDE_FROM_COMMON
#include <azac_api_c_common.h>
#undef AZAC_SUPPRESS_ERROR_INCLUDE_FROM_COMMON
#endif

typedef const char * const_char_ptr;

AZAC_API_(const_char_ptr) error_get_message(AZAC_HANDLE errorHandle);

AZAC_API_(const_char_ptr) error_get_call_stack(AZAC_HANDLE errorHandle);

AZAC_API error_get_error_code(AZAC_HANDLE errorHandle);

AZAC_API error_release(AZAC_HANDLE errorHandle);
