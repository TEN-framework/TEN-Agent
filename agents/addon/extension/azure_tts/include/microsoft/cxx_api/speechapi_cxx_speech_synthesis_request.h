//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speech_config.h: Public API declarations for SpeechConfig C++ class
//
#pragma once

#include <string>

#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c_common.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Class that defines the speech synthesis request.
/// This class is in preview and is subject to change.
/// Added in version 1.37.0
/// </summary>
class SpeechSynthesisRequest
{
public:

    /// <summary>
    /// Represents an input stream for speech synthesis request.
    /// Note: This class is in preview and may be subject to change in future versions.
    /// Added in version 1.37.0
    /// </summary>
    class InputStream
    {
    public:
        friend class SpeechSynthesisRequest;
        /// <summary>
        /// Send a piece of text to the speech synthesis service to be synthesized.
        /// </summary>
        /// <param name="text">The text piece to be synthesized.</param>
        void Write(const std::string &text)
        {
            m_parent.SendTextPiece(text);
        }

        /// <summary>
        /// Finish the text input.
        /// </summary>
        void Close()
        {
            m_parent.FinishInput();
        }

    private:
        InputStream(SpeechSynthesisRequest& parent)
            : m_parent(parent)
        {
        }
        SpeechSynthesisRequest& m_parent;
        DISABLE_COPY_AND_MOVE(InputStream);
    };

    /// <summary>
    /// Internal operator used to get underlying handle value.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXREQUESTHANDLE() const { return m_hrequest; }

    /// <summary>
    /// Creates a speech synthesis request, which text streaming is enabled.
    /// </summary>
    /// <returns>A shared pointer to the new speech synthesis request instance.</returns>
    static std::shared_ptr<SpeechSynthesisRequest> NewTextStreamingRequest()
    {
        SPXREQUESTHANDLE hrequest = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(speech_synthesis_request_create(true, false, nullptr, 0, &hrequest));

        auto ptr = new SpeechSynthesisRequest(hrequest);
        return std::shared_ptr<SpeechSynthesisRequest>(ptr);
    }

    // void SetPersonalVoicePromptAudio(const uint8_t* audioData, uint32_t audioSize)
    // {
    //     SPXREQUESTHANDLE hrequest = SPXHANDLE_INVALID;
    //     SPX_THROW_ON_FAIL(speech_synthesis_request_create_from_personal_voice_prompt_audio_data(audioData, audioSize, &hrequest));
    // }

    /// <summary>
    /// Gets the input stream for the speech synthesis request.
    /// </summary>
    InputStream& GetInputStream()
    {
        return m_inputStream;
    }

    /// <summary>
    /// Destructs the object.
    /// </summary>
    virtual ~SpeechSynthesisRequest()
    {
        speech_synthesis_request_release(m_hrequest);
        property_bag_release(m_propertybag);
    }

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    explicit SpeechSynthesisRequest(SPXREQUESTHANDLE hrequest)
        :m_hrequest(hrequest),
        m_inputStream(*this)
        {
            SPX_THROW_ON_FAIL(speech_synthesis_request_get_property_bag(hrequest, &m_propertybag));
        }

    /// <summary>
    /// Internal member variable that holds the speech synthesis request handle.
    /// </summary>
    SPXREQUESTHANDLE m_hrequest;

    /// <summary>
    /// Internal member variable that holds the properties of the speech synthesis request.
    /// </summary>
    SPXPROPERTYBAGHANDLE m_propertybag;

    InputStream m_inputStream;

    /// <summary>
    /// Send a piece of text to the speech synthesis service to be synthesized, used in text streaming mode.
    /// </summary>
    /// <param name="text">The text piece to be synthesized.</param>
    void SendTextPiece(const SPXSTRING& text)
    {
        auto u8text = Utils::ToUTF8(text);
        SPX_THROW_ON_FAIL(speech_synthesis_request_send_text_piece(m_hrequest, u8text.c_str(), static_cast<uint32_t>(u8text.length())));
    }

    /// <summary>
    /// Finish the text input, used in text streaming mode.
    /// </summary>
    void FinishInput()
    {
        SPX_THROW_ON_FAIL(speech_synthesis_request_finish(m_hrequest));
    }

    /*! \endcond */

private:
    DISABLE_COPY_AND_MOVE(SpeechSynthesisRequest);

    };

}}}
