#ifndef APP_COMMON_H
#define APP_COMMON_H
#ifdef __cplusplus
extern "C" {
#endif

#include <stdlib.h>
#include "app_config.h"

#define RTC_APP_ID_LEN   32
#define RTC_TOKEN_LEN    512

#define AUDIO_I2S_BITS   32
#define PRIO_TASK_FETCH (21)

#if defined(CONFIG_USE_G722_CODEC)
#define AUDIO_CODEC_TYPE AUDIO_CODEC_TYPE_G722
#define CONFIG_PCM_SAMPLE_RATE (16000)
#define CONFIG_PCM_DATA_LEN     640
#define CONFIG_SEND_PCM_DATA
#define TENAI_AUDIO_CODEC           "{\"che.audio.custom_payload_type\":9}"
#elif defined(CONFIG_USE_G711U_CODEC)
#define AUDIO_CODEC_TYPE AUDIO_CODEC_TYPE_G711U
#define CONFIG_PCM_SAMPLE_RATE (8000)
#define CONFIG_PCM_DATA_LEN     320
#define CONFIG_SEND_PCM_DATA
#define TENAI_AUDIO_CODEC           "{\"che.audio.custom_payload_type\":0}"
#else
#pragma message "should config audio codec type first"
#endif

#define CONFIG_PCM_CHANNEL_NUM (1)
#define CONFIG_AUDIO_FRAME_DURATION_MS                                               \
  (CONFIG_PCM_DATA_LEN * 1000 / CONFIG_PCM_SAMPLE_RATE / CONFIG_PCM_CHANNEL_NUM / sizeof(int16_t))


typedef struct {
  bool b_wifi_connected;
  bool b_ai_agent_generated;
  bool b_call_session_started;
  bool b_ai_agent_joined;

  char app_id[RTC_APP_ID_LEN];
  char token[RTC_TOKEN_LEN];

} app_t;

extern app_t g_app;

#ifdef __cplusplus
}
#endif
#endif