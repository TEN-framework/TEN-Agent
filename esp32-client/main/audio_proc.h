#ifndef AUDIO_PROC_H
#define AUDIO_PROC_H
#ifdef __cplusplus
extern "C" {
#endif


#include <stdlib.h>


/* sema init for audio */
int audio_sema_init(void);

/* sema post */
void audio_sema_post(void);

/* sema pend */
void audio_sema_pend(void);

/* playback the audio */
int playback_stream_write(char *data, int len);

/* audio dev init */
void setup_audio(void);

/* start audio process */
int audio_start_proc(void);

/* get current volume */
int audio_get_volume(void);

/* set volume */
void audio_set_volume(int volume);


#ifdef __cplusplus
}
#endif
#endif