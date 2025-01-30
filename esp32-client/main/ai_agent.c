#include <string.h>
#include <sys/param.h>
#include <stdlib.h>
#include <ctype.h>
#include "esp_log.h"
#include "esp_event.h"

#include "esp_system.h"
#include "cJSON.h"

#include "esp_http_client.h"
#include "common.h"


#define JSON_URL_LEN           128
#define REQ_JSON_LEN           512
#define MAX_HTTP_OUTPUT_BUFFER 2048


#define TENAI_AGENT_GENERATE  "token/generate"
#define TENAI_AGENT_START     "start"
#define TENAI_AGENT_STOP      "stop"
#define TENAI_AGENT_PING      "ping"


static int _parse_resp_data(const char *resp_data, const int data_len)
{
    if (data_len == 0) {
        return -1;
    }

    // parse JSON buffer
    cJSON *root_json = cJSON_Parse(resp_data);
    if (root_json == NULL) {
        const char *error_ptr = cJSON_GetErrorPtr();
        if (error_ptr != NULL) {
            printf("Error before: %s\n", error_ptr);
        }
        return -1;
    }

    // get JSON object item
    cJSON *code = cJSON_GetObjectItemCaseSensitive(root_json, "code");
    // make sure it is string and get value
    if (cJSON_IsString(code) && (code->valuestring != NULL)) {
        printf("code: %s\n", code->valuestring);
    }

    cJSON *msg = cJSON_GetObjectItemCaseSensitive(root_json, "msg");
    // make sure it is string and get value
    if (cJSON_IsString(msg) && (msg->valuestring != NULL)) {
        printf("msg: %s\n", msg->valuestring);
    }

    // make sure code value is "0" and msg is "success"
    if (strcmp(code->valuestring, "0") != 0 || strcmp(msg->valuestring, "success") != 0) {
        printf("ai agent is not ok\n");
        cJSON_Delete(root_json);
        return -1;
    }

    if (g_app.b_ai_agent_generated) {
        cJSON_Delete(root_json);
        return 0;
    }

    cJSON *data = cJSON_GetObjectItemCaseSensitive(root_json, "data");
    
    // check data is null
    if (data != NULL && cJSON_IsNull(data)) {
        printf("The 'data' field is null.\n");
        cJSON_Delete(root_json);
        return 0;
    }

    cJSON *app_id = cJSON_GetObjectItemCaseSensitive(data, "appId");

    // make sure it is string and get value
    if (cJSON_IsString(app_id) && (app_id->valuestring != NULL)) {
        printf("appId: %s\n", app_id->valuestring);
        memcpy(g_app.app_id, app_id->valuestring, RTC_APP_ID_LEN);
    }

    cJSON *token = cJSON_GetObjectItemCaseSensitive(data, "token");

    // make sure it is string and get value
    if (cJSON_IsString(token) && (token->valuestring != NULL)) {
        printf("token: %s\n", token->valuestring);
        memcpy(g_app.token, token->valuestring, RTC_TOKEN_LEN);
    }  

    g_app.b_ai_agent_generated = true;

    cJSON_Delete(root_json);
    return 0;
}

/*
{
    "code": "0",
    "data": null,
    "msg": "success"
}
 */
