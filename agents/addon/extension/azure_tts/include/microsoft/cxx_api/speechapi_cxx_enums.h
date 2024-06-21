//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_enums.h: Public API declarations for C++ enumerations
//

#pragma once

#include <string>
#include <speechapi_cxx_common.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

constexpr const char* TrueString = "true";
constexpr const char* FalseString = "false";
constexpr const char CommaDelim = ',';

/// <summary>
/// Defines speech property ids.
/// Changed in version 1.4.0.
/// </summary>
enum class PropertyId
{
    /// <summary>
    /// The Cognitive Services Speech Service subscription key. If you are using an intent recognizer, you need
    /// to specify the LUIS endpoint key for your particular LUIS app. Under normal circumstances, you shouldn't
    /// have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::FromSubscription"/>.
    /// </summary>
    SpeechServiceConnection_Key = 1000,

    /// <summary>
    /// The Cognitive Services Speech Service endpoint (url). Under normal circumstances, you shouldn't
    /// have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::FromEndpoint"/>.
    /// NOTE: This endpoint is not the same as the endpoint used to obtain an access token.
    /// </summary>
    SpeechServiceConnection_Endpoint = 1001,

    /// <summary>
    /// The Cognitive Services Speech Service region. Under normal circumstances, you shouldn't have to
    /// use this property directly.
    /// Instead, use <see cref="SpeechConfig::FromSubscription"/>, <see cref="SpeechConfig::FromEndpoint"/>,
    /// <see cref="SpeechConfig::FromHost"/>, <see cref="SpeechConfig::FromAuthorizationToken"/>.
    /// </summary>
    SpeechServiceConnection_Region = 1002,

    /// <summary>
    /// The Cognitive Services Speech Service authorization token (aka access token). Under normal circumstances,
    /// you shouldn't have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::FromAuthorizationToken"/>,
    /// <see cref="SpeechRecognizer::SetAuthorizationToken"/>, <see cref="IntentRecognizer::SetAuthorizationToken"/>,
    /// <see cref="TranslationRecognizer::SetAuthorizationToken"/>.
    /// </summary>
    SpeechServiceAuthorization_Token = 1003,

    /// <summary>
    /// The Cognitive Services Speech Service authorization type. Currently unused.
    /// </summary>
    SpeechServiceAuthorization_Type = 1004,

    /// <summary>
    /// The Cognitive Services Custom Speech or Custom Voice Service endpoint id. Under normal circumstances, you shouldn't
    /// have to use this property directly.
    /// Instead use <see cref="SpeechConfig::SetEndpointId"/>.
    /// NOTE: The endpoint id is available in the Custom Speech Portal, listed under Endpoint Details.
    /// </summary>
    SpeechServiceConnection_EndpointId = 1005,

    /// <summary>
    /// The Cognitive Services Speech Service host (url). Under normal circumstances, you shouldn't
    /// have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::FromHost"/>.
    /// </summary>
    SpeechServiceConnection_Host = 1006,

    /// <summary>
    /// The host name of the proxy server used to connect to the Cognitive Services Speech Service. Under normal circumstances,
    /// you shouldn't have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::SetProxy"/>.
    /// NOTE: This property id was added in version 1.1.0.
    /// </summary>
    SpeechServiceConnection_ProxyHostName = 1100,

    /// <summary>
    /// The port of the proxy server used to connect to the Cognitive Services Speech Service. Under normal circumstances,
    /// you shouldn't have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::SetProxy"/>.
    /// NOTE: This property id was added in version 1.1.0.
    /// </summary>
    SpeechServiceConnection_ProxyPort = 1101,

    /// <summary>
    /// The user name of the proxy server used to connect to the Cognitive Services Speech Service. Under normal circumstances,
    /// you shouldn't have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::SetProxy"/>.
    /// NOTE: This property id was added in version 1.1.0.
    /// </summary>
    SpeechServiceConnection_ProxyUserName = 1102,

    /// <summary>
    /// The password of the proxy server used to connect to the Cognitive Services Speech Service. Under normal circumstances,
    /// you shouldn't have to use this property directly.
    /// Instead, use <see cref="SpeechConfig::SetProxy"/>.
    /// NOTE: This property id was added in version 1.1.0.
    /// </summary>
    SpeechServiceConnection_ProxyPassword = 1103,

    /// <summary>
    /// The URL string built from speech configuration.
    /// This property is intended to be read-only. The SDK is using it internally.
    /// NOTE: Added in version 1.5.0.
    /// </summary>
    SpeechServiceConnection_Url = 1104,

    /// <summary>
    /// The list of comma separated languages used as target translation languages. Under normal circumstances,
    /// you shouldn't have to use this property directly. Instead use <see cref="SpeechTranslationConfig::AddTargetLanguage"/>
    /// and <see cref="SpeechTranslationConfig::GetTargetLanguages"/>.
    /// </summary>
    SpeechServiceConnection_TranslationToLanguages = 2000,

    /// <summary>
    /// The name of the Cognitive Service Text to Speech Service voice. Under normal circumstances, you shouldn't have to use this
    /// property directly. Instead use <see cref="SpeechTranslationConfig::SetVoiceName"/>.
    /// NOTE: Valid voice names can be found <a href="https://aka.ms/csspeech/voicenames">here</a>.
    /// </summary>
    SpeechServiceConnection_TranslationVoice = 2001,

    /// <summary>
    /// Translation features. For internal use.
    /// </summary>
    SpeechServiceConnection_TranslationFeatures = 2002,

    /// <summary>
    /// The Language Understanding Service region. Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead use <see cref="LanguageUnderstandingModel"/>.
    /// </summary>
    SpeechServiceConnection_IntentRegion = 2003,

    /// <summary>
    /// The Cognitive Services Speech Service recognition mode. Can be "INTERACTIVE", "CONVERSATION", "DICTATION".
    /// This property is intended to be read-only. The SDK is using it internally.
    /// </summary>
    SpeechServiceConnection_RecoMode = 3000,

    /// <summary>
    /// The spoken language to be recognized (in BCP-47 format). Under normal circumstances, you shouldn't have to use this property
    /// directly.
    /// Instead, use <see cref="SpeechConfig::SetSpeechRecognitionLanguage"/>.
    /// </summary>
    SpeechServiceConnection_RecoLanguage = 3001,

    /// <summary>
    /// The session id. This id is a universally unique identifier (aka UUID) representing a specific binding of an audio input stream
    /// and the underlying speech recognition instance to which it is bound. Under normal circumstances, you shouldn't have to use this
    /// property directly.
    /// Instead use <see cref="SessionEventArgs::SessionId"/>.
    /// </summary>
    Speech_SessionId = 3002,

