//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include "speechapi_c_common.h"

const char CODECCREATEEXPORTNAME[] = "codec_create";
struct codec_c_interface;
typedef struct codec_c_interface* codec_c_interface_P;
typedef codec_c_interface_P SPXCODECCTYPE;

/*! \cond INTERNAL */

/**
 * The SPX_CODEC_CLIENT_GET_PROPERTY represents the function reading a property value
 * @param id Property id.
 * @param buffer caller provided buffer to receive the value of the property
 * @param buffersize buffer size. If buffer is passed as null it will return the required buffer size.
 * @param codecContext A pointer to caller data provided through the codec_create call.
 * @return A return code or zero if successful.
 */
typedef SPXAPI_RESULTTYPE (SPXAPI_CALLTYPE *SPX_CODEC_CLIENT_GET_PROPERTY)(const char* id, char* buffer, uint64_t* buffersize, void* codecContext);

/**
 * The AUDIO_ENCODER_ONENCODEDDATA type represents an application-defined
 * status callback function used to provide the encoded data.
 * @param pBuffer audio data buffer.
 * @param bytesToWrite The length of pBuffer in bytes.
 * @param duration_100nanos The duration of the audio sample
 * @param pContext A pointer to the application-defined callback context.
 */
typedef void(SPXAPI_CALLTYPE *AUDIO_ENCODER_ONENCODEDDATA)(const uint8_t* pBuffer, size_t bytesToWrite, uint64_t duration_100nanos, void* pContext);

struct codec_c_interface
{
    /**
    * @param codec codec Object returned by the codec_create call to be initialized
    * @param inputSamplesPerSecond sample rate for the input audio
    * @param inputBitsPerSample bits per sample for the input audio
    * @param inputChannels number of channel of the input audio
    * @param dataCallback An application defined callback.
    * @param pContext A pointer to the application-defined callback context.
    * @return A return code or zero if successful.
    */
    SPXAPI_RESULTTYPE (SPXAPI_CALLTYPE *init)(
                                        SPXCODECCTYPE codec,
                                        uint32_t inputSamplesPerSecond,
                                        uint8_t inputBitsPerSample,
                                        uint8_t inputChannels,
                                        AUDIO_ENCODER_ONENCODEDDATA datacallback,
                                        void* pContext);

    /**
    * @param codec codec object returned by the codec_create call.
    * @param buffer caller provided buffer to receive the value of the property
    * @param buffersize buffer size. If buffer is passed as null it will return the required buffer size.
    * @return A return code or zero if successful.
    */
    SPXAPI_RESULTTYPE (SPXAPI_CALLTYPE* get_format_type)(SPXCODECCTYPE codec, char* buffer, uint64_t* buffersize);

    /**
     * Encodes raw PCM data.
     * @param codec codec object returned by the codec_create call.
     * @param pBuffer The PCM data.
     * @param bytesToWrite The length pBuffer.
     * @return A return code or zero if successful.
     */
    SPXAPI_RESULTTYPE (SPXAPI_CALLTYPE *encode) (SPXCODECCTYPE codec, const uint8_t* pBuffer, size_t bytesToWrite);

    /**
     * Flushes the encoder.
     * @param codec codec object returned by the codec_create call.
     * @return A return code or zero if successful.
     */
    SPXAPI_RESULTTYPE(SPXAPI_CALLTYPE* flush)(SPXCODECCTYPE codec);

    /**
     * Terminate the encoded stream immediately
     * @param codec codec object returned by the codec_create call.
     * @return A return code or zero if successful.
     */
    SPXAPI_RESULTTYPE (SPXAPI_CALLTYPE *endstream)(SPXCODECCTYPE codec);

    /**
     * Destroys the encoder. The codec object should not be used anymore after this call.
     * @param codec codec object returned by the codec_create call.
     * @return A return code or zero if successful.
     */
    SPXAPI_RESULTTYPE (SPXAPI_CALLTYPE *destroy) (SPXCODECCTYPE codec);
};

/**
* Creates a codec object. This method needs to be exported from the dll
* @param codecid - codec id, can be null or empty if the library implements only one codec.
* @param codecContext - context to be used to call back to the caller
* @param property_read_func - function to read properties
* @return A codec object
*/

SPX_EXTERN_C SPXDLL_EXPORT SPXCODECCTYPE codec_create(const char* codecid, void* codecContext, SPX_CODEC_CLIENT_GET_PROPERTY property_read_func);
typedef SPXCODECCTYPE (*PCODEC_CREATE_FUNC)(const char* codecid, void* codecContext, SPX_CODEC_CLIENT_GET_PROPERTY property_read_func);

/*! \endcond */
