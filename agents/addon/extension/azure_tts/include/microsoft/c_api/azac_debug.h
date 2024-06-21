//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/license202106 for the full license information.
//

#pragma once
#include <azac_error.h>
#include <inttypes.h>

// TODO: TFS#3671215 - Vision: C/C++ azac_api* files are in shared include directory, speech and vision share

#ifndef _MSC_VER
// macros in this header generate a bunch of
// "ISO C++11 requires at least one argument for the "..." in a variadic macro" errors.
// system_header pragma is the only mechanism that helps to suppress them.
// https://stackoverflow.com/questions/35587137/how-to-suppress-gcc-variadic-macro-argument-warning-for-zero-arguments-for-a-par
// TODO: try to make macros standard-compliant.
#pragma GCC system_header
#endif

#ifndef __cplusplus
#define static_assert _Static_assert
#endif

#define UNUSED(x) (void)(x)

//-------------------------------------------------------
//  Re-enabled ability to compile out all macros...
//  However, currently still need to keep all macros until
//  final review of all macros is complete.
//-------------------------------------------------------

#define AZAC_CONFIG_TRACE_INCLUDE_DBG_WITH_ALL       1

#ifdef AZAC_CONFIG_TRACE_INCLUDE_DBG_WITH_ALL
#if defined(AZAC_CONFIG_TRACE_ALL) && !defined(AZAC_CONFIG_DBG_TRACE_ALL) && (!defined(DEBUG) || !defined(_DEBUG))
#define AZAC_CONFIG_DBG_TRACE_ALL                    1
#endif
#endif

//-------------------------------------------------------
//  AZAC_ and AZAC_DBG_ macro configuration
//-------------------------------------------------------

#ifdef AZAC_CONFIG_DBG_TRACE_ALL
#define AZAC_CONFIG_DBG_TRACE_VERBOSE               1
#define AZAC_CONFIG_DBG_TRACE_INFO                  1
#define AZAC_CONFIG_DBG_TRACE_WARNING               1
#define AZAC_CONFIG_DBG_TRACE_ERROR                 1
#define AZAC_CONFIG_DBG_TRACE_FUNCTION              1
#define AZAC_CONFIG_DBG_TRACE_SCOPE                 1
#define AZAC_CONFIG_DBG_TRACE_ASSERT                1
#define AZAC_CONFIG_DBG_TRACE_VERIFY                1
#ifndef AZAC_CONFIG_TRACE_ALL
#define AZAC_CONFIG_TRACE_ALL                       1
#endif
#endif

#ifdef AZAC_CONFIG_TRACE_ALL
#define AZAC_CONFIG_TRACE_VERBOSE                   1
#define AZAC_CONFIG_TRACE_INFO                      1
#define AZAC_CONFIG_TRACE_WARNING                   1
#define AZAC_CONFIG_TRACE_ERROR                     1
#define AZAC_CONFIG_TRACE_FUNCTION                  1
#define AZAC_CONFIG_TRACE_SCOPE                     1
#define AZAC_CONFIG_TRACE_THROW_ON_FAIL             1
#define AZAC_CONFIG_TRACE_REPORT_ON_FAIL            1
#define AZAC_CONFIG_TRACE_RETURN_ON_FAIL            1
#define AZAC_CONFIG_TRACE_EXITFN_ON_FAIL            1
#endif

//-----------------------------------------------------------
//  AZAC_TRACE macro common implementations
//-----------------------------------------------------------

#define __AZAC_TRACE_LEVEL_INFO         0x08 // Trace_Info
#define __AZAC_TRACE_LEVEL_WARNING      0x04 // Trace_Warning
#define __AZAC_TRACE_LEVEL_ERROR        0x02 // Trace_Error
#define __AZAC_TRACE_LEVEL_VERBOSE      0x10 // Trace_Verbose

#ifndef __AZAC_DO_TRACE_IMPL
#ifdef __cplusplus
#include <algorithm>
#include <stdio.h>
#include <stdarg.h>
#include <string>
inline void __azac_do_trace_message(int level, const char* pszTitle, const char* fileName, const int lineNumber, const char* pszFormat, ...) throw()
{
    UNUSED(level);

    bool logToConsole = false;
#if defined(DEBUG) || defined(_DEBUG)
    logToConsole = true;
#endif

    if (!logToConsole)
    {
        return;
    }

    try
    {
        va_list argptr;
        va_start(argptr, pszFormat);

        std::string format;
        while (*pszFormat == '\n' || *pszFormat == '\r')
        {
            if (*pszFormat == '\r')
            {
                pszTitle = nullptr;
            }

            format += *pszFormat++;
        }

        if (pszTitle != nullptr)
        {
            format += pszTitle;
        }

        std::string fileNameOnly(fileName);
        std::replace(fileNameOnly.begin(), fileNameOnly.end(), '\\', '/');

        std::string fileNameLineNumber = " " + fileNameOnly.substr(fileNameOnly.find_last_of('/', std::string::npos) + 1) + ":" + std::to_string(lineNumber) + " ";

        format += fileNameLineNumber;

        format += pszFormat;

        if (format.length() < 1 || format[format.length() - 1] != '\n')
        {
            format += "\n";
        }

        vfprintf(stderr, format.c_str(), argptr);

        va_end(argptr);
    }
    catch(...)
    {
    }
}
#define __AZAC_DO_TRACE_IMPL __azac_do_trace_message
#else // __cplusplus
#define __AZAC_DO_TRACE_IMPL
#endif // __cplusplus
#endif