    /// <summary>
    /// The query parameters provided by users. They will be passed to service as URL query parameters.
    /// Added in version 1.5.0
    /// </summary>
    SpeechServiceConnection_UserDefinedQueryParameters = 3003,

    /// <summary>
    /// The string to specify the backend to be used for speech recognition;
    /// allowed options are online and offline.
    /// Under normal circumstances, you shouldn't use this property directly.
    /// Currently the offline option is only valid when EmbeddedSpeechConfig is used.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_RecoBackend = 3004,

    /// <summary>
    /// The name of the model to be used for speech recognition.
    /// Under normal circumstances, you shouldn't use this property directly.
    /// Currently this is only valid when EmbeddedSpeechConfig is used.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_RecoModelName = 3005,

    /// <summary>
    /// The decryption key of the model to be used for speech recognition.
    /// Under normal circumstances, you shouldn't use this property directly.
    /// Currently this is only valid when EmbeddedSpeechConfig is used.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_RecoModelKey = 3006,

    /// <summary>
    /// The path to the ini file of the model to be used for speech recognition.
    /// Under normal circumstances, you shouldn't use this property directly.
    /// Currently this is only valid when EmbeddedSpeechConfig is used.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_RecoModelIniFile = 3007,

    /// <summary>
    /// The spoken language to be synthesized (e.g. en-US)
    /// Added in version 1.4.0
    /// </summary>
    SpeechServiceConnection_SynthLanguage = 3100,

    /// <summary>
    /// The name of the TTS voice to be used for speech synthesis
    /// Added in version 1.4.0
    /// </summary>
    SpeechServiceConnection_SynthVoice = 3101,

    /// <summary>
    /// The string to specify TTS output audio format
    /// Added in version 1.4.0
    /// </summary>
    SpeechServiceConnection_SynthOutputFormat = 3102,

    /// <summary>
    /// Indicates if use compressed audio format for speech synthesis audio transmission.
    /// This property only affects when SpeechServiceConnection_SynthOutputFormat is set to a pcm format.
    /// If this property is not set and GStreamer is available, SDK will use compressed format for synthesized audio transmission,
    /// and decode it. You can set this property to "false" to use raw pcm format for transmission on wire.
    /// Added in version 1.16.0
    /// </summary>
    SpeechServiceConnection_SynthEnableCompressedAudioTransmission = 3103,

    /// <summary>
    /// The string to specify TTS backend; valid options are online and offline.
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="EmbeddedSpeechConfig::FromPath"/> or <see cref="EmbeddedSpeechConfig::FromPaths"/>
    /// to set the synthesis backend to offline.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_SynthBackend = 3110,

    /// <summary>
    /// The data file path(s) for offline synthesis engine; only valid when synthesis backend is offline.
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="EmbeddedSpeechConfig::FromPath"/> or <see cref="EmbeddedSpeechConfig::FromPaths"/>.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_SynthOfflineDataPath = 3112,

    /// <summary>
    /// The name of the offline TTS voice to be used for speech synthesis
    /// Under normal circumstances, you shouldn't use this property directly.
    /// Instead, use <see cref="EmbeddedSpeechConfig::SetSpeechSynthesisVoice"/> and <see cref="EmbeddedSpeechConfig::GetSpeechSynthesisVoiceName"/>.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_SynthOfflineVoice = 3113,

    /// <summary>
    /// The decryption key of the voice to be used for speech synthesis.
    /// Under normal circumstances, you shouldn't use this property directly.
    /// Instead, use <see cref="EmbeddedSpeechConfig::SetSpeechSynthesisVoice"/>.
    /// Added in version 1.19.0
    /// </summary>
    SpeechServiceConnection_SynthModelKey = 3114,

    /// <summary>
    /// The Cognitive Services Speech Service voices list api endpoint (url). Under normal circumstances,
    /// you don't need to specify this property, SDK will construct it based on the region/host/endpoint of <see cref="SpeechConfig"/>.
    /// Added in version 1.16.0
    /// </summary>
    SpeechServiceConnection_VoicesListEndpoint = 3130,

    /// <summary>
    /// The initial silence timeout value (in milliseconds) used by the service.
    /// Added in version 1.5.0
    /// </summary>
    SpeechServiceConnection_InitialSilenceTimeoutMs = 3200,

    /// <summary>
    /// The end silence timeout value (in milliseconds) used by the service.
    /// Added in version 1.5.0
    /// </summary>
    SpeechServiceConnection_EndSilenceTimeoutMs = 3201,

    /// <summary>
    /// A boolean value specifying whether audio logging is enabled in the service or not.
    /// Audio and content logs are stored either in Microsoft-owned storage, or in your own storage account linked
    /// to your Cognitive Services subscription (Bring Your Own Storage (BYOS) enabled Speech resource).
    /// Added in version 1.5.0.
    /// </summary>
    SpeechServiceConnection_EnableAudioLogging = 3202,

    /// <summary>
    /// The speech service connection language identifier mode.
    /// Can be "AtStart" (the default), or "Continuous". See [Language
    /// Identification](https://aka.ms/speech/lid?pivots=programming-language-cpp) document.
    /// Added in 1.25.0
    /// </summary>
    SpeechServiceConnection_LanguageIdMode = 3205,

    /// <summary>
    /// The auto detect source languages
    /// Added in version 1.8.0
    /// </summary>
    SpeechServiceConnection_AutoDetectSourceLanguages = 3300,

    /// <summary>
    /// The auto detect source language result
    /// Added in version 1.8.0
    /// </summary>
    SpeechServiceConnection_AutoDetectSourceLanguageResult = 3301,

    /// <summary>
    /// The requested Cognitive Services Speech Service response output format (simple or detailed). Under normal circumstances, you shouldn't have
    /// to use this property directly.
    /// Instead use <see cref="SpeechConfig::SetOutputFormat"/>.
    /// </summary>
    SpeechServiceResponse_RequestDetailedResultTrueFalse = 4000,

    /// <summary>
    /// The requested Cognitive Services Speech Service response output profanity level. Currently unused.
    /// </summary>
    SpeechServiceResponse_RequestProfanityFilterTrueFalse = 4001,

    /// <summary>
    /// The requested Cognitive Services Speech Service response output profanity setting.
    /// Allowed values are "masked", "removed", and "raw".
    /// Added in version 1.5.0.
    /// </summary>
    SpeechServiceResponse_ProfanityOption = 4002,

