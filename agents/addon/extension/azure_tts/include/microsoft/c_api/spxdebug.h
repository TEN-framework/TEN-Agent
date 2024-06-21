//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// spxdebug.h: Public API definitions for global C Trace/Debug methods and related #defines
//

#pragma once

//-------------------------------------------------------
//  Re-enabled ability to compile out all macros...
//  However, currently still need to keep all macros until
//  final review of all macros is complete.
//-------------------------------------------------------
#define SPX_CONFIG_TRACE_INCLUDE_DBG_WITH_ALL       1

#ifdef SPX_CONFIG_TRACE_INCLUDE_DBG_WITH_ALL
#if defined(SPX_CONFIG_TRACE_ALL) && !defined(SPX_CONFIG_DBG_TRACE_ALL) && (!defined(DEBUG) || !defined(_DEBUG))
#define SPX_CONFIG_DBG_TRACE_ALL                    1
#endif
#endif

//-------------------------------------------------------
//  SPX_ and AZAC_ compatibility section
//  (must preceed #include <azac_debug.h>)
//-------------------------------------------------------

#if defined(SPX_CONFIG_DBG_TRACE_ALL) && !defined(AZAC_CONFIG_DBG_TRACE_ALL)
#define AZAC_CONFIG_DBG_TRACE_ALL SPX_CONFIG_DBG_TRACE_ALL
#elif !defined(SPX_CONFIG_DBG_TRACE_ALL) && defined(AZAC_CONFIG_DBG_TRACE_ALL)
#define SPX_CONFIG_DBG_TRACE_ALL AZAC_CONFIG_DBG_TRACE_ALL
#endif

#if defined(SPX_CONFIG_DBG_TRACE_VERBOSE) && !defined(AZAC_CONFIG_DBG_TRACE_VERBOSE)
#define AZAC_CONFIG_DBG_TRACE_VERBOSE SPX_CONFIG_DBG_TRACE_VERBOSE
#elif !defined(SPX_CONFIG_DBG_TRACE_VERBOSE) && defined(AZAC_CONFIG_DBG_TRACE_VERBOSE)
#define SPX_CONFIG_DBG_TRACE_VERBOSE AZAC_CONFIG_DBG_TRACE_VERBOSE
#endif

#if defined(SPX_CONFIG_DBG_TRACE_INFO) && !defined(AZAC_CONFIG_DBG_TRACE_INFO)
#define AZAC_CONFIG_DBG_TRACE_INFO SPX_CONFIG_DBG_TRACE_INFO
#elif !defined(SPX_CONFIG_DBG_TRACE_INFO) && defined(AZAC_CONFIG_DBG_TRACE_INFO)
#define SPX_CONFIG_DBG_TRACE_INFO AZAC_CONFIG_DBG_TRACE_INFO
#endif

#if defined(SPX_CONFIG_DBG_TRACE_WARNING) && !defined(AZAC_CONFIG_DBG_TRACE_WARNING)
#define AZAC_CONFIG_DBG_TRACE_WARNING SPX_CONFIG_DBG_TRACE_WARNING
#elif !defined(SPX_CONFIG_DBG_TRACE_WARNING) && defined(AZAC_CONFIG_DBG_TRACE_WARNING)
#define SPX_CONFIG_DBG_TRACE_WARNING AZAC_CONFIG_DBG_TRACE_WARNING
#endif

#if defined(SPX_CONFIG_DBG_TRACE_ERROR) && !defined(AZAC_CONFIG_DBG_TRACE_ERROR)
#define AZAC_CONFIG_DBG_TRACE_ERROR SPX_CONFIG_DBG_TRACE_ERROR
#elif !defined(SPX_CONFIG_DBG_TRACE_ERROR) && defined(AZAC_CONFIG_DBG_TRACE_ERROR)
#define SPX_CONFIG_DBG_TRACE_ERROR AZAC_CONFIG_DBG_TRACE_ERROR
#endif

#if defined(SPX_CONFIG_DBG_TRACE_FUNCTION) && !defined(AZAC_CONFIG_DBG_TRACE_FUNCTION)
#define AZAC_CONFIG_DBG_TRACE_FUNCTION SPX_CONFIG_DBG_TRACE_FUNCTION
#elif !defined(SPX_CONFIG_DBG_TRACE_FUNCTION) && defined(AZAC_CONFIG_DBG_TRACE_FUNCTION)
#define SPX_CONFIG_DBG_TRACE_FUNCTION AZAC_CONFIG_DBG_TRACE_FUNCTION
#endif

