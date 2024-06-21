//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_utils.h: General utility classes and functions.
//

#pragma once

#include <speechapi_c_common.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Utils {

/// <summary>
/// Base class that disables the copy constructor
/// </summary>
struct NonCopyable
{
    /// <summary>
    /// Default destructor.
    /// </summary>
    NonCopyable() = default;

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~NonCopyable() = default;

    /// <summary>
    /// Disable copy constructor.
    /// </summary>
    NonCopyable(const NonCopyable&) = delete;

    /// <summary>
    /// Disable copy assignment operator.
    /// </summary>
    /// <returns>Reference to the object.</returns>
    NonCopyable& operator=(const NonCopyable &) = delete;
};

/// <summary>
/// Base class that disables the move constructor
/// </summary>
struct NonMovable
{
    /// <summary>
    /// Default destructor.
    /// </summary>
    NonMovable() = default;

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~NonMovable() = default;

    /// <summary>
    /// Disable move constructor.
    /// </summary>
    NonMovable(NonMovable &&) = delete;

    /// <summary>
    /// Disable move assignment operator.
    /// </summary>
    /// <returns>Reference to the object.</returns>
    NonMovable& operator=(NonMovable &&) = delete;
};

template<typename F, typename... Args>
SPXHANDLE CallFactoryMethodRight(F method, Args&&... args)
{
    SPXHANDLE handle;
    auto hr = method(std::forward<Args>(args)..., &handle);
    SPX_THROW_ON_FAIL(hr);
    return handle;
}

template<typename F, typename... Args>
SPXHANDLE CallFactoryMethodLeft(F method, Args&&... args)
{
    SPXHANDLE handle;
    auto hr = method(&handle, std::forward<Args>(args)...);
    SPX_THROW_ON_FAIL(hr);
    return handle;
}

/// <summary>
/// Helper class implementing the scope guard idiom.
/// (The given function will be executed on destruction)
/// </summary>
template<typename F>
class ScopeGuard
{
public:
    ScopeGuard(ScopeGuard&&) = default;
    ScopeGuard(const ScopeGuard&) = delete;

    explicit ScopeGuard(F f): m_fn{ f }
    {}

    ~ScopeGuard()
    {
        m_fn();
    }

private:
    F m_fn;
};

/// <summary>
/// Creates a scope guard with the given function.
/// </summary>
template<typename F>
ScopeGuard<F> MakeScopeGuard(F fn)
{
    return ScopeGuard<F>{ fn };
}

/// <summary>
/// A wrapper around ABI handles that simplifies resource cleanup on exit
/// </summary>
/// <typeparam name="THandle">The type of the ABI handle</typeparam>
/// <typeparam name="THandleDefault">The default value to set the handle to when initialising or after destroying</typeparam>
/// <typeparam name="TRet">The return type of the free function</typeparam>
/// <typeparam name="TFreeFunc">The signature of the free function called to release the ABI handle</typeparam>
template<
    typename THandle,
    typename TRet = AZACHR,
    typename TFreeFunc = TRet(AZAC_API_CALLTYPE*)(THandle)>
class AbiHandleWrapper : public NonCopyable
{
private:
    THandle m_handle;
    TFreeFunc m_free;
    bool m_isValid;

public:
    /// <summary>
    /// The signature of the free function
    /// </summary>
    using FreeFunc = TFreeFunc;