    /// <summary>
    /// A string value specifying which post processing option should be used by service.
    /// Allowed values are "TrueText".
    /// Added in version 1.5.0
    /// </summary>
    SpeechServiceResponse_PostProcessingOption = 4003,

    /// <summary>
    /// A boolean value specifying whether to include word-level timestamps in the response result.
    /// Added in version 1.5.0
    /// </summary>
    SpeechServiceResponse_RequestWordLevelTimestamps = 4004,

    /// <summary>
    /// The number of times a word has to be in partial results to be returned.
    /// Added in version 1.5.0
    /// </summary>
    SpeechServiceResponse_StablePartialResultThreshold = 4005,

    /// <summary>
    /// A string value specifying the output format option in the response result. Internal use only.
    /// Added in version 1.5.0.
    /// </summary>
    SpeechServiceResponse_OutputFormatOption = 4006,

    /// <summary>
    /// A boolean value specifying whether to include SNR (signal to noise ratio) in the response result.
    /// Added in version 1.18.0
    /// </summary>
    SpeechServiceResponse_RequestSnr = 4007,

    /// <summary>
    /// A boolean value to request for stabilizing translation partial results by omitting words in the end.
    /// Added in version 1.5.0.
    /// </summary>
    SpeechServiceResponse_TranslationRequestStablePartialResult = 4100,

    /// <summary>
    /// A boolean value specifying whether to request WordBoundary events.
    /// Added in version 1.21.0.
    /// </summary>
    SpeechServiceResponse_RequestWordBoundary = 4200,

    /// <summary>
    /// A boolean value specifying whether to request punctuation boundary in WordBoundary Events. Default is true.
    /// Added in version 1.21.0.
    /// </summary>
    SpeechServiceResponse_RequestPunctuationBoundary = 4201,

    /// <summary>
    /// A boolean value specifying whether to request sentence boundary in WordBoundary Events. Default is false.
    /// Added in version 1.21.0.
    /// </summary>
    SpeechServiceResponse_RequestSentenceBoundary = 4202,

    /// <summary>
    /// A boolean value specifying whether the SDK should synchronize synthesis metadata events,
    /// (e.g. word boundary, viseme, etc.) to the audio playback. This only takes effect when the audio is played through the SDK.
    /// Default is true.
    /// If set to false, the SDK will fire the events as they come from the service, which may be out of sync with the audio playback.
    /// Added in version 1.31.0.
    /// </summary>
    SpeechServiceResponse_SynthesisEventsSyncToAudio = 4210,

    /// <summary>
    /// The Cognitive Services Speech Service response output (in JSON format). This property is available on recognition result objects only.
    /// </summary>
    SpeechServiceResponse_JsonResult = 5000,

    /// <summary>
    /// The Cognitive Services Speech Service error details (in JSON format). Under normal circumstances, you shouldn't have to
    /// use this property directly.
    /// Instead, use <see cref="CancellationDetails::ErrorDetails"/>.
    /// </summary>
    SpeechServiceResponse_JsonErrorDetails = 5001,

    /// <summary>
    /// The recognition latency in milliseconds. Read-only, available on final speech/translation/intent results.
    /// This measures the latency between when an audio input is received by the SDK, and the moment the final result is received from the service.
    /// The SDK computes the time difference between the last audio fragment from the audio input that is contributing to the final result, and the time the final result is received from the speech service.
    /// Added in version 1.3.0.
    /// </summary>
    SpeechServiceResponse_RecognitionLatencyMs = 5002,

    /// <summary>
    /// The recognition backend. Read-only, available on speech recognition results.
    /// This indicates whether cloud (online) or embedded (offline) recognition was used to produce the result.
    /// </summary>
    SpeechServiceResponse_RecognitionBackend = 5003,

    /// <summary>
    /// The speech synthesis first byte latency in milliseconds. Read-only, available on final speech synthesis results.
    /// This measures the latency between when the synthesis is started to be processed, and the moment the first byte audio is available.
    /// Added in version 1.17.0.
    /// </summary>
    SpeechServiceResponse_SynthesisFirstByteLatencyMs = 5010,

    /// <summary>
    /// The speech synthesis all bytes latency in milliseconds. Read-only, available on final speech synthesis results.
    /// This measures the latency between when the synthesis is started to be processed, and the moment the whole audio is synthesized.
    /// Added in version 1.17.0.
    /// </summary>
    SpeechServiceResponse_SynthesisFinishLatencyMs = 5011,

    /// <summary>
    /// The underrun time for speech synthesis in milliseconds. Read-only, available on results in SynthesisCompleted events.
    /// This measures the total underrun time from <see cref="PropertyId::AudioConfig_PlaybackBufferLengthInMs"/> is filled to synthesis completed.
    /// Added in version 1.17.0.
    /// </summary>
    SpeechServiceResponse_SynthesisUnderrunTimeMs = 5012,

    /// <summary>
    /// The speech synthesis connection latency in milliseconds. Read-only, available on final speech synthesis results.
    /// This measures the latency between when the synthesis is started to be processed, and the moment the HTTP/WebSocket connection is established.
    /// Added in version 1.26.0.
    /// </summary>
    SpeechServiceResponse_SynthesisConnectionLatencyMs = 5013,

    /// <summary>
    /// The speech synthesis network latency in milliseconds. Read-only, available on final speech synthesis results.
    /// This measures the network round trip time.
    /// Added in version 1.26.0.
    /// </summary>
    SpeechServiceResponse_SynthesisNetworkLatencyMs = 5014,

    /// <summary>
    /// The speech synthesis service latency in milliseconds. Read-only, available on final speech synthesis results.
    /// This measures the service processing time to synthesize the first byte of audio.
    /// Added in version 1.26.0.
    /// </summary>
    SpeechServiceResponse_SynthesisServiceLatencyMs = 5015,

    /// <summary>
    /// Indicates which backend the synthesis is finished by. Read-only, available on speech synthesis results, except for the result in SynthesisStarted event
    /// Added in version 1.17.0.
    /// </summary>
    SpeechServiceResponse_SynthesisBackend = 5020,

    /// <summary>
    /// The cancellation reason. Currently unused.
    /// </summary>
    CancellationDetails_Reason = 6000,

    /// <summary>
    /// The cancellation text. Currently unused.
    /// </summary>
    CancellationDetails_ReasonText = 6001,

    /// <summary>
    /// The cancellation detailed text. Currently unused.
    /// </summary>
    CancellationDetails_ReasonDetailedText = 6002,