#if defined(SPX_CONFIG_DBG_TRACE_SCOPE) && !defined(AZAC_CONFIG_DBG_TRACE_SCOPE)
#define AZAC_CONFIG_DBG_TRACE_SCOPE SPX_CONFIG_DBG_TRACE_SCOPE
#elif !defined(SPX_CONFIG_DBG_TRACE_SCOPE) && defined(AZAC_CONFIG_DBG_TRACE_SCOPE)
#define SPX_CONFIG_DBG_TRACE_SCOPE AZAC_CONFIG_DBG_TRACE_SCOPE
#endif

#if defined(SPX_CONFIG_DBG_TRACE_ASSERT) && !defined(AZAC_CONFIG_DBG_TRACE_ASSERT)
#define AZAC_CONFIG_DBG_TRACE_ASSERT SPX_CONFIG_DBG_TRACE_ASSERT
#elif !defined(SPX_CONFIG_DBG_TRACE_ASSERT) && defined(AZAC_CONFIG_DBG_TRACE_ASSERT)
#define SPX_CONFIG_DBG_TRACE_ASSERT AZAC_CONFIG_DBG_TRACE_ASSERT
#endif

#if defined(SPX_CONFIG_DBG_TRACE_VERIFY) && !defined(AZAC_CONFIG_DBG_TRACE_VERIFY)
#define AZAC_CONFIG_DBG_TRACE_VERIFY SPX_CONFIG_DBG_TRACE_VERIFY
#elif !defined(SPX_CONFIG_DBG_TRACE_VERIFY) && defined(AZAC_CONFIG_DBG_TRACE_VERIFY)
#define SPX_CONFIG_DBG_TRACE_VERIFY AZAC_CONFIG_DBG_TRACE_VERIFY
#endif

#if defined(SPX_CONFIG_TRACE_ALL) && !defined(AZAC_CONFIG_TRACE_ALL)
#define AZAC_CONFIG_TRACE_ALL SPX_CONFIG_TRACE_ALL
#elif !defined(SPX_CONFIG_TRACE_ALL) && defined(AZAC_CONFIG_TRACE_ALL)
#define SPX_CONFIG_TRACE_ALL AZAC_CONFIG_TRACE_ALL
#endif

#if defined(SPX_CONFIG_TRACE_VERBOSE) && !defined(AZAC_CONFIG_TRACE_VERBOSE)
#define AZAC_CONFIG_TRACE_VERBOSE SPX_CONFIG_TRACE_VERBOSE
#elif !defined(SPX_CONFIG_TRACE_VERBOSE) && defined(AZAC_CONFIG_TRACE_VERBOSE)
#define SPX_CONFIG_TRACE_VERBOSE AZAC_CONFIG_TRACE_VERBOSE
#endif

#if defined(SPX_CONFIG_TRACE_INFO) && !defined(AZAC_CONFIG_TRACE_INFO)
#define AZAC_CONFIG_TRACE_INFO SPX_CONFIG_TRACE_INFO
#elif !defined(SPX_CONFIG_TRACE_INFO) && defined(AZAC_CONFIG_TRACE_INFO)
#define SPX_CONFIG_TRACE_INFO AZAC_CONFIG_TRACE_INFO
#endif

#if defined(SPX_CONFIG_TRACE_WARNING) && !defined(AZAC_CONFIG_TRACE_WARNING)
#define AZAC_CONFIG_TRACE_WARNING SPX_CONFIG_TRACE_WARNING
#elif !defined(SPX_CONFIG_TRACE_WARNING) && defined(AZAC_CONFIG_TRACE_WARNING)
#define SPX_CONFIG_TRACE_WARNING AZAC_CONFIG_TRACE_WARNING
#endif

#if defined(SPX_CONFIG_TRACE_ERROR) && !defined(AZAC_CONFIG_TRACE_ERROR)
#define AZAC_CONFIG_TRACE_ERROR SPX_CONFIG_TRACE_ERROR
#elif !defined(SPX_CONFIG_TRACE_ERROR) && defined(AZAC_CONFIG_TRACE_ERROR)
#define SPX_CONFIG_TRACE_ERROR AZAC_CONFIG_TRACE_ERROR
#endif

#if defined(SPX_CONFIG_TRACE_FUNCTION) && !defined(AZAC_CONFIG_TRACE_FUNCTION)
#define AZAC_CONFIG_TRACE_FUNCTION SPX_CONFIG_TRACE_FUNCTION
#elif !defined(SPX_CONFIG_TRACE_FUNCTION) && defined(AZAC_CONFIG_TRACE_FUNCTION)
#define SPX_CONFIG_TRACE_FUNCTION AZAC_CONFIG_TRACE_FUNCTION
#endif

