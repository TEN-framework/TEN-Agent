//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_recognizer.h>
#include <speechapi_cxx_eventsignal.h>
#include <speechapi_cxx_connection_eventargs.h>
#include <speechapi_cxx_connection_message_eventargs.h>
#include <speechapi_c.h>
#include <speechapi_cxx_conversation_translator.h>
#include <speechapi_cxx_speech_synthesizer.h>
#include <speechapi_cxx_dialog_service_connector.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/// <summary>
/// Connection is a proxy class for managing connection to the speech service of the specified Recognizer.
/// By default, a Recognizer autonomously manages connection to service when needed.
/// The Connection class provides additional methods for users to explicitly open or close a connection and
/// to subscribe to connection status changes.
/// The use of Connection is optional. It is intended for scenarios where fine tuning of application
/// behavior based on connection status is needed. Users can optionally call Open() to manually
/// initiate a service connection before starting recognition on the Recognizer associated with this Connection.
/// After starting a recognition, calling Open() or Close() might fail. This will not impact
/// the Recognizer or the ongoing recognition. Connection might drop for various reasons, the Recognizer will
/// always try to reinstitute the connection as required to guarantee ongoing operations. In all these cases
/// Connected/Disconnected events will indicate the change of the connection status.
/// Updated in version 1.17.0.
/// </summary>
class Connection : public std::enable_shared_from_this<Connection>
{

public:
    /// <summary>
    /// Gets the Connection instance from the specified recognizer.
    /// </summary>
    /// <param name="recognizer">The recognizer associated with the connection.</param>
    /// <returns>The Connection instance of the recognizer.</returns>
    static std::shared_ptr<Connection> FromRecognizer(std::shared_ptr<Recognizer> recognizer)
    {
        SPX_INIT_HR(hr);
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, recognizer == nullptr);

        SPXCONNECTIONHANDLE handle = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(hr = ::connection_from_recognizer(recognizer->m_hreco, &handle));