static esp_err_t _http_event_handler(esp_http_client_event_t *evt)
{
    static char *output_buffer;  // Buffer to store response of http request from event handler
    static int output_len;       // Stores number of bytes read
    switch(evt->event_id) {
        case HTTP_EVENT_ERROR:
            printf("HTTP_EVENT_ERROR\n");
            break;
        case HTTP_EVENT_ON_CONNECTED:
            printf("HTTP_EVENT_ON_CONNECTED\n");
            break;
        case HTTP_EVENT_HEADER_SENT:
            printf("HTTP_EVENT_HEADER_SENT\n");
            break;
        case HTTP_EVENT_ON_HEADER:
            printf("HTTP_EVENT_ON_HEADER, key=%s, value=%s\n", evt->header_key, evt->header_value);
            break;
        case HTTP_EVENT_ON_DATA:
            printf("HTTP_EVENT_ON_DATA, len=%d, data=%s\n", evt->data_len, (char *)evt->data);
            // Clean the buffer in case of a new request
            if (output_len == 0 && evt->user_data) {
                // we are just starting to copy the output data into the use
                memset(evt->user_data, 0, MAX_HTTP_OUTPUT_BUFFER);
            }
            /*
             *  Check for chunked encoding is added as the URL for chunked encoding used in this example returns binary data.
             *  However, event handler can also be used in case chunked encoding is used.
             */
            if (!esp_http_client_is_chunked_response(evt->client)) {
                // If user_data buffer is configured, copy the response into the buffer
                int copy_len = 0;
                if (evt->user_data) {
                    // The last byte in evt->user_data is kept for the NULL character in case of out-of-bound access.
                    copy_len = MIN(evt->data_len, (MAX_HTTP_OUTPUT_BUFFER - output_len));
                    if (copy_len) {
                        memcpy(evt->user_data + output_len, evt->data, copy_len);
                    }
                } else {
                    int content_len = esp_http_client_get_content_length(evt->client);
                    if (output_buffer == NULL) {
                        // We initialize output_buffer with 0 because it is used by strlen() and similar functions therefore should be null terminated.
                        output_buffer = (char *) calloc(content_len + 1, sizeof(char));
                        output_len = 0;
                        if (output_buffer == NULL) {
                            printf("Failed to allocate memory for output buffer\n");
                            return ESP_FAIL;
                        }
                    }
                    copy_len = MIN(evt->data_len, (content_len - output_len));
                    if (copy_len) {
                        memcpy(output_buffer + output_len, evt->data, copy_len);
                    }
                }
                output_len += copy_len;
            }
            break;
        case HTTP_EVENT_ON_FINISH:
            printf("HTTP_EVENT_ON_FINISH\n");
            _parse_resp_data(output_buffer, output_len);

            if (output_buffer != NULL) {
                // Response is accumulated in output_buffer.
                free(output_buffer);
                output_buffer = NULL;
            }
            output_len = 0;

            break;
        case HTTP_EVENT_DISCONNECTED:
            printf("HTTP_EVENT_DISCONNECTED\n");
            if (output_buffer != NULL) {
                free(output_buffer);
                output_buffer = NULL;
            }
            output_len = 0;
            break;
        default:
            break;
    }
    return ESP_OK;
}


/************************************************************************
{
    "request_id": "tenai_test_1234111",
    "uid":166993,
    "channel_name":"agora_tmw"
}

{
    "code": "0",
    "data": {
        "appId": "b8d13d3e1ed74347b21ec75d170e87ea",
        "channel_name": "agora_tmw",
        "token": "007eJxSYLB6eni2srOm+r4jDybaPJubwl24brXl7deJtgH2Mrd7+//876J2Y=",
        "uid": 166993
    },
    "msg": "success"
}
************************************************************************/
static char *_build_generate_json(void)
{
    char *json_ptr = NULL;

    cJSON *root = cJSON_CreateObject();
    if (root == NULL) {
      goto BUILD_END;
    }

    cJSON_AddItemToObject(root, "request_id", cJSON_CreateString(AI_AGENT_NAME));
    cJSON_AddNumberToObject(root, "uid", AI_AGENT_USER_ID);
    cJSON_AddItemToObject(root, "channel_name", cJSON_CreateString(AI_AGENT_CHANNEL_NAME));

    json_ptr = cJSON_Print(root);

BUILD_END:
    cJSON_Delete(root);

    return json_ptr;
}


