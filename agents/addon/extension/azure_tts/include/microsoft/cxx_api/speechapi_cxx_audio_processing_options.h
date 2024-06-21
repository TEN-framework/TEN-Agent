//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_audio_processing_options.h: Public API declarations for AudioProcessingOptions and related C++ classes
//

#pragma once
#include <vector>
#include <memory>
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_smart_handle.h>
#include <speechapi_c_audio_processing_options.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Audio {

/// <summary>
/// Types of preset microphone array geometries.
/// See [Microphone Array Recommendations](/azure/cognitive-services/speech-service/speech-devices-sdk-microphone) for more details.
/// </summary>
enum class PresetMicrophoneArrayGeometry
{
    /// <summary>
    /// Indicates that no geometry specified. Speech SDK will determine the microphone array geometry.
    /// </summary>
    Uninitialized,
    /// <summary>
    /// Indicates a microphone array with one microphone in the center and six microphones evenly spaced
    /// in a circle with radius approximately equal to 42.5 mm.
    /// </summary>
    Circular7,
    /// <summary>
    /// Indicates a microphone array with one microphone in the center and three microphones evenly spaced
    /// in a circle with radius approximately equal to 42.5 mm.
    /// </summary>
    Circular4,
    /// <summary>
    /// Indicates a microphone array with four linearly placed microphones with 40 mm spacing between them.
    /// </summary>
    Linear4,
    /// <summary>
    /// Indicates a microphone array with two linearly placed microphones with 40 mm spacing between them.
    /// </summary>
    Linear2,
    /// <summary>
    /// Indicates a microphone array with a single microphone.
    /// </summary>
    Mono,
    /// <summary>
    /// Indicates a microphone array with custom geometry.
    /// </summary>
    Custom
};

/// <summary>
/// Types of microphone arrays.
/// </summary>
enum class MicrophoneArrayType
{
    /// <summary>
    /// Indicates that the microphone array has microphones in a straight line.
    /// </summary>
    Linear,
    /// <summary>
    /// Indicates that the microphone array has microphones in a plane.
    /// </summary>
    Planar
};

/// <summary>
/// Defines speaker reference channel position in input audio.
/// </summary>
enum class SpeakerReferenceChannel
{
    /// <summary>
    /// Indicates that the input audio does not have a speaker reference channel.
    /// </summary>
    None,
    /// <summary>
    /// Indicates that the last channel in the input audio corresponds to the speaker
    /// reference for echo cancellation.
    /// </summary>
    LastChannel
};

typedef AudioProcessingOptions_MicrophoneCoordinates MicrophoneCoordinates;

/// <summary>
/// Represents the geometry of a microphone array.
/// </summary>
struct MicrophoneArrayGeometry
{
    /// <summary>
    /// Type of microphone array.
    /// </summary>
    MicrophoneArrayType microphoneArrayType;
    /// <summary>
    /// Start angle for beamforming in degrees.
    /// </summary>
    uint16_t beamformingStartAngle;
    /// <summary>
    /// End angle for beamforming in degrees.
    /// </summary>
    uint16_t beamformingEndAngle;
    /// <summary>
    /// Coordinates of microphones in the microphone array.
    /// </summary>
    std::vector<MicrophoneCoordinates> microphoneCoordinates;

    /// <summary>
    /// Creates a new instance of MicrophoneArrayGeometry.
    /// Beamforming start angle is set to zero.
    /// Beamforming end angle is set to 180 degrees if microphoneArrayType is Linear, otherwise it is set to 360 degrees.
    /// </summary>
    /// <param name="microphoneArrayType">Type of microphone array.</param>
    /// <param name="microphoneCoordinates">Coordinates of microphones in the microphone array.</param>
    MicrophoneArrayGeometry(MicrophoneArrayType microphoneArrayType, const std::vector<MicrophoneCoordinates>& microphoneCoordinates)
    {
        this->microphoneArrayType = microphoneArrayType;
        this->beamformingStartAngle = 0;
        this->beamformingEndAngle = (microphoneArrayType == MicrophoneArrayType::Linear) ? 180 : 360;
        this->microphoneCoordinates.resize(microphoneCoordinates.size());
        for (size_t i = 0; i < microphoneCoordinates.size(); i++)
        {
            this->microphoneCoordinates[i] = microphoneCoordinates[i];
        }
    }

