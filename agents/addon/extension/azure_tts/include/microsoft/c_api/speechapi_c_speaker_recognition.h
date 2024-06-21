//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_speaker_recogntion.h: c API declarations for speaker recognition.
//

#pragma once

#include <speechapi_c_common.h>

SPXAPI create_voice_profile_client_from_config(SPXVOICEPROFILECLIENTHANDLE* phclient, SPXSPEECHCONFIGHANDLE hSpeechConfig);
SPXAPI voice_profile_client_release_handle(SPXVOICEPROFILECLIENTHANDLE hVoiceClient);
SPXAPI create_voice_profile(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient, int id, const char* locale, SPXVOICEPROFILEHANDLE* pProfileHandle);

SPXAPI enroll_voice_profile(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient, SPXVOICEPROFILEHANDLE hProfileHandle, SPXAUDIOCONFIGHANDLE hAudioInput, SPXRESULTHANDLE* phresult);
SPXAPI voice_profile_client_get_property_bag(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient, SPXPROPERTYBAGHANDLE* hpropbag);
SPXAPI create_voice_profile_from_id_and_type(SPXVOICEPROFILEHANDLE* phVoiceProfile, const char* id, int type);
SPXAPI voice_profile_get_id(SPXVOICEPROFILEHANDLE hVoiceProfile, char* psz, uint32_t* pcch);
SPXAPI voice_profile_get_type(SPXVOICEPROFILEHANDLE hVoiceProfile, int* ptype);
SPXAPI voice_profile_release_handle(SPXVOICEPROFILEHANDLE hVoiceProfile);
SPXAPI voice_profile_get_property_bag(SPXVOICEPROFILEHANDLE voiceprofilehandle, SPXPROPERTYBAGHANDLE* pProperties);
SPXAPI delete_voice_profile(SPXVOICEPROFILECLIENTHANDLE hclient, SPXVOICEPROFILEHANDLE hProfileHandle, SPXRESULTHANDLE* phresult);
SPXAPI reset_voice_profile(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient, SPXVOICEPROFILEHANDLE hProfileHandle, SPXRESULTHANDLE* phresult);
SPXAPI get_profiles_json(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient, int type, char** ppsz, size_t* pcch);
SPXAPI retrieve_enrollment_result(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient, const char* pId, int type, SPXVOICEPROFILEHANDLE* phVoiceProfile);
SPXAPI get_activation_phrases(SPXVOICEPROFILECLIENTHANDLE hVoiceProfileClient, const char* pLocale, int type, SPXRESULTHANDLE* phresult);
SPXAPI recognizer_create_speaker_recognizer_from_config(SPXSPEAKERIDHANDLE* phspeakerid, SPXSPEECHCONFIGHANDLE hspeechconfig, SPXAUDIOCONFIGHANDLE haudioInput);
SPXAPI speaker_recognizer_release_handle(SPXSPEAKERIDHANDLE phspeakerid);
SPXAPI speaker_recognizer_get_property_bag(SPXSPEAKERIDHANDLE phspeakerid, SPXPROPERTYBAGHANDLE* hpropbag);
SPXAPI speaker_identification_model_create(SPXSIMODELHANDLE* psimodel);
SPXAPI speaker_identification_model_add_profile(SPXSIMODELHANDLE hsimodel, SPXVOICEPROFILEHANDLE hprofile);
SPXAPI speaker_identification_model_release_handle(SPXSIMODELHANDLE hmodel);
SPXAPI speaker_recognizer_identify(SPXSPEAKERIDHANDLE phspeakerid, SPXSIMODELHANDLE hsimodel, SPXRESULTHANDLE* phresult);
SPXAPI speaker_recognizer_verify(SPXSPEAKERIDHANDLE phspeakerid, SPXSVMODELHANDLE hsvmodel, SPXRESULTHANDLE* phresult);
SPXAPI speaker_verification_model_create(SPXSVMODELHANDLE* psvmodel, SPXVOICEPROFILEHANDLE hprofile);
SPXAPI speaker_verification_model_release_handle(SPXSVMODELHANDLE hsvmodel);