#define __AZAC_DOTRACE(level, title, fileName, lineNumber, ...)                     \
    do {                                                                            \
        __AZAC_DO_TRACE_IMPL(level, title, fileName, lineNumber, ##__VA_ARGS__);    \
    } while (0)

#define __AZAC_TRACE_INFO(title, fileName, lineNumber, msg, ...) __AZAC_DOTRACE(__AZAC_TRACE_LEVEL_INFO, title, fileName, lineNumber, msg, ##__VA_ARGS__)
#define __AZAC_TRACE_INFO_IF(cond, title, fileName, lineNumber, msg, ...)           \
    do {                                                                            \
        int fCond = !!(cond);                                                       \
        if (fCond) {                                                                \
            __AZAC_TRACE_INFO(title, fileName, lineNumber, msg, ##__VA_ARGS__);     \
    } } while (0)

#define __AZAC_TRACE_WARNING(title, fileName, lineNumber, msg, ...) __AZAC_DOTRACE(__AZAC_TRACE_LEVEL_WARNING, title, fileName, lineNumber, msg, ##__VA_ARGS__)
#define __AZAC_TRACE_WARNING_IF(cond, title, fileName, lineNumber, msg, ...)        \
    do {                                                                            \
        int fCond = !!(cond);                                                       \
        if (fCond) {                                                                \
            __AZAC_TRACE_WARNING(title, fileName, lineNumber, msg, ##__VA_ARGS__);  \
    } } while (0)

#define __AZAC_TRACE_ERROR(title, fileName, lineNumber, msg, ...) __AZAC_DOTRACE(__AZAC_TRACE_LEVEL_ERROR, title, fileName, lineNumber, msg, ##__VA_ARGS__)
#define __AZAC_TRACE_ERROR_IF(cond, title, fileName, lineNumber, msg, ...)          \
    do {                                                                            \
        int fCond = !!(cond);                                                       \
        if (fCond) {                                                                \
            __AZAC_TRACE_ERROR(title, fileName, lineNumber, msg, ##__VA_ARGS__);    \
    } } while (0)

#define __AZAC_TRACE_VERBOSE(title, fileName, lineNumber, msg, ...) __AZAC_DOTRACE(__AZAC_TRACE_LEVEL_VERBOSE, title, fileName, lineNumber, msg, ##__VA_ARGS__)
#define __AZAC_TRACE_VERBOSE_IF(cond, title, fileName, lineNumber, msg, ...)        \
    do {                                                                            \
        int fCond = !!(cond);                                                       \
        if (fCond) {                                                                \
            __AZAC_TRACE_VERBOSE(title, fileName, lineNumber, msg, ##__VA_ARGS__);  \
    } } while (0)

#define ___AZAC_EXPR_AS_STRING(_String) "" #_String
#define __AZAC_EXPR_AS_STRING(_String) ___AZAC_EXPR_AS_STRING(_String)

#define __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x)             __AZAC_TRACE_ERROR(title, fileName, lineNumber, __AZAC_EXPR_AS_STRING(hr) " = 0x%0" PRIxPTR, x)

#define __AZAC_REPORT_ON_FAIL(title, fileName, lineNumber, hr)                      \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (AZAC_FAILED(x)) {                                                       \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                    \
    } } while (0)
#define __AZAC_REPORT_ON_FAIL_IFNOT(title, fileName, lineNumber, hr, hrNot)         \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (x != hrNot) {                                                           \
            if (AZAC_FAILED(x)) {                                                   \
                __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
    } } } while (0)

#define __AZAC_T_RETURN_HR(title, fileName, lineNumber, hr)                         \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (AZAC_FAILED(x)) {                                                       \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                    \
        }                                                                           \
        return x;                                                                   \
    } while (0)
#define __AZAC_T_RETURN_HR_IF(title, fileName, lineNumber, hr, cond)                \
    do {                                                                            \
        int fCond = !!(cond);                                                       \
        if (fCond) {                                                                \
            AZACHR x = hr;                                                          \
            if (AZAC_FAILED(x)) {                                                   \
                __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
            }                                                                       \
            return x;                                                               \
    } } while (0)
#define __AZAC_T_RETURN_ON_FAIL(title, fileName, lineNumber, hr)                    \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (AZAC_FAILED(x)) {                                                       \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                    \
            return x;                                                               \
    } } while (0)
#define __AZAC_T_RETURN_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot)      \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (x != hrNot) {                                                           \
            if (AZAC_FAILED(x)) {                                                   \
                __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
                return x;                                                           \
    } } } while (0)
#define __AZAC_RETURN_HR(hr) return hr
#define __AZAC_RETURN_HR_IF(hr, cond)                           \
    do {                                                        \
        int fCond = !!(cond);                                   \
        if (fCond) {                                            \
            return hr;                                          \
    } } while (0)
#define __AZAC_RETURN_ON_FAIL(hr)                               \
    do {                                                        \
        AZACHR x = hr;                                          \
        if (AZAC_FAILED(x)) {                                   \
            return x;                                           \
    } } while (0)
