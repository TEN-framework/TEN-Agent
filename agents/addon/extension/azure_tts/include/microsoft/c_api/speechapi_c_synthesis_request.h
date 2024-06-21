//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI speech_synthesis_request_create(bool textStreamingEnabled, bool isSSML, const char* inputText, uint32_t textLength, SPXREQUESTHANDLE* hrequest);
SPXAPI speech_synthesis_request_send_text_piece(SPXREQUESTHANDLE hrequest, const char* text, uint32_t textLength);
SPXAPI speech_synthesis_request_finish(SPXREQUESTHANDLE hrequest);
SPXAPI speech_synthesis_request_handle_is_valid(SPXREQUESTHANDLE hrequest);
SPXAPI speech_synthesis_request_release(SPXREQUESTHANDLE hrequest);

SPXAPI speech_synthesis_request_get_property_bag(SPXREQUESTHANDLE hrequest, SPXPROPERTYBAGHANDLE* hpropbag);

