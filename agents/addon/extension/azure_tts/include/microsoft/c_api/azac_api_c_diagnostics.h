//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/license202106 for the full license information.
//

#pragma once

// TODO: TFS#3671215 - Vision: C/C++ azac_api* files are in shared include directory, speech and vision share

#ifndef AZAC_SUPPRESS_COMMON_INCLUDE_FROM_DIAGNOSTICS
#define AZAC_SUPPRESS_DIAGNOSTICS_INCLUDE_FROM_COMMON
#include <azac_api_c_common.h>
#undef AZAC_SUPPRESS_DIAGNOSTICS_INCLUDE_FROM_COMMON
#endif

#include <stdarg.h>
#include <stddef.h>

//
// APIs to manage logging to file
//
AZAC_API diagnostics_log_start_logging(AZAC_HANDLE hpropbag, void* reserved);
AZAC_API diagnostics_log_apply_properties(AZAC_HANDLE hpropbag, void* reserved);
AZAC_API diagnostics_log_stop_logging();

//
// APIs to manage logging events
//
typedef void(*DIAGNOSTICS_CALLBACK_FUNC)(const char *logLine);
AZAC_API diagnostics_logmessage_set_callback(DIAGNOSTICS_CALLBACK_FUNC callback);
AZAC_API diagnostics_logmessage_set_filters(const char* filters);

//
// APIs to managed eventSource events
//
typedef void(*DIAGNOSTICS_EVENTSOURCE_CALLBACK_FUNC)(const char *logLine, const int level);
AZAC_API diagnostics_eventsource_logmessage_set_callback(DIAGNOSTICS_EVENTSOURCE_CALLBACK_FUNC callback);
AZAC_API diagnostics_eventsource_logmessage_set_filters(const char* filters);

//
// APIs to manage logging to memory
//
AZAC_API_(void) diagnostics_log_memory_start_logging();
AZAC_API_(void) diagnostics_log_memory_stop_logging();
AZAC_API_(void) diagnostics_log_memory_set_filters(const char* filters);

// The binding layers use these to implement a dump to vector of strings or an output stream
AZAC_API_(size_t) diagnostics_log_memory_get_line_num_oldest();
AZAC_API_(size_t) diagnostics_log_memory_get_line_num_newest();
AZAC_API__(const char*) diagnostics_log_memory_get_line(size_t lineNum);

// Dump to file, std out or std err with optional prefix string
AZAC_API diagnostics_log_memory_dump_to_stderr(); // This calls diagnostics_log_memory_dump(nullptr, nullptr, false, true)
AZAC_API diagnostics_log_memory_dump(const char* filename, const char* linePrefix, bool emitToStdOut, bool emitToStdErr);
AZAC_API diagnostics_log_memory_dump_on_exit(const char* filename, const char* linePrefix, bool emitToStdOut, bool emitToStdErr);

//
// APIs to manage logging to the console
//
AZAC_API_(void) diagnostics_log_console_start_logging(bool logToStderr);
AZAC_API_(void) diagnostics_log_console_stop_logging();
AZAC_API_(void) diagnostics_log_console_set_filters(const char* filters);

//
// APIs to log a string
//
AZAC_API_(void) diagnostics_log_format_message(char* buffer, size_t bufferSize, int level, const char* pszTitle, const char* fileName, const int lineNumber, const char* pszFormat, va_list argptr);
AZAC_API_(void) diagnostics_log_trace_string(int level, const char* pszTitle, const char* fileName, const int lineNumber, const char* psz);
AZAC_API_(void) diagnostics_log_trace_message(int level, const char* pszTitle, const char* fileName, const int lineNumber, const char* pszFormat, ...);
AZAC_API_(void) diagnostics_log_trace_message2(int level, const char* pszTitle, const char* fileName, const int lineNumber, const char* pszFormat, va_list argptr);

AZAC_API_(void) diagnostics_set_log_level(const char * logger, const char * level);
AZAC_API_(bool) diagnostics_is_log_level_enabled(int level);

//
// Memory tracking API's
//
AZAC_API_(size_t) diagnostics_get_handle_count();
AZAC_API__(const char*) diagnostics_get_handle_info();
AZAC_API diagnostics_free_string(const char* value);
