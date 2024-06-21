//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_eventsignalbase.h: Public API declarations for EventSignalBase<T> C++ template class
//

#pragma once
#include <algorithm>
#include <functional>
#include <map>
#include <mutex>
#include <string>

// TODO: TFS#3671067 - Vision: Consider moving majority of EventSignal to AI::Core::Details namespace, and refactoring Vision::Core::Events to inherit, and relay to private base

#include <speechapi_cxx_common.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Clients can connect to the event signal to receive events, or disconnect from the event signal to stop receiving events.
/// </summary>
/// <remarks>
/// At construction time, connect and disconnect callbacks can be provided that are called when
/// the number of connected clients changes from zero to one or one to zero, respectively.
/// </remarks>
// <typeparam name="T">
template <class T>
class EventSignalBase
{
public:
    /// <summary>
    /// Constructs an event signal with empty connect and disconnect actions.
    /// <summary>
    EventSignalBase() :
        m_nextCallbackToken(0)
    {
    }

    /// <summary>
    /// Destructor.
    /// <summary>
    virtual ~EventSignalBase()
    {
        UnregisterAllCallbacks();
    }

    /// <summary>
    /// Callback type that is used for signalling the event to connected clients.
    /// </summary>
    using CallbackFunction = std::function<void(T eventArgs)>;

    /// <summary>
    /// The argument type for the callback event
    /// </summary>
    using CallbackArgument = T;

    /// <summary>
    /// A monotonically increasing token used for registration, tracking, and unregistration of callbacks.
    /// </summary>
    using CallbackToken = uint32_t;

    /// <summary>
    /// Registers a callback to this EventSignalBase and assigns it a unique token.
    /// </summary>
    /// <param name="callback"> The callback to register. </param>
    /// <returns>
    /// The new token associated with this registration that can be used for subsequent unregistration.
    /// </returns>
    CallbackToken RegisterCallback(CallbackFunction callback)
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);

        auto token = m_nextCallbackToken;
        m_nextCallbackToken++;

        m_callbacks.emplace(token, callback);

        return token;
    }

    /// <summary>
    /// If present, unregisters a callback from this EventSource associated with the provided token. Tokens are
    /// returned from RegisterCallback at the time of registration.
    /// </summary>
    /// <param name="token">
    /// The token associated with the callback to be removed. This token is provided by the return value of
    /// RegisterCallback at the time of registration.
    /// </param>
    /// <returns> A value indicating whether any callback was unregistered in response to this request. </returns>
    bool UnregisterCallback(CallbackToken token)
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);
        return (bool)m_callbacks.erase(token);
    }

    /// <summary>
    /// Function call operator.
    /// Signals the event with given arguments <paramref name="t"/> to connected clients, see also <see cref="Signal"/>.
    /// </summary>
    /// <param name="t">Event arguments to signal.</param>
    void operator()(T t)
    {
        Signal(t);
    }

    /// <summary>
    /// Unregisters all registered callbacks.
    /// <summary>
    void UnregisterAllCallbacks()
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);
        m_callbacks.clear();
    }

    /// <summary>
    /// Signals the event with given arguments <paramref name="t"/> to all connected callbacks.
    /// <summary>
    /// <param name="t">Event arguments to signal.</param>
    void Signal(T t)
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);

        auto callbacksSnapshot = m_callbacks;
        for (auto callbackCopyPair : callbacksSnapshot)
        {
            // now, while a callback is in progress, it can disconnect itself and any other connected
            // callback. Check to see if the next one stored in the copy container is still connected.
            bool stillConnected = (std::find_if(m_callbacks.begin(), m_callbacks.end(),
                [&](const std::pair<CallbackToken, CallbackFunction> item) {
                return callbackCopyPair.first == item.first;
            }) != m_callbacks.end());

            if (stillConnected)
            {
                callbackCopyPair.second(t);
            }
        }
    }

    /// <summary>
    /// Checks if a callback is connected.
    /// <summary>
    /// <returns>true if a callback is connected</returns>
    bool IsConnected() const
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);
        return !m_callbacks.empty();
    }

protected:
    std::map<CallbackToken, CallbackFunction> m_callbacks;
    CallbackToken m_nextCallbackToken;
    mutable std::recursive_mutex m_mutex;

private:
    EventSignalBase(const EventSignalBase&) = delete;
    EventSignalBase(const EventSignalBase&&) = delete;
    EventSignalBase& operator=(const EventSignalBase&) = delete;
};


} } } // Microsoft::CognitiveServices::Speech