        return std::make_shared<Connection>(handle);
    }

    /// <summary>
    /// Gets the Connection instance from the specified conversation translator.
    /// </summary>
    /// <param name="convTrans">The conversation translator associated with the connection.</param>
    /// <returns>The Connection instance of the conversation translator.</returns>
    static std::shared_ptr<Connection> FromConversationTranslator(std::shared_ptr<Transcription::ConversationTranslator> convTrans)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, convTrans == nullptr);

        SPXCONNECTIONHANDLE handle = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(::connection_from_conversation_translator(convTrans->m_handle, &handle));

        return std::make_shared<Connection>(handle);
    }

    /// <summary>
    /// Gets the Connection instance from the specified dialog service connector, used for observing and managing
    /// connection and disconnection from the speech service.
    /// </summary>
    /// <param name="dialogServiceConnector">The dialog service connector associated with the connection.</param>
    /// <returns>The Connection instance of the dialog service connector.</returns>
    static std::shared_ptr<Connection> FromDialogServiceConnector(std::shared_ptr<Dialog::DialogServiceConnector> dialogServiceConnector)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, dialogServiceConnector == nullptr);

        SPXCONNECTIONHANDLE handle = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(::connection_from_dialog_service_connector(dialogServiceConnector->m_handle, &handle));

        return std::make_shared<Connection>(handle);
    }

    /// <summary>
    /// Gets the Connection instance from the specified speech synthesizer.
    /// Added in version 1.17.0
    /// </summary>
    /// <param name="synthesizer">The speech synthesizer associated with the connection.</param>
    /// <returns>The Connection instance of the speech synthesizer.</returns>
    static std::shared_ptr<Connection> FromSpeechSynthesizer(std::shared_ptr<SpeechSynthesizer> synthesizer)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, synthesizer == nullptr);

        SPXCONNECTIONHANDLE handle = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(::connection_from_speech_synthesizer(synthesizer->m_hsynth, &handle));

        return std::make_shared<Connection>(handle);
    }

    /// <summary>
    /// Starts to set up connection to the service.
    /// Users can optionally call Open() to manually set up a connection in advance before starting recognition/synthesis on the
    /// Recognizer/Synthesizer associated with this Connection. After starting recognition, calling Open() might fail, depending on
    /// the process state of the Recognizer/Synthesizer. But the failure does not affect the state of the associated Recognizer/Synthesizer.
    /// Note: On return, the connection might not be ready yet. Please subscribe to the Connected event to
    /// be notified when the connection is established.
    /// </summary>
    /// <param name="forContinuousRecognition">Indicates whether the connection is used for continuous recognition or single-shot recognition. It takes no effect if the connection is from SpeechSynthsizer.</param>
    void Open(bool forContinuousRecognition)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_connectionHandle == SPXHANDLE_INVALID);
        SPX_THROW_ON_FAIL(::connection_open(m_connectionHandle, forContinuousRecognition));
    }

    /// <summary>
    /// Closes the connection the service.
    /// Users can optionally call Close() to manually shutdown the connection of the associated Recognizer/Synthesizer. The call
    /// might fail, depending on the process state of the Recognizer/Synthesizer. But the failure does not affect the state of the
    /// associated Recognizer/Synthesizer.
    /// </summary>
    void Close()
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_connectionHandle == SPXHANDLE_INVALID);
        SPX_THROW_ON_FAIL(::connection_close(m_connectionHandle));
    }

    /// <summary>
    /// Appends a parameter in a message to service.
    /// This method doesn't work for the connection of SpeechSynthesizer.
    /// Added in version 1.7.0.
    /// </summary>
    /// <param name="path">the message path.</param>
    /// <param name="propertyName">Name of the property.</param>
    /// <param name="propertyValue">Value of the property. This is a json string.</param>
    /// <returns>void.</returns>
    void SetMessageProperty(const SPXSTRING& path, const SPXSTRING& propertyName, const SPXSTRING& propertyValue)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_connectionHandle == SPXHANDLE_INVALID);
        SPX_THROW_ON_FAIL(::connection_set_message_property(m_connectionHandle, Utils::ToUTF8(path).c_str(), Utils::ToUTF8(propertyName).c_str(), Utils::ToUTF8(propertyValue).c_str()));
    }

    /// <summary>
    /// Send a message to the speech service.
    /// This method doesn't work for the connection of SpeechSynthesizer.
    /// Added in version 1.7.0.
    /// </summary>
    /// <param name="path">The path of the message.</param>
    /// <param name="payload">The payload of the message. This is a json string.</param>
    /// <returns>An empty future.</returns>
    std::future<void> SendMessageAsync(const SPXSTRING& path, const SPXSTRING& payload)
    {
        auto keep_alive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keep_alive, this, path, payload]() -> void {
            SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_connectionHandle == SPXHANDLE_INVALID);
            SPX_THROW_ON_FAIL(::connection_send_message(m_connectionHandle, Utils::ToUTF8(path.c_str()), Utils::ToUTF8(payload.c_str())));
        });
        return future;
    }

    /// <summary>
    /// Send a binary message to the speech service.
    /// This method doesn't work for the connection of SpeechSynthesizer.
    /// Added in version 1.10.0.
    /// </summary>
    /// <param name="path">The path of the message.</param>
    /// <param name="payload">The binary payload of the message.</param>
    /// <param name="size">The size of the binary payload.</param>
    /// <returns>An empty future.</returns>
    std::future<void> SendMessageAsync(const SPXSTRING& path, uint8_t* payload, uint32_t size)
    {
        auto keep_alive = this->shared_from_this();
        auto future = std::async(std::launch::async, [keep_alive, this, path, payload, size]() -> void {
            SPX_THROW_HR_IF(SPXERR_INVALID_HANDLE, m_connectionHandle == SPXHANDLE_INVALID);
            SPX_THROW_ON_FAIL(::connection_send_message_data(m_connectionHandle, Utils::ToUTF8(path.c_str()), payload, size));
        });
        return future;
    }

    /// <summary>
    /// The Connected event to indicate that the recognizer is connected to service.
    /// </summary>
    EventSignal<const ConnectionEventArgs&> Connected;

    /// <summary>
    /// The Disconnected event to indicate that the recognizer is disconnected from service.
    /// </summary>
    EventSignal<const ConnectionEventArgs&> Disconnected;

    /// <summary>
    /// The MessageReceived event to indicate that the underlying protocol received a message from the service.
    /// Added in version 1.10.0.
    /// </summary>
    EventSignal<const ConnectionMessageEventArgs&> MessageReceived;

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="handle">The connection handle.</param>
    explicit Connection(SPXCONNECTIONHANDLE handle) :
        Connected(GetConnectionEventConnectionsChangedCallback(), GetConnectionEventConnectionsChangedCallback()),
        Disconnected(GetConnectionEventConnectionsChangedCallback(), GetConnectionEventConnectionsChangedCallback()),
        MessageReceived(GetConnectionMessageEventConnectionsChangedCallback(), GetConnectionMessageEventConnectionsChangedCallback()),
        m_connectionHandle(handle)
    {
        SPX_DBG_TRACE_FUNCTION();
    }

    /// <summary>
    /// Destructor.
    /// </summary>
    ~Connection()
    {
        SPX_DBG_TRACE_FUNCTION();

        try
        {
            Disconnected.DisconnectAll();
            Connected.DisconnectAll();
        }
        catch (const std::exception& ex)
        {
            SPX_TRACE_ERROR("Exception caught in ~Connection(): %s", ex.what());
            (void)ex;
        }
        catch (...)
        {
            SPX_TRACE_ERROR("Unknown exception happened during ~Connection().");
        }

        if (m_connectionHandle != SPXHANDLE_INVALID)
        {
            ::connection_handle_release(m_connectionHandle);
            m_connectionHandle = SPXHANDLE_INVALID;
        }
    }

