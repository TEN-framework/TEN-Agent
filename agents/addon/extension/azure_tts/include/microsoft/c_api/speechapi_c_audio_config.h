//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_audio_config.h: Public API declarations for audio configuration related C methods and types
//

#pragma once
#include <speechapi_c_common.h>


SPXAPI_(bool) audio_config_is_handle_valid(SPXAUDIOCONFIGHANDLE haudioConfig);
SPXAPI audio_config_create_audio_input_from_default_microphone(SPXAUDIOCONFIGHANDLE* haudioConfig);
SPXAPI audio_config_create_audio_input_from_a_microphone(SPXAUDIOCONFIGHANDLE* haudioConfig, const char* deviceName);
SPXAPI audio_config_create_audio_input_from_wav_file_name(SPXAUDIOCONFIGHANDLE* haudioConfig, const char* fileName);
SPXAPI audio_config_create_audio_input_from_stream(SPXAUDIOCONFIGHANDLE* haudioConfig, SPXAUDIOSTREAMHANDLE haudioStream);
SPXAPI audio_config_create_push_audio_input_stream(SPXAUDIOCONFIGHANDLE* haudioConfig, SPXAUDIOSTREAMHANDLE* haudioStream, SPXAUDIOSTREAMFORMATHANDLE hformat);
SPXAPI audio_config_create_pull_audio_input_stream(SPXAUDIOCONFIGHANDLE* haudioConfig, SPXAUDIOSTREAMHANDLE* haudioStream, SPXAUDIOSTREAMFORMATHANDLE hformat);
SPXAPI audio_config_create_audio_output_from_default_speaker(SPXAUDIOCONFIGHANDLE* haudioConfig);
SPXAPI audio_config_create_audio_output_from_a_speaker(SPXAUDIOCONFIGHANDLE* haudioConfig, const char* deviceName);
SPXAPI audio_config_create_audio_output_from_wav_file_name(SPXAUDIOCONFIGHANDLE* haudioConfig, const char* fileName);
SPXAPI audio_config_create_audio_output_from_stream(SPXAUDIOCONFIGHANDLE* haudioConfig, SPXAUDIOSTREAMHANDLE haudioStream);
SPXAPI audio_config_set_audio_processing_options(SPXAUDIOCONFIGHANDLE haudioConfig, SPXAUDIOPROCESSINGOPTIONSHANDLE haudioProcessingOptions);
SPXAPI audio_config_get_audio_processing_options(SPXAUDIOCONFIGHANDLE haudioConfig, SPXAUDIOPROCESSINGOPTIONSHANDLE* haudioProcessingOptions);
SPXAPI audio_config_release(SPXAUDIOCONFIGHANDLE haudioConfig);
SPXAPI audio_config_get_property_bag(SPXAUDIOCONFIGHANDLE haudioConfig, SPXPROPERTYBAGHANDLE* hpropbag);

