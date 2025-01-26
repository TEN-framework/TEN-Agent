
#ifndef AI_AGENT_H
#define AI_AGENT_H
#ifdef __cplusplus
extern "C" {
#endif


#include <stdlib.h>

/* generate ai agent information */
void ai_agent_generate(void);

/* start ai agent */
void ai_agent_start(void);

/* ping ai agent to keepalive */
void ai_agent_ping(void);

/* stop ai agent */
void ai_agent_stop(void);


#ifdef __cplusplus
}
#endif
#endif