/*
{
    "request_id": "conversational_test_1234111",
    "channel_name":"agora_tmw",
    "user_uid":166993,
    "graph_name":"va_openai_v2v",
    "properties":
    {
        "agora_rtc":
        {
            "sdk_params": "{\"che.audio.custom_payload_type\":0}"
        },
        "v2v":
        {
            "model":"gpt-4o-realtime-preview-2024-12-17",
            "voice":"ash",
            "language":"en-US",
            "greeting":"",
            "prompt":""
        }
    }
}
*/
static char *_build_start_json(void)
{
    char *json_ptr = NULL;

    cJSON *root = cJSON_CreateObject();
    if (root == NULL) {
      goto BUILD_END;
    }

    cJSON_AddItemToObject(root, "request_id", cJSON_CreateString(AI_AGENT_NAME));
    cJSON_AddItemToObject(root, "channel_name", cJSON_CreateString(AI_AGENT_CHANNEL_NAME));
    cJSON_AddNumberToObject(root, "user_uid", AI_AGENT_USER_ID);
    cJSON_AddItemToObject(root, "graph_name", cJSON_CreateString(GRAPH_NAME));

    cJSON *properties = cJSON_CreateObject();
    cJSON_AddItemToObject(root, "properties", properties);   //properties object

    cJSON *agora_rtc = cJSON_CreateObject();
    cJSON_AddItemToObject(properties, "agora_rtc", agora_rtc);   //agora rtc object
    cJSON_AddItemToObject(agora_rtc, "sdk_params", cJSON_CreateString(TENAI_AUDIO_CODEC)); 

    cJSON *custom_llm = cJSON_CreateObject();
    cJSON_AddItemToObject(properties, "v2v", custom_llm);   //v2v object
    cJSON_AddItemToObject(custom_llm, "model", cJSON_CreateString(V2V_MODEL));
    cJSON_AddItemToObject(custom_llm, "voice", cJSON_CreateString(VOICE));
    cJSON_AddItemToObject(custom_llm, "language", cJSON_CreateString(LANGUAGE));
    cJSON_AddItemToObject(custom_llm, "greeting", cJSON_CreateString(GREETING));
    cJSON_AddItemToObject(custom_llm, "prompt", cJSON_CreateString(PROMPT));

    json_ptr = cJSON_Print(root);

BUILD_END:
    cJSON_Delete(root);

    return json_ptr;
}


/*
{
    "request_id": "conversational_test_1234111",
    "channel_name":"agora_tmw",
}
*/
static char *_build_common_json(void)
{
    char *json_ptr = NULL;

    cJSON *root = cJSON_CreateObject();
    if (root == NULL) {
      goto BUILD_END;
    }

    cJSON_AddItemToObject(root, "request_id", cJSON_CreateString(AI_AGENT_NAME));
    cJSON_AddItemToObject(root, "channel_name", cJSON_CreateString(AI_AGENT_CHANNEL_NAME));

    json_ptr = cJSON_Print(root);

BUILD_END:
    cJSON_Delete(root);

    return json_ptr;
}


/* generate ai agent information */
void ai_agent_generate(void)
{
    char request[REQ_JSON_LEN] = {'\0'};

    char generate_url[JSON_URL_LEN] = { 0 };
    snprintf(generate_url, JSON_URL_LEN, "%s/%s", TENAI_AGENT_URL, TENAI_AGENT_GENERATE);

    esp_event_loop_create_default();

    esp_http_client_config_t config = {
        .url           = generate_url,
        .event_handler = _http_event_handler,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "application/json");

    char *json_buff = _build_generate_json();
    snprintf(request, REQ_JSON_LEN, "%s", json_buff);
    free(json_buff);

    esp_err_t err = esp_http_client_open(client, strlen(request));
    printf("http_with_url request =%s\n",request);
    if (err != ESP_OK) {
        printf("Failed to open HTTP connection: %s\n", esp_err_to_name(err));
    } else {
        int wlen = esp_http_client_write(client, request, strlen(request));
        if (wlen < 0) {
            printf("https client write failed\n");
        }

        esp_err_t err = esp_http_client_perform(client);
        if (err == ESP_OK) {
            printf("HTTPS Status = %d, content_length = %lld\n",
                esp_http_client_get_status_code(client),
                esp_http_client_get_content_length(client));
        } else {
            printf("Error perform http request %s\n", esp_err_to_name(err));
        }
    }

    esp_http_client_cleanup(client);
}

