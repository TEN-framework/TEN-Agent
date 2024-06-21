//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_eventsignal.h: Public API declarations for the EventSignal<T> class. This derives from
// EventSignalBase<T> and uses runtime type information (RTTI) to facilitate management and disconnection of handlers
// without explicit callback token management.
//

#pragma once
#include <algorithm>
#include <functional>
#include <mutex>
#include <string>

#include <speechapi_cxx_eventsignalbase.h>

// TODO: TFS#3671067 - Vision: Consider moving majority of EventSignal to AI::Core::Details namespace, and refactoring Vision::Core::Events to inherit, and relay to private base

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
class EventSignal : public EventSignalBase<T>
{
public:
    /// <summary>
    /// Callback type that is used for signalling the event to connected clients.
    /// </summary>
    using CallbackFunction = std::function<void(T eventArgs)>;

    /// <summary>
    /// A monotonically increasing token used for registration, tracking, and unregistration of callbacks.
    /// </summary>
    using CallbackToken = uint32_t;

    /// <summary>
    /// Type for callbacks used when any client connects to the signal (the number of connected clients changes from zero to one) or
    /// the last client disconnects from the signal (the number of connected clients changes from one to zero).
    /// </summary>
    using NotifyCallback_Type = std::function<void(EventSignal<T>&)>;

    /// <summary>
    /// Constructs an event signal with empty register and disconnect callbacks.
    /// <summary>
    EventSignal() : EventSignal(nullptr)
    {
    }

    /// <summary>
    /// Constructor.
    /// <summary>
    /// <param name="connectedAndDisconnected">Callback to invoke if the number of connected clients changes from zero to one, or one to zero</param>
    EventSignal(NotifyCallback_Type connectedAndDisconnected)
        : EventSignal(connectedAndDisconnected, connectedAndDisconnected)
    {
    }

    /// <summary>
    /// Constructor.
    /// <summary>
    /// <param name="connected">Callback to invoke if the number of connected clients changes from zero to one.</param>
    /// <param name="disconnected">Callback to invoke if the number of connected clients changes from one to zero.</param>
    EventSignal(NotifyCallback_Type connected, NotifyCallback_Type disconnected)
        : EventSignalBase<T>()
        , m_firstConnectedCallback(connected)
        , m_lastDisconnectedCallback(disconnected)
    {
    }

    /// <summary>
    /// Addition assignment operator overload.
    /// Connects the provided callback <paramref name="callback"/> to the event signal, see also <see cref="Connect"/>.
    /// </summary>
    /// <param name="callback">Callback to connect.</param>
    /// <returns>Event signal reference.</returns>
    EventSignal<T>& operator+=(CallbackFunction callback)
    {
        Connect(callback);
        return *this;
    }

    /// <summary>
    /// Subtraction assignment operator overload.
    /// Disconnects the provided callback <paramref name="callback"/> from the event signal, see also <see cref="Disconnect"/>.
    /// </summary>
    /// <param name="callback">Callback to disconnect.</param>
    /// <returns>Event signal reference.</returns>
    EventSignal<T>& operator-=(CallbackFunction callback)
    {
        Disconnect(callback);
        return *this;
    }

    /// <summary>
    /// Connects given callback function to the event signal, to be invoked when the event is signalled.
    /// </summary>
    /// <remarks>
    /// When the number of connected clients changes from zero to one, the connect callback will be called, if provided.
    /// </remarks>
    /// <param name="callback">Callback to connect.</param>
    void Connect(CallbackFunction callback)
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);

        auto shouldFireFirstConnected = m_callbacks.empty() && m_firstConnectedCallback != nullptr;

        (void)EventSignalBase<T>::RegisterCallback(callback);

        lock.unlock();

        if (shouldFireFirstConnected)
        {
            m_firstConnectedCallback(*this);
        }
    }

#ifndef AZAC_CONFIG_CXX_NO_RTTI
    /// <summary>
    /// Disconnects given callback.
    /// <summary>
    /// <remarks>
    /// When the number of connected clients changes from one to zero, the disconnect callback will be called, if provided.
    /// </remarks>
    /// <param name="callback">Callback function.</param>
    void Disconnect(CallbackFunction callback)
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);

        auto itMatchingCallback = std::find_if(
            m_callbacks.begin(),
            m_callbacks.end(),
            [&](const std::pair<CallbackToken, CallbackFunction>& item)
            {
                return callback.target_type() == item.second.target_type();
            });

        auto removeHappened = EventSignal<T>::UnregisterCallback(itMatchingCallback->first);
        lock.unlock();
        if (removeHappened && m_callbacks.empty() && m_lastDisconnectedCallback != nullptr)
        {
            m_lastDisconnectedCallback(*this);
        }
    }
#else
    void Disconnect(CallbackFunction)
    {
        // Callback disconnection without a stored token requires runtime type information.
        // To remove callbacks with RTTI disabled, use UnregisterCallback(token).
        SPX_THROW_HR(SPXERR_NOT_IMPL);
    }
#endif

    /// <summary>
    /// Disconnects all registered callbacks.
    /// </summary>
    void DisconnectAll()
    {
        std::unique_lock<std::recursive_mutex> lock(m_mutex);
        auto shouldFireLastDisconnected = !m_callbacks.empty() && m_lastDisconnectedCallback != nullptr;

        EventSignal<T>::UnregisterAllCallbacks();

        lock.unlock();

        if (shouldFireLastDisconnected)
        {
            m_lastDisconnectedCallback(*this);
        }
    }

    /// <summary>
    /// Signals the event with given arguments <paramref name="t"/> to all connected callbacks.
    /// <summary>
    /// <param name="t">Event arguments to signal.</param>
    void Signal(T t)
    {
        EventSignalBase<T>::Signal(t);
    }

private:
    using EventSignalBase<T>::m_mutex;
    using EventSignalBase<T>::m_callbacks;

    NotifyCallback_Type m_firstConnectedCallback;
    NotifyCallback_Type m_lastDisconnectedCallback;

    EventSignal(const EventSignal&) = delete;
    EventSignal(const EventSignal&&) = delete;
    EventSignal& operator=(const EventSignal&) = delete;
};

} } } // Microsoft::CognitiveServices::Speech
