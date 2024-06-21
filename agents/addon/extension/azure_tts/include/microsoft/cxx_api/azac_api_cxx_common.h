//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/license202106 for the full license information.
//

#pragma once

// TODO: TFS#3671215 - Vision: C/C++ azac_api* files are in shared include directory, speech and vision share

#include <azac_api_c_common.h>
#include <azac_api_c_error.h>
#include <azac_debug.h>
#include <azac_error.h>
#include <functional>
#include <stdexcept>
#include <string>

#define AZAC_DISABLE_COPY_AND_MOVE(T)     \
    /** \brief Disable copy constructor */ \
    T(const T&) = delete;            \
    /** \brief Disable copy assignment */ \
    T& operator=(const T&) = delete; \
    /** \brief Disable move constructor */ \
    T(T&&) = delete;                 \
    /** \brief Disable move assignment */ \
    T& operator=(T&&) = delete

#define AZAC_DISABLE_DEFAULT_CTORS(T)     \
    /** \brief Disable default constructor */ \
    T() = delete;                    \
    AZAC_DISABLE_COPY_AND_MOVE(T)

#if defined(__GNUG__) && defined(__linux__) && !defined(ANDROID) && !defined(__ANDROID__)
#include <cxxabi.h>
#define SHOULD_HANDLE_FORCED_UNWIND 1
#endif

/*! \cond INTERNAL */

namespace Azure {
namespace AI {
namespace Core {
namespace _detail {

template <class T>
class ProtectedAccess : public T
{
public:

    static AZAC_HANDLE HandleFromPtr(T* ptr) {
        if (ptr == nullptr)
        {
            return nullptr;
        }
        auto access = static_cast<ProtectedAccess*>(ptr);
        return (AZAC_HANDLE)(*access);
    }

    static AZAC_HANDLE HandleFromConstPtr(const T* ptr) {
        if (ptr == nullptr)
        {
            return nullptr;
        }
        auto access = static_cast<const ProtectedAccess*>(ptr);
        return (AZAC_HANDLE)(*access);
    }

    template<typename... Args>
    static std::shared_ptr<T> FromHandle(AZAC_HANDLE handle, Args... extras) {
        return T::FromHandle(handle, extras...);
    }

    template<typename... Args>
    static std::shared_ptr<T> Create(Args&&... args) {
        return T::Create(std::forward<Args&&>(args)...);
    }

};

} } } } // Azure::AI::Core::Details

/*! \endcond */