#if defined(SPX_CONFIG_TRACE_SCOPE) && !defined(AZAC_CONFIG_TRACE_SCOPE)
#define AZAC_CONFIG_TRACE_SCOPE SPX_CONFIG_TRACE_SCOPE
#elif !defined(SPX_CONFIG_TRACE_SCOPE) && defined(AZAC_CONFIG_TRACE_SCOPE)
#define SPX_CONFIG_TRACE_SCOPE AZAC_CONFIG_TRACE_SCOPE
#endif

#if defined(SPX_CONFIG_TRACE_THROW_ON_FAIL) && !defined(AZAC_CONFIG_TRACE_THROW_ON_FAIL)
#define AZAC_CONFIG_TRACE_THROW_ON_FAIL SPX_CONFIG_TRACE_THROW_ON_FAIL
#elif !defined(SPX_CONFIG_TRACE_THROW_ON_FAIL) && defined(AZAC_CONFIG_TRACE_THROW_ON_FAIL)
#define SPX_CONFIG_TRACE_THROW_ON_FAIL AZAC_CONFIG_TRACE_THROW_ON_FAIL
#endif

#if defined(SPX_CONFIG_TRACE_REPORT_ON_FAIL) && !defined(AZAC_CONFIG_TRACE_REPORT_ON_FAIL)
#define AZAC_CONFIG_TRACE_REPORT_ON_FAIL SPX_CONFIG_TRACE_REPORT_ON_FAIL
#elif !defined(SPX_CONFIG_TRACE_REPORT_ON_FAIL) && defined(AZAC_CONFIG_TRACE_REPORT_ON_FAIL)
#define SPX_CONFIG_TRACE_REPORT_ON_FAIL AZAC_CONFIG_TRACE_REPORT_ON_FAIL
#endif

#if defined(SPX_CONFIG_TRACE_RETURN_ON_FAIL) && !defined(AZAC_CONFIG_TRACE_RETURN_ON_FAIL)
#define AZAC_CONFIG_TRACE_RETURN_ON_FAIL SPX_CONFIG_TRACE_RETURN_ON_FAIL
#elif !defined(SPX_CONFIG_TRACE_RETURN_ON_FAIL) && defined(AZAC_CONFIG_TRACE_RETURN_ON_FAIL)
#define SPX_CONFIG_TRACE_RETURN_ON_FAIL AZAC_CONFIG_TRACE_RETURN_ON_FAIL
#endif

#if defined(SPX_CONFIG_TRACE_EXITFN_ON_FAIL) && !defined(AZAC_CONFIG_TRACE_EXITFN_ON_FAIL)
#define AZAC_CONFIG_TRACE_EXITFN_ON_FAIL SPX_CONFIG_TRACE_EXITFN_ON_FAIL
#elif !defined(SPX_CONFIG_TRACE_EXITFN_ON_FAIL) && defined(AZAC_CONFIG_TRACE_EXITFN_ON_FAIL)
#define SPX_CONFIG_TRACE_EXITFN_ON_FAIL AZAC_CONFIG_TRACE_EXITFN_ON_FAIL
#endif

#if !defined(__AZAC_THROW_HR_IMPL) && defined(__SPX_THROW_HR_IMPL)
#define __AZAC_THROW_HR_IMPL __SPX_THROW_HR_IMPL
#elif !defined(__SPX_THROW_HR_IMPL) && defined(__AZAC_THROW_HR_IMPL)
#define __SPX_THROW_HR_IMPL __AZAC_THROW_HR_IMPL
#elif !defined(__AZAC_THROW_HR_IMPL) && !defined(__SPX_THROW_HR_IMPL)
#define __AZAC_THROW_HR_IMPL __azac_rethrow
#define __SPX_THROW_HR_IMPL __azac_rethrow
#else
#error Both __AZAC_THROW_HR_IMPL and __SPX_THROW_HR_IMPL cannot be defined at the same time
#endif

//-------------------------------------------------------
//  SPX_ and SPX_DBG_ macro configuration
//-------------------------------------------------------

#ifdef SPX_CONFIG_DBG_TRACE_ALL
#define SPX_CONFIG_DBG_TRACE_VERBOSE                1
#define SPX_CONFIG_DBG_TRACE_INFO                   1
#define SPX_CONFIG_DBG_TRACE_WARNING                1
#define SPX_CONFIG_DBG_TRACE_ERROR                  1
#define SPX_CONFIG_DBG_TRACE_FUNCTION               1
#define SPX_CONFIG_DBG_TRACE_SCOPE                  1
#define SPX_CONFIG_DBG_TRACE_ASSERT                 1
#define SPX_CONFIG_DBG_TRACE_VERIFY                 1
#ifndef SPX_CONFIG_TRACE_ALL
#define SPX_CONFIG_TRACE_ALL                        1
#endif
#endif // SPX_CONFIG_DBG_TRACE_ALL

