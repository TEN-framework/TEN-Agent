
#include <unistd.h>
#include <string.h>
#include <sys/param.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_err.h"
#include "esp_jpeg_common.h"
#include "esp_camera.h"
#include "esp_jpeg_enc.h"

#include "common.h"
#include "rtc_proc.h"


#ifndef CONFIG_AUDIO_ONLY


#define CONFIG_FRAME_WIDTH 640//480
#define CONFIG_FRAME_HIGH  480//320
#define CONFIG_FRAME_SIZE  (FRAMESIZE_VGA)//(FRAMESIZE_HVGA)

#define CAMERA_WIDTH (CONFIG_FRAME_WIDTH)
#define CAMERA_HIGH (CONFIG_FRAME_HIGH)

#define CAM_PIN_PWDN -1 // power down is not used
#define CAM_PIN_RESET -1 // software reset will be performed
#define CAM_PIN_XCLK GPIO_NUM_40
#define CAM_PIN_SIOD GPIO_NUM_17
#define CAM_PIN_SIOC GPIO_NUM_18

#define CAM_PIN_D7 GPIO_NUM_39
#define CAM_PIN_D6 GPIO_NUM_41
#define CAM_PIN_D5 GPIO_NUM_42
#define CAM_PIN_D4 GPIO_NUM_12
#define CAM_PIN_D3 GPIO_NUM_3
#define CAM_PIN_D2 GPIO_NUM_14
#define CAM_PIN_D1 GPIO_NUM_47
#define CAM_PIN_D0 GPIO_NUM_13
#define CAM_PIN_VSYNC GPIO_NUM_21
#define CAM_PIN_HREF GPIO_NUM_38
#define CAM_PIN_PCLK GPIO_NUM_11


/* camera config */
static camera_config_t camera_config = {
  .pin_pwdn  = CAM_PIN_PWDN,
  .pin_reset = CAM_PIN_RESET,
  .pin_xclk  = CAM_PIN_XCLK,
  .pin_sscb_sda = CAM_PIN_SIOD,
  .pin_sscb_scl = CAM_PIN_SIOC,

  .pin_d7 = CAM_PIN_D7,
  .pin_d6 = CAM_PIN_D6,
  .pin_d5 = CAM_PIN_D5,
  .pin_d4 = CAM_PIN_D4,
  .pin_d3 = CAM_PIN_D3,
  .pin_d2 = CAM_PIN_D2,
  .pin_d1 = CAM_PIN_D1,
  .pin_d0 = CAM_PIN_D0,
  .pin_vsync = CAM_PIN_VSYNC,
  .pin_href  = CAM_PIN_HREF,
  .pin_pclk  = CAM_PIN_PCLK,

  // XCLK 20MHz or 10MHz for OV2640 double FPS (Experimental)
  .xclk_freq_hz = 10000000,
  .ledc_timer   = LEDC_TIMER_0,
  .ledc_channel = LEDC_CHANNEL_0,

  .pixel_format = PIXFORMAT_YUV422, // YUV422,GRAYSCALE,RGB565,JPEG
  .frame_size   = CONFIG_FRAME_SIZE, // QQVGA-UXGA Do not use sizes above QVGA
  // when not JPEG

  .jpeg_quality = 12, // 0-63 lower number means higher quality
  .fb_count     = 1, // if more than one, i2s runs in continuous mode. Use only with JPEG
  .grab_mode    = CAMERA_GRAB_WHEN_EMPTY,
};


static jpeg_enc_handle_t init_jpeg_encoder(int quality, int hfm_core, int hfm_priority, jpeg_subsampling_t subsampling)
{
  jpeg_enc_handle_t jpeg_enc = NULL;

  jpeg_enc_config_t jpeg_enc_info = DEFAULT_JPEG_ENC_CONFIG();

  jpeg_enc_info.width       = CAMERA_WIDTH;
  jpeg_enc_info.height      = CAMERA_HIGH;
  // jpeg_enc_info.src_type    = JPEG_RAW_TYPE_YCbY2YCrY2;  //conv_mode = YUV422_TO_YUV420 
  jpeg_enc_info.src_type    = JPEG_PIXEL_FORMAT_YCbYCr;
  jpeg_enc_info.subsampling = subsampling;
  jpeg_enc_info.quality     = quality;
  // jpeg_enc_info.task_enable = true;
  jpeg_enc_info.hfm_task_core     = hfm_core;
  jpeg_enc_info.hfm_task_priority = hfm_priority;

  jpeg_error_t ret = jpeg_enc_open(&jpeg_enc_info, &jpeg_enc);
  if (ret != JPEG_ERR_OK) {
    printf("jpeg enc open failed\n");
    return NULL;
  }

  return jpeg_enc;
}

static void video_send_thread(void *arg)
{
  int image_len = 0;
  const int image_buf_len = 30 * 1024;

  jpeg_enc_handle_t jpeg_enc_hdl = NULL;

  uint8_t *image_buf = heap_caps_malloc(image_buf_len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!image_buf) {
    printf( "Failed to alloc video buffer!\n");
    goto THREAD_END;
  }

  // initialize the camera
  esp_err_t err = esp_camera_init(&camera_config);
  if (err != ESP_OK) {
    printf( "Camera Init Failed\n");
    goto THREAD_END;
  }

  jpeg_enc_hdl = init_jpeg_encoder(40, 0, 20, JPEG_SUBSAMPLE_420);
  if (!jpeg_enc_hdl) {
    printf( "Failed to initialize jpeg enc!\n");
    goto THREAD_END;
  }

  while (g_app.b_call_session_started) {
    camera_fb_t *pic = esp_camera_fb_get();

    jpeg_enc_process(jpeg_enc_hdl, pic->buf, pic->len, image_buf, image_buf_len, &image_len);

    // printf("esp_camera_fb_get buf %p, len %d, image %p, image_len %d\n", pic->buf, pic->len, image_buf, image_len);

    send_rtc_video_frame(image_buf, image_len);

    esp_camera_fb_return(pic);
  
    // sleep and wait until time is up for next send
    usleep(200 * 1000);
  }

THREAD_END:
  if (jpeg_enc_hdl) {
    jpeg_enc_close(jpeg_enc_hdl);
  }

  if (image_buf) {
    free(image_buf);
  }

  // deinitialize the camera
  err = esp_camera_deinit();
  if (err != ESP_OK) {
    printf( "Camera DeInit Failed\n");
  }

  vTaskDelete(NULL);
}

int start_video_proc(void)
{
  int rval = xTaskCreatePinnedToCore(video_send_thread, "video_send_task", 5 * 1024, NULL, PRIO_TASK_FETCH, NULL, 0);
  if (rval != pdTRUE) {
    printf("Unable to create audio capture thread!\r\n");
    return -1;
  }

  return rval;
}

#endif
