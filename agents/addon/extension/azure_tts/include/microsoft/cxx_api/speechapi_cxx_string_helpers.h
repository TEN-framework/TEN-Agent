//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once

#include <string>
#include <codecvt>
#include <locale>
#include <wchar.h>
#include <vector>
#include <limits>

#include <azac_api_c_pal.h>
#include <speechapi_cxx_common.h>
#include <speechapi_c_error.h>
#include <speechapi_c_property_bag.h>

#define SPXSTRING std::string
#define SPXSTRING_EMPTY std::string()

namespace Microsoft{
namespace CognitiveServices {
namespace Speech {
namespace Utils {

namespace Details {

    inline std::string to_string(const std::wstring& value)
    {
        const auto size = pal_wstring_to_string(nullptr, value.c_str(), 0);
        auto buffer = std::make_unique<std::string::value_type[]>(size);
        pal_wstring_to_string(buffer.get(), value.c_str(), size);
        return std::string{ buffer.get() };
    }

    inline std::wstring to_string(const std::string& value)
    {
        const auto size = pal_string_to_wstring(nullptr, value.c_str(), 0);
        auto buffer = std::make_unique<std::wstring::value_type[]>(size);
        pal_string_to_wstring(buffer.get(), value.c_str(), size);
        return std::wstring{ buffer.get() };
    }
}

inline std::string ToSPXString(const char* value)
{
    return value == nullptr ? "" : value;
}

inline std::string ToSPXString(const std::string& value)
{
    return value;
}

inline std::string ToUTF8(const std::wstring& value)
{
    return Details::to_string(value);
}

inline std::string ToUTF8(const wchar_t* value)
{
    if (!value)
        return "";
    return ToUTF8(std::wstring(value));
}

inline std::string ToUTF8(const std::string& value)
{
    return value;
}

inline const char* ToUTF8(const char* value)
{
    return value;
}

inline static std::string CopyAndFreePropertyString(const char* value)
{
    std::string copy = (value == nullptr) ? "" : value;
    property_bag_free_string(value);
    return copy;
}

template<typename TCHAR>
inline static size_t Find(const TCHAR* pStr, const size_t numChars, const TCHAR find, size_t startAt = 0)
{
    for (size_t i = startAt; i < numChars; i++)
    {
        TCHAR c = pStr[i];
        if (c == '\0')
        {
            break;
        }
        else if (c == find)
        {
            return i;
        }
    }

    return (std::numeric_limits<size_t>::max)(); // weird syntax to avoid Windows min/max macros
}

template<typename TCHAR>
static std::vector<std::basic_string<TCHAR>> Split(const TCHAR* pStr, const size_t numChars, const TCHAR delim)
{
    std::vector<std::basic_string<TCHAR>> result;
    if (pStr == nullptr)
    {
        return result;
    }

    size_t start = 0;
    size_t end = Find(pStr, numChars, delim, 0);
    while (end != (std::numeric_limits<size_t>::max)())
    {
        result.push_back(std::basic_string<TCHAR>(pStr + start, end - start));
        start = end + 1;
        end = Find(pStr, numChars, delim, start);
    }

    if (start < numChars)
    {
        result.push_back(std::basic_string<TCHAR>(pStr + start, numChars - start));
    }

    return result;
}

template<typename TCHAR>
inline static std::vector<std::basic_string<TCHAR>> Split(const std::basic_string<TCHAR>& str, const TCHAR delim)
{
    return Split(str.c_str(), str.size(), delim);
}

}}}}
