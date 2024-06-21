//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <string>
#include <sstream>
#include <iterator>
#include <functional>
#include <azac_api_c_diagnostics.h>
#include <azac_api_cxx_common.h>
#include <speechapi_cxx_log_level.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Diagnostics {
namespace Logging {

/// <summary>
/// Class with static methods to control callback-based SDK logging.
/// Turning on logging while running your Speech SDK scenario provides
/// detailed information from the SDK's core native components. If you
/// report an issue to Microsoft, you may be asked to provide logs to help
/// Microsoft diagnose the issue. Your application should not take dependency
/// on particular log strings, as they may change from one SDK release to another
/// without notice.
/// Use EventLogger when you want to get access to new log strings as soon
/// as they are available, and you need to further process them. For example,
/// integrating Speech SDK logs with your existing logging collection system.
/// Added in version 1.20.0
/// </summary>
/// <remarks>Event logging is a process wide construct. That means that if (for example)
/// you have multiple speech recognizer objects running in parallel, you can only register
/// one callback function to receive interleaved logs from all recognizers. You cannot register
/// a separate callback for each recognizer.</remarks>
class EventLogger
{
public:
    using CallbackFunction_Type = ::std::function<void(std::string message)>;

    /// <summary>
    /// Register a callback function that will be invoked for each new log messages.
    /// </summary>
    /// <param name="callback">callback function to call. Set a nullptr value
    /// to stop the Event Logger.</param>
    /// <remarks>You can only register one callback function. This call will happen on a working thread of the SDK,
    /// so the log string should be copied somewhere for further processing by another thread, and the function should return immediately.
    /// No heavy processing or network calls should be done in this callback function.</remarks>
    static void SetCallback(CallbackFunction_Type callback = nullptr)
    {
        AZAC_THROW_ON_FAIL(diagnostics_logmessage_set_callback(nullptr == callback ? nullptr : LineLogged));

        SetOrGet(true, callback);
    }

    /// <summary>
    /// Sets or clears filters for callbacks.
    /// Once filters are set, the callback will be invoked only if the log string
    /// contains at least one of the strings specified by the filters. The match is case sensitive.
    /// </summary>
    /// <param name="filters">Optional. Filters to use, or an empty list to clear previously set filters</param>
    static void SetFilters(std::initializer_list<std::string> filters = {})
    {
        std::string str = "";

        if (filters.size() > 0)
        {
            std::ostringstream filtersCollapsed;
            std::copy(filters.begin(), filters.end(), std::ostream_iterator<std::string>(filtersCollapsed, ";"));
            str = filtersCollapsed.str();
        }

        AZAC_THROW_ON_FAIL(diagnostics_logmessage_set_filters(str.c_str()));
    }

    /// <summary>
    /// Sets the level of the messages to be captured by the logger
    /// </summary>
    /// <param name="level">Maximum level of detail to be captured by the logger.</param>
    static void SetLevel(Level level)
    {
        const auto levelStr = Details::LevelToString(level);
        diagnostics_set_log_level("event", levelStr);
    }

private:
    static CallbackFunction_Type SetOrGet(bool set, CallbackFunction_Type callback)
    {
        static CallbackFunction_Type staticCallback = nullptr;
        if (set)
        {
            staticCallback = callback;
        }
        return staticCallback;
    }

    static void LineLogged(const char* line)
    {
        auto callback = SetOrGet(false, nullptr);
        if (nullptr != callback)
        {
            callback(line);
        }
    }
};
}}}}}