    /// <summary>
    /// Creates a new instance of MicrophoneArrayGeometry.
    /// </summary>
    /// <param name="microphoneArrayType">Type of microphone array.</param>
    /// <param name="beamformingStartAngle">Start angle for beamforming in degrees.</param>
    /// <param name="beamformingEndAngle">End angle for beamforming in degrees.</param>
    /// <param name="microphoneCoordinates">Coordinates of microphones in the microphone array.</param>
    MicrophoneArrayGeometry(MicrophoneArrayType microphoneArrayType, uint16_t beamformingStartAngle, uint16_t beamformingEndAngle, const std::vector<MicrophoneCoordinates>& microphoneCoordinates)
    {
        this->microphoneArrayType = microphoneArrayType;
        this->beamformingStartAngle = beamformingStartAngle;
        this->beamformingEndAngle = beamformingEndAngle;
        this->microphoneCoordinates.resize(microphoneCoordinates.size());
        for (size_t i = 0; i < microphoneCoordinates.size(); i++)
        {
            this->microphoneCoordinates[i] = microphoneCoordinates[i];
        }
    }
};

/// <summary>
/// Represents audio processing options used with audio config class.
/// </summary>
class AudioProcessingOptions
{
public:

    /// <summary>
    /// Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hoptions">A handle to audio processing options.</param>
    explicit AudioProcessingOptions(SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions)
        : m_hoptions(hoptions)
    {
        SPX_THROW_ON_FAIL(audio_processing_options_get_property_bag(m_hoptions, &m_propertybag));
    }

    /// <summary>
    /// Destructs an instance of the AudioProcessingOptions class.
    /// </summary>
    ~AudioProcessingOptions() = default;

    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXAUDIOPROCESSINGOPTIONSHANDLE() const { return m_hoptions.get(); }

    /// <summary>
    /// Creates a new instance of the AudioProcessingOptions class.
    /// </summary>
    /// <param name="audioProcessingFlags">Specifies flags to control the audio processing performed by Speech SDK. It is bitwise OR of AUDIO_INPUT_PROCESSING_XXX constants.</param>
    /// <returns>The newly created AudioProcessingOptions wrapped inside a std::shared_ptr.</returns>
    /// <remarks>
    /// This function should only be used when the audio input is from a microphone array.
    /// On Windows, this function will try to query the microphone array geometry from the audio driver. Audio data is also read from speaker reference channel.
    /// On Linux, it assumes that the microphone is a single channel microphone.
    /// </remarks>
    static std::shared_ptr<AudioProcessingOptions> Create(int audioProcessingFlags)
    {
        SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(audio_processing_options_create(&hoptions, audioProcessingFlags));

        auto options = new AudioProcessingOptions(hoptions);
        return std::shared_ptr<AudioProcessingOptions>(options);
    }

