//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_audio_processing_options.h: Public API declarations for audio processing options related C methods and types
//

#pragma once
#include <speechapi_c_common.h>

/// <summary>
/// Types of preset microphone array geometries.
/// See [Microphone Array Recommendations](/azure/cognitive-services/speech-service/speech-devices-sdk-microphone) for more details.
/// </summary>
typedef enum
{
    /// <summary>
    /// Indicates that no geometry specified. Speech SDK will determine the microphone array geometry.
    /// </summary>
    AudioProcessingOptions_PresetMicrophoneArrayGeometry_Uninitialized,
    /// <summary>
    /// Indicates a microphone array with one microphone in the center and six microphones evenly spaced
    /// in a circle with radius approximately equal to 42.5 mm.
    /// </summary>
    AudioProcessingOptions_PresetMicrophoneArrayGeometry_Circular7,
    /// <summary>
    /// Indicates a microphone array with one microphone in the center and three microphones evenly spaced
    /// in a circle with radius approximately equal to 42.5 mm.
    /// </summary>
    AudioProcessingOptions_PresetMicrophoneArrayGeometry_Circular4,
    /// <summary>
    /// Indicates a microphone array with four linearly placed microphones with 40 mm spacing between them.
    /// </summary>
    AudioProcessingOptions_PresetMicrophoneArrayGeometry_Linear4,
    /// <summary>
    /// Indicates a microphone array with two linearly placed microphones with 40 mm spacing between them.
    /// </summary>
    AudioProcessingOptions_PresetMicrophoneArrayGeometry_Linear2,
    /// <summary>
    /// Indicates a microphone array with a single microphone.
    /// </summary>
    AudioProcessingOptions_PresetMicrophoneArrayGeometry_Mono,
    /// <summary>
    /// Indicates a microphone array with custom geometry.
    /// </summary>
    AudioProcessingOptions_PresetMicrophoneArrayGeometry_Custom
} AudioProcessingOptions_PresetMicrophoneArrayGeometry;

/// <summary>
/// Types of microphone arrays.
/// </summary>
typedef enum
{
    AudioProcessingOptions_MicrophoneArrayType_Linear,
    AudioProcessingOptions_MicrophoneArrayType_Planar
} AudioProcessingOptions_MicrophoneArrayType;

/// <summary>
/// Defines speaker reference channel position in input audio.
/// </summary>
typedef enum
{
    /// <summary>
    /// Indicates that the input audio does not have a speaker reference channel.
    /// </summary>
    AudioProcessingOptions_SpeakerReferenceChannel_None,
    /// <summary>
    /// Indicates that the last channel in the input audio corresponds to the speaker
    /// reference for echo cancellation.
    /// </summary>
    AudioProcessingOptions_SpeakerReferenceChannel_LastChannel
} AudioProcessingOptions_SpeakerReferenceChannel;

#pragma pack(push, 1)

/// <summary>
/// Represents coordinates of a microphone.
/// </summary>
typedef struct
{
    /// <summary>
    /// X-coordinate of the microphone in millimeters.
    /// </summary>
    int X;
    /// <summary>
    /// Y-coordinate of the microphone in millimeters.
    /// </summary>
    int Y;
    /// <summary>
    /// Z-coordinate of the microphone in millimeters.
    /// </summary>
    int Z;
} AudioProcessingOptions_MicrophoneCoordinates;

/// <summary>
/// Represents the geometry of a microphone array.
/// </summary>
typedef struct
{
    /// <summary>
    /// Type of microphone array.
    /// </summary>
    AudioProcessingOptions_MicrophoneArrayType microphoneArrayType;
    /// <summary>
    /// Start angle for beamforming in degrees.
    /// </summary>
    uint16_t beamformingStartAngle;
    /// <summary>
    /// End angle for beamforming in degrees.
    /// </summary>
    uint16_t beamformingEndAngle;
    /// <summary>
    /// Number of microphones in the microphone array.
    /// </summary>
    uint16_t numberOfMicrophones;
    /// <summary>
    /// Coordinates of microphones in the microphone array.
    /// </summary>
    AudioProcessingOptions_MicrophoneCoordinates* microphoneCoordinates;
} AudioProcessingOptions_MicrophoneArrayGeometry;