#ifdef SPX_CONFIG_TRACE_ALL
#define SPX_CONFIG_TRACE_VERBOSE                    1
#define SPX_CONFIG_TRACE_INFO                       1
#define SPX_CONFIG_TRACE_WARNING                    1
#define SPX_CONFIG_TRACE_ERROR                      1
#define SPX_CONFIG_TRACE_FUNCTION                   1
#define SPX_CONFIG_TRACE_SCOPE                      1
#define SPX_CONFIG_TRACE_THROW_ON_FAIL              1
#define SPX_CONFIG_TRACE_REPORT_ON_FAIL             1
#define SPX_CONFIG_TRACE_RETURN_ON_FAIL             1
#define SPX_CONFIG_TRACE_EXITFN_ON_FAIL             1
#endif // SPX_CONFIG_TRACE_ALL

//-------------------------------------------------------
//  #include section ...
//  (must come after everything above)
//-------------------------------------------------------

#include <azac_debug.h>
#include <inttypes.h>
#include <spxerror.h>

#ifndef _MSC_VER
// macros in this header generate a bunch of
// "ISO C++11 requires at least one argument for the "..." in a variadic macro" errors.
// system_header pragma is the only mechanism that helps to suppress them.
// https://stackoverflow.com/questions/35587137/how-to-suppress-gcc-variadic-macro-argument-warning-for-zero-arguments-for-a-par
// TODO: try to make macros standard-compliant.
#pragma GCC system_header
#endif

//-----------------------------------------------------------
//  SPX_TRACE macro common implementations
//-----------------------------------------------------------

#define __SPX_TRACE_LEVEL_INFO        __AZAC_TRACE_LEVEL_INFO    // Trace_Info
#define __SPX_TRACE_LEVEL_WARNING     __AZAC_TRACE_LEVEL_WARNING // Trace_Warning
#define __SPX_TRACE_LEVEL_ERROR       __AZAC_TRACE_LEVEL_ERROR   // Trace_Error
#define __SPX_TRACE_LEVEL_VERBOSE     __AZAC_TRACE_LEVEL_VERBOSE // Trace_Verbose

#ifndef __SPX_DO_TRACE_IMPL
#define __SPX_DO_TRACE_IMPL __AZAC_DO_TRACE_IMPL
#endif

#define __SPX_DOTRACE(level, title, fileName, lineNumber, ...) \
        __AZAC_DOTRACE(level, title, fileName, lineNumber, ##__VA_ARGS__)

#define __SPX_TRACE_INFO(title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_INFO(title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define __SPX_TRACE_INFO_IF(cond, title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_INFO_IF(cond, title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define __SPX_TRACE_WARNING(title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_WARNING(title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define __SPX_TRACE_WARNING_IF(cond, title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_WARNING_IF(cond, title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define __SPX_TRACE_ERROR(title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_ERROR(title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define __SPX_TRACE_ERROR_IF(cond, title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_ERROR_IF(cond, title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define __SPX_TRACE_VERBOSE(title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_VERBOSE(title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define __SPX_TRACE_VERBOSE_IF(cond, title, fileName, lineNumber, msg, ...) \
        __AZAC_TRACE_VERBOSE_IF(cond, title, fileName, lineNumber, msg, ##__VA_ARGS__)

#define ___SPX_EXPR_AS_STRING(_String) \
        ___AZAC_EXPR_AS_STRING(_String)

#define __SPX_EXPR_AS_STRING(_String) \
        __AZAC_EXPR_AS_STRING(_String)

#define __SPX_TRACE_HR(title, fileName, lineNumber, hr, x) \
        __AZAC_TRACE_HR(title, fileName, lineNumber, hr, x)

#define __SPX_REPORT_ON_FAIL(title, fileName, lineNumber, hr) \
        __AZAC_REPORT_ON_FAIL(title, fileName, lineNumber, hr)

#define __SPX_REPORT_ON_FAIL_IFNOT(title, fileName, lineNumber, hr, hrNot) \
        __AZAC_REPORT_ON_FAIL_IFNOT(title, fileName, lineNumber, hr, hrNot)

#define __SPX_T_RETURN_HR(title, fileName, lineNumber, hr) \
        __AZAC_T_RETURN_HR(title, fileName, lineNumber, hr)

#define __SPX_T_RETURN_HR_IF(title, fileName, lineNumber, hr, cond) \
        __AZAC_T_RETURN_HR_IF(title, fileName, lineNumber, hr, cond)

#define __SPX_T_RETURN_ON_FAIL(title, fileName, lineNumber, hr) \
        __AZAC_T_RETURN_ON_FAIL(title, fileName, lineNumber, hr)

#define __SPX_T_RETURN_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot) \
        __AZAC_T_RETURN_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot)

#define __SPX_RETURN_HR(hr) \
        __AZAC_RETURN_HR(hr)

#define __SPX_RETURN_HR_IF(hr, cond) \
        __AZAC_RETURN_HR_IF(hr, cond)

#define __SPX_RETURN_ON_FAIL(hr) \
        __AZAC_RETURN_ON_FAIL(hr)

#define __SPX_RETURN_ON_FAIL_IF_NOT(hr, hrNot) \
        __AZAC_RETURN_ON_FAIL_IF_NOT(hr, hrNot)

#define SPX_EXITFN_CLEANUP AZAC_EXITFN_CLEANUP

#define __SPX_T_EXITFN_HR(title, fileName, lineNumber, hr) \
        __AZAC_T_EXITFN_HR(title, fileName, lineNumber, hr)

#define __SPX_T_EXITFN_HR_IF(title, fileName, lineNumber, hr, cond) \
        __AZAC_T_EXITFN_HR_IF(title, fileName, lineNumber, hr, cond)

#define __SPX_T_EXITFN_ON_FAIL(title, fileName, lineNumber, hr) \
        __AZAC_T_EXITFN_ON_FAIL(title, fileName, lineNumber, hr)

#define __SPX_T_EXITFN_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot) \
        __AZAC_T_EXITFN_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot)