#define __AZAC_RETURN_ON_FAIL_IF_NOT(hr, hrNot)                 \
    do {                                                        \
        AZACHR x = hr;                                          \
        if (x != hrNot) {                                       \
            if (AZAC_FAILED(x)) {                               \
                return x;                                       \
    } } } while (0)

#define __AZAC_T_EXITFN_HR(title, fileName, lineNumber, hr)                         \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (AZAC_FAILED(x)) {                                                       \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                    \
        }                                                                           \
        goto AZAC_EXITFN_CLEANUP;                                                   \
    } while (0)
#define __AZAC_T_EXITFN_HR_IF(title, fileName, lineNumber, hr, cond)                \
    do {                                                                            \
        int fCond = !!(cond);                                                       \
        if (fCond) {                                                                \
            AZACHR x = hr;                                                          \
            if (AZAC_FAILED(x)) {                                                   \
                __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
            }                                                                       \
            goto AZAC_EXITFN_CLEANUP;                                               \
    } } while (0)
#define __AZAC_T_EXITFN_ON_FAIL(title, fileName, lineNumber, hr)                    \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (AZAC_FAILED(x)) {                                                       \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                    \
            goto AZAC_EXITFN_CLEANUP;                                               \
    } } while (0)
#define __AZAC_T_EXITFN_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot)      \
    do {                                                                            \
        AZACHR x = hr;                                                              \
        if (x != hrNot) {                                                           \
            if (AZAC_FAILED(x)) {                                                   \
                __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
                goto AZAC_EXITFN_CLEANUP;                                           \
    } } } while (0)

#define __AZAC_EXITFN_HR(hr)                                    \
    do {                                                        \
        AZACHR x = hr;                                          \
        goto AZAC_EXITFN_CLEANUP;                               \
    } while (0)
#define __AZAC_EXITFN_HR_IF(hr, cond)                           \
    do {                                                        \
        int fCond = !!(cond);                                   \
        if (fCond) {                                            \
            AZACHR x = hr;                                      \
            goto AZAC_EXITFN_CLEANUP;                           \
    } } while (0)
#define __AZAC_EXITFN_ON_FAIL(hr)                               \
    do {                                                        \
        AZACHR x = hr;                                          \
        if (AZAC_FAILED(x)) {                                   \
            goto AZAC_EXITFN_CLEANUP;                           \
    } } while (0)
#define __AZAC_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)                 \
    do {                                                        \
        AZACHR x = hr;                                          \
        if (x != hrNot) {                                       \
            if (AZAC_FAILED(x)) {                               \
                goto AZAC_EXITFN_CLEANUP;                       \
    } } } while (0)

#define __AZAC_TRACE_ASSERT(title, fileName, lineNumber, expr)          __AZAC_TRACE_ERROR(title, fileName, lineNumber, __AZAC_EXPR_AS_STRING(expr) " = false")
#define __AZAC_TRACE_ASSERT_MSG(title, fileName, lineNumber, expr, ...) __AZAC_TRACE_ERROR(title, fileName, lineNumber, __AZAC_EXPR_AS_STRING(expr) " = false; " __VA_ARGS__)

#define __AZAC_DBG_ASSERT(title, fileName, lineNumber, expr)                            \
    do {                                                                                \
        int fCond = !!(expr);                                                           \
        if (!fCond) {                                                                   \
            __AZAC_TRACE_ASSERT(title, fileName, lineNumber, expr);                     \
            abort();                                                                    \
    } } while (0)
