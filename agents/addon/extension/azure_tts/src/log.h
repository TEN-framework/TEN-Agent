/**
 *
 * Agora Real Time Engagement
 * Created by Zhang Jie in 2024-06.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
#pragma once

#define AZURE_TTS_LOG_TAG "AZURE_TTS_EXTENSION"

#include "utils/log/log.h"

#define AZURE_TTS_LOGI(...) RTE_LOG_WRITE(RTE_LOG_INFO, AZURE_TTS_LOG_TAG, __VA_ARGS__)
#define AZURE_TTS_LOGE(...) RTE_LOG_WRITE(RTE_LOG_ERROR, AZURE_TTS_LOG_TAG, __VA_ARGS__)
#define AZURE_TTS_LOGW(...) RTE_LOG_WRITE(RTE_LOG_WARN, AZURE_TTS_LOG_TAG, __VA_ARGS__)
#define AZURE_TTS_LOGD(...) RTE_LOG_WRITE(RTE_LOG_DEBUG, AZURE_TTS_LOG_TAG, __VA_ARGS__)