    /// <summary>
    /// Creates and ABI handle wrapper for SPXHANDLE types initializing the handle
    /// to be SPXHANDLE_INVALID
    /// </summary>
    /// <param name="freeFunc">The function used to release the ABI handle</param>
    template<
        typename IsHandle = THandle,
        std::enable_if_t<std::is_same<IsHandle, SPXHANDLE>::value, bool> = true
    >
    AbiHandleWrapper(TFreeFunc freeFunc) :
        m_handle{ SPXHANDLE_INVALID },
        m_free{ freeFunc },
        m_isValid{ false }
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, freeFunc == nullptr);
    }

    /// <summary>
    /// Creates an ABI handle wrapper
    /// </summary>
    /// <param name="freeFunc">The function used to release the ABI handle</param>
    template<
        typename IsHandle = THandle,
        std::enable_if_t<!std::is_same<IsHandle, SPXHANDLE>::value, bool> = true
    >
    AbiHandleWrapper(TFreeFunc freeFunc) :
        m_handle{ nullptr },
        m_free{ freeFunc },
        m_isValid{ false }
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, freeFunc == nullptr);
    }

    /// <summary>
    /// Creates an ABI handle wrapper
    /// </summary>
    /// <param name="freeFunc">The function used to release the ABI handle</param>
    /// <param name="handle">The initial ABI handle value</param>
    AbiHandleWrapper(TFreeFunc freeFunc, THandle&& handle) :
        m_handle{ std::move(handle) },
        m_free{ freeFunc },
        m_isValid{ true }
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, freeFunc == nullptr);
    }

    /// <summary>
    /// Destructor
    /// </summary>
    ~AbiHandleWrapper() { Destroy(); }

    /// <summary>
    /// Move constructor
    /// </summary>
    /// <param name="other">The other item being moved</param>
    AbiHandleWrapper(AbiHandleWrapper&& other) :
        m_handle{ other.m_handle },
        m_free{ other.m_free },
        m_isValid{ other.m_isValid }
    {
        other.m_handle = THandle{};
        other.m_free = nullptr;
        other.m_isValid = false;
    }

    /// <summary>
    /// Move assignment operator
    /// </summary>
    /// <param name="other">The item being moved</param>
    /// <returns>Reference to ABI handle</returns>
    AbiHandleWrapper& operator=(AbiHandleWrapper&& other)
    {
        if (this != &other)
        {
            Destroy();

            m_handle = std::move(other.m_handle);
            m_free = other.m_free;
            m_isValid = other.m_isValid;

            other.m_free = nullptr;
            other.m_isValid = false;
        }

        return *this;
    }

    /// <summary>
    /// Helper to simplify assigning a new ABI handle value to this wrapper
    /// </summary>
    /// <param name="other">The handle to assign</param>
    /// <returns>Reference to assigned handle</returns>
    THandle& operator=(const THandle& other)
    {
        Destroy();

        m_handle = other;
        return m_handle;
    }

    /// <summary>
    /// Gets the address of the ABI handle. This is useful when calling ABI functions that set the value
    /// </summary>
    THandle* operator&() { return &m_handle; }

    /// <summary>
    /// Gets the ABI handle value
    /// </summary>
    operator THandle() const { return m_handle; }

private:
    void Destroy()
    {
        if (m_isValid)
        {
            m_isValid = false;
            if (m_free != nullptr)
            {
                m_free(m_handle);
            }
        }
    }
};

/// <summary>
/// A wrapper around ABI handles
/// </summary>
using AbiHandle = AbiHandleWrapper<SPXHANDLE>;

/// <summary>
/// A wrapper around strings allocated in the ABI layer
/// </summary>
using AbiStringHandle = AbiHandleWrapper<const char*, void>;

/// <summary>
/// Function that converts a handle to its underlying type.
/// </summary>
/// <typeparam name="Handle">Handle type.</typeparam>
/// <typeparam name="T">Object type.</typeparam>
/// <param name="obj">Object from which to get the handle.</param>
template <typename Handle, typename T>
inline Handle HandleOrInvalid(std::shared_ptr<T> obj)
{
    return obj == nullptr
        ? static_cast<Handle>(SPXHANDLE_INVALID)
        : static_cast<Handle>(*obj.get());
}


template<typename... Ts>
struct TypeList {};

template<typename T, template<typename...> class F, typename L>
struct TypeListIfAny;

template<typename T, template<typename...> class F>
struct TypeListIfAny<T, F, TypeList<>>
{
    static constexpr bool value{ false };
};

template<typename T, template<typename...> class F, typename U, typename... Us>
struct TypeListIfAny<T, F, TypeList<U, Us...>>
{
    static constexpr bool value = F<U, T>::value || Microsoft::CognitiveServices::Speech::Utils::TypeListIfAny<T, F, TypeList<Us...>>::value;
};

} } } }
