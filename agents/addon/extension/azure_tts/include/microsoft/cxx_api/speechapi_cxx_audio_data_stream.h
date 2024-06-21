//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_audio_data_stream.h: Public API declarations for AudioDataStream C++ class
//

#pragma once

#include <memory>

#include <speechapi_cxx_common.h>
#include <speechapi_cxx_smart_handle.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_utils.h>
#include <speechapi_c_audio_stream.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

class SpeechSynthesisResult;
class KeywordRecognitionResult;

/// <summary>
/// Represents audio data stream used for operating audio data as a stream.
/// Added in version 1.4.0
/// </summary>
class AudioDataStream : public std::enable_shared_from_this<AudioDataStream>
{
private:

    /// <summary>
    /// Internal member variable that holds the smart handle.
    /// </summary>
    SmartHandle<SPXAUDIOSTREAMHANDLE, &audio_data_stream_release> m_haudioStream;

    /*! \cond PRIVATE */

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXAUDIOSTREAMHANDLE hstream) :
            PropertyCollection(
                [=]() {
            SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
            audio_data_stream_get_property_bag(hstream, &hpropbag);
            return hpropbag;
        }())
        {
        }
    };

    /// <summary>
    /// Internal member variable that holds the properties associating to the audio data stream.
    /// </summary>
    PrivatePropertyCollection m_properties;

    /*! \endcond */

