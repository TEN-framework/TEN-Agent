#include <string.h>
#include "board.h"

#include "common.h"
#include "agora_rtc_api.h"
#include "audio_proc.h"
#include "rtc_proc.h"

#define DEFAULT_SDK_LOG_PATH      "io.agora.rtc_sdk"
#define DEFAULT_AREA_CODE         AREA_CODE_GLOB

static connection_id_t g_conn_id;

static void __on_join_channel_success(connection_id_t conn_id, uint32_t uid, int elapsed)
{
  connection_info_t conn_info = { 0 };

  audio_sema_pend();

  g_app.b_call_session_started = true;
  agora_rtc_get_connection_info(conn_id, &conn_info);
  printf("[conn-%lu] Join the channel %s successfully, uid %lu elapsed %d ms\n", conn_id, conn_info.channel_name, uid, elapsed);
}

static void __on_connection_lost(connection_id_t conn_id)
{
  g_app.b_call_session_started = false;
  printf("[conn-%lu] Lost connection from the channel\n", conn_id);
}

static void __on_rejoin_channel_success(connection_id_t conn_id, uint32_t uid, int elapsed_ms)
{
  g_app.b_call_session_started = true;
  printf("[conn-%lu] Rejoin the channel successfully, uid %lu elapsed %d ms\n", conn_id, uid, elapsed_ms);
}

static void __on_user_joined(connection_id_t conn_id, uint32_t uid, int elapsed_ms)
{
  printf("[conn-%lu] Remote user \"%lu\" has joined the channel, elapsed %d ms\n", uid, conn_id, elapsed_ms);
}

static void __on_user_offline(connection_id_t conn_id, uint32_t uid, int reason)
{
  printf("[conn-%lu] Remote user \"%lu\" has left the channel, reason %d\n", conn_id, uid, reason);
}

static void __on_user_mute_audio(connection_id_t conn_id, uint32_t uid, bool muted)
{
  printf("[conn-%lu] audio: uid=%lu muted=%d\n", conn_id, uid, muted);
}

static void __on_error(connection_id_t conn_id, int code, const char *msg)
{
  if (code == ERR_VIDEO_SEND_OVER_BANDWIDTH_LIMIT) {
    printf("Not enough uplink bandwdith. Error msg \"%s\"\n", msg);
    return;
  }

  if (code == ERR_INVALID_APP_ID) {
    printf("Invalid App ID. Please double check. Error msg \"%s\"\n", msg);
  } else if (code == ERR_INVALID_CHANNEL_NAME) {
    printf("Invalid channel name. Please double check. Error msg \"%s\"\n", msg);
  } else if (code == ERR_INVALID_TOKEN || code == ERR_TOKEN_EXPIRED) {
    printf("Invalid token. Please double check. Error msg \"%s\"\n", msg);
  } else if (code == ERR_DYNAMIC_TOKEN_BUT_USE_STATIC_KEY) {
    printf("Dynamic token is enabled but is not provided. Error msg \"%s\"\n", msg);
  } else {
    printf("Error %d is captured. Error msg \"%s\"\n", code, msg);
  }
}

#ifdef CONFIG_ENABLE_AUDIO_MIXING
static void __on_mixed_audio_data(connection_id_t conn_id, const void *data, size_t len,
                                  const audio_frame_info_t *info_ptr)
{
  //LOG_I("[conn-%u] on_mixed_audio_data, data_type %d, len %zu\n", conn_id, info_ptr->data_type, len);
}
#else
static void __on_audio_data(connection_id_t conn_id, const uint32_t uid, uint16_t sent_ts, const void *data, size_t len,
                            const audio_frame_info_t *info_ptr)
{
  // printf("[conn-%lu] on_audio_data, uid %lu sent_ts %u data_type %d, len %zu\n", conn_id, uid, sent_ts,
  //        info_ptr->data_type, len);
  playback_stream_write((char *)data, len);
}
#endif //#ifdef CONFIG_ENABLE_AUDIO_MIXING

#ifndef CONFIG_AUDIO_ONLY
static void __on_video_data(connection_id_t conn_id, const uint32_t uid, uint16_t sent_ts, const void *data, size_t len,
                            const video_frame_info_t *info_ptr)
{
  /*LOG_I("[conn-%u] on_video_data: uid %u sent_ts %u data_type %d frame_type %d stream_type %d len %zu\n", conn_id, uid,
         sent_ts, info_ptr->data_type, info_ptr->frame_type, info_ptr->stream_type, len);*/
}

static void __on_target_bitrate_changed(connection_id_t conn_id, uint32_t target_bps)
{
  printf("[conn-%lu] Bandwidth change detected. Please adjust encoder bitrate to %lu kbps\n", conn_id, target_bps / 1000);
}

static void __on_key_frame_gen_req(connection_id_t conn_id, uint32_t uid, video_stream_type_e stream_type)
{
  printf("[conn-%lu] Frame loss detected. Please notify the encoder to generate key frame immediately\n", conn_id);
}

static void __on_user_mute_video(connection_id_t conn_id, uint32_t uid, bool muted)
{
  printf("[conn-%lu] video: uid=%lu muted=%d\n", conn_id, uid, muted);
}
#endif //#ifndef CONFIG_AUDIO_ONLY

