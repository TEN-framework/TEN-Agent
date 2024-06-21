//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

typedef enum
{
    PronunciationAssessmentGradingSystem_FivePoint = 1,
    PronunciationAssessmentGradingSystem_HundredMark = 2
} Pronunciation_Assessment_Grading_System;

typedef enum
{
    PronunciationAssessmentGranularity_Phoneme = 1,
    PronunciationAssessmentGranularity_Word = 2,
    PronunciationAssessmentGranularity_FullText = 3
} Pronunciation_Assessment_Granularity;

SPXAPI create_pronunciation_assessment_config(SPXPRONUNCIATIONASSESSMENTCONFIGHANDLE* hPronunciationAssessmentConfig,
                                              const char* referenceText,
                                              Pronunciation_Assessment_Grading_System gradingSystem,
                                              Pronunciation_Assessment_Granularity granularity,
                                              bool enableMiscue);
SPXAPI create_pronunciation_assessment_config_from_json(SPXPRONUNCIATIONASSESSMENTCONFIGHANDLE* hPronunciationAssessmentConfig, const char* json);
SPXAPI_(bool) pronunciation_assessment_config_is_handle_valid(SPXPRONUNCIATIONASSESSMENTCONFIGHANDLE hPronunciationAssessmentConfig);
SPXAPI pronunciation_assessment_config_release(SPXPRONUNCIATIONASSESSMENTCONFIGHANDLE hPronunciationAssessmentConfig);
SPXAPI pronunciation_assessment_config_get_property_bag(
    SPXPRONUNCIATIONASSESSMENTCONFIGHANDLE hPronunciationAssessmentConfig, SPXPROPERTYBAGHANDLE* hpropbag);
SPXAPI__(const char*) pronunciation_assessment_config_to_json(SPXPRONUNCIATIONASSESSMENTCONFIGHANDLE hPronunciationAssessmentConfig);
SPXAPI pronunciation_assessment_config_apply_to_recognizer(SPXPRONUNCIATIONASSESSMENTCONFIGHANDLE hPronunciationAssessmentConfig, SPXRECOHANDLE hreco);