    /// <summary>
    /// The Language Understanding Service response output (in JSON format). Available via <see cref="IntentRecognitionResult.Properties"/>.
    /// </summary>
    LanguageUnderstandingServiceResponse_JsonResult = 7000,

    /// <summary>
    /// The device name for audio capture. Under normal circumstances, you shouldn't have to
    /// use this property directly.
    /// Instead, use <see cref="AudioConfig::FromMicrophoneInput"/>.
    /// NOTE: This property id was added in version 1.3.0.
    /// </summary>
    AudioConfig_DeviceNameForCapture = 8000,

    /// <summary>
    /// The number of channels for audio capture. Internal use only.
    /// NOTE: This property id was added in version 1.3.0.
    /// </summary>
    AudioConfig_NumberOfChannelsForCapture = 8001,

    /// <summary>
    /// The sample rate (in Hz) for audio capture. Internal use only.
    /// NOTE: This property id was added in version 1.3.0.
    /// </summary>
    AudioConfig_SampleRateForCapture = 8002,

    /// <summary>
    /// The number of bits of each sample for audio capture. Internal use only.
    /// NOTE: This property id was added in version 1.3.0.
    /// </summary>
    AudioConfig_BitsPerSampleForCapture = 8003,

    /// <summary>
    /// The audio source. Allowed values are "Microphones", "File", and "Stream".
    /// Added in version 1.3.0.
    /// </summary>
    AudioConfig_AudioSource = 8004,

    /// <summary>
    /// The device name for audio render. Under normal circumstances, you shouldn't have to
    /// use this property directly.
    /// Instead, use <see cref="AudioConfig::FromSpeakerOutput"/>.
    /// Added in version 1.14.0
    /// </summary>
    AudioConfig_DeviceNameForRender = 8005,

    /// <summary>
    /// Playback buffer length in milliseconds, default is 50 milliseconds.
    /// </summary>
    AudioConfig_PlaybackBufferLengthInMs = 8006,

    /// <summary>
    /// Audio processing options in JSON format.
    /// </summary>
    AudioConfig_AudioProcessingOptions = 8007,

    /// <summary>
    /// The file name to write logs.
    /// Added in version 1.4.0.
    /// </summary>
    Speech_LogFilename = 9001,

    /// <summary>
    /// A duration of detected silence, measured in milliseconds, after which speech-to-text will determine a spoken
    /// phrase has ended and generate a final Recognized result. Configuring this timeout may be helpful in situations
    /// where spoken input is significantly faster or slower than usual and default segmentation behavior consistently
    /// yields results that are too long or too short. Segmentation timeout values that are inappropriately high or low
    /// can negatively affect speech-to-text accuracy; this property should be carefully configured and the resulting
    /// behavior should be thoroughly validated as intended.
    ///
    /// For more information about timeout configuration that includes discussion of default behaviors, please visit
    /// https://aka.ms/csspeech/timeouts.
    /// </summary>
    Speech_SegmentationSilenceTimeoutMs = 9002,

    /// <summary>
    /// Identifier used to connect to the backend service.
    /// Added in version 1.5.0.
    /// </summary>
    Conversation_ApplicationId = 10000,

    /// <summary>
    /// Type of dialog backend to connect to.
    /// Added in version 1.7.0.
    /// </summary>
    Conversation_DialogType = 10001,

    /// <summary>
    /// Silence timeout for listening
    /// Added in version 1.5.0.
    /// </summary>
    Conversation_Initial_Silence_Timeout = 10002,

    /// <summary>
    /// From id to be used on speech recognition activities
    /// Added in version 1.5.0.
    /// </summary>
    Conversation_From_Id = 10003,

    /// <summary>
    /// ConversationId for the session.
    /// Added in version 1.8.0.
    /// </summary>
    Conversation_Conversation_Id = 10004,

    /// <summary>
    /// Comma separated list of custom voice deployment ids.
    /// Added in version 1.8.0.
    /// </summary>
    Conversation_Custom_Voice_Deployment_Ids = 10005,

    /// <summary>
    /// Speech activity template, stamp properties in the template on the activity generated by the service for speech.
    /// Added in version 1.10.0.
    /// </summary>
    Conversation_Speech_Activity_Template = 10006,

    /// <summary>
    /// Your participant identifier in the current conversation.
    /// Added in version 1.13.0
    /// </summary>
    Conversation_ParticipantId = 10007,

    // If specified as true, request that the service send MessageStatus payloads via the ActivityReceived event
    // handler. These messages communicate the outcome of ITurnContext resolution from the dialog system.
    // Added in version 1.14.0.
    Conversation_Request_Bot_Status_Messages = 10008,

    // Additional identifying information, such as a Direct Line token, used to authenticate with the backend service.
    // Added in version 1.16.0.
    Conversation_Connection_Id = 10009,

    /// <summary>
    /// The time stamp associated to data buffer written by client when using Pull/Push audio input streams.
    /// The time stamp is a 64-bit value with a resolution of 90 kHz. It is the same as the presentation timestamp in an MPEG transport stream. See https://en.wikipedia.org/wiki/Presentation_timestamp
    /// Added in version 1.5.0.
    /// </summary>
    DataBuffer_TimeStamp = 11001,

    /// <summary>
    /// The user id associated to data buffer written by client when using Pull/Push audio input streams.
    /// Added in version 1.5.0.
    /// </summary>
    DataBuffer_UserId = 11002,

    /// <summary>
    /// The reference text of the audio for pronunciation evaluation.
    /// For this and the following pronunciation assessment parameters, see the table
    /// [Pronunciation assessment parameters](/azure/cognitive-services/speech-service/rest-speech-to-text-short#pronunciation-assessment-parameters).
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::Create"/> or <see cref="PronunciationAssessmentConfig::SetReferenceText"/>.
    /// Added in version 1.14.0
    /// </summary>
    PronunciationAssessment_ReferenceText = 12001,

    /// <summary>
    /// The point system for pronunciation score calibration (FivePoint or HundredMark).
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::Create"/>.
    /// Added in version 1.14.0
    /// </summary>
    PronunciationAssessment_GradingSystem = 12002,

    /// <summary>
    /// The pronunciation evaluation granularity (Phoneme, Word, or FullText).
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::Create"/>.
    /// Added in version 1.14.0
    /// </summary>
    PronunciationAssessment_Granularity = 12003,

