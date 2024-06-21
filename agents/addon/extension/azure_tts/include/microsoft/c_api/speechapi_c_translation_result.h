//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI translation_text_result_get_translation_count(SPXRESULTHANDLE handle, size_t * size);
SPXAPI translation_text_result_get_translation(SPXRESULTHANDLE handle, size_t index, char * language, char * text, size_t * language_size, size_t * text_size);

// audioBuffer: point to the header for storing synthesis audio data. The parameter lengthPointer points to the variable saving the size of buffer. On return, *lengthPointer is set to the size of the buffer returned.
// If textBuffer is nullptr or the length is smaller than the size required, the function returns SPXERR_BUFFER_TOO_SMALL.
SPXAPI translation_synthesis_result_get_audio_data(SPXRESULTHANDLE handle, uint8_t* audioBuffer, size_t* lengthPointer);
