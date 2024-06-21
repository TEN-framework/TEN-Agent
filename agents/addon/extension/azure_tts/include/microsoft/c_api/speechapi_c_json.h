//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/vision/license for the full license information.
//

#pragma once
#include <speechapi_c_common.h>

SPXAPI__(const char*) ai_core_string_create(const char* str, size_t size);
SPXAPI_(void) ai_core_string_free(const char* str);

SPXAPI_(int) ai_core_json_parser_create(SPXHANDLE* parser, const char* json, size_t jsize); // returns item for root
SPXAPI_(bool) ai_core_json_parser_handle_is_valid(SPXHANDLE parser);
SPXAPI ai_core_json_parser_handle_release(SPXHANDLE parser);

SPXAPI_(int) ai_core_json_builder_create(SPXHANDLE* builder, const char* json, size_t jsize); // returns item for root
SPXAPI_(bool) ai_core_json_builder_handle_is_valid(SPXHANDLE builder);
SPXAPI ai_core_json_builder_handle_release(SPXHANDLE builder);

SPXAPI_(int) ai_core_json_item_count(SPXHANDLE parserOrBuilder, int item);
SPXAPI_(int) ai_core_json_item_at(SPXHANDLE parserOrBuilder, int item, int index, const char* find); // returns item found
SPXAPI_(int) ai_core_json_item_next(SPXHANDLE parserOrBuilder, int item); // returns next item
SPXAPI_(int) ai_core_json_item_name(SPXHANDLE parserOrBuilder, int item); // returns item representing name of item specified

SPXAPI_(int) ai_core_json_value_kind(SPXHANDLE parserOrBuilder, int item);
SPXAPI_(bool) ai_core_json_value_as_bool(SPXHANDLE parserOrBuilder, int item, bool defaultValue);
SPXAPI_(double) ai_core_json_value_as_double(SPXHANDLE parserOrBuilder, int item, double defaultValue);
SPXAPI_(int64_t) ai_core_json_value_as_int(SPXHANDLE parserOrBuilder, int item, int64_t defaultValue);
SPXAPI_(uint64_t) ai_core_json_value_as_uint(SPXHANDLE parserOrBuilder, int item, uint64_t defaultValue);

SPXAPI__(const char*) ai_core_json_value_as_string_ptr(SPXHANDLE parserOrBuilder, int item, size_t* size);

SPXAPI__(const char*) ai_core_json_value_as_string_copy(SPXHANDLE parserOrBuilder, int item, const char* defaultValue);
SPXAPI__(const char*) ai_core_json_value_as_json_copy(SPXHANDLE parserOrBuilder, int item);

SPXAPI_(int) ai_core_json_builder_item_add(SPXHANDLE builder, int item, int index, const char* find);
SPXAPI ai_core_json_builder_item_set(SPXHANDLE builder, int item, const char* json, size_t jsize, int kind, const char* str, size_t ssize, bool boolean, int integer, double number);
