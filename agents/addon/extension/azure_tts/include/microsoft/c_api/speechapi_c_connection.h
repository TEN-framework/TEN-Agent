//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI connection_from_recognizer(SPXRECOHANDLE recognizerHandle, SPXCONNECTIONHANDLE* connectionHandle);
SPXAPI connection_from_conversation_translator(SPXCONVERSATIONTRANSLATORHANDLE convTransHandle, SPXCONNECTIONHANDLE* connectionHandle);
SPXAPI connection_from_dialog_service_connector(SPXRECOHANDLE convTransHandle, SPXCONNECTIONHANDLE* connectionHandle);
SPXAPI connection_from_speech_synthesizer(SPXSYNTHHANDLE synthesizerHandle, SPXCONNECTIONHANDLE* connectionHandle);

SPXAPI_(bool) connection_handle_is_valid(SPXCONNECTIONHANDLE handle);
SPXAPI connection_handle_release(SPXCONNECTIONHANDLE handle);
SPXAPI connection_async_handle_release(SPXASYNCHANDLE hasync);

SPXAPI connection_open(SPXCONNECTIONHANDLE handle, bool forContinuousRecognition);
SPXAPI connection_close(SPXCONNECTIONHANDLE handle);
SPXAPI connection_set_message_property(SPXCONNECTIONHANDLE handle, const char* path, const char* name, const char* value);
SPXAPI connection_send_message(SPXCONNECTIONHANDLE handle, const char* path, const char* payload);
SPXAPI connection_send_message_async(SPXCONNECTIONHANDLE handle, const char* path, const char* payload, SPXASYNCHANDLE* phasync);

SPXAPI connection_send_message_data(SPXCONNECTIONHANDLE handle, const char* path, uint8_t* data, uint32_t size);
SPXAPI connection_send_message_data_async(SPXCONNECTIONHANDLE handle, const char* path, uint8_t* data, uint32_t size, SPXASYNCHANDLE* phasync);

SPXAPI connection_send_message_wait_for(SPXASYNCHANDLE hasync, uint32_t milliseconds);

SPXAPI connection_get_property_bag(SPXRECOHANDLE hconn, SPXPROPERTYBAGHANDLE* hpropbag);

typedef void(*CONNECTION_CALLBACK_FUNC)(SPXEVENTHANDLE event, void* context);
SPXAPI connection_connected_set_callback(SPXCONNECTIONHANDLE connection, CONNECTION_CALLBACK_FUNC callback, void* context);
SPXAPI connection_disconnected_set_callback(SPXCONNECTIONHANDLE connection, CONNECTION_CALLBACK_FUNC callback, void* context);
SPXAPI connection_message_received_set_callback(SPXCONNECTIONHANDLE connection, CONNECTION_CALLBACK_FUNC callback, void* context);

SPXAPI_(bool) connection_message_received_event_handle_is_valid(SPXEVENTHANDLE hevent);
SPXAPI connection_message_received_event_handle_release(SPXEVENTHANDLE hevent);

SPXAPI connection_message_received_event_get_message(SPXEVENTHANDLE hevent, SPXCONNECTIONMESSAGEHANDLE* hcm);

SPXAPI_(bool) connection_message_handle_is_valid(SPXCONNECTIONMESSAGEHANDLE handle);
SPXAPI connection_message_handle_release(SPXCONNECTIONMESSAGEHANDLE handle);

SPXAPI connection_message_get_property_bag(SPXCONNECTIONMESSAGEHANDLE hcm, SPXPROPERTYBAGHANDLE* hpropbag);
SPXAPI connection_message_get_data(SPXCONNECTIONMESSAGEHANDLE hcm, uint8_t* data, uint32_t size);
SPXAPI_(uint32_t) connection_message_get_data_size(SPXCONNECTIONMESSAGEHANDLE hcm);
