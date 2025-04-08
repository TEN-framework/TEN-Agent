/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2022 Agora Lab, Inc (http://www.agora.io/)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 */

#include <string.h>

#include <pthread.h>

#include "audio_element.h"
#include "audio_hal.h"
#include "audio_mem.h"
#include "audio_sys.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "i2c_bus.h"
#include "input_key_service.h"
#include "nvs_flash.h"

#include "ai_agent.h"
#include "audio_proc.h"
#include "common.h"
#include "rtc_proc.h"

#ifndef CONFIG_AUDIO_ONLY
#include "video_proc.h"
#endif

app_t g_app = {
  .b_call_session_started = false,
  .b_ai_agent_generated   = false,
  .b_wifi_connected       = false,
  .b_ai_agent_joined      = false,
  .app_id                 = { 0 },
  .token                  = { 0 },
};

static void event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
  printf("wifi event %ld\n", event_id);
  if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
    esp_wifi_connect();
  } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
    esp_wifi_connect();
  } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_CONNECTED) {
    //g_app.b_wifi_connected = true;
    printf("wifi sta mode connect.\n");
  } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
    ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
    g_app.b_wifi_connected = true;
    printf("got ip: \n" IPSTR, IP2STR(&event->ip_info.ip));
  }
}

/*init wifi as sta */
static void setup_wifi(void)
{
  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());
  esp_netif_t *sta_netif = esp_netif_create_default_wifi_sta();
  assert(sta_netif);

  wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_wifi_init(&cfg));

  ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL, NULL));
  ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL, NULL));

  wifi_config_t wifi_config = {
    .sta = {
      .ssid            = CONFIG_WIFI_SSID,
      .password        = CONFIG_WIFI_PASSWORD,
      .listen_interval = CONFIG_EXAMPLE_WIFI_LISTEN_INTERVAL,
    },
  };
  ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
  ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
  ESP_ERROR_CHECK(esp_wifi_start());

  esp_wifi_set_ps(WIFI_PS_NONE);
}

static esp_err_t input_key_service_cb(periph_service_handle_t handle, periph_service_event_t *evt, void *ctx)
{
  switch ((int)evt->data) {
    case INPUT_KEY_USER_ID_MUTE:
      printf("[ * ] [Stop] Stop Ai Agent\n");
      if (evt->type == INPUT_KEY_SERVICE_ACTION_CLICK_RELEASE) {
        if (g_app.b_ai_agent_joined) {
          g_app.b_ai_agent_joined = false;
          // stop ai agent
          ai_agent_stop();
        } else {
          printf("Ai Agent has already stopped.\n");
        }
      }
      break;
    case INPUT_KEY_USER_ID_SET:
      printf("[ * ] [Start] Start Ai Agent\n");
      if (evt->type == INPUT_KEY_SERVICE_ACTION_CLICK_RELEASE) {
        if (!g_app.b_ai_agent_joined) {
          // start ai agent
          ai_agent_start();
          g_app.b_ai_agent_joined = true;
        } else {
          printf("Ai Agent has already Started.\n");
        }
      }
      break;
    case INPUT_KEY_USER_ID_VOLDOWN:
      if (evt->type == INPUT_KEY_SERVICE_ACTION_CLICK_RELEASE) {
        printf("[ * ] [Vol-] input key event\n");
        int player_volume = audio_get_volume();
        player_volume -= 10;
        if (player_volume < 0) {
          player_volume = 0;
        }
        audio_set_volume(player_volume);
        printf("Now volume is %d\n", player_volume);
      }
      break;
    case INPUT_KEY_USER_ID_VOLUP:
      if (evt->type == INPUT_KEY_SERVICE_ACTION_CLICK_RELEASE) {
        printf( "[ * ] [Vol+] input key event\n");
        int player_volume = audio_get_volume();
        player_volume += 10;
        if (player_volume > 100) {
          player_volume = 100;
        }
        audio_set_volume(player_volume);
        printf("Now volume is %d\n", player_volume);
      }
    default:
        break;
  }
  return ESP_OK;
}


static void setup_key_button(void)
{
  // init the peripherals set and peripherls
  esp_periph_config_t periph_cfg = DEFAULT_ESP_PERIPH_SET_CONFIG();
  periph_cfg.extern_stack = true;
  esp_periph_set_handle_t set = esp_periph_set_init(&periph_cfg);

  // setup the input key service
  audio_board_key_init(set);

  input_key_service_info_t input_info[] = INPUT_KEY_DEFAULT_INFO();
  input_key_service_cfg_t key_serv_info = INPUT_KEY_SERVICE_DEFAULT_CONFIG();
  key_serv_info.based_cfg.task_stack   = 8 * 1024;
  key_serv_info.based_cfg.extern_stack = false;
  key_serv_info.handle = set;

  periph_service_handle_t input_key_handle = input_key_service_create(&key_serv_info);
  if (!input_key_handle) {
    return;
  }
  input_key_service_add_key(input_key_handle, input_info, INPUT_KEY_NUM);
  periph_service_set_callback(input_key_handle, input_key_service_cb, NULL);
}

int app_main(void)
{
  // Initialize NVS
  esp_err_t ret = nvs_flash_init();
  if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    ret = nvs_flash_init();
  }
  ESP_ERROR_CHECK(ret);

  // init and start wifi
  setup_wifi();

  // Wait until WiFi is connected
  while (!g_app.b_wifi_connected) {
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }

  ai_agent_generate();

  // init and start key button
  setup_key_button();

  //setup and start audio
  setup_audio();
  audio_sema_init();
  audio_start_proc();

  printf("~~~~~start agora rtc demo~~~~\r\n");

  while (!g_app.b_ai_agent_generated) {
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }

  agora_rtc_proc_create(NULL, AI_AGENT_USER_ID);

  while(!g_app.b_call_session_started) {
    usleep(200 * 1000);
  }
  printf("~~~~~agora_rtc_join_channel success~~~~\r\n");

#ifndef CONFIG_AUDIO_ONLY
    start_video_proc();
#endif

  printf("Agora: Press [SET] key to join the Ai Agent ...\n");

  while (1) {
    // audio_sys_get_real_time_stats();
    printf("MEM Total:%ld Bytes, Inter:%d Bytes, Dram:%d Bytes\n", esp_get_free_heap_size(),
              heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
              heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));

    if (g_app.b_ai_agent_joined) {
      printf("ai agent keepalive\r\n");
      ai_agent_ping();
    }

    sleep(10);
  }

  agora_rtc_proc_destroy();

  return 0;
}
