//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <string>
#include <sstream>
#include <iterator>
#include <azac_api_c_diagnostics.h>
#include <speechapi_c_property_bag.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_log_level.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Diagnostics {
namespace Logging {

/// <summary>
/// Class with static methods to control file-based SDK logging.
/// Turning on logging while running your Speech SDK scenario provides
/// detailed information from the SDK's core native components. If you
/// report an issue to Microsoft, you may be asked to provide logs to help
/// Microsoft diagnose the issue. Your application should not take dependency
/// on particular log strings, as they may change from one SDK release to another
/// without notice.
/// FileLogger is the simplest logging solution and suitable for diagnosing
/// most on-device issues when running Speech SDK.
/// Added in version 1.20.0
/// </summary>
/// <remarks>File logging is a process wide construct. That means that if (for example)
/// you have multiple speech recognizer objects running in parallel, there will be one
/// log file containing interleaved logs lines from all recognizers. You cannot get a
/// separate log file for each recognizer.</remarks>
class FileLogger
{
public:
    /// <summary>
    /// Starts logging to a file.
    /// </summary>
    /// <param name="filePath">Path to a log file on local disk</param>
    /// <param name="append">Optional. If true, appends to existing log file. If false, creates a new log file</param>
    /// <remarks>Note that each write operation to the file is immediately followed by a flush to disk.
    /// For typical usage (e.g. one Speech Recognizer and a Solid State Drive (SSD)) this should not
    /// cause performace issues. You may however want to avoid file logging when running many Speech
    /// SDK recognizers or other SDK objects simultaneously. Use MemoryLogger or EventLogger instead.</remarks>
    static void Start(const SPXSTRING& filePath, bool append = false)
    {
        SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;

        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, filePath.empty());

        SPX_THROW_ON_FAIL(property_bag_create(&hpropbag));
        SPX_THROW_ON_FAIL(property_bag_set_string(hpropbag, -1, "SPEECH-LogFilename", Utils::ToUTF8(filePath).c_str()));
        SPX_THROW_ON_FAIL(property_bag_set_string(hpropbag, -1, "SPEECH-AppendToLogFile", append ? "1" : "0"));
        SPX_THROW_ON_FAIL(diagnostics_log_start_logging(hpropbag, nullptr));
        SPX_THROW_ON_FAIL(property_bag_release(hpropbag));
    }

    /// <summary>
    /// Stops logging to a file.
    /// </summary>
    /// <remarks>This call is optional. If logging as been started,
    /// the log file will be written when the process exists normally.</remarks>
    static void Stop()
    {
        SPX_THROW_ON_FAIL(diagnostics_log_stop_logging());
    }

    /// <summary>
    /// Sets or clears the filters that apply to file logging.
    /// Once filters are set, the callback will be invoked only if the log string
    /// contains at least one of the strings specified by the filters. The match is case sensitive.
    /// </summary>
    /// <param name="filters">Optional. Filters to use, or an empty list to remove previously set filters.</param>
    static void SetFilters(std::initializer_list<std::string> filters = {})
    {
        SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(property_bag_create(&hpropbag));

        PropBagSetFilter(hpropbag, filters);

        SPX_THROW_ON_FAIL(diagnostics_log_apply_properties(hpropbag, nullptr));
        SPX_THROW_ON_FAIL(property_bag_release(hpropbag));
    }

    /// <summary>
    /// Sets the level of the messages to be captured by the logger
    /// </summary>
    /// <param name="level">Maximum level of detail to be captured by the logger.</param>
    static void SetLevel(Level level)
    {
        const auto levelStr = Details::LevelToString(level);
        diagnostics_set_log_level("memory", levelStr);
    }

private:
    static void PropBagSetFilter(AZAC_HANDLE hpropbag, std::initializer_list<std::string> filters)
    {
        std::string str = "";

        if (filters.size() > 0)
        {
            std::ostringstream filtersCollapsed;
            std::copy(filters.begin(), filters.end(), std::ostream_iterator<std::string>(filtersCollapsed, ";"));
            str = filtersCollapsed.str();
        }

        SPX_THROW_ON_FAIL(property_bag_set_string(hpropbag, -1, "SPEECH-LogFileFilters", str.c_str()));
    }
};

}}}}}