    /// <summary>
    /// Defines if enable miscue calculation.
    /// With this enabled, the pronounced words will be compared to the reference text,
    /// and will be marked with omission/insertion based on the comparison. The default setting is False.
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::Create"/>.
    /// Added in version 1.14.0
    /// </summary>
    PronunciationAssessment_EnableMiscue = 12005,

    /// <summary>
    /// The pronunciation evaluation phoneme alphabet. The valid values are "SAPI" (default) and "IPA"
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::SetPhonemeAlphabet"/>.
    /// Added in version 1.20.0
    /// </summary>
    PronunciationAssessment_PhonemeAlphabet = 12006,

    /// <summary>
    /// The pronunciation evaluation nbest phoneme count.
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::SetNBestPhonemeCount"/>.
    /// Added in version 1.20.0
    /// </summary>
    PronunciationAssessment_NBestPhonemeCount = 12007,

    /// <summary>
    /// Whether to enable prosody assessment.
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::EnableProsodyAssessment"/>.
    /// Added in version 1.33.0
    /// </summary>
    PronunciationAssessment_EnableProsodyAssessment = 12008,

    /// <summary>
    /// The json string of pronunciation assessment parameters
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::Create"/>.
    /// Added in version 1.14.0
    /// </summary>
    PronunciationAssessment_Json = 12009,

    /// <summary>
    /// Pronunciation assessment parameters.
    /// This property is intended to be read-only. The SDK is using it internally.
    /// Added in version 1.14.0
    /// </summary>
    PronunciationAssessment_Params = 12010,

    /// <summary>
    /// The content topic of the pronunciation assessment.
    /// Under normal circumstances, you shouldn't have to use this property directly.
    /// Instead, use <see cref="PronunciationAssessmentConfig::EnableContentAssessmentWithTopic"/>.
    /// Added in version 1.33.0
    /// </summary>
    PronunciationAssessment_ContentTopic = 12020,

    /// <summary>
    /// Speaker Recognition backend API version.
    /// This property is added to allow testing and use of previous versions of Speaker Recognition APIs, where applicable.
    /// Added in version 1.18.0
    /// </summary>
    SpeakerRecognition_Api_Version = 13001,

    /// <summary>
    /// The name of a model to be used for speech translation.
    /// Do not use this property directly.
    /// Currently this is only valid when EmbeddedSpeechConfig is used.
    /// </summary>
    SpeechTranslation_ModelName = 13100,

    /// <summary>
    /// The decryption key of a model to be used for speech translation.
    /// Do not use this property directly.
    /// Currently this is only valid when EmbeddedSpeechConfig is used.
    /// </summary>
    SpeechTranslation_ModelKey = 13101,

    /// <summary>
    /// The name of a model to be used for keyword recognition.
    /// Do not use this property directly.
    /// Currently this is only valid when EmbeddedSpeechConfig is used.
    /// </summary>
    KeywordRecognition_ModelName = 13200,

    /// <summary>
    /// The decryption key of a model to be used for keyword recognition.
    /// Do not use this property directly.
    /// Currently this is only valid when EmbeddedSpeechConfig is used.
    /// </summary>
    KeywordRecognition_ModelKey = 13201,

    /// <summary>
    /// Enable the collection of embedded speech performance metrics which can
    /// be used to evaluate the capability of a device to use embedded speech.
    /// The collected data is included in results from specific scenarios like
    /// speech recognition.
    /// The default setting is "false". Note that metrics may not be available
    /// from all embedded speech scenarios.
    /// </summary>
    EmbeddedSpeech_EnablePerformanceMetrics = 13300
};

/// <summary>
/// Output format.
/// </summary>
enum class OutputFormat
{
    Simple = 0,
    Detailed = 1
};

/// <summary>
/// Removes profanity (swearing), or replaces letters of profane words with stars.
/// Added in version 1.5.0.
/// </summary>
enum class ProfanityOption
{
    /// <summary>
    /// Replaces letters in profane words with star characters.
    /// </summary>
    Masked = 0,
    /// <summary>
    /// Removes profane words.
    /// </summary>
    Removed = 1,
    /// <summary>
    /// Does nothing to profane words.
    /// </summary>
    Raw = 2
};

/// <summary>
/// Specifies the possible reasons a recognition result might be generated.
/// </summary>
enum class ResultReason
{
    /// <summary>
    /// Indicates speech could not be recognized. More details can be found in the NoMatchDetails object.
    /// </summary>
    NoMatch = 0,

    /// <summary>
    /// Indicates that the recognition was canceled. More details can be found using the CancellationDetails object.
    /// </summary>
    Canceled = 1,

    /// <summary>
    /// Indicates the speech result contains hypothesis text.
    /// </summary>
    RecognizingSpeech = 2,

    /// <summary>
    /// Indicates the speech result contains final text that has been recognized.
    /// Speech Recognition is now complete for this phrase.
    /// </summary>
    RecognizedSpeech = 3,

    /// <summary>
    /// Indicates the intent result contains hypothesis text and intent.
    /// </summary>
    RecognizingIntent = 4,

    /// <summary>
    /// Indicates the intent result contains final text and intent.
    /// Speech Recognition and Intent determination are now complete for this phrase.
    /// </summary>
    RecognizedIntent = 5,

    /// <summary>
    /// Indicates the translation result contains hypothesis text and its translation(s).
    /// </summary>
    TranslatingSpeech = 6,

    /// <summary>
    /// Indicates the translation result contains final text and corresponding translation(s).
    /// Speech Recognition and Translation are now complete for this phrase.
    /// </summary>
    TranslatedSpeech = 7,

    /// <summary>
    /// Indicates the synthesized audio result contains a non-zero amount of audio data
    /// </summary>
    SynthesizingAudio = 8,

    /// <summary>
    /// Indicates the synthesized audio is now complete for this phrase.
    /// </summary>
    SynthesizingAudioCompleted = 9,

    /// <summary>
    /// Indicates the speech result contains (unverified) keyword text.
    /// Added in version 1.3.0
    /// </summary>
    RecognizingKeyword = 10,

    /// <summary>
    /// Indicates that keyword recognition completed recognizing the given keyword.
    /// Added in version 1.3.0
    /// </summary>
    RecognizedKeyword = 11,

    /// <summary>
    /// Indicates the speech synthesis is now started
    /// Added in version 1.4.0
    /// </summary>
    SynthesizingAudioStarted = 12,

    /// <summary>
    /// Indicates the transcription result contains hypothesis text and its translation(s) for
    /// other participants in the conversation.
    /// Added in version 1.8.0
    /// </summary>
    TranslatingParticipantSpeech = 13,

