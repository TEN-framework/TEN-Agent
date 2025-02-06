#ifndef RTC_PROC_H
#define RTC_PROC_H
#ifdef __cplusplus
extern "C" {
#endif


#include <stdlib.h>


#define BANDWIDTH_ESTIMATE_MIN_BITRATE     (500000)
#define BANDWIDTH_ESTIMATE_MAX_BITRATE     (2000000)
#define BANDWIDTH_ESTIMATE_START_BITRATE   (750000)


int agora_rtc_proc_create(char *license, uint32_t uid);

void agora_rtc_proc_destroy(void);

int send_rtc_video_frame(uint8_t *data, uint32_t len);

int send_rtc_audio_frame(uint8_t *data, uint32_t len);

#ifdef __cplusplus
}
#endif
#endif