//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_session.h: Public API declarations for Session related C methods
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI session_from_recognizer(SPXRECOHANDLE hreco, SPXSESSIONHANDLE* phsession);

SPXAPI_(bool) session_handle_is_valid(SPXSESSIONHANDLE hsession);
SPXAPI session_handle_release(SPXSESSIONHANDLE hsession);

SPXAPI session_get_property_bag(SPXSESSIONHANDLE hsession, SPXPROPERTYBAGHANDLE* hpropbag);
