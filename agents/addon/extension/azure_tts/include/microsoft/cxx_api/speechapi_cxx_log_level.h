//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/azai/vision/license for the full license information.
//

#pragma once

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Diagnostics {
namespace Logging {

/// <summary>
/// Defines the different available log levels.
/// </summary>
/// <remarks>
/// This is used by different loggers to set the maximum level of detail they will output.
///
/// <see cref="MemoryLogger.SetLevel(Level)" />
///
/// <see cref="EventLogger.SetLevel(Level)" />
///
/// <see cref="FileLogger.SetLevel(Level)" />
/// </remarks>
enum class Level
{
    /// <summary>
    /// Error logging level. Only errors will be logged.
    /// <remarks>
    Error,

    /// <summary>
    /// Warning logging level. Only errors and warnings will be logged.
    /// <remarks>
    Warning,

    /// <summary>
    /// Informational logging level. Only errors, warnings and informational log messages will be logged.
    /// <remarks>
    Info,

    /// <summary>
    /// Verbose logging level. All log messages will be logged.
    /// <remarks>
    Verbose
};

/*! \cond INTERNAL */
namespace Details
{
    inline const char * LevelToString(Level level)
    {
        switch (level)
        {
        case Level::Error: return "error";
        case Level::Warning: return "warning";
        case Level::Info: return "info";
        default:
        case Level::Verbose: return "verbose";
        }
    }
}
/*! \endcond */

}}}}}