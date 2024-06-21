//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_result.h: Public API declarations for Result related C methods and enumerations
//

#pragma once
#include <speechapi_c_common.h>

enum Result_Reason
{
    ResultReason_NoMatch = 0,
    ResultReason_Canceled = 1,
    ResultReason_RecognizingSpeech = 2,
    ResultReason_RecognizedSpeech = 3,
    ResultReason_RecognizingIntent = 4,
    ResultReason_RecognizedIntent = 5,
    ResultReason_TranslatingSpeech = 6,
    ResultReason_TranslatedSpeech = 7,
    ResultReason_SynthesizingAudio = 8,
    ResultReason_SynthesizingAudioComplete = 9,
    ResultReason_RecognizingKeyword = 10,
    ResultReason_RecognizedKeyword = 11,
    ResultReason_SynthesizingAudioStart = 12
};
typedef enum Result_Reason Result_Reason;

enum Result_CancellationReason
{
    CancellationReason_Error = 1,
    CancellationReason_EndOfStream = 2,
    CancellationReason_UserCancelled = 3,
};

typedef enum Result_CancellationReason Result_CancellationReason;

enum Result_CancellationErrorCode
{
    CancellationErrorCode_NoError = 0,
    CancellationErrorCode_AuthenticationFailure = 1,
    CancellationErrorCode_BadRequest = 2,
    CancellationErrorCode_TooManyRequests = 3,
    CancellationErrorCode_Forbidden = 4,
    CancellationErrorCode_ConnectionFailure = 5,
    CancellationErrorCode_ServiceTimeout = 6,
    CancellationErrorCode_ServiceError = 7,
    CancellationErrorCode_ServiceUnavailable = 8,
    CancellationErrorCode_RuntimeError = 9
};
typedef enum Result_CancellationErrorCode Result_CancellationErrorCode;

enum Result_NoMatchReason
{
    NoMatchReason_NotRecognized = 1,
    NoMatchReason_InitialSilenceTimeout = 2,
    NoMatchReason_InitialBabbleTimeout = 3,
    NoMatchReason_KeywordNotRecognized = 4,
    NoMatchReason_EndSilenceTimeout = 5
};
typedef enum Result_NoMatchReason Result_NoMatchReason;

enum Synthesis_VoiceType
{
    SynthesisVoiceType_OnlineNeural = 1,
    SynthesisVoiceType_OnlineStandard = 2,
    SynthesisVoiceType_OfflineNeural = 3,
    SynthesisVoiceType_OfflineStandard = 4
};
typedef enum Synthesis_VoiceType Synthesis_VoiceType;

SPXAPI result_get_reason(SPXRESULTHANDLE hresult, Result_Reason* reason);
SPXAPI result_get_reason_canceled(SPXRESULTHANDLE hresult, Result_CancellationReason* reason);
SPXAPI result_get_canceled_error_code(SPXRESULTHANDLE hresult, Result_CancellationErrorCode* errorCode);
SPXAPI result_get_no_match_reason(SPXRESULTHANDLE hresult, Result_NoMatchReason* reason);

SPXAPI result_get_result_id(SPXRESULTHANDLE hresult, char* pszResultId, uint32_t cchResultId);

SPXAPI result_get_text(SPXRESULTHANDLE hresult, char* pszText, uint32_t cchText);
SPXAPI result_get_offset(SPXRESULTHANDLE hresult, uint64_t* offset);
SPXAPI result_get_duration(SPXRESULTHANDLE hresult, uint64_t* duration);

SPXAPI result_get_property_bag(SPXRESULTHANDLE hresult, SPXPROPERTYBAGHANDLE* hpropbag);

SPXAPI synth_result_get_result_id(SPXRESULTHANDLE hresult, char* resultId, uint32_t resultIdLength);
SPXAPI synth_result_get_reason(SPXRESULTHANDLE hresult, Result_Reason* reason);
SPXAPI synth_result_get_reason_canceled(SPXRESULTHANDLE hresult, Result_CancellationReason* reason);
SPXAPI synth_result_get_canceled_error_code(SPXRESULTHANDLE hresult, Result_CancellationErrorCode* errorCode);
SPXAPI synth_result_get_audio_data(SPXRESULTHANDLE hresult, uint8_t* buffer, uint32_t bufferSize, uint32_t* filledSize);
SPXAPI synth_result_get_audio_length_duration(SPXRESULTHANDLE hresult, uint32_t* audioLength, uint64_t* audioDuration);
SPXAPI synth_result_get_audio_format(SPXRESULTHANDLE hresult, SPXAUDIOSTREAMFORMATHANDLE* hformat);
SPXAPI synth_result_get_property_bag(SPXRESULTHANDLE hresult, SPXPROPERTYBAGHANDLE* hpropbag);

SPXAPI synthesis_voices_result_get_result_id(SPXRESULTHANDLE hresult, char* resultId, uint32_t resultIdLength);
SPXAPI synthesis_voices_result_get_reason(SPXRESULTHANDLE hresult, Result_Reason* reason);
SPXAPI synthesis_voices_result_get_voice_num(SPXRESULTHANDLE hresult, uint32_t* voiceNum);
SPXAPI synthesis_voices_result_get_voice_info(SPXRESULTHANDLE hresult, uint32_t index, SPXRESULTHANDLE* hVoiceInfo);
SPXAPI synthesis_voices_result_get_property_bag(SPXRESULTHANDLE hresult, SPXPROPERTYBAGHANDLE* hpropbag);

SPXAPI voice_info_handle_release(SPXRESULTHANDLE hVoiceInfo);
SPXAPI__(const char*) voice_info_get_name(SPXRESULTHANDLE hVoiceInfo);
SPXAPI__(const char*) voice_info_get_locale(SPXRESULTHANDLE hVoiceInfo);
SPXAPI__(const char*) voice_info_get_short_name(SPXRESULTHANDLE hVoiceInfo);
SPXAPI__(const char*) voice_info_get_local_name(SPXRESULTHANDLE hVoiceInfo);
SPXAPI__(const char*) voice_info_get_style_list(SPXRESULTHANDLE hVoiceInfo);
SPXAPI__(const char*) voice_info_get_voice_path(SPXRESULTHANDLE hVoiceInfo);
SPXAPI voice_info_get_voice_type(SPXRESULTHANDLE hVoiceInfo, Synthesis_VoiceType* voiceType);
SPXAPI voice_info_get_property_bag(SPXRESULTHANDLE hVoiceInfo, SPXPROPERTYBAGHANDLE* hpropbag);