private:
    DISABLE_COPY_AND_MOVE(Connection);

    SPXCONNECTIONHANDLE m_connectionHandle;

    static void FireConnectionEvent(bool firingConnectedEvent, SPXEVENTHANDLE event, void* context)
    {
        std::exception_ptr p;
        try
        {
            std::unique_ptr<ConnectionEventArgs> connectionEvent{ new ConnectionEventArgs(event) };

            auto connection = static_cast<Connection*>(context);
            auto keepAlive = connection->shared_from_this();
            if (firingConnectedEvent)
            {
                connection->Connected.Signal(*connectionEvent.get());
            }
            else
            {
                connection->Disconnected.Signal(*connectionEvent.get());
            }
        }

#ifdef SHOULD_HANDLE_FORCED_UNWIND
        // Currently Python forcibly kills the thread by throwing __forced_unwind,
        // taking care we propagate this exception further.
        catch (abi::__forced_unwind&)
        {
            SPX_TRACE_ERROR("__forced_unwind exception caught in FireConnectionEvent.");
            throw;
        }
#endif
        catch (...)
        {
            if (recognizer_event_handle_is_valid(event)) {
                recognizer_event_handle_release(event);
            }
            SPX_TRACE_ERROR("Caught exception in FireConnectionEvent(%s). Will rethrow later.", firingConnectedEvent ? "Connected" : "Disconnected");
            throw;
        }

        // ConnectionEventArgs doesn't hold hevent, and thus can't release it properly ... release it here
        SPX_DBG_ASSERT(recognizer_event_handle_is_valid(event));
        recognizer_event_handle_release(event);
    }

    static void FireEvent_Connected(SPXEVENTHANDLE event, void* context)
    {
        FireConnectionEvent(true, event, context);
    }

    static void FireEvent_Disconnected(SPXEVENTHANDLE event, void* context)
    {
        FireConnectionEvent(false, event, context);
    }

    static void FireEvent_MessageReceived(SPXEVENTHANDLE event, void* context)
    {
        std::unique_ptr<ConnectionMessageEventArgs> connectionEvent { new ConnectionMessageEventArgs(event) };

        auto connection = static_cast<Connection*>(context);
        auto keepAlive = connection->shared_from_this();
        connection->MessageReceived.Signal(*connectionEvent.get());
    }

    void ConnectionEventConnectionsChanged(const EventSignal<const ConnectionEventArgs&>& connectionEvent)
    {
        if (m_connectionHandle != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_connectionHandle=0x%8p", __FUNCTION__, (void*)m_connectionHandle);
            SPX_DBG_TRACE_VERBOSE_IF(!::connection_handle_is_valid(m_connectionHandle), "%s: m_connectionHandle is INVALID!!!", __FUNCTION__);

            if (&connectionEvent == &Connected)
            {
                SPX_THROW_ON_FAIL(connection_connected_set_callback(m_connectionHandle, Connected.IsConnected() ? FireEvent_Connected : nullptr, this));
            }
            else if (&connectionEvent == &Disconnected)
            {
                SPX_THROW_ON_FAIL(connection_disconnected_set_callback(m_connectionHandle, Disconnected.IsConnected() ? FireEvent_Disconnected : nullptr, this));
            }
        }
    }

    void ConnectionMessageEventConnectionsChanged(const EventSignal<const ConnectionMessageEventArgs&>& connectionEvent)
    {
        if (m_connectionHandle != SPXHANDLE_INVALID)
        {
            SPX_DBG_TRACE_VERBOSE("%s: m_connectionHandle=0x%8p", __FUNCTION__, (void*)m_connectionHandle);
            SPX_DBG_TRACE_VERBOSE_IF(!::connection_handle_is_valid(m_connectionHandle), "%s: m_connectionHandle is INVALID!!!", __FUNCTION__);

            if (&connectionEvent == &MessageReceived)
            {
                SPX_THROW_ON_FAIL(connection_message_received_set_callback(m_connectionHandle, MessageReceived.IsConnected() ? FireEvent_MessageReceived : nullptr, this));
            }
        }
    }

    inline std::function<void(const EventSignal<const ConnectionEventArgs&>&)> GetConnectionEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const ConnectionEventArgs&>& connectionEvent) { this->ConnectionEventConnectionsChanged(connectionEvent); };
    }

    inline std::function<void(const EventSignal<const ConnectionMessageEventArgs&>&)> GetConnectionMessageEventConnectionsChangedCallback()
    {
        return [=](const EventSignal<const ConnectionMessageEventArgs&>& connectionEvent) { this->ConnectionMessageEventConnectionsChanged(connectionEvent); };
    }
};

} } } // Microsoft::CognitiveServices::Speech