#define __AZAC_DBG_ASSERT_WITH_MESSAGE(title, fileName, lineNumber, expr, ...)          \
    do {                                                                                \
        int fCond = !!(expr);                                                           \
        if (!fCond) {                                                                   \
            __AZAC_TRACE_ASSERT_MSG(title, fileName, lineNumber, expr, ##__VA_ARGS__);  \
            abort();                                                                    \
    } } while (0)

#define __AZAC_DBG_VERIFY(title, fileName, lineNumber, expr)                            \
    do {                                                                                \
        int fCond = !!(expr);                                                           \
        if (!fCond) {                                                                   \
            __AZAC_TRACE_ASSERT(title, fileName, lineNumber, expr);                     \
            abort();                                                                    \
    } } while (0)
#define __AZAC_DBG_VERIFY_WITH_MESSAGE(title, fileName, lineNumber, expr, ...)          \
    do {                                                                                \
        int fCond = !!(expr);                                                           \
        if (!fCond) {                                                                   \
            __AZAC_TRACE_ASSERT_MSG(title, fileName, lineNumber, expr, ##__VA_ARGS__);  \
            abort();                                                                    \
    } } while (0)

#ifdef __cplusplus

#include <memory>
#define __AZAC_TRACE_SCOPE(t1, fileName, lineNumber, t2, x, y)                                                  \
    __AZAC_TRACE_INFO(t1, fileName, lineNumber, "%s", x);                                                       \
    auto evaluateYInScopeInMacros##lineNumber = y;                                                              \
    auto leavingScopePrinterInMacros##lineNumber = [&evaluateYInScopeInMacros##lineNumber](int*) -> void {      \
        __AZAC_TRACE_INFO(t2, fileName, lineNumber, "%s", evaluateYInScopeInMacros##lineNumber);                \
    };                                                                                                          \
    std::unique_ptr<int, decltype(leavingScopePrinterInMacros##lineNumber)> onExit##lineNumber((int*)1, leavingScopePrinterInMacros##lineNumber)

#ifndef __AZAC_THROW_HR_IMPL
#define __AZAC_THROW_HR_IMPL(hr) __azac_rethrow(hr)
#endif
#ifndef __AZAC_THROW_HR
#define __AZAC_THROW_HR(hr) __AZAC_THROW_HR_IMPL(hr)
#endif

#ifndef __AZAC_LOG_HR_IMPL
#define __AZAC_LOG_HR_IMPL(hr) __azac_log_only(hr)
#endif
#ifndef __AZAC_LOG_HR
#define __AZAC_LOG_HR(hr) __AZAC_LOG_HR_IMPL(hr)
#endif

#define __AZAC_T_LOG_ON_FAIL(title, fileName, lineNumber, hr)                   \
    do {                                                                        \
        AZACHR x = hr;                                                          \
        if (AZAC_FAILED(x)) {                                                   \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
            __AZAC_LOG_HR(x);                                                   \
    } } while (0)
#define __AZAC_T_THROW_ON_FAIL(title, fileName, lineNumber, hr)                 \
    do {                                                                        \
        AZACHR x = hr;                                                          \
        if (AZAC_FAILED(x)) {                                                   \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
            __AZAC_THROW_HR(x);                                                 \
    } } while (0)
#define __AZAC_T_THROW_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot)   \
    do {                                                                        \
        AZACHR x = hr;                                                          \
        if (x != hrNot) {                                                       \
            if (AZAC_FAILED(x)) {                                               \
                __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);            \
                __AZAC_THROW_HR(x);                                             \
    } } } while (0)
#define __AZAC_T_THROW_HR_IF(title, fileName, lineNumber, hr, cond)             \
    do {                                                                        \
        int fCond = !!(cond);                                                   \
        if (fCond) {                                                            \
            AZACHR x = hr;                                                      \
            __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                \
            __AZAC_THROW_HR(x);                                                 \
    } } while (0)
#define __AZAC_T_THROW_HR(title, fileName, lineNumber, hr)                      \
    do {                                                                        \
        AZACHR x = hr;                                                          \
        __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x);                    \
        __AZAC_THROW_HR(x);                                                     \
    } while (0)


#define __AZAC_LOG_ON_FAIL(hr)                                  \
    do {                                                        \
        AZACHR x = hr;                                          \
        if (AZAC_FAILED(x)) {                                   \
            __AZAC_LOG_HR(x);                                   \
    } } while (0)
#define __AZAC_THROW_ON_FAIL(hr)                                \
    do {                                                        \
        AZACHR x = hr;                                          \
        if (AZAC_FAILED(x)) {                                   \
            __AZAC_THROW_HR(x);                                 \
    } } while (0)
#define __AZAC_THROW_ON_FAIL_IF_NOT(hr, hrNot)                  \
    do {                                                        \
        AZACHR x = hr;                                          \
        if (x != hrNot) {                                       \
            if (AZAC_FAILED(x)) {                               \
                __AZAC_THROW_HR(x);                             \
    } } } while (0)
#define __AZAC_THROW_HR_IF(hr, cond)                            \
    do {                                                        \
        int fCond = !!(cond);                                   \
        if (fCond) {                                            \
            AZACHR x = hr;                                      \
            __AZAC_THROW_HR(x);                                 \
    } } while (0)

#endif // __cplusplus



//-------------------------------------------------------
//  AZAC_ macro definitions
//-------------------------------------------------------

#ifdef AZAC_CONFIG_TRACE_VERBOSE
#define AZAC_TRACE_VERBOSE(msg, ...)          __AZAC_TRACE_VERBOSE("AZAC_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_TRACE_VERBOSE_IF(cond, msg, ...) __AZAC_TRACE_VERBOSE_IF(cond, "AZAC_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_TRACE_VERBOSE(...)
#define AZAC_TRACE_VERBOSE_IF(...)
#endif

#ifdef AZAC_CONFIG_DBG_TRACE_VERBOSE
#define AZAC_DBG_TRACE_VERBOSE(msg, ...)          __AZAC_TRACE_VERBOSE("AZAC_DBG_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_DBG_TRACE_VERBOSE_IF(cond, msg, ...) __AZAC_TRACE_VERBOSE_IF(cond, "AZAC_DBG_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_DBG_TRACE_VERBOSE(...)
#define AZAC_DBG_TRACE_VERBOSE_IF(...)
#endif

#ifdef AZAC_CONFIG_TRACE_INFO
#define AZAC_TRACE_INFO(msg, ...)           __AZAC_TRACE_INFO("AZAC_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_TRACE_INFO_IF(cond, msg, ...)  __AZAC_TRACE_INFO_IF(cond, "AZAC_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_TRACE_INFO(...)
#define AZAC_TRACE_INFO_IF(...)
#endif

#ifdef AZAC_CONFIG_DBG_TRACE_INFO
#define AZAC_DBG_TRACE_INFO(msg, ...)           __AZAC_TRACE_INFO("AZAC_DBG_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_DBG_TRACE_INFO_IF(cond, msg, ...)  __AZAC_TRACE_INFO_IF(cond, "AZAC_DBG_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_DBG_TRACE_INFO(...)
#define AZAC_DBG_TRACE_INFO_IF(...)
#endif

#ifdef AZAC_CONFIG_TRACE_WARNING
#define AZAC_TRACE_WARNING(msg, ...)          __AZAC_TRACE_WARNING("AZAC_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_TRACE_WARNING_IF(cond, msg, ...) __AZAC_TRACE_WARNING_IF(cond, "AZAC_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_TRACE_WARNING(...)
#define AZAC_TRACE_WARNING_IF(...)
#endif

#ifdef AZAC_CONFIG_DBG_TRACE_WARNING
#define AZAC_DBG_TRACE_WARNING(msg, ...)          __AZAC_TRACE_WARNING("AZAC_DBG_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_DBG_TRACE_WARNING_IF(cond, msg, ...) __AZAC_TRACE_WARNING_IF(cond, "AZAC_DBG_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_DBG_TRACE_WARNING(...)
#define AZAC_DBG_TRACE_WARNING_IF(...)
#endif

#ifdef AZAC_CONFIG_TRACE_ERROR
#define AZAC_TRACE_ERROR(msg, ...)            __AZAC_TRACE_ERROR("AZAC_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_TRACE_ERROR_IF(cond, msg, ...)   __AZAC_TRACE_ERROR_IF(cond, "AZAC_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_TRACE_ERROR(...)
#define AZAC_TRACE_ERROR_IF(...)
#endif

#ifdef AZAC_CONFIG_DBG_TRACE_ERROR
#define AZAC_DBG_TRACE_ERROR(msg, ...)            __AZAC_TRACE_ERROR("AZAC_DBG_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define AZAC_DBG_TRACE_ERROR_IF(cond, msg, ...)   __AZAC_TRACE_ERROR_IF(cond, "AZAC_DBG_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define AZAC_DBG_TRACE_ERROR(...)
#define AZAC_DBG_TRACE_ERROR_IF(...)
#endif

#ifdef AZAC_CONFIG_TRACE_FUNCTION
#define AZAC_TRACE_FUNCTION(...) __AZAC_TRACE_VERBOSE("AZAC_TRACE_FUNCTION: ", __FILE__, __LINE__, __FUNCTION__)
#else
#define AZAC_TRACE_FUNCTION(...)
#endif

#ifdef AZAC_CONFIG_DBG_TRACE_FUNCTION
#define AZAC_DBG_TRACE_FUNCTION(...) __AZAC_TRACE_VERBOSE("AZAC_DBG_TRACE_FUNCTION: ", __FILE__, __LINE__, __FUNCTION__)
#else
#define AZAC_DBG_TRACE_FUNCTION(...)
#endif

#ifdef AZAC_CONFIG_TRACE_REPORT_ON_FAIL
#define AZAC_REPORT_ON_FAIL(hr)                     __AZAC_REPORT_ON_FAIL("AZAC_REPORT_ON_FAIL: ", __FILE__, __LINE__, hr)
#define AZAC_REPORT_ON_FAIL_IFNOT(hr, hrNot)        __AZAC_REPORT_ON_FAIL_IFNOT("AZAC_REPORT_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#else
#define AZAC_REPORT_ON_FAIL(hr)                     UNUSED(hr)
#define AZAC_REPORT_ON_FAIL_IFNOT(hr, hrNot)        UNUSED(hr); UNUSED(hrNot)
#endif

#ifdef AZAC_CONFIG_TRACE_RETURN_ON_FAIL
#define AZAC_RETURN_HR(hr)                          __AZAC_T_RETURN_HR("AZAC_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define AZAC_RETURN_HR_IF(hr, cond)                 __AZAC_T_RETURN_HR_IF("AZAC_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr, cond)
#define AZAC_RETURN_ON_FAIL(hr)                     __AZAC_T_RETURN_ON_FAIL("AZAC_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define AZAC_RETURN_ON_FAIL_IF_NOT(hr, hrNot)       __AZAC_T_RETURN_ON_FAIL_IF_NOT("AZAC_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#else
#define AZAC_RETURN_HR(hr)                          __AZAC_RETURN_HR(hr)
#define AZAC_RETURN_HR_IF(hr, cond)                 __AZAC_RETURN_HR_IF(hr, cond)
#define AZAC_RETURN_ON_FAIL(hr)                     __AZAC_RETURN_ON_FAIL(hr)
#define AZAC_RETURN_ON_FAIL_IF_NOT(hr, hrNot)       __AZAC_RETURN_ON_FAIL_IF_NOT(hr, hrNot)
#endif

#define AZAC_IFTRUE_RETURN_HR(cond, hr)             AZAC_RETURN_HR_IF(hr, cond)
#define AZAC_IFFALSE_RETURN_HR(cond, hr)            AZAC_RETURN_HR_IF(hr, !(cond))
#define AZAC_IFFAILED_RETURN_HR(hr)                 AZAC_RETURN_ON_FAIL(hr)
#define AZAC_IFFAILED_RETURN_HR_IFNOT(hr, hrNot)    AZAC_RETURN_ON_FAIL_IF_NOT(hr, hrNot)

#ifdef AZAC_CONFIG_TRACE_EXITFN_ON_FAIL
#define AZAC_EXITFN_HR(hr)                          __AZAC_T_EXITFN_HR("AZAC_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define AZAC_EXITFN_HR_IF(hr, cond)                 __AZAC_T_EXITFN_HR_IF("AZAC_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr, cond)
#define AZAC_EXITFN_ON_FAIL(hr)                     __AZAC_T_EXITFN_ON_FAIL("AZAC_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define AZAC_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)       __AZAC_EXITFN_ON_FAIL_IF_NOT("AZAC_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#else
#define AZAC_EXITFN_HR(hr)                          __AZAC_EXITFN_HR(hr)
#define AZAC_EXITFN_HR_IF(hr, cond)                 __AZAC_EXITFN_HR_IF(hr, cond)
#define AZAC_EXITFN_ON_FAIL(hr)                     __AZAC_EXITFN_ON_FAIL(hr)
#define AZAC_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)       __AZAC_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)
#endif

#define AZAC_IFTRUE_EXITFN_WHR(cond, hr)            AZAC_EXITFN_HR_IF(hr, cond)
#define AZAC_IFFALSE_EXITFN_WHR(cond, hr)           AZAC_EXITFN_HR_IF(hr, !(cond))
#define AZAC_IFFAILED_EXITFN_WHR(hr)                AZAC_EXITFN_ON_FAIL(hr)
#define AZAC_IFFAILED_EXITFN_WHR_IFNOT(hr, hrNot)   AZAC_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)

#define AZAC_IFTRUE_EXITFN_CLEANUP(cond, expr)                  \
    do {                                                        \
        int fCondT = !!(cond);                                  \
        if (fCondT) {                                           \
            expr;                                               \
            goto AZAC_EXITFN_CLEANUP;                           \
    } } while (0)

#define AZAC_IFFALSE_EXITFN_CLEANUP(cond, expr)                 \
    do {                                                        \
        int fCondF = !!(cond);                                  \
        if (!fCondF) {                                          \
            expr;                                               \
            goto AZAC_EXITFN_CLEANUP;                           \
    } } while (0)

#if defined(AZAC_CONFIG_DBG_TRACE_ASSERT) && (defined(DEBUG) || defined(_DEBUG))
#define AZAC_DBG_ASSERT(expr)                   __AZAC_DBG_ASSERT("AZAC_ASSERT: ", __FILE__, __LINE__, expr)
#define AZAC_DBG_ASSERT_WITH_MESSAGE(expr, ...) __AZAC_DBG_ASSERT_WITH_MESSAGE("AZAC_ASSERT: ", __FILE__, __LINE__, expr, ##__VA_ARGS__)
#else
#define AZAC_DBG_ASSERT(expr)
#define AZAC_DBG_ASSERT_WITH_MESSAGE(expr, ...)
#endif

#if defined(AZAC_CONFIG_DBG_TRACE_VERIFY) && (defined(DEBUG) || defined(_DEBUG))
#define AZAC_DBG_VERIFY(expr)                   __AZAC_DBG_VERIFY("AZAC_VERIFY: ", __FILE__, __LINE__, expr)
#define AZAC_DBG_VERIFY_WITH_MESSAGE(expr, ...) __AZAC_DBG_VERIFY_WITH_MESSAGE("AZAC_VERIFY: ", __FILE__, __LINE__, expr, ##__VA_ARGS__)
#else
#define AZAC_DBG_VERIFY(expr)                        (expr)
#define AZAC_DBG_VERIFY_WITH_MESSAGE(expr, ...)      (expr)
#endif

#define AZAC_IFTRUE(cond, expr) \
    do {                                                        \
        int fCondT = !!(cond);                                  \
        if (fCondT) {                                           \
            expr;                                               \
    } } while (0)

#define AZAC_IFFALSE(cond, expr) \
    do {                                                        \
        int fCondF = !!(cond);                                  \
        if (!fCondF) {                                          \
            expr;                                               \
    } } while (0)

// handle circular dependency
#ifndef AZAC_SUPPRESS_COMMON_INCLUDE_FROM_DEBUG
#define AZAC_SUPPRESS_DEBUG_INCLUDE_FROM_COMMON
#include <azac_api_c_common.h>
#undef AZAC_SUPPRESS_DEBUG_INCLUDE_FROM_COMMON
#endif

#ifdef __cplusplus

#ifdef AZAC_CONFIG_TRACE_SCOPE
#define AZAC_TRACE_SCOPE(x, y) __AZAC_TRACE_SCOPE("AZAC_TRACE_SCOPE_ENTER: ", __FILE__, __LINE__, "AZAC_TRACE_SCOPE_EXIT: ", x, y)
#else
#define AZAC_TRACE_SCOPE(x, y)
#endif

#ifdef AZAC_CONFIG_DBG_TRACE_SCOPE
#define AZAC_DBG_TRACE_SCOPE(x, y) __AZAC_TRACE_SCOPE("AZAC_DBG_TRACE_SCOPE_ENTER: ", __FILE__, __LINE__, "AZAC_DBG_TRACE_SCOPE_EXIT: ", x, y)
#else
#define AZAC_DBG_TRACE_SCOPE(x, y)
#endif

#ifdef AZAC_CONFIG_TRACE_THROW_ON_FAIL
#define AZAC_THROW_ON_FAIL(hr)                      __AZAC_T_THROW_ON_FAIL("AZAC_THROW_ON_FAIL: ", __FILE__, __LINE__, hr)
#define AZAC_THROW_ON_FAIL_IF_NOT(hr, hrNot)        __AZAC_T_THROW_ON_FAIL_IF_NOT("AZAC_THROW_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#define AZAC_LOG_ON_FAIL(hr)                        __AZAC_T_LOG_ON_FAIL("AZAC_LOG_ON_FAIL: ", __FILE__, __LINE__, hr)
#define AZAC_THROW_HR_IF(hr, cond)                  __AZAC_T_THROW_HR_IF("AZAC_THROW_HR_IF: ", __FILE__, __LINE__, hr, cond)
#define AZAC_THROW_HR(hr)                           __AZAC_T_THROW_HR("AZAC_THROW_HR: ", __FILE__, __LINE__, hr)
#else
#define AZAC_THROW_ON_FAIL(hr)                      __AZAC_THROW_ON_FAIL(hr)
#define AZAC_THROW_ON_FAIL_IF_NOT(hr, hrNot)        __AZAC_THROW_ON_FAIL_IF_NOT(hr, hrNot)
#define AZAC_LOG_ON_FAIL(hr)                        __AZAC_LOG_ON_FAIL(hr)
#define AZAC_THROW_HR_IF(hr, cond)                  __AZAC_THROW_HR_IF(hr, cond)
#define AZAC_THROW_HR(hr)                           __AZAC_THROW_HR(hr)
#endif

#define AZAC_IFTRUE_THROW_HR(cond, hr)              AZAC_THROW_HR_IF(hr, cond)
#define AZAC_IFFALSE_THROW_HR(cond, hr)             AZAC_THROW_HR_IF(hr, !(cond))
#define AZAC_IFFAILED_THROW_HR(hr)                  AZAC_THROW_ON_FAIL(hr)
#define AZAC_IFFAILED_THROW_HR_IFNOT(hr, hrNot)     AZAC_THROW_ON_FAIL_IF_NOT(hr, hrNot)

#include <azac_api_c_error.h>
#include <azac_api_c_diagnostics.h>
#include <stdexcept>
#include <string>

inline void __azac_handle_native_ex(AZACHR hr, bool throwException)
{
    AZAC_TRACE_SCOPE(__FUNCTION__, __FUNCTION__);

    auto handle = reinterpret_cast<AZAC_HANDLE>(hr);
    auto error = error_get_error_code(handle);
    if (error == AZAC_ERR_NONE)
    {
        if (throwException)
        {
            throw hr;
        }
        else
        {
            // do nothing. This is already logged by the macros that call this function
            return;
        }
    }

    std::string errorMsg;
    try
    {
        auto callstack = error_get_call_stack(handle);
        auto what = error_get_message(handle);

        if (what)
        {
            errorMsg += what;
        }
        else
        {
            errorMsg += "Exception with error code: ";
            errorMsg += std::to_string(error);
        }

        if (callstack)
        {
            errorMsg += callstack;
        }
    }
    catch (...)
    {
        error_release(handle);
        throw hr;
    }

    error_release(handle);
    if (throwException)
    {
        throw std::runtime_error(errorMsg);
    }
    else
    {
        AZAC_TRACE_ERROR("Error details: %s", errorMsg.c_str());
    }
}

inline void __azac_log_only(AZACHR hr)
{
    __azac_handle_native_ex(hr, false);
}

inline void __azac_rethrow(AZACHR hr)
{
    __azac_handle_native_ex(hr, true);
}

#else // __cplusplus

#define AZAC_TRACE_SCOPE(x, y)                      static_assert(false)
#define AZAC_DBG_TRACE_SCOPE(x, y)                  static_assert(false)
#define AZAC_LOG_ON_FAIL(hr)                        static_assert(false)
#define AZAC_THROW_ON_FAIL(hr)                      static_assert(false)
#define AZAC_THROW_ON_FAIL_IF_NOT(hr, hrNot)        static_assert(false)
#define AZAC_THROW_HR_IF(hr, cond)                  static_assert(false)
#define AZAC_THROW_HR(hr)                           static_assert(false)
#define AZAC_IFTRUE_THROW_HR(cond, hr)              static_assert(false)
#define AZAC_IFFALSE_THROW_HR(cond, hr)             static_assert(false)
#define AZAC_IFFAILED_THROW_HR(hr)                  static_assert(false)
#define AZAC_IFFAILED_THROW_HR_IFNOT(hr, hrNot)     static_assert(false)

#endif // __cplusplus

//---------------------------------------------------------------------------

#ifdef __AZAC_DEBUG_H_EXAMPLES_IN_MAIN

void main()
{
    int x = 4;
    printf("%s = %d\n", __AZAC_EXPR_AS_STRING(x + 3), x + 3);

    AZAC_TRACE_INFO("hello there");
    AZAC_TRACE_ERROR("hello there");
    AZAC_TRACE_WARNING("hello there");
    AZAC_TRACE_VERBOSE("hello there");

    AZAC_TRACE_INFO("hello there %d", 5);
    AZAC_TRACE_ERROR("hello there %d", 5);
    AZAC_TRACE_WARNING("hello there %d", 5);
    AZAC_TRACE_VERBOSE("hello there %d", 5);

    AZAC_TRACE_INFO_IF(false, "hello there false");
    AZAC_TRACE_ERROR_IF(false, "hello there false");
    AZAC_TRACE_WARNING_IF(false, "hello there false");
    AZAC_TRACE_VERBOSE_IF(false, "hello there false");

    AZAC_TRACE_INFO_IF(false, "hello there false %d", 5);
    AZAC_TRACE_ERROR_IF(false, "hello there false %d", 5);
    AZAC_TRACE_WARNING_IF(false, "hello there false %d", 5);
    AZAC_TRACE_VERBOSE_IF(false, "hello there false %d", 5);

    AZAC_TRACE_INFO_IF(true, "hello there true");
    AZAC_TRACE_ERROR_IF(true, "hello there true");
    AZAC_TRACE_WARNING_IF(true, "hello there true");
    AZAC_TRACE_VERBOSE_IF(true, "hello there true");

    AZAC_TRACE_INFO_IF(true, "hello there true %d", 5);
    AZAC_TRACE_ERROR_IF(true, "hello there true %d", 5);
    AZAC_TRACE_WARNING_IF(true, "hello there true %d", 5);
    AZAC_TRACE_VERBOSE_IF(true, "hello there true %d", 5);

    AZAC_DBG_TRACE_INFO("hello there");
    AZAC_DBG_TRACE_ERROR("hello there");
    AZAC_DBG_TRACE_WARNING("hello there");
    AZAC_DBG_TRACE_VERBOSE("hello there");

    AZAC_DBG_TRACE_INFO("hello there %d", 5);
    AZAC_DBG_TRACE_ERROR("hello there %d", 5);
    AZAC_DBG_TRACE_WARNING("hello there %d", 5);
    AZAC_DBG_TRACE_VERBOSE("hello there %d", 5);

    AZAC_DBG_TRACE_INFO_IF(false, "hello there false");
    AZAC_DBG_TRACE_ERROR_IF(false, "hello there false");
    AZAC_DBG_TRACE_WARNING_IF(false, "hello there false");
    AZAC_DBG_TRACE_VERBOSE_IF(false, "hello there false");

    AZAC_DBG_TRACE_INFO_IF(false, "hello there false %d", 5);
    AZAC_DBG_TRACE_ERROR_IF(false, "hello there false %d", 5);
    AZAC_DBG_TRACE_WARNING_IF(false, "hello there false %d", 5);
    AZAC_DBG_TRACE_VERBOSE_IF(false, "hello there false %d", 5);

    AZAC_DBG_TRACE_INFO_IF(true, "hello there true");
    AZAC_DBG_TRACE_ERROR_IF(true, "hello there true");
    AZAC_DBG_TRACE_WARNING_IF(true, "hello there true");
    AZAC_DBG_TRACE_VERBOSE_IF(true, "hello there true");

    AZAC_DBG_TRACE_INFO_IF(true, "hello there true %d", 5);
    AZAC_DBG_TRACE_ERROR_IF(true, "hello there true %d", 5);
    AZAC_DBG_TRACE_WARNING_IF(true, "hello there true %d", 5);
    AZAC_DBG_TRACE_VERBOSE_IF(true, "hello there true %d", 5);

    AZAC_TRACE_SCOPE("A", "B");

    AZAC_TRACE_FUNCTION();
    AZAC_DBG_TRACE_FUNCTION();

    AZAC_DBG_ASSERT(false);
    AZAC_DBG_ASSERT(true);

    AZAC_DBG_ASSERT_WITH_MESSAGE(false, "HEY!");
    AZAC_DBG_ASSERT_WITH_MESSAGE(true, "HEY!!");

    AZAC_DBG_VERIFY(false);
    AZAC_DBG_VERIFY(true);

    AZAC_DBG_VERIFY_WITH_MESSAGE(false, "HEY!");
    AZAC_DBG_VERIFY_WITH_MESSAGE(true, "HEY!!");

    AZACHR hr1 { 0x80001111 };
    AZACHR hr2 { 0x00001111 };

    AZAC_TRACE_VERBOSE("Testing out AZAC_REPORT_ON_FAIL, should see two failures...");
    AZAC_REPORT_ON_FAIL(hr1);
    AZAC_REPORT_ON_FAIL_IFNOT(hr1, 0x80001000);
    AZAC_TRACE_VERBOSE("Testing out AZAC_REPORT_ON_FAIL, should see two failures... Done!");

    AZAC_TRACE_VERBOSE("Testing out AZAC_REPORT_ON_FAIL, should see zero failures...");
    AZAC_REPORT_ON_FAIL(hr2);
    AZAC_REPORT_ON_FAIL_IFNOT(hr1, 0x80001111);
    AZAC_REPORT_ON_FAIL_IFNOT(hr2, 0x80001111);
    AZAC_REPORT_ON_FAIL_IFNOT(hr2, 0x80001000);
    AZAC_TRACE_VERBOSE("Testing out AZAC_REPORT_ON_FAIL, should see zero failures... Done!");
}

#endif
