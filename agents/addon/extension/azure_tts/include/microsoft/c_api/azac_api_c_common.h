//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/license202106 for the full license information.
//

#pragma once

// TODO: TFS#3671215 - Vision: C/C++ azac_api* files are in shared include directory, speech and vision share

#include <stdbool.h>
#include <azac_error.h>

#ifdef __cplusplus
#define AZAC_EXTERN_C           extern "C"
#else
#define AZAC_EXTERN_C
#endif

#ifdef _WIN32
#define AZAC_DLL_EXPORT         __declspec(dllexport)
#define AZAC_DLL_IMPORT         __declspec(dllimport)
#define AZAC_API_NOTHROW        __declspec(nothrow)
#define AZAC_API_RESULTTYPE     AZACHR
#define AZAC_API_CALLTYPE       __stdcall
#define AZAC_API_VCALLTYPE      __cdecl
#else
#define AZAC_DLL_EXPORT         __attribute__ ((__visibility__("default")))
#define AZAC_DLL_IMPORT
#define AZAC_API_NOTHROW        __attribute__((nothrow))
#define AZAC_API_RESULTTYPE     AZACHR
#define AZAC_API_CALLTYPE
#define AZAC_API_VCALLTYPE      __attribute__((cdecl))
#endif

#ifdef AZAC_CONFIG_EXPORTAPIS
#define AZAC_API_EXPORT         AZAC_DLL_EXPORT
#endif
#ifdef AZAC_CONFIG_IMPORTAPIS
#define AZAC_API_EXPORT         AZAC_DLL_IMPORT
#endif
#ifdef AZAC_CONFIG_STATIC_LINK_APIS
#define AZAC_API_EXPORT
#endif
#ifndef AZAC_API_EXPORT
#define AZAC_API_EXPORT         AZAC_DLL_IMPORT
#endif

#define AZAC_API                AZAC_EXTERN_C AZAC_API_EXPORT AZAC_API_RESULTTYPE AZAC_API_NOTHROW AZAC_API_CALLTYPE
#define AZAC_API_(type)         AZAC_EXTERN_C AZAC_API_EXPORT type AZAC_API_NOTHROW AZAC_API_CALLTYPE
#define AZAC_API__(type)        AZAC_EXTERN_C AZAC_API_EXPORT AZAC_API_NOTHROW type AZAC_API_CALLTYPE
#define AZAC_APIV               AZAC_EXTERN_C AZAC_API_EXPORT AZAC_API_NOTHROW AZAC_API_RESULTTYPE AZAC_API_VCALLTYPE
#define AZAC_APIV_(type)        AZAC_EXTERN_C AZAC_API_EXPORT AZAC_API_NOTHROW type AZAC_API_VCALLTYPE
#define AZAC_API_PRIVATE        AZAC_EXTERN_C AZAC_API_RESULTTYPE AZAC_API_NOTHROW AZAC_API_CALLTYPE
#define AZAC_API_PRIVATE_(type) AZAC_EXTERN_C type AZAC_API_NOTHROW AZAC_API_CALLTYPE

struct _azac_empty {};
typedef struct _azac_empty* _azachandle;
typedef _azachandle AZAC_HANDLE;

#define AZAC_HANDLE_INVALID     ((AZAC_HANDLE)-1)
#define AZAC_HANDLE_RESERVED1   ((AZAC_HANDLE)+1)

#ifndef AZAC_SUPPRESS_DIAGNOSTICS_INCLUDE_FROM_COMMON
#define AZAC_SUPPRESS_COMMON_INCLUDE_FROM_DIAGNOSTICS
#include <azac_api_c_diagnostics.h>
#undef AZAC_SUPPRESS_COMMON_INCLUDE_FROM_DIAGNOSTICS
#endif

#ifndef AZAC_SUPPRESS_ERROR_INCLUDE_FROM_COMMON
#define AZAC_SUPPRESS_COMMON_INCLUDE_FROM_ERROR
#include <azac_api_c_error.h>
#undef AZAC_SUPPRESS_COMMON_INCLUDE_FROM_ERROR
#endif

#ifndef AZAC_SUPPRESS_DEBUG_INCLUDE_FROM_COMMON
#define AZAC_SUPPRESS_COMMON_INCLUDE_FROM_DEBUG
#include <azac_debug.h>
#undef AZAC_SUPPRESS_COMMON_INCLUDE_FROM_DEBUG
#endif

#define AZACPROPERTYBAGHANDLE AZAC_HANDLE
