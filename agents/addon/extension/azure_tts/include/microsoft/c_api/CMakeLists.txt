cmake_minimum_required(VERSION 3.19)

project(c_headers)

set(SRC_DIR "${PROJECT_SOURCE_DIR}")
add_library(${PROJECT_NAME} INTERFACE ${SPEECH_C_API_HEADERS})
target_include_directories(${PROJECT_NAME} INTERFACE ${PROJECT_SOURCE_DIR})
set_target_properties(${PROJECT_NAME} PROPERTIES FOLDER api)