    /// <summary>
    /// Creates a new instance of the AudioProcessingOptions class with preset microphone array geometry.
    /// </summary>
    /// <param name="audioProcessingFlags">Specifies flags to control the audio processing performed by Speech SDK. It is bitwise OR of AUDIO_INPUT_PROCESSING_XXX constants.</param>
    /// <param name="microphoneArrayGeometry">Specifies the type of microphone array geometry.</param>
    /// <param name="speakerReferenceChannel">Specifies the speaker reference channel position in the input audio.</param>
    /// <returns>The newly created AudioProcessingOptions wrapped inside a std::shared_ptr.</returns>
    static std::shared_ptr<AudioProcessingOptions> Create(int audioProcessingFlags, PresetMicrophoneArrayGeometry microphoneArrayGeometry, SpeakerReferenceChannel speakerReferenceChannel = SpeakerReferenceChannel::None)
    {
        SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(audio_processing_options_create_from_preset_microphone_array_geometry(&hoptions, audioProcessingFlags, (AudioProcessingOptions_PresetMicrophoneArrayGeometry)microphoneArrayGeometry, (AudioProcessingOptions_SpeakerReferenceChannel)speakerReferenceChannel));

        auto options = new AudioProcessingOptions(hoptions);
        return std::shared_ptr<AudioProcessingOptions>(options);
    }

    /// <summary>
    /// Creates a new instance of the AudioProcessingOptions class with microphone array geometry.
    /// </summary>
    /// <param name="audioProcessingFlags">Specifies flags to control the audio processing performed by Speech SDK. It is bitwise OR of AUDIO_INPUT_PROCESSING_XXX constants.</param>
    /// <param name="microphoneArrayGeometry">Specifies the microphone array geometry.</param>
    /// <param name="speakerReferenceChannel">Specifies the speaker reference channel position in the input audio.</param>
    /// <returns>The newly created AudioProcessingOptions wrapped inside a std::shared_ptr.</returns>
    static std::shared_ptr<AudioProcessingOptions> Create(int audioProcessingFlags, MicrophoneArrayGeometry microphoneArrayGeometry, SpeakerReferenceChannel speakerReferenceChannel = SpeakerReferenceChannel::None)
    {
        AudioProcessingOptions_MicrophoneArrayGeometry geometry
        {
            (AudioProcessingOptions_MicrophoneArrayType)microphoneArrayGeometry.microphoneArrayType,
            microphoneArrayGeometry.beamformingStartAngle,
            microphoneArrayGeometry.beamformingEndAngle,
            (uint16_t)microphoneArrayGeometry.microphoneCoordinates.size(),
            microphoneArrayGeometry.microphoneCoordinates.data()
        };

        SPXAUDIOPROCESSINGOPTIONSHANDLE hoptions = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(audio_processing_options_create_from_microphone_array_geometry(&hoptions, audioProcessingFlags, &geometry, (AudioProcessingOptions_SpeakerReferenceChannel)speakerReferenceChannel));

        auto options = new AudioProcessingOptions(hoptions);
        return std::shared_ptr<AudioProcessingOptions>(options);
    }

    /// <summary>
    /// Returns the type of audio processing performed by Speech SDK.
    /// </summary>
    /// <returns>Bitwise OR of AUDIO_INPUT_PROCESSING_XXX constant flags indicating the input audio processing performed by Speech SDK.</returns>
    int GetAudioProcessingFlags() const
    {
        int audioProcessingFlags;
        SPX_THROW_ON_FAIL(audio_processing_options_get_audio_processing_flags(m_hoptions, &audioProcessingFlags));
        return audioProcessingFlags;
    }

    /// <summary>
    /// Returns the microphone array geometry of the microphone used for audio input.
    /// </summary>
    /// <returns>A value of type PresetMicrophoneArrayGeometry enum.</returns>
    PresetMicrophoneArrayGeometry GetPresetMicrophoneArrayGeometry() const
    {
        PresetMicrophoneArrayGeometry microphoneArrayGeometry = PresetMicrophoneArrayGeometry::Uninitialized;
        SPX_THROW_ON_FAIL(audio_processing_options_get_preset_microphone_array_geometry(m_hoptions, (AudioProcessingOptions_PresetMicrophoneArrayGeometry*)&microphoneArrayGeometry));
        return microphoneArrayGeometry;
    }

