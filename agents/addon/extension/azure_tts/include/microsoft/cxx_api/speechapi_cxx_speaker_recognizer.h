//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_speaker_recognizer.h: Public API declarations for speaker recognizer C++ class
//

#pragma once
#include <string>
#include <future>
#include <speechapi_cxx_common.h>

#include <speechapi_c.h>
#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_speaker_recognition_result.h>
#include <speechapi_cxx_speaker_verification_model.h>
#include <speechapi_cxx_speaker_identification_model.h>
#include <speechapi_cxx_audio_config.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Speaker {

/// <summary>
/// Perform speaker recognition.
/// Added in version 1.12.0
/// </summary>
class SpeakerRecognizer : public std::enable_shared_from_this<SpeakerRecognizer>
{
public:

    /// <summary>
    /// Create a speaker recognizer from a speech config and audio config.
    /// </summary>
    /// <param name="speechconfig">A shared smart pointer of a speech config.</param>
    /// <param name="audioInput">A shared smart pointer of a audio config.</param>
    /// <returns>A smart pointer wrapped speaker recognizer pointer.</returns>
    static std::shared_ptr<SpeakerRecognizer> FromConfig(std::shared_ptr<SpeechConfig> speechconfig, std::shared_ptr<Audio::AudioConfig> audioInput)
    {
        SPXSPEAKERIDHANDLE hSpeakerRecognizerHandle;
        SPX_THROW_ON_FAIL(::recognizer_create_speaker_recognizer_from_config(
            &hSpeakerRecognizerHandle,
            Utils::HandleOrInvalid<SPXSPEECHCONFIGHANDLE, SpeechConfig>(speechconfig),
            Utils::HandleOrInvalid<SPXAUDIOCONFIGHANDLE, Audio::AudioConfig>(audioInput)));
        return std::shared_ptr<SpeakerRecognizer>{ new SpeakerRecognizer(hSpeakerRecognizerHandle) };
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    virtual ~SpeakerRecognizer()
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

        ::speaker_recognizer_release_handle(m_hSpeakerRecognizer);
        m_hSpeakerRecognizer = SPXHANDLE_INVALID;
    }

    /// <summary>
    /// Verify the speaker in the verification model.
    /// </summary>
    /// <param name="model">A shared smart pointer of a speaker verficiation model.</param>
    /// <returns>A smart pointer wrapped speaker recognition result future.</returns>
    std::future<std::shared_ptr<SpeakerRecognitionResult>> RecognizeOnceAsync(std::shared_ptr<SpeakerVerificationModel> model)
    {
        return RunAsync<SpeakerVerificationModel, SPXSVMODELHANDLE>(speaker_recognizer_verify, model);
    }

    /// <summary>
    /// Identify the speakers in the Speaker Identification Model.
    /// </summary>
    /// <param name="model">A shared smart pointer of a speaker identification model.</param>
    /// <returns>A smart pointer wrapped speaker recognition result future.</returns>
    std::future<std::shared_ptr<SpeakerRecognitionResult>> RecognizeOnceAsync(std::shared_ptr<SpeakerIdentificationModel> model)
    {
        return RunAsync<SpeakerIdentificationModel, SPXSIMODELHANDLE>(speaker_recognizer_identify, model);
    }

protected:

    /*! \cond PROTECTED */

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hSpeakerRecognizer"> A Speaker Recognizer handle.</param>
    explicit SpeakerRecognizer(SPXSPEAKERIDHANDLE hSpeakerRecognizer) :
        m_hSpeakerRecognizer(hSpeakerRecognizer),
        m_properties(hSpeakerRecognizer),
        Properties(m_properties)
    {
        SPX_DBG_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);
    }

    /*! \endcond */

private:

    /*! \cond PRIVATE */

    SPXSPEAKERIDHANDLE m_hSpeakerRecognizer;

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXSPEAKERIDHANDLE hSpeakerRecognizer) :
            PropertyCollection(
                [=]() {
                    SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                    speaker_recognizer_get_property_bag(hSpeakerRecognizer, &hpropbag);
                    return hpropbag;
                }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

    template < class SpeakerModelPtrType, class SpeakerModelHandleType>
    inline std::future<std::shared_ptr<SpeakerRecognitionResult>> RunAsync(std::function<SPXHR(SPXSPEAKERIDHANDLE, SpeakerModelHandleType, SPXRESULTHANDLE*)> func, std::shared_ptr<SpeakerModelPtrType> model)
    {
        auto keepalive = this->shared_from_this();
        return std::async(std::launch::async, [keepalive, this, func, model]()
            {
                SPXRESULTHANDLE hResultHandle = SPXHANDLE_INVALID;
                SPX_THROW_ON_FAIL(func(m_hSpeakerRecognizer, (SpeakerModelHandleType)(*model), &hResultHandle));
                return std::shared_ptr<SpeakerRecognitionResult> { new SpeakerRecognitionResult{ hResultHandle } };
            });
    }

    /*! \endcond */

public:

    /// <summary>
    /// A collection of properties and their values defined for this <see cref="SpeakerRecognizer"/>.
    /// </summary>
    PropertyCollection& Properties;
};

} } } } // Microsoft::CognitiveServices::Speech::Speaker
