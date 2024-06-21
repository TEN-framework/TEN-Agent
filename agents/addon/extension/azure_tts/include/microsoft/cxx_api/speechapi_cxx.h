//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx.h: Master include header for public C++ API declarations
//

#pragma once

#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_smart_handle.h>

#include <speechapi_cxx_properties.h>
#include <speechapi_cxx_audio_stream_format.h>
#include <speechapi_cxx_audio_stream.h>
#include <speechapi_cxx_speech_config.h>
#include <speechapi_cxx_embedded_speech_config.h>
#include <speechapi_cxx_hybrid_speech_config.h>
#include <speechapi_cxx_audio_config.h>
#include <speechapi_cxx_audio_processing_options.h>

#include <speechapi_cxx_eventargs.h>
#include <speechapi_cxx_eventsignal.h>

#include <speechapi_cxx_session_eventargs.h>

#include <speechapi_cxx_recognition_result.h>
#include <speechapi_cxx_recognition_eventargs.h>
#include <speechapi_cxx_recognition_async_recognizer.h>
#include <speechapi_cxx_recognition_base_async_recognizer.h>

#include <speechapi_cxx_recognizer.h>

#include <speechapi_cxx_speech_recognition_result.h>
#include <speechapi_cxx_speech_recognition_eventargs.h>
#include <speechapi_cxx_speech_recognizer.h>
#include <speechapi_cxx_speech_recognition_model.h>

#include <speechapi_cxx_conversational_language_understanding_model.h>
#include <speechapi_cxx_intent_recognition_result.h>
#include <speechapi_cxx_intent_recognition_eventargs.h>
#include <speechapi_cxx_intent_recognizer.h>
#include <speechapi_cxx_intent_trigger.h>
#include <speechapi_cxx_language_understanding_model.h>
#include <speechapi_cxx_pattern_matching_model.h>
#include <speechapi_cxx_pattern_matching_intent.h>

#include <speechapi_cxx_translation_result.h>
#include <speechapi_cxx_translation_eventargs.h>
#include <speechapi_cxx_speech_translation_config.h>
#include <speechapi_cxx_translation_recognizer.h>
#include <speechapi_cxx_auto_detect_source_lang_config.h>
#include <speechapi_cxx_source_lang_config.h>
#include <speechapi_cxx_speech_translation_model.h>

#include <speechapi_cxx_pronunciation_assessment_config.h>
#include <speechapi_cxx_pronunciation_assessment_result.h>

#include <speechapi_cxx_grammar.h>
#include <speechapi_cxx_grammar_phrase.h>
#include <speechapi_cxx_phrase_list_grammar.h>
#include <speechapi_cxx_grammar_list.h>
#include <speechapi_cxx_class_language_model.h>

#include <speechapi_cxx_session.h>

#include <speechapi_cxx_dialog_service_connector.h>

#include <speechapi_cxx_connection.h>
#include <speechapi_cxx_connection_eventargs.h>

#include <speechapi_cxx_audio_data_stream.h>

#include <speechapi_cxx_speech_synthesis_request.h>
#include <speechapi_cxx_speech_synthesis_result.h>
#include <speechapi_cxx_speech_synthesis_eventargs.h>
#include <speechapi_cxx_speech_synthesis_word_boundary_eventargs.h>
#include <speechapi_cxx_speech_synthesis_viseme_eventargs.h>
#include <speechapi_cxx_speech_synthesis_bookmark_eventargs.h>
#include <speechapi_cxx_speech_synthesizer.h>
#include <speechapi_cxx_synthesis_voices_result.h>
#include <speechapi_cxx_voice_info.h>

#include <speechapi_cxx_keyword_recognition_result.h>
#include <speechapi_cxx_keyword_recognition_eventargs.h>
#include <speechapi_cxx_keyword_recognizer.h>

#include <speechapi_cxx_conversation.h>
#include <speechapi_cxx_conversation_transcriber.h>
#include <speechapi_cxx_conversation_transcription_eventargs.h>
#include <speechapi_cxx_conversation_transcription_result.h>
#include <speechapi_cxx_meeting.h>
#include <speechapi_cxx_meeting_transcriber.h>
#include <speechapi_cxx_meeting_transcription_eventargs.h>
#include <speechapi_cxx_meeting_transcription_result.h>
#include <speechapi_cxx_user.h>
#include <speechapi_cxx_participant.h>
#include <speechapi_cxx_conversation_translator.h>
#include <speechapi_cxx_conversation_translator_events.h>

#include <speechapi_cxx_auto_detect_source_lang_result.h>

#include <speechapi_cxx_source_language_recognizer.h>
#include <speechapi_cxx_speaker_recognizer.h>
#include <speechapi_cxx_speaker_verification_model.h>
#include <speechapi_cxx_speaker_identification_model.h>
#include <speechapi_cxx_voice_profile_client.h>
#include <speechapi_cxx_voice_profile.h>
#include <speechapi_cxx_voice_profile_result.h>
#include <speechapi_cxx_voice_profile_enrollment_result.h>
#include <speechapi_cxx_voice_profile_phrase_result.h>
#include <speechapi_cxx_speaker_recognition_result.h>

#include <speechapi_cxx_file_logger.h>
#include <speechapi_cxx_event_logger.h>
#include <speechapi_cxx_memory_logger.h>