#define __SPX_EXITFN_HR(hr) \
        __AZAC_EXITFN_HR(hr)

#define __SPX_EXITFN_HR_IF(hr, cond) \
        __AZAC_EXITFN_HR_IF(hr, cond)

#define __SPX_EXITFN_ON_FAIL(hr) \
        __AZAC_EXITFN_ON_FAIL(hr)

#define __SPX_EXITFN_ON_FAIL_IF_NOT(hr, hrNot) \
        __AZAC_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)

#define __SPX_TRACE_ASSERT(title, fileName, lineNumber, expr) \
        __AZAC_TRACE_ASSERT(title, fileName, lineNumber, expr)

#define __SPX_TRACE_ASSERT_MSG(title, fileName, lineNumber, expr, ...) \
        __AZAC_TRACE_ASSERT_MSG(title, fileName, lineNumber, expr, ##__VA_ARGS__)

#define __SPX_DBG_ASSERT(title, fileName, lineNumber, expr) \
        __AZAC_DBG_ASSERT(title, fileName, lineNumber, expr)

#define __SPX_DBG_ASSERT_WITH_MESSAGE(title, fileName, lineNumber, expr, ...) \
        __AZAC_DBG_ASSERT_WITH_MESSAGE(title, fileName, lineNumber, expr, ##__VA_ARGS__)

#define __SPX_DBG_VERIFY(title, fileName, lineNumber, expr) \
        __AZAC_DBG_VERIFY(title, fileName, lineNumber, expr)

#define __SPX_DBG_VERIFY_WITH_MESSAGE(title, fileName, lineNumber, expr, ...) \
        __AZAC_DBG_VERIFY_WITH_MESSAGE(title, fileName, lineNumber, expr, ##__VA_ARGS__)

#ifdef __cplusplus

#define __SPX_TRACE_SCOPE(t1, fileName, lineNumber, t2, x, y) \
        __AZAC_TRACE_SCOPE(t1, fileName, lineNumber, t2, x, y)

#ifndef __SPX_THROW_HR
#define __SPX_THROW_HR(hr) __SPX_THROW_HR_IMPL(hr)
#endif

#define __SPX_T_THROW_ON_FAIL(title, fileName, lineNumber, hr) \
        __AZAC_T_THROW_ON_FAIL(title, fileName, lineNumber, hr)

#define __SPX_T_THROW_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot) \
        __AZAC_T_THROW_ON_FAIL_IF_NOT(title, fileName, lineNumber, hr, hrNot)

#define __SPX_T_THROW_HR_IF(title, fileName, lineNumber, hr, cond) \
        __AZAC_T_THROW_HR_IF(title, fileName, lineNumber, hr, cond)

#define __SPX_T_THROW_HR(title, fileName, lineNumber, hr) \
        __AZAC_T_THROW_HR(title, fileName, lineNumber, hr)

#define __SPX_THROW_ON_FAIL(hr) \
        __AZAC_THROW_ON_FAIL(hr)

#define __SPX_THROW_ON_FAIL_IF_NOT(hr, hrNot) \
        __AZAC_THROW_ON_FAIL_IF_NOT(hr, hrNot)

#define __SPX_THROW_HR_IF(hr, cond) \
        __AZAC_THROW_HR_IF(hr, cond)

#endif // __cplusplus


//-------------------------------------------------------
//  SPX_ macro definitions
//-------------------------------------------------------

#ifdef SPX_CONFIG_TRACE_VERBOSE
#define SPX_TRACE_VERBOSE(msg, ...)             __SPX_TRACE_VERBOSE("SPX_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_TRACE_VERBOSE_IF(cond, msg, ...)    __SPX_TRACE_VERBOSE_IF(cond, "SPX_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_TRACE_VERBOSE(...)
#define SPX_TRACE_VERBOSE_IF(...)
#endif

#ifdef SPX_CONFIG_DBG_TRACE_VERBOSE
#define SPX_DBG_TRACE_VERBOSE(msg, ...)             __SPX_TRACE_VERBOSE("SPX_DBG_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_DBG_TRACE_VERBOSE_IF(cond, msg, ...)    __SPX_TRACE_VERBOSE_IF(cond, "SPX_DBG_TRACE_VERBOSE: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_DBG_TRACE_VERBOSE(...)
#define SPX_DBG_TRACE_VERBOSE_IF(...)
#endif

#ifdef SPX_CONFIG_TRACE_INFO
#define SPX_TRACE_INFO(msg, ...)                __SPX_TRACE_INFO("SPX_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_TRACE_INFO_IF(cond, msg, ...)       __SPX_TRACE_INFO_IF(cond, "SPX_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_TRACE_INFO(...)
#define SPX_TRACE_INFO_IF(...)
#endif

#ifdef SPX_CONFIG_DBG_TRACE_INFO
#define SPX_DBG_TRACE_INFO(msg, ...)            __SPX_TRACE_INFO("SPX_DBG_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_DBG_TRACE_INFO_IF(cond, msg, ...)   __SPX_TRACE_INFO_IF(cond, "SPX_DBG_TRACE_INFO: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_DBG_TRACE_INFO(...)
#define SPX_DBG_TRACE_INFO_IF(...)
#endif

#ifdef SPX_CONFIG_TRACE_WARNING
#define SPX_TRACE_WARNING(msg, ...)             __SPX_TRACE_WARNING("SPX_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_TRACE_WARNING_IF(cond, msg, ...)    __SPX_TRACE_WARNING_IF(cond, "SPX_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_TRACE_WARNING(...)
#define SPX_TRACE_WARNING_IF(...)
#endif

#ifdef SPX_CONFIG_DBG_TRACE_WARNING
#define SPX_DBG_TRACE_WARNING(msg, ...)          __SPX_TRACE_WARNING("SPX_DBG_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_DBG_TRACE_WARNING_IF(cond, msg, ...) __SPX_TRACE_WARNING_IF(cond, "SPX_DBG_TRACE_WARNING:", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_DBG_TRACE_WARNING(...)
#define SPX_DBG_TRACE_WARNING_IF(...)
#endif

#ifdef SPX_CONFIG_TRACE_ERROR
#define SPX_TRACE_ERROR(msg, ...)               __SPX_TRACE_ERROR("SPX_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_TRACE_ERROR_IF(cond, msg, ...)      __SPX_TRACE_ERROR_IF(cond, "SPX_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_TRACE_ERROR(...)
#define SPX_TRACE_ERROR_IF(...)
#endif

#ifdef SPX_CONFIG_DBG_TRACE_ERROR
#define SPX_DBG_TRACE_ERROR(msg, ...)           __SPX_TRACE_ERROR("SPX_DBG_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#define SPX_DBG_TRACE_ERROR_IF(cond, msg, ...)  __SPX_TRACE_ERROR_IF(cond, "SPX_DBG_TRACE_ERROR: ", __FILE__, __LINE__, msg, ##__VA_ARGS__)
#else
#define SPX_DBG_TRACE_ERROR(...)
#define SPX_DBG_TRACE_ERROR_IF(...)
#endif

#ifdef SPX_CONFIG_TRACE_FUNCTION
#define SPX_TRACE_FUNCTION(...)                 __SPX_TRACE_VERBOSE("SPX_TRACE_FUNCTION: ", __FILE__, __LINE__, __FUNCTION__)
#else
#define SPX_TRACE_FUNCTION(...)
#endif

#ifdef SPX_CONFIG_DBG_TRACE_FUNCTION
#define SPX_DBG_TRACE_FUNCTION(...)             __SPX_TRACE_VERBOSE("SPX_DBG_TRACE_FUNCTION: ", __FILE__, __LINE__, __FUNCTION__)
#else
#define SPX_DBG_TRACE_FUNCTION(...)
#endif

#ifdef SPX_CONFIG_TRACE_REPORT_ON_FAIL
#define SPX_REPORT_ON_FAIL(hr)                      __SPX_REPORT_ON_FAIL("SPX_REPORT_ON_FAIL: ", __FILE__, __LINE__, hr)
#define SPX_REPORT_ON_FAIL_IFNOT(hr, hrNot)         __SPX_REPORT_ON_FAIL_IFNOT("SPX_REPORT_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#else
#define SPX_REPORT_ON_FAIL(hr)                      UNUSED(hr)
#define SPX_REPORT_ON_FAIL_IFNOT(hr, hrNot)         UNUSED(hr); UNUSED(hrNot)
#endif

#ifdef SPX_CONFIG_TRACE_RETURN_ON_FAIL
#define SPX_RETURN_HR(hr)                           __SPX_T_RETURN_HR("SPX_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define SPX_RETURN_HR_IF(hr, cond)                  __SPX_T_RETURN_HR_IF("SPX_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr, cond)
#define SPX_RETURN_ON_FAIL(hr)                      __SPX_T_RETURN_ON_FAIL("SPX_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define SPX_RETURN_ON_FAIL_IF_NOT(hr, hrNot)        __SPX_T_RETURN_ON_FAIL_IF_NOT("SPX_RETURN_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#else
#define SPX_RETURN_HR(hr)                           __SPX_RETURN_HR(hr)
#define SPX_RETURN_HR_IF(hr, cond)                  __SPX_RETURN_HR_IF(hr, cond)
#define SPX_RETURN_ON_FAIL(hr)                      __SPX_RETURN_ON_FAIL(hr)
#define SPX_RETURN_ON_FAIL_IF_NOT(hr, hrNot)        __SPX_RETURN_ON_FAIL_IF_NOT(hr, hrNot)
#endif

#define SPX_IFTRUE_RETURN_HR(cond, hr)              SPX_RETURN_HR_IF(hr, cond)
#define SPX_IFFALSE_RETURN_HR(cond, hr)             SPX_RETURN_HR_IF(hr, !(cond))
#define SPX_IFFAILED_RETURN_HR(hr)                  SPX_RETURN_ON_FAIL(hr)
#define SPX_IFFAILED_RETURN_HR_IFNOT(hr, hrNot)     SPX_RETURN_ON_FAIL_IF_NOT(hr, hrNot)

#ifdef SPX_CONFIG_TRACE_EXITFN_ON_FAIL
#define SPX_EXITFN_HR(hr)                           __SPX_T_EXITFN_HR("SPX_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define SPX_EXITFN_HR_IF(hr, cond)                  __SPX_T_EXITFN_HR_IF("SPX_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr, cond)
#define SPX_EXITFN_ON_FAIL(hr)                      __SPX_T_EXITFN_ON_FAIL("SPX_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr)
#define SPX_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)        __SPX_T_EXITFN_ON_FAIL_IF_NOT("SPX_EXITFN_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#else
#define SPX_EXITFN_HR(hr)                           __SPX_EXITFN_HR(hr)
#define SPX_EXITFN_HR_IF(hr, cond)                  __SPX_EXITFN_HR_IF(hr, cond)
#define SPX_EXITFN_ON_FAIL(hr)                      __SPX_EXITFN_ON_FAIL(hr)
#define SPX_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)        __SPX_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)
#endif

#define SPX_IFTRUE_EXITFN_WHR(cond, hr)             SPX_EXITFN_HR_IF(hr, cond)
#define SPX_IFFALSE_EXITFN_WHR(cond, hr)            SPX_EXITFN_HR_IF(hr, !(cond))
#define SPX_IFFAILED_EXITFN_WHR(hr)                 SPX_EXITFN_ON_FAIL(hr)
#define SPX_IFFAILED_EXITFN_WHR_IFNOT(hr, hrNot)    SPX_EXITFN_ON_FAIL_IF_NOT(hr, hrNot)

#define SPX_IFTRUE_EXITFN_CLEANUP(cond, expr)       AZAC_IFTRUE_EXITFN_CLEANUP(cond, expr)
#define SPX_IFFALSE_EXITFN_CLEANUP(cond, expr)      AZAC_IFFALSE_EXITFN_CLEANUP(cond, expr)

#if defined(SPX_CONFIG_DBG_TRACE_ASSERT) && (defined(DEBUG) || defined(_DEBUG))
#define SPX_DBG_ASSERT(expr)                    __SPX_DBG_ASSERT("SPX_ASSERT: ", __FILE__, __LINE__, expr)
#define SPX_DBG_ASSERT_WITH_MESSAGE(expr, ...)  __SPX_DBG_ASSERT_WITH_MESSAGE("SPX_ASSERT: ", __FILE__, __LINE__, expr, ##__VA_ARGS__)
#else
#define SPX_DBG_ASSERT(expr)
#define SPX_DBG_ASSERT_WITH_MESSAGE(expr, ...)
#endif

#if defined(SPX_CONFIG_DBG_TRACE_VERIFY) && (defined(DEBUG) || defined(_DEBUG))
#define SPX_DBG_VERIFY(expr)                    __SPX_DBG_VERIFY("SPX_VERIFY: ", __FILE__, __LINE__, expr)
#define SPX_DBG_VERIFY_WITH_MESSAGE(expr, ...)  __SPX_DBG_VERIFY_WITH_MESSAGE("SPX_VERIFY: ", __FILE__, __LINE__, expr, ##__VA_ARGS__)
#else
#define SPX_DBG_VERIFY(expr)                    (expr)
#define SPX_DBG_VERIFY_WITH_MESSAGE(expr, ...)  (expr)
#endif

#define SPX_IFTRUE(cond, expr)                      AZAC_IFTRUE(cond, expr)
#define SPX_IFFALSE(cond, expr)                     AZAC_IFFALSE(cond, expr)

#ifdef __cplusplus

#ifdef SPX_CONFIG_TRACE_SCOPE
#define SPX_TRACE_SCOPE(x, y)                   __SPX_TRACE_SCOPE("SPX_TRACE_SCOPE_ENTER: ", __FILE__, __LINE__, "SPX_TRACE_SCOPE_EXIT: ", x, y)
#else
#define SPX_TRACE_SCOPE(x, y)
#endif

#ifdef SPX_CONFIG_DBG_TRACE_SCOPE
#define SPX_DBG_TRACE_SCOPE(x, y)               __SPX_TRACE_SCOPE("SPX_DBG_TRACE_SCOPE_ENTER: ", __FILE__, __LINE__, "SPX_DBG_TRACE_SCOPE_EXIT: ", x, y)
#else
#define SPX_DBG_TRACE_SCOPE(x, y)
#endif

#ifdef SPX_CONFIG_TRACE_THROW_ON_FAIL
#define SPX_THROW_ON_FAIL(hr)                      __SPX_T_THROW_ON_FAIL("SPX_THROW_ON_FAIL: ", __FILE__, __LINE__, hr)
#define SPX_THROW_ON_FAIL_IF_NOT(hr, hrNot)        __SPX_T_THROW_ON_FAIL_IF_NOT("SPX_THROW_ON_FAIL: ", __FILE__, __LINE__, hr, hrNot)
#define SPX_THROW_HR_IF(hr, cond)                  __SPX_T_THROW_HR_IF("SPX_THROW_HR_IF: ", __FILE__, __LINE__, hr, cond)
#define SPX_THROW_HR(hr)                           __SPX_T_THROW_HR("SPX_THROW_HR: ", __FILE__, __LINE__, hr)
#else
#define SPX_THROW_ON_FAIL(hr)                      __SPX_THROW_ON_FAIL(hr)
#define SPX_THROW_ON_FAIL_IF_NOT(hr, hrNot)        __SPX_THROW_ON_FAIL_IF_NOT(hr, hrNot)
#define SPX_THROW_HR_IF(hr, cond)                  __SPX_THROW_HR_IF(hr, cond)
#define SPX_THROW_HR(hr)                           __SPX_THROW_HR(hr)
#endif

#define SPX_IFFAILED_THROW_HR(hr)                   SPX_THROW_ON_FAIL(hr)
#define SPX_IFFAILED_THROW_HR_IFNOT(hr, hrNot)      SPX_THROW_ON_FAIL_IF_NOT(hr, hrNot)

#else // __cplusplus

#define SPX_TRACE_SCOPE(x, y)                      static_assert(false)
#define SPX_DBG_TRACE_SCOPE(x, y)                  static_assert(false)
#define SPX_THROW_ON_FAIL(hr)                      static_assert(false)
#define SPX_THROW_ON_FAIL_IF_NOT(hr, hrNot)        static_assert(false)
#define SPX_THROW_HR_IF(hr, cond)                  static_assert(false)
#define SPX_THROW_HR(hr)                           static_assert(false)
#define SPX_IFFAILED_THROW_HR(hr)                  static_assert(false)
#define SPX_IFFAILED_THROW_HR_IFNOT(hr, hrNot)     static_assert(false)

#endif // __cplusplus