    /// <summary>
    /// Indicates the transcription result contains final text and corresponding translation(s)
    /// for other participants in the conversation. Speech Recognition and Translation are now
    /// complete for this phrase.
    /// Added in version 1.8.0
    /// </summary>
    TranslatedParticipantSpeech = 14,

    /// <summary>
    /// Indicates the transcription result contains the instant message and corresponding
    /// translation(s).
    /// Added in version 1.8.0
    /// </summary>
    TranslatedInstantMessage = 15,

    /// <summary>
    /// Indicates the transcription result contains the instant message for other participants
    /// in the conversation and corresponding translation(s).
    /// Added in version 1.8.0
    /// </summary>
    TranslatedParticipantInstantMessage = 16,

    /// <summary>
    /// Indicates the voice profile is being enrolling and customers need to send more audio to create a voice profile.
    /// Added in version 1.12.0
    /// </summary>
    EnrollingVoiceProfile = 17,

    /// <summary>
    /// The voice profile has been enrolled.
    /// Added in version 1.12.0
    /// </summary>
    EnrolledVoiceProfile = 18,

    /// <summary>
    /// Indicates successful identification of some speakers.
    /// Added in version 1.12.0
    /// </summary>
    RecognizedSpeakers = 19,

    /// <summary>
    /// Indicates successfully verified one speaker.
    /// Added in version 1.12.0
    /// </summary>
    RecognizedSpeaker = 20,

    /// <summary>
    /// Indicates a voice profile has been reset successfully.
    /// Added in version 1.12.0
    /// </summary>
    ResetVoiceProfile = 21,

    /// <summary>
    /// Indicates a voice profile has been deleted successfully.
    /// Added in version 1.12.0
    /// </summary>
    DeletedVoiceProfile = 22,

    /// <summary>
    /// Indicates the voices list has been retrieved successfully.
    /// Added in version 1.16.0
    /// </summary>
    VoicesListRetrieved = 23
};

/// <summary>
/// Defines the possible reasons a recognition result might be canceled.
/// </summary>
enum class CancellationReason
{
    /// <summary>
    /// Indicates that an error occurred during speech recognition.
    /// </summary>
    Error = 1,

    /// <summary>
    /// Indicates that the end of the audio stream was reached.
    /// </summary>
    EndOfStream = 2,

    /// <summary>
    /// Indicates that request was cancelled by the user.
    /// Added in version 1.14.0
    /// </summary>
    CancelledByUser = 3,
};

/// <summary>
/// Defines error code in case that CancellationReason is Error.
/// Added in version 1.1.0.
/// </summary>
enum class CancellationErrorCode
{
    /// <summary>
    /// No error.
    /// If CancellationReason is EndOfStream, CancellationErrorCode
    /// is set to NoError.
    /// </summary>
    NoError = 0,

    /// <summary>
    /// Indicates an authentication error.
    /// An authentication error occurs if subscription key or authorization token is invalid, expired,
    /// or does not match the region being used.
    /// </summary>
    AuthenticationFailure = 1,

    /// <summary>
    /// Indicates that one or more recognition parameters are invalid or the audio format is not supported.
    /// </summary>
    BadRequest = 2,

    /// <summary>
    /// Indicates that the number of parallel requests exceeded the number of allowed concurrent transcriptions for the subscription.
    /// </summary>
    TooManyRequests = 3,

    /// <summary>
    /// Indicates that the free subscription used by the request ran out of quota.
    /// </summary>
    Forbidden = 4,

    /// <summary>
    /// Indicates a connection error.
    /// </summary>
    ConnectionFailure = 5,

    /// <summary>
    /// Indicates a time-out error when waiting for response from service.
    /// </summary>
    ServiceTimeout = 6,

    /// <summary>
    /// Indicates that an error is returned by the service.
    /// </summary>
    ServiceError = 7,

    /// <summary>
    /// Indicates that the service is currently unavailable.
    /// </summary>
    ServiceUnavailable = 8,

    /// <summary>
    /// Indicates an unexpected runtime error.
    /// </summary>
    RuntimeError = 9,

    /// <summary>
    /// Indicates the Speech Service is temporarily requesting a reconnect to a different endpoint.
    /// </summary>
    /// <remarks>Used internally</remarks>
    ServiceRedirectTemporary = 10,

    /// <summary>
    /// Indicates the Speech Service is permanently requesting a reconnect to a different endpoint.
    /// </summary>
    /// <remarks>Used internally</remarks>
    ServiceRedirectPermanent = 11,

    /// <summary>
    /// Indicates the embedded speech (SR or TTS) model is not available or corrupted.
    /// </summary>
    EmbeddedModelError = 12,
};

/// <summary>
/// Defines the possible reasons a recognition result might not be recognized.
/// </summary>
enum class NoMatchReason
{
    /// <summary>
    /// Indicates that speech was detected, but not recognized.
    /// </summary>
    NotRecognized = 1,

    /// <summary>
    /// Indicates that the start of the audio stream contained only silence, and the service timed out waiting for speech.
    /// </summary>
    InitialSilenceTimeout = 2,

    /// <summary>
    /// Indicates that the start of the audio stream contained only noise, and the service timed out waiting for speech.
    /// </summary>
    InitialBabbleTimeout = 3,

    /// <summary>
    /// Indicates that the spotted keyword has been rejected by the keyword verification service.
    /// Added in version 1.5.0.
    /// </summary>
    KeywordNotRecognized = 4,

    /// <summary>
    /// Indicates that the audio stream contained only silence after the last recognized phrase.
    /// </summary>
    EndSilenceTimeout = 5
};

/// <summary>
/// Defines the possible types for an activity json value.
/// Added in version 1.5.0
/// </summary>
enum class ActivityJSONType : int
{
    Null = 0,
    Object = 1,
    Array = 2,
    String = 3,
    Double = 4,
    UInt = 5,
    Int = 6,
    Boolean = 7
};


/// <summary>
/// Defines the possible speech synthesis output audio formats.
/// Updated in version 1.19.0
/// </summary>
enum class SpeechSynthesisOutputFormat
{
    /// <summary>
    /// raw-8khz-8bit-mono-mulaw
    /// </summary>
    Raw8Khz8BitMonoMULaw = 1,

    /// <summary>
    /// riff-16khz-16kbps-mono-siren
    /// Unsupported by the service. Do not use this value.
    /// </summary>
    Riff16Khz16KbpsMonoSiren = 2,

    /// <summary>
    /// audio-16khz-16kbps-mono-siren
    /// Unsupported by the service. Do not use this value.
    /// </summary>
    Audio16Khz16KbpsMonoSiren = 3,

