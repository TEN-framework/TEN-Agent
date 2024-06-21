//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_smart_handle.h: Public API declarations for SmartHandle class and related typedef
//

#pragma once
#include <speechapi_cxx_common.h>


namespace Microsoft {
namespace CognitiveServices {
namespace Speech {


typedef SPXHR(SPXAPI_CALLTYPE *SmartHandleCloseFunction)(SPXHANDLE);


/// <summary>
/// Smart handle class.
/// </summary>
template <typename T, SmartHandleCloseFunction closeFunction>
class SmartHandle
{
public:

    SmartHandle(T handle = SPXHANDLE_INVALID) : m_handle(handle) { };
    ~SmartHandle() { reset(); }

    explicit operator T&() const { return m_handle; }

    T get() const { return m_handle; }
    operator T() const { return m_handle; }

    T* operator &()
    {
        SPX_THROW_HR_IF(SPXERR_ALREADY_INITIALIZED, !InvalidHandle(m_handle));
        return &m_handle;
    }

    void reset()
    {
        if (!InvalidHandle(m_handle))
        {
            closeFunction(m_handle);
            m_handle = SPXHANDLE_INVALID;
        }
    }

private:

    static bool InvalidHandle(T t) { return t == nullptr || t == SPXHANDLE_INVALID; }

    DISABLE_COPY_AND_MOVE(SmartHandle);
    T m_handle;
};


} } } // Microsoft::CognitiveServices::Speech