    /// <summary>
    /// Returns the microphone array type of the microphone used for audio input.
    /// </summary>
    /// <returns>A value of type MicrophoneArrayType enum.</returns>
    MicrophoneArrayType GetMicrophoneArrayType() const
    {
        MicrophoneArrayType microphoneArrayType = MicrophoneArrayType::Linear;
        SPX_THROW_ON_FAIL(audio_processing_options_get_microphone_array_type(m_hoptions, (AudioProcessingOptions_MicrophoneArrayType*)&microphoneArrayType));
        return microphoneArrayType;
    }

    /// <summary>
    /// Returns the start angle used for beamforming.
    /// </summary>
    /// <returns>Beamforming start angle.</returns>
    uint16_t GetBeamformingStartAngle() const
    {
        uint16_t startAngle;
        SPX_THROW_ON_FAIL(audio_processing_options_get_beamforming_start_angle(m_hoptions, &startAngle));
        return startAngle;
    }

    /// <summary>
    /// Returns the end angle used for beamforming.
    /// </summary>
    /// <returns>Beamforming end angle.</returns>
    uint16_t GetBeamformingEndAngle() const
    {
        uint16_t endAngle;
        SPX_THROW_ON_FAIL(audio_processing_options_get_beamforming_end_angle(m_hoptions, &endAngle));
        return endAngle;
    }

    /// <summary>
    /// Returns the coordinates of microphones in the microphone array used for audio input.
    /// </summary>
    /// <returns>A std::vector of MicrophoneCoordinates elements.</returns>
    std::vector<MicrophoneCoordinates> GetMicrophoneCoordinates() const
    {
        uint16_t microphoneCount;
        SPX_THROW_ON_FAIL(audio_processing_options_get_microphone_count(m_hoptions, &microphoneCount));

        std::vector<MicrophoneCoordinates> microphoneCoordinates(microphoneCount);
        SPX_THROW_ON_FAIL(audio_processing_options_get_microphone_coordinates(m_hoptions, microphoneCoordinates.data(), microphoneCount));
        return microphoneCoordinates;
    }

    /// <summary>
    /// Returns the speaker reference channel position in the audio input.
    /// </summary>
    /// <returns>A value of type SpeakerReferenceChannel enum.</returns>
    SpeakerReferenceChannel GetSpeakerReferenceChannel() const
    {
        SpeakerReferenceChannel speakerReferenceChannel = SpeakerReferenceChannel::None;
        SPX_THROW_ON_FAIL(audio_processing_options_get_speaker_reference_channel(m_hoptions, (AudioProcessingOptions_SpeakerReferenceChannel*)&speakerReferenceChannel));
        return speakerReferenceChannel;
    }

    /// <summary>
    /// Sets a property value by name.
    /// </summary>
    /// <param name="name">The property name.</param>
    /// <param name="value">The property value.</param>
    void SetProperty(const SPXSTRING& name, const SPXSTRING& value)
    {
        property_bag_set_string(m_propertybag, -1, Utils::ToUTF8(name).c_str(), Utils::ToUTF8(value).c_str());
    }

    /// <summary>
    /// Gets a property value by name.
    /// </summary>
    /// <param name="name">The parameter name.</param>
    /// <returns>The property value.</returns>
    SPXSTRING GetProperty(const SPXSTRING& name) const
    {
        const char* value = property_bag_get_string(m_propertybag, -1, Utils::ToUTF8(name).c_str(), "");
        return Utils::ToSPXString(Utils::CopyAndFreePropertyString(value));
    }

private:

    DISABLE_COPY_AND_MOVE(AudioProcessingOptions);

    /// <summary>
    /// Internal member variable that holds the smart handle.
    /// </summary>
    SmartHandle<SPXAUDIOPROCESSINGOPTIONSHANDLE, &audio_processing_options_release> m_hoptions;

    /// <summary>
    /// Internal member variable that holds the properties of the audio processing options.
    /// </summary>
    SmartHandle<SPXPROPERTYBAGHANDLE, &property_bag_release> m_propertybag;
};

} } } } // Microsoft::CognitiveServices::Speech::Audio