    /// <summary>
    /// audio-16khz-32kbitrate-mono-mp3
    /// </summary>
    Audio16Khz32KBitRateMonoMp3 = 4,

    /// <summary>
    /// audio-16khz-128kbitrate-mono-mp3
    /// </summary>
    Audio16Khz128KBitRateMonoMp3 = 5,

    /// <summary>
    /// audio-16khz-64kbitrate-mono-mp3
    /// </summary>
    Audio16Khz64KBitRateMonoMp3 = 6,

    /// <summary>
    /// audio-24khz-48kbitrate-mono-mp3
    /// </summary>
    Audio24Khz48KBitRateMonoMp3 =7,

    /// <summary>
    /// audio-24khz-96kbitrate-mono-mp3
    /// </summary>
    Audio24Khz96KBitRateMonoMp3 = 8,

    /// <summary>
    /// audio-24khz-160kbitrate-mono-mp3
    /// </summary>
    Audio24Khz160KBitRateMonoMp3 = 9,

    /// <summary>
    /// raw-16khz-16bit-mono-truesilk
    /// </summary>
    Raw16Khz16BitMonoTrueSilk = 10,

    /// <summary>
    /// riff-16khz-16bit-mono-pcm
    /// </summary>
    Riff16Khz16BitMonoPcm = 11,

    /// <summary>
    /// riff-8khz-16bit-mono-pcm
    /// </summary>
    Riff8Khz16BitMonoPcm = 12,

    /// <summary>
    /// riff-24khz-16bit-mono-pcm
    /// </summary>
    Riff24Khz16BitMonoPcm = 13,

    /// <summary>
    /// riff-8khz-8bit-mono-mulaw
    /// </summary>
    Riff8Khz8BitMonoMULaw = 14,

    /// <summary>
    /// raw-16khz-16bit-mono-pcm
    /// </summary>
    Raw16Khz16BitMonoPcm = 15,

    /// <summary>
    /// raw-24khz-16bit-mono-pcm
    /// </summary>
    Raw24Khz16BitMonoPcm = 16,

    /// <summary>
    /// raw-8khz-16bit-mono-pcm
    /// </summary>
    Raw8Khz16BitMonoPcm = 17,

    /// <summary>
    /// ogg-16khz-16bit-mono-opus
    /// </summary>
    Ogg16Khz16BitMonoOpus = 18,

    /// <summary>
    /// ogg-24khz-16bit-mono-opus
    /// </summary>
    Ogg24Khz16BitMonoOpus = 19,

    /// <summary>
    /// raw-48khz-16bit-mono-pcm
    /// </summary>
    Raw48Khz16BitMonoPcm = 20,

    /// <summary>
    /// riff-48khz-16bit-mono-pcm
    /// </summary>
    Riff48Khz16BitMonoPcm = 21,

    /// <summary>
    /// audio-48khz-96kbitrate-mono-mp3
    /// </summary>
    Audio48Khz96KBitRateMonoMp3 = 22,

    /// <summary>
    /// audio-48khz-192kbitrate-mono-mp3
    /// </summary>
    Audio48Khz192KBitRateMonoMp3 = 23,

    /// <summary>
    /// ogg-48khz-16bit-mono-opus
    /// Added in version 1.16.0
    /// </summary>
    Ogg48Khz16BitMonoOpus = 24,

    /// <summary>
    /// webm-16khz-16bit-mono-opus
    /// Added in version 1.16.0
    /// </summary>
    Webm16Khz16BitMonoOpus = 25,

    /// <summary>
    /// webm-24khz-16bit-mono-opus
    /// Added in version 1.16.0
    /// </summary>
    Webm24Khz16BitMonoOpus = 26,

    /// <summary>
    /// raw-24khz-16bit-mono-truesilk
    /// Added in version 1.17.0
    /// </summary>
    Raw24Khz16BitMonoTrueSilk = 27,

    /// <summary>
    /// raw-8khz-8bit-mono-alaw
    /// Added in version 1.17.0
    /// </summary>
    Raw8Khz8BitMonoALaw = 28,

    /// <summary>
    /// riff-8khz-8bit-mono-alaw
    /// Added in version 1.17.0
    /// </summary>
    Riff8Khz8BitMonoALaw = 29,

    /// <summary>
    /// webm-24khz-16bit-24kbps-mono-opus
    /// Audio compressed by OPUS codec in a WebM container, with bitrate of 24kbps, optimized for IoT scenario.
    /// (Added in 1.19.0)
    /// </summary>
    Webm24Khz16Bit24KbpsMonoOpus = 30,

    /// <summary>
    /// audio-16khz-16bit-32kbps-mono-opus
    /// Audio compressed by OPUS codec without container, with bitrate of 32kbps.
    /// (Added in 1.20.0)
    /// </summary>
    Audio16Khz16Bit32KbpsMonoOpus = 31,

    /// <summary>
    /// audio-24khz-16bit-48kbps-mono-opus
    /// Audio compressed by OPUS codec without container, with bitrate of 48kbps.
    /// (Added in 1.20.0)
    /// </summary>
    Audio24Khz16Bit48KbpsMonoOpus = 32,

    /// <summary>
    /// audio-24khz-16bit-24kbps-mono-opus
    /// Audio compressed by OPUS codec without container, with bitrate of 24kbps.
    /// (Added in 1.20.0)
    /// </summary>
    Audio24Khz16Bit24KbpsMonoOpus = 33,

    /// <summary>
    /// raw-22050hz-16bit-mono-pcm
    /// Raw PCM audio at 22050Hz sampling rate and 16-bit depth.
    /// (Added in 1.22.0)
    /// </summary>
    Raw22050Hz16BitMonoPcm = 34,

    /// <summary>
    /// riff-22050hz-16bit-mono-pcm
    /// PCM audio at 22050Hz sampling rate and 16-bit depth, with RIFF header.
    /// (Added in 1.22.0)
    /// </summary>
    Riff22050Hz16BitMonoPcm = 35,

    /// <summary>
    /// raw-44100hz-16bit-mono-pcm
    /// Raw PCM audio at 44100Hz sampling rate and 16-bit depth.
    /// (Added in 1.22.0)
    /// </summary>
    Raw44100Hz16BitMonoPcm = 36,

    /// <summary>
    /// riff-44100hz-16bit-mono-pcm
    /// PCM audio at 44100Hz sampling rate and 16-bit depth, with RIFF header.
    /// (Added in 1.22.0)
    /// </summary>
    Riff44100Hz16BitMonoPcm = 37,

