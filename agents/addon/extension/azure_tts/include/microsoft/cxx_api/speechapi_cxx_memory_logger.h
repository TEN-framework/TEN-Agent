//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//

#pragma once
#include <string>
#include <sstream>
#include <iostream>
#include <iterator>
#include <vector>
#include <azac_api_c_diagnostics.h>
#include <azac_api_cxx_common.h>
#include <speechapi_cxx_log_level.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Diagnostics {
namespace Logging {

/// <summary>
/// Class with static methods to control SDK logging into an in-memory buffer.
/// Turning on logging while running your Speech SDK scenario provides
/// detailed information from the SDK's core native components. If you
/// report an issue to Microsoft, you may be asked to provide logs to help
/// Microsoft diagnose the issue. Your application should not take dependency
/// on particular log strings, as they may change from one SDK release to another
/// without notice.
/// MemoryLogger is designed for the case where you want to get access to logs
/// that were taken in the short duration before some unexpected event happens.
/// For example, if you are running a Speech Recognizer, you may want to dump the MemoryLogger
/// after getting an event indicating recognition was canceled due to some error.
/// The size of the memory buffer is fixed at 2MB and cannot be changed. This is
/// a "ring" buffer, that is, new log strings written replace the oldest ones
/// in the buffer.
/// Added in version 1.20.0
/// </summary>
/// <remarks>Memory logging is a process wide construct. That means that if (for example)
/// you have multiple speech recognizer objects running in parallel, there will be one
/// memory buffer containing interleaved logs from all recognizers. You cannot get a
/// separate logs for each recognizer.</remarks>
class MemoryLogger
{
public:
    /// <summary>
    /// Starts logging into the internal memory buffer.
    /// </summary>
    static void Start()
    {
       diagnostics_log_memory_start_logging();
    }

    /// <summary>
    /// Stops logging into the internal memory buffer.
    /// </summary>
    static void Stop()
    {
        diagnostics_log_memory_stop_logging();
    }

    /// <summary>
    /// Sets or clears filters for memory logging.
    /// Once filters are set, memory logger will only be updated with log strings
    /// containing at least one of the strings specified by the filters. The match is case sensitive.
    /// </summary>
    /// <param name="filters">Optional. Filters to use, or an empty list to remove previously set filters.</param>
    static void SetFilters(std::initializer_list<std::string> filters = {})
    {
        std::string collapsedFilters = MemoryLogger::CollapseFilters(filters);

        diagnostics_log_memory_set_filters(collapsedFilters.c_str());
    }

    /// <summary>
    /// Writes the content of the whole memory buffer to the specified file.
    /// It does not block other SDK threads from continuing to log into the buffer.
    /// </summary>
    /// <param name="filePath">Path to a log file on local disk.</param>
    /// <remarks>This does not reset (clear) the memory buffer.</remarks>
    static void Dump(const SPXSTRING& filePath)
    {
        SPX_THROW_HR_IF(SPXERR_INVALID_ARG, filePath.empty());

        SPX_THROW_ON_FAIL(diagnostics_log_memory_dump(Utils::ToUTF8(filePath).c_str(), nullptr, false, false));
    }

    /// <summary>
    /// Writes the content of the whole memory buffer to an object that implements std::ostream.
    /// For example, std::cout (for console output).
    /// It does not block other SDK threads from continuing to log into the buffer.
    /// </summary>
    /// <param name="outStream">std::ostream object to write to.</param>
    /// <remarks>This does not reset (clear) the memory buffer.</remarks>
    static void Dump(std::ostream& outStream)
    {
        auto start = diagnostics_log_memory_get_line_num_oldest();
        auto stop = diagnostics_log_memory_get_line_num_newest();
        for (auto i = start;
            i < stop;
            i++)
        {
            const char* line = diagnostics_log_memory_get_line(i);
            if (line)
            {
                outStream << line;
            }
        }
    }

    /// <summary>
    /// Returns the content of the whole memory buffer as a vector of strings.
    /// It does not block other SDK threads from continuing to log into the buffer.
    /// </summary>
    /// <returns>A vector with the contents of the memory buffer copied into it.</returns>
    /// <remarks>This does not reset (clear) the memory buffer.</remarks>
    static std::vector<std::string> Dump()
    {
        std::vector<std::string> results;

        auto start = diagnostics_log_memory_get_line_num_oldest();
        auto stop = diagnostics_log_memory_get_line_num_newest();
        for (auto i = start;
            i < stop;
            i++)
        {
            const char* line = diagnostics_log_memory_get_line(i);
            if (line)
            {
                results.push_back(line);
            }
        }

        return results;
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
    static std::string CollapseFilters(std::initializer_list<std::string> filters)
    {
        std::string str = "";

        if (filters.size() > 0)
        {
            std::ostringstream filtersCollapsed;
            std::copy(filters.begin(), filters.end(), std::ostream_iterator<std::string>(filtersCollapsed, ";"));
            str = filtersCollapsed.str();
        }

        return str;
    }
};

}}}}}
