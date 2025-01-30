idf_component_register(SRCS llm_main.c ai_agent.c rtc_proc.c audio_proc.c
					REQUIRES audio_hal audio_pipeline audio_stream audio_board esp_peripherals esp-adf-libs 
							 input_key_service esp_wifi nvs_flash agora_iot_sdk mbedtls)