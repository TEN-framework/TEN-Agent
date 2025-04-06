#pragma once


//LLM Agent Service
#define TENAI_AGENT_URL       "http://<ip_address>:<port>"

// LLM Agent Graph, you can select openai or gemini 
// #define CONFIG_GRAPH_OPENAI   /* openai, just only audio */
#define CONFIG_GRAPH_GEMINI     /* gemini, for video and audio, but not support chinese language */

/* greeting */
#define GREETING               "Can I help You?"
#define PROMPT                 ""

/* different settings for different agent graph */
#if defined(CONFIG_GRAPH_OPENAI)
#define GRAPH_NAME             "va_openai_v2v"

#define V2V_MODEL              "gpt-4o-realtime-preview-2024-12-17"
#define LANGUAGE               "en-US"
#define VOICE                  "ash"
#elif defined(CONFIG_GRAPH_GEMINI)
#define GRAPH_NAME             "va_gemini_v2v"
#else
#error "not config graph for aiAgent"
#endif

// LLM Agent Task Name
#define AI_AGENT_NAME          "tenai0125-11"
// LLM Agent Channel Name
#define AI_AGENT_CHANNEL_NAME  "aiAgent_chn0124-11"
// LLM User Id
#define AI_AGENT_USER_ID        12345 // user id, for device



/* function config */
/* audio codec */
#define CONFIG_USE_G711U_CODEC
/* video process */
// #define CONFIG_AUDIO_ONLY