#pragma pack(pop)

/// <summary>
/// Disables built-in input audio processing.
/// </summary>
const int AUDIO_INPUT_PROCESSING_NONE = 0x00000000;
/// <summary>
/// Enables default built-in input audio processing.
/// </summary>
const int AUDIO_INPUT_PROCESSING_ENABLE_DEFAULT = 0x00000001;
/// <summary>
/// Disables dereverberation in the default audio processing pipeline.
/// </summary>
const int AUDIO_INPUT_PROCESSING_DISABLE_DEREVERBERATION = 0x00000002;
/// <summary>
/// Disables noise suppression in the default audio processing pipeline.
/// </summary>
const int AUDIO_INPUT_PROCESSING_DISABLE_NOISE_SUPPRESSION = 0x00000004;
/// <summary>
/// Disables automatic gain control in the default audio processing pipeline.
/// </summary>
const int AUDIO_INPUT_PROCESSING_DISABLE_GAIN_CONTROL = 0x00000008;
/// <summary>
/// Disables echo cancellation in the default audio processing pipeline.
/// </summary>
const int AUDIO_INPUT_PROCESSING_DISABLE_ECHO_CANCELLATION = 0x00000010;
/// <summary>
/// Enables voice activity detection in input audio processing.
/// </summary>
const int AUDIO_INPUT_PROCESSING_ENABLE_VOICE_ACTIVITY_DETECTION = 0x00000020;
/// <summary>
/// Enables the new version (V2) of input audio processing with improved echo cancellation performance.
/// This flag is mutually exclusive with AUDIO_INPUT_PROCESSING_ENABLE_DEFAULT flag.
/// AUDIO_INPUT_PROCESSING_DISABLE_* flags do not affect this pipeline.
/// This feature is currently in preview and only available for Windows x64 and ARM64 platform.
/// </summary>
const int AUDIO_INPUT_PROCESSING_ENABLE_V2 = 0x00000040;

SPXAPI_(bool) audio_processing_options_is_handle_valid(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions);
SPXAPI audio_processing_options_create(SPXAUDIOPROCESSINGOPTIONSHANDLE* hoptions, int audioProcessingFlags);
SPXAPI audio_processing_options_create_from_preset_microphone_array_geometry(SPXAUDIOPROCESSINGOPTIONSHANDLE* hoptions, int audioProcessingFlags, AudioProcessingOptions_PresetMicrophoneArrayGeometry microphoneArrayGeometry, AudioProcessingOptions_SpeakerReferenceChannel speakerReferenceChannel);
SPXAPI audio_processing_options_create_from_microphone_array_geometry(SPXAUDIOPROCESSINGOPTIONSHANDLE* hoptions, int audioProcessingFlags, const AudioProcessingOptions_MicrophoneArrayGeometry* microphoneArrayGeometry, AudioProcessingOptions_SpeakerReferenceChannel speakerReferenceChannel);
SPXAPI audio_processing_options_get_audio_processing_flags(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, int* audioProcessingFlags);
SPXAPI audio_processing_options_get_preset_microphone_array_geometry(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, AudioProcessingOptions_PresetMicrophoneArrayGeometry* microphoneArrayGeometry);
SPXAPI audio_processing_options_get_microphone_array_type(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, AudioProcessingOptions_MicrophoneArrayType* microphoneArrayType);
SPXAPI audio_processing_options_get_beamforming_start_angle(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, uint16_t* startAngle);
SPXAPI audio_processing_options_get_beamforming_end_angle(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, uint16_t* endAngle);
SPXAPI audio_processing_options_get_microphone_count(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, uint16_t* microphoneCount);
SPXAPI audio_processing_options_get_microphone_coordinates(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, AudioProcessingOptions_MicrophoneCoordinates* microphoneCoordinates, uint16_t microphoneCount);
SPXAPI audio_processing_options_get_speaker_reference_channel(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, AudioProcessingOptions_SpeakerReferenceChannel* speakerReferenceChannel);
SPXAPI audio_processing_options_release(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions);
SPXAPI audio_processing_options_get_property_bag(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions, SPXPROPERTYBAGHANDLE* hpropbag);
