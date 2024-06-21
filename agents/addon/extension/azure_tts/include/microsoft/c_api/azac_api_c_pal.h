//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/license202106 for the full license information.
//

#pragma once

// TODO: TFS#3671215 - Vision: C/C++ azac_api* files are in shared include directory, speech and vision share

#include "azac_api_c_common.h"

AZAC_API_(size_t) pal_wstring_to_string(char * dst, const wchar_t * src, size_t dstSize);
AZAC_API_(size_t) pal_string_to_wstring(wchar_t * dst, const char * src, size_t dstSize);