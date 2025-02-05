#include <string.h>

#include <pthread.h>

#include "board.h"
#include "audio_element.h"
#include "audio_hal.h"
#include "audio_mem.h"
#include "audio_sys.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "i2c_bus.h"


#include "filter_resample.h"
#include "algorithm_stream.h"
#include "i2s_stream.h"
#include "raw_stream.h"
#include "audio_thread.h"
#include "audio_pipeline.h"

#include "common.h"
#include "rtc_proc.h"



static audio_element_handle_t raw_read, element_algo, raw_write;
static audio_pipeline_handle_t recorder, player;
static SemaphoreHandle_t g_audio_capture_sem  = NULL;
static audio_thread_t *g_audio_thread;

audio_board_handle_t board_handle;


int audio_sema_init(void)
{
  g_audio_capture_sem = xSemaphoreCreateBinary();
  if (NULL == g_audio_capture_sem) {
    printf("Unable to create audio capture semaphore!\n");
    return -1;
  }

  return 0;
}

void audio_sema_post(void)
{
  xSemaphoreTake(g_audio_capture_sem, portMAX_DELAY);
}

void audio_sema_pend(void)
{
  xSemaphoreGive(g_audio_capture_sem);
}


static esp_err_t recorder_pipeline_open(void)
{
  audio_element_handle_t i2s_stream_reader;
  audio_pipeline_cfg_t pipeline_cfg = DEFAULT_AUDIO_PIPELINE_CONFIG();
  recorder = audio_pipeline_init(&pipeline_cfg);
  if (!recorder) {
    return ESP_FAIL;
  }

  i2s_stream_cfg_t i2s_cfg = I2S_STREAM_CFG_DEFAULT_WITH_PARA(CODEC_ADC_I2S_PORT, CONFIG_PCM_SAMPLE_RATE, AUDIO_I2S_BITS, AUDIO_STREAM_READER);
  i2s_cfg.task_core     = 0;
  i2s_cfg.stack_in_ext  = true;
  i2s_stream_set_channel_type(&i2s_cfg, I2S_CHANNEL_TYPE_ONLY_LEFT);
  // i2s_cfg.out_rb_size  = 2 * 1024;
  i2s_cfg.stack_in_ext  = true;
  i2s_stream_reader = i2s_stream_init(&i2s_cfg);

  algorithm_stream_cfg_t algo_config = ALGORITHM_STREAM_CFG_DEFAULT();
  algo_config.input_type = ALGORITHM_STREAM_INPUT_TYPE1;
  algo_config.algo_mask  = ALGORITHM_STREAM_USE_AEC;
  algo_config.swap_ch    = true;
  element_algo = algo_stream_init(&algo_config);
  audio_element_set_music_info(element_algo, CONFIG_PCM_SAMPLE_RATE, 1, 16);

  raw_stream_cfg_t raw_cfg = RAW_STREAM_CFG_DEFAULT();
  raw_cfg.type        = AUDIO_STREAM_READER;
  raw_cfg.out_rb_size = 2 * 1024;
  raw_read = raw_stream_init(&raw_cfg);
  audio_element_set_output_timeout(raw_read, portMAX_DELAY);

  audio_pipeline_register(recorder, i2s_stream_reader, "i2s");
  audio_pipeline_register(recorder, element_algo, "algo");
  audio_pipeline_register(recorder, raw_read, "raw");

  const char *link_tag[3] = { "i2s", "algo", "raw" };
  audio_pipeline_link(recorder, &link_tag[0], 3);

  printf("audio recorder has been created\n");
  return ESP_OK;
}

static esp_err_t player_pipeline_open(void)
{
  audio_element_handle_t i2s_stream_writer;
  audio_pipeline_cfg_t pipeline_cfg = DEFAULT_AUDIO_PIPELINE_CONFIG();
  player = audio_pipeline_init(&pipeline_cfg);
  if (!player) {
    return ESP_FAIL;
  }

  raw_stream_cfg_t raw_cfg = RAW_STREAM_CFG_DEFAULT();
  raw_cfg.type        = AUDIO_STREAM_WRITER;
  raw_cfg.out_rb_size = 8 * 1024;
  raw_write = raw_stream_init(&raw_cfg);

  i2s_stream_cfg_t i2s_cfg = I2S_STREAM_CFG_DEFAULT_WITH_PARA(CODEC_ADC_I2S_PORT, CONFIG_PCM_SAMPLE_RATE, AUDIO_I2S_BITS, AUDIO_STREAM_WRITER);
  i2s_cfg.need_expand  = true;
  i2s_stream_set_channel_type(&i2s_cfg, I2S_CHANNEL_TYPE_ONLY_LEFT);
  i2s_cfg.stack_in_ext = true;
  i2s_stream_writer = i2s_stream_init(&i2s_cfg);

  audio_pipeline_register(player, raw_write, "raw");
  audio_pipeline_register(player, i2s_stream_writer, "i2s");
  const char *link_tag[2] = {"raw", "i2s"};
  audio_pipeline_link(player, &link_tag[0], 2);

  return ESP_OK;
}

static void _pipeline_close(audio_pipeline_handle_t handle)
{
  audio_pipeline_stop(handle);
  audio_pipeline_wait_for_stop(handle);
  audio_pipeline_deinit(handle);
}

static void audio_send_thread(void *arg)
{
  int ret = 0;

  uint8_t *audio_pcm_buf = heap_caps_malloc(CONFIG_PCM_DATA_LEN, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!audio_pcm_buf) {
    printf("Failed to alloc audio buffer!\n");
    goto THREAD_END;
  }

  recorder_pipeline_open();
  player_pipeline_open();

  audio_sema_post();

  audio_pipeline_run(recorder);
  audio_pipeline_run(player);
  while (g_app.b_call_session_started) {
    ret = raw_stream_read(raw_read, (char *)audio_pcm_buf, CONFIG_PCM_DATA_LEN);
    if (ret != CONFIG_PCM_DATA_LEN) {
      printf("read raw stream error, expect %d, but only %d\n", CONFIG_PCM_DATA_LEN, ret);
    }

    send_rtc_audio_frame(audio_pcm_buf, CONFIG_PCM_DATA_LEN);
  }

  //deinit
  _pipeline_close(player);
  _pipeline_close(recorder);

THREAD_END:
  if (audio_pcm_buf) {
    free(audio_pcm_buf);
  }

  vTaskDelete(NULL);
}

int playback_stream_write(char *data, int len)
{
  return raw_stream_write(raw_write, data, len);
}

void setup_audio(void)
{
  board_handle = audio_board_init();
  audio_hal_ctrl_codec(board_handle->audio_hal, AUDIO_HAL_CODEC_MODE_BOTH, AUDIO_HAL_CTRL_START);
  audio_hal_set_volume(board_handle->audio_hal, 85);
}

int audio_start_proc(void)
{
  int rval = audio_thread_create(g_audio_thread, "audio_send_task", audio_send_thread, NULL, 4 * 1024, PRIO_TASK_FETCH, true, 0);
  if (rval != ESP_OK) {
    printf("Unable to create audio capture thread!\n");
    return -1;
  }

  return rval;
}

int audio_get_volume(void)
{
  int volume = 0;
  audio_hal_get_volume(board_handle->audio_hal, &volume);

  return volume;
}

void audio_set_volume(int volume)
{
  audio_hal_set_volume(board_handle->audio_hal, volume);
}