void __on_stream_message(connection_id_t conn_id, uint32_t uid, int stream_id, const char* data, size_t length, uint64_t sent_ts)
{
  // printf("[conn-%lu] stream message: uid=%lu stream_id=%d length=%zu\n", conn_id, uid, stream_id, length);
}


static void app_init_event_handler(agora_rtc_event_handler_t *event_handler)
{
  event_handler->on_join_channel_success   = __on_join_channel_success;
  event_handler->on_connection_lost        = __on_connection_lost;
  event_handler->on_rejoin_channel_success = __on_rejoin_channel_success;
  event_handler->on_user_joined            = __on_user_joined;
  event_handler->on_user_offline           = __on_user_offline;
  event_handler->on_user_mute_audio        = __on_user_mute_audio;
#ifdef CONFIG_ENABLE_AUDIO_MIXING
  event_handler->on_mixed_audio_data       = __on_mixed_audio_data;
#else
  event_handler->on_audio_data             = __on_audio_data;
#endif

#ifndef CONFIG_AUDIO_ONLY
  event_handler->on_user_mute_video        = __on_user_mute_video;
  event_handler->on_target_bitrate_changed = __on_target_bitrate_changed;
  event_handler->on_key_frame_gen_req      = __on_key_frame_gen_req;
  event_handler->on_video_data             = __on_video_data;
#endif
  event_handler->on_stream_message         = __on_stream_message;
  event_handler->on_error                  = __on_error;
}


int agora_rtc_proc_create(char *license, uint32_t uid)
{
  int rval = -1;

  // 1. API: init agora rtc sdk
  agora_rtc_event_handler_t event_handler = { 0 };
  app_init_event_handler(&event_handler);

  rtc_service_option_t service_opt = { 0 };
  service_opt.area_code            = AREA_CODE_GLOB;
  service_opt.log_cfg.log_disable  = false;
  service_opt.log_cfg.log_level    = RTC_LOG_WARNING;
  service_opt.log_cfg.log_path     = DEFAULT_SDK_LOG_PATH;

  if (!license) {
    service_opt.license_value[0]   = '\0';
  } else {
    memcpy(service_opt.license_value, license, 32);
  }
  service_opt.domain_limit         = false;

  rval = agora_rtc_init(g_app.app_id, &event_handler, &service_opt);
  if (rval < 0) {
    printf("Failed to initialize Agora sdk, license %p, reason: %s\n", service_opt.license_value, agora_rtc_err_2_str(rval));
    return -1;
  }

  printf("~~~~~agora_rtc_init success~~~~\r\n");

  // 2. API: Create connection
  rval = agora_rtc_create_connection(&g_conn_id);
  if (rval < 0) {
    printf("Failed to create connection, reason: %s\n", agora_rtc_err_2_str(rval));
    return -1;
  }

  // 3. API: join channel
  rtc_channel_options_t channel_options = { 0 };
  channel_options.auto_subscribe_audio = true;
  channel_options.auto_subscribe_video = false;

#ifdef CONFIG_SEND_PCM_DATA
  /* If we want to send PCM data instead of encoded audio like AAC or Opus, here please enable
   * audio codec, as well as configure the PCM sample rate and number of channels
   */
  channel_options.audio_codec_opt.audio_codec_type = AUDIO_CODEC_TYPE;
  channel_options.audio_codec_opt.pcm_sample_rate  = CONFIG_PCM_SAMPLE_RATE; 
  channel_options.audio_codec_opt.pcm_channel_num  = CONFIG_PCM_CHANNEL_NUM;
#endif

  rval = agora_rtc_join_channel(g_conn_id, AI_AGENT_CHANNEL_NAME, uid, g_app.token, &channel_options);
  if (rval < 0) {
    printf("Failed to join channel \"%s\", reason: %s\n", AI_AGENT_CHANNEL_NAME, agora_rtc_err_2_str(rval));
    return -1;
  }

  return 0;
}

void agora_rtc_proc_destroy(void)
{
  agora_rtc_leave_channel(g_conn_id);

  agora_rtc_destroy_connection(g_conn_id);

  agora_rtc_fini();
}

int send_rtc_audio_frame(uint8_t *data, uint32_t len)
{
  // API: send audio data
  audio_frame_info_t info = { 0 };
  info.data_type = AUDIO_DATA_TYPE_PCM;

  int rval = agora_rtc_send_audio_data(g_conn_id, data, len, &info);
  if (rval < 0) {
    printf("Failed to send audio data, reason: %s\n", agora_rtc_err_2_str(rval));
    return -1;
  }

  return 0;
}

int send_rtc_video_frame(uint8_t *data, uint32_t len)
{
  // API: send video data
  video_frame_info_t info = {
    .data_type    = VIDEO_DATA_TYPE_GENERIC_JPEG,
    .stream_type  = VIDEO_STREAM_HIGH,
    .frame_type   = VIDEO_FRAME_KEY,
    .rotation     = VIDEO_ORIENTATION_0,
    .frame_rate   = 0
  };

  int rval = agora_rtc_send_video_data(g_conn_id, data, len, &info);
  if (rval < 0) {
    printf("Failed to send video data, reason: %s\n", agora_rtc_err_2_str(rval));
    return -1;
  }

  return 0;
}