public:

    /// <summary>
    /// Destroy the instance.
    /// </summary>
    ~AudioDataStream()
    {
        DetachInput();
    }

    /// <summary>
    /// Creates a memory backed AudioDataStream for the specified audio input file.
    /// Added in version 1.14.0
    /// </summary>
    /// <param name="fileName">Specifies the audio input file.</param>
    /// <returns>A shared pointer to AudioDataStream</returns>
    static std::shared_ptr<AudioDataStream> FromWavFileInput(const SPXSTRING& fileName)
    {
        SPXAUDIOSTREAMHANDLE hstream = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(audio_data_stream_create_from_file(&hstream, Utils::ToUTF8(fileName).c_str()));

        auto stream = new AudioDataStream(hstream);
        return std::shared_ptr<AudioDataStream>(stream);
    }

    /// <summary>
    /// Creates a memory backed AudioDataStream from given speech synthesis result.
    /// </summary>
    /// <param name="result">The speech synthesis result.</param>
    /// <returns>A shared pointer to AudioDataStream</returns>
    static std::shared_ptr<AudioDataStream> FromResult(std::shared_ptr<SpeechSynthesisResult> result);

    /// <summary>
    /// Obtains the memory backed AudioDataStream associated with a given KeywordRecognition result.
    /// </summary>
    /// <param name="result">The keyword recognition result.</param>
    /// <returns>An audio stream with the input to the KeywordRecognizer starting from right before the Keyword.</returns>
    static std::shared_ptr<AudioDataStream> FromResult(std::shared_ptr<KeywordRecognitionResult> result);

    /// <summary>
    /// Get current status of the audio data stream.
    /// </summary>
    /// <returns>Current status</returns>
    StreamStatus GetStatus()
    {
        Stream_Status status = StreamStatus_Unknown;
        SPX_THROW_ON_FAIL(audio_data_stream_get_status(m_haudioStream, &status));
        return (StreamStatus)status;
    }

    /// <summary>
    /// Check whether the stream has enough data to be read.
    /// </summary>
    /// <param name="bytesRequested">The requested data size in bytes.</param>
    /// <returns>A bool indicating whether the stream has enough data to be read.</returns>
    bool CanReadData(uint32_t bytesRequested)
    {
        return audio_data_stream_can_read_data(m_haudioStream, bytesRequested);
    }

    /// <summary>
    /// Check whether the stream has enough data to be read, starting from the specified position.
    /// </summary>
    /// <param name="pos">The position counting from start of the stream.</param>
    /// <param name="bytesRequested">The requested data size in bytes.</param>
    /// <returns>A bool indicating whether the stream has enough data to be read.</returns>
    bool CanReadData(uint32_t pos, uint32_t bytesRequested)
    {
        return audio_data_stream_can_read_data_from_position(m_haudioStream, bytesRequested, pos);
    }

    /// <summary>
    /// Reads a chunk of the audio data and fill it to given buffer
    /// </summary>
    /// <param name="buffer">A buffer to receive read data.</param>
    /// <param name="bufferSize">Size of the buffer.</param>
    /// <returns>Size of data filled to the buffer, 0 means end of stream</returns>
    uint32_t ReadData(uint8_t* buffer, uint32_t bufferSize)
    {
        uint32_t filledSize = 0;
        SPX_THROW_ON_FAIL(audio_data_stream_read(m_haudioStream, buffer, bufferSize, &filledSize));

        return filledSize;
    }

    /// <summary>
    /// Reads a chunk of the audio data and fill it to given buffer, starting from the specified position.
    /// </summary>
    /// <param name="pos">The position counting from start of the stream.</param>
    /// <param name="buffer">A buffer to receive read data.</param>
    /// <param name="bufferSize">Size of the buffer.</param>
    /// <returns>Size of data filled to the buffer, 0 means end of stream</returns>
    uint32_t ReadData(uint32_t pos, uint8_t* buffer, uint32_t bufferSize)
    {
        uint32_t filledSize = 0;
        SPX_THROW_ON_FAIL(audio_data_stream_read_from_position(m_haudioStream, buffer, bufferSize, pos, &filledSize));

        return filledSize;
    }

    /// <summary>
    /// Save the audio data to a file, synchronously.
    /// </summary>
    /// <param name="fileName">The file name with full path.</param>
    void SaveToWavFile(const SPXSTRING& fileName)
    {
        SPX_THROW_ON_FAIL(audio_data_stream_save_to_wave_file(m_haudioStream, Utils::ToUTF8(fileName).c_str()));
    }

    /// <summary>
    /// Save the audio data to a file, asynchronously.
    /// </summary>
    /// <param name="fileName">The file name with full path.</param>
    /// <returns>An asynchronous operation representing the saving.</returns>
    std::future<void> SaveToWavFileAsync(const SPXSTRING& fileName)
    {
        auto keepAlive = this->shared_from_this();

        auto future = std::async(std::launch::async, [keepAlive, this, fileName]() -> void {
            SPX_THROW_ON_FAIL(audio_data_stream_save_to_wave_file(m_haudioStream, Utils::ToUTF8(fileName).c_str()));
        });

        return future;
    }

    /// <summary>
    /// Get current position of the audio data stream.
    /// </summary>
    /// <returns>Current position</returns>
    uint32_t GetPosition()
    {
        uint32_t position = 0;
        SPX_THROW_ON_FAIL(audio_data_stream_get_position(m_haudioStream, &position));
        return position;
    }

    /// <summary>
    /// Set current position of the audio data stream.
    /// </summary>
    /// <param name="pos">Position to be set.</param>
    void SetPosition(uint32_t pos)
    {
        SPX_THROW_ON_FAIL(audio_data_stream_set_position(m_haudioStream, pos));
    }

    /// <summary>
    /// Stops any more data from getting to the stream.
    /// </summary>
    void DetachInput()
    {
        SPX_THROW_ON_FAIL(audio_data_stream_detach_input(m_haudioStream));
    }

    /// <summary>
    /// Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXAUDIOSTREAMHANDLE() { return m_haudioStream; }

    /// <summary>
    /// Collection of additional SpeechSynthesisResult properties.
    /// </summary>
    const PropertyCollection& Properties;

private:

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    explicit AudioDataStream(SPXAUDIOSTREAMHANDLE haudioStream) :
        m_haudioStream(haudioStream),
        m_properties(haudioStream),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }
};

} } } // Microsoft::CognitiveServices::Speech