    /// <summary>
    /// amr-wb-16000hz
    /// AMR-WB audio at 16kHz sampling rate.
    /// (Added in 1.24.0)
    /// </summary>
    AmrWb16000Hz = 38
};

/// <summary>
/// Defines the possible status of audio data stream.
/// Added in version 1.4.0
/// </summary>
enum class StreamStatus
{
    /// <summary>
    /// The audio data stream status is unknown
    /// </summary>
    Unknown = 0,

    /// <summary>
    /// The audio data stream contains no data
    /// </summary>
    NoData = 1,

    /// <summary>
    /// The audio data stream contains partial data of a speak request
    /// </summary>
    PartialData = 2,

    /// <summary>
    /// The audio data stream contains all data of a speak request
    /// </summary>
    AllData = 3,

    /// <summary>
    /// The audio data stream was canceled
    /// </summary>
    Canceled = 4
};

/// <summary>
/// Defines channels used to pass property settings to service.
/// Added in version 1.5.0.
/// </summary>
enum class ServicePropertyChannel
{
    /// <summary>
    /// Uses URI query parameter to pass property settings to service.
    /// </summary>
    UriQueryParameter = 0,

    /// <summary>
    /// Uses HttpHeader to set a key/value in a HTTP header.
    /// </summary>
    HttpHeader = 1
};

namespace Transcription
{
    /// <summary>
    /// Why the participant changed event was raised
    /// Added in version 1.8.0
    /// </summary>
    enum class ParticipantChangedReason
    {
        /// <summary>
        /// Participant has joined the conversation
        /// </summary>
        JoinedConversation = 0,

        /// <summary>
        /// Participant has left the conversation. This could be voluntary, or involuntary
        /// (e.g. they are experiencing networking issues)
        /// </summary>
        LeftConversation = 1,

        /// <summary>
        /// The participants' state has changed (e.g. they became muted, changed their nickname)
        /// </summary>
        Updated = 2
    };
}

namespace Intent
{
    /// <summary>
    /// Used to define the type of entity used for intent recognition.
    /// </summary>
    enum class EntityType
    {
        /// <summary>
        /// This will match any text that fills the slot.
        /// </summary>
        Any = 0,
        /// <summary>
        /// This will match text that is contained within the list or any text if the mode is set to "fuzzy".
        /// </summary>
        List = 1,
        /// <summary>
        /// This will match cardinal and ordinal integers.
        /// </summary>
        PrebuiltInteger = 2
    };

    /// <summary>
    /// Used to define the type of entity used for intent recognition.
    /// </summary>
    enum class EntityMatchMode
    {
        /// <summary>
        /// This is the basic or default mode of matching based on the EntityType
        /// </summary>
        Basic = 0,
        /// <summary>
        /// This will match only exact matches within the entities phrases.
        /// </summary>
        Strict = 1,
        /// <summary>
        /// This will match text within the slot the entity is in, but not require anything from that text.
        /// </summary>
        Fuzzy = 2
    };

    /// <summary>
    /// Used to define the greediness of the entity.
    /// </summary>
    enum class EntityGreed
    {
        /// <summary>
        /// Lazy will match as little as possible.
        /// </summary>
        Lazy = 0,
        /// <summary>
        /// Greedy will match as much as possible.
        /// </summary>
        Greedy = 1,
    };
}
/// <summary>
/// Defines voice profile types
/// </summary>
enum class VoiceProfileType
{
    /// <summary>
    /// Text independent speaker identification.
    /// </summary>
    TextIndependentIdentification = 1,

    /// <summary>
    ///  Text dependent speaker verification.
    /// </summary>
    TextDependentVerification = 2,

    /// <summary>
    /// Text independent verification.
    /// </summary>
    TextIndependentVerification = 3
};

/// <summary>
/// Defines the scope that a Recognition Factor is applied to.
/// </summary>
enum class RecognitionFactorScope
{
    /// <summary>
    /// A Recognition Factor will apply to grammars that can be referenced as individual partial phrases.
    /// </summary>
    /// <remarks>
    /// Currently only applies to PhraseListGrammars
    /// </remarks>
    PartialPhrase = 1,
};

/// <summary>
/// Defines the point system for pronunciation score calibration; default value is FivePoint.
/// Added in version 1.14.0
/// </summary>
enum class PronunciationAssessmentGradingSystem
{
    /// <summary>
    /// Five point calibration
    /// </summary>
    FivePoint = 1,

    /// <summary>
    /// Hundred mark
    /// </summary>
    HundredMark = 2
};

/// <summary>
/// Defines the pronunciation evaluation granularity; default value is Phoneme.
/// Added in version 1.14.0
/// </summary>
enum class PronunciationAssessmentGranularity
{
    /// <summary>
    /// Shows the score on the full text, word and phoneme level
    /// </summary>
    Phoneme = 1,

    /// <summary>
    /// Shows the score on the full text and word level
    /// </summary>
    Word = 2,

    /// <summary>
    /// Shows the score on the full text level only
    /// </summary>
    FullText = 3
};

/// <summary>
/// Defines the type of synthesis voices
/// Added in version 1.16.0
/// </summary>
enum class SynthesisVoiceType
{
    /// <summary>
    /// Online neural voice
    /// </summary>
    OnlineNeural = 1,

    /// <summary>
    /// Online standard voice
    /// </summary>
    OnlineStandard = 2,

    /// <summary>
    /// Offline neural voice
    /// </summary>
    OfflineNeural = 3,

    /// <summary>
    /// Offline standard voice
    /// </summary>
    OfflineStandard = 4
};

/// <summary>
/// Defines the gender of synthesis voices
/// Added in version 1.17.0
/// </summary>
enum class SynthesisVoiceGender
{
    /// <summary>
    /// Gender unknown.
    /// </summary>
    Unknown = 0,

    /// <summary>
    /// Female voice
    /// </summary>
    Female = 1,

    /// <summary>
    /// Male voice
    /// </summary>
    Male = 2
};

/// <summary>
/// Defines the boundary type of speech synthesis boundary event
/// Added in version 1.21.0
/// </summary>
enum class SpeechSynthesisBoundaryType
{
    /// <summary>
    /// Word boundary
    /// </summary>
    Word = 0,

    /// <summary>
    /// Punctuation boundary
    /// </summary>
    Punctuation = 1,

    /// <summary>
    /// Sentence boundary
    /// </summary>
    Sentence = 2
};

} } } // Microsoft::CognitiveServices::Speech