/* start ai agent */
void ai_agent_start(void)
{
    char request[REQ_JSON_LEN] = {'\0'};

    char start_url[JSON_URL_LEN] = { 0 };
    snprintf(start_url, JSON_URL_LEN, "%s/%s", TENAI_AGENT_URL, TENAI_AGENT_START);

    esp_event_loop_create_default();

    esp_http_client_config_t config = {
        .url           = start_url,
        .event_handler = _http_event_handler,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "application/json");

    char *json_buff = _build_start_json();
    snprintf(request, REQ_JSON_LEN, "%s", json_buff);
    free(json_buff);

    esp_err_t err = esp_http_client_open(client, strlen(request));
    printf("http_with_url request =%s\n",request);
    if (err != ESP_OK) {
        printf("Failed to open HTTP connection: %s\n", esp_err_to_name(err));
    } else {
        int wlen = esp_http_client_write(client, request, strlen(request));
        if (wlen < 0) {
            printf("https client write failed\n");
        }

        esp_err_t err = esp_http_client_perform(client);
        if (err == ESP_OK) {
            printf("HTTPS Status = %d, content_length = %lld\n",
                esp_http_client_get_status_code(client),
                esp_http_client_get_content_length(client));
        } else {
            printf("Error perform http request %s\n", esp_err_to_name(err));
        }
    }

    esp_http_client_cleanup(client);
}

/* ping ai agent to keepalive */
void ai_agent_ping(void)
{
    char request[REQ_JSON_LEN] = {'\0'};

    char ping_url[JSON_URL_LEN] = { 0 };

    snprintf(ping_url, JSON_URL_LEN, "%s/%s", TENAI_AGENT_URL, TENAI_AGENT_PING);

    esp_http_client_config_t config = {
        .url           = ping_url,
        .event_handler = _http_event_handler,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "application/json");

    char *json_buff = _build_common_json();
    snprintf(request, REQ_JSON_LEN, "%s", json_buff);
    free(json_buff);

    esp_err_t err = esp_http_client_open(client, strlen(request));
    printf("http_with_url request =%s\n",request);
    if (err != ESP_OK) {
        printf("Failed to open HTTP connection: %s\n", esp_err_to_name(err));
    } else {
        int wlen = esp_http_client_write(client, request, strlen(request));
        if (wlen < 0) {
            printf("https client write failed\n");
        }

        esp_err_t err = esp_http_client_perform(client);
        if (err == ESP_OK) {
            printf("HTTPS Status = %d, content_length = %lld\n",
                esp_http_client_get_status_code(client),
                esp_http_client_get_content_length(client));
        } else {
            printf("Error perform http request %s\n", esp_err_to_name(err));
        }
    }

    esp_http_client_cleanup(client);
}

/* stop ai agent */
void ai_agent_stop(void)
{
    char request[REQ_JSON_LEN] = {'\0'};

    char stop_url[JSON_URL_LEN] = { 0 };

    snprintf(stop_url, JSON_URL_LEN, "%s/%s", TENAI_AGENT_URL, TENAI_AGENT_STOP);

    esp_http_client_config_t config = {
        .url           = stop_url,
        .event_handler = _http_event_handler,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "application/json");

    char *json_buff = _build_common_json();
    snprintf(request, REQ_JSON_LEN, "%s", json_buff);
    free(json_buff);

    esp_err_t err = esp_http_client_open(client, strlen(request));
    printf("http_with_url request =%s\n",request);
    if (err != ESP_OK) {
        printf("Failed to open HTTP connection: %s\n", esp_err_to_name(err));
    } else {
        int wlen = esp_http_client_write(client, request, strlen(request));
        if (wlen < 0) {
            printf("https client write failed\n");
        }

        esp_err_t err = esp_http_client_perform(client);
        if (err == ESP_OK) {
            printf("HTTPS Status = %d, content_length = %lld\n",
                esp_http_client_get_status_code(client),
                esp_http_client_get_content_length(client));
        } else {
            printf("Error perform http request %s\n", esp_err_to_name(err));
        }
    }

    esp_http_client_cleanup(client);
}
