//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "include_internal/ten_runtime/binding/cpp/ten.h"
#include "ten_utils/lib/thread.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
#include "tests/ten_runtime/smoke/util/binding/cpp/check.h"

#define DEST_EXTENSION_MIN_ID 2
#define DEST_EXTENSION_MAX_ID 35

namespace {

typedef enum RESPONSE {
  RESPONSE_2,
  RESPONSE_3,
  RESPONSE_4,
  RESPONSE_5,
  RESPONSE_6,
  RESPONSE_7,
  RESPONSE_8,
  RESPONSE_9,
  RESPONSE_10,
  RESPONSE_11,
  RESPONSE_12,
  RESPONSE_13,
  RESPONSE_14,
  RESPONSE_15,
  RESPONSE_16,
  RESPONSE_17,
  RESPONSE_18,
  RESPONSE_19,
  RESPONSE_20,
  RESPONSE_21,
  RESPONSE_22,
  RESPONSE_23,
  RESPONSE_24,
  RESPONSE_25,
  RESPONSE_26,
  RESPONSE_27,
  RESPONSE_28,
  RESPONSE_29,
  RESPONSE_30,
  RESPONSE_31,
  RESPONSE_32,
  RESPONSE_33,
  RESPONSE_34,
  RESPONSE_35,
} RESPONSE;

class test_extension_1 : public ten::extension_t {
 public:
  explicit test_extension_1(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      ten_env.send_cmd(
          std::move(cmd), [this](ten::ten_env_t &ten_env,
                                 std::unique_ptr<ten::cmd_result_t> cmd_result,
                                 ten::error_t *err) {
            pending_resp_num--;
            if (pending_resp_num == 0) {
              cmd_result->set_property("detail", "return from extension 1");
              ten_env.return_result(std::move(cmd_result));
            }
          });
      return;
    }
  }

 private:
  int pending_resp_num{1};
};

#define DEFINE_TEST_EXTENSION(N)                                               \
  class test_extension_##N : public ten::extension_t {                         \
   public:                                                                     \
    explicit test_extension_##N(const char *name) : ten::extension_t(name) {}  \
                                                                               \
    void on_cmd(ten::ten_env_t &ten_env,                                       \
                std::unique_ptr<ten::cmd_t> cmd) override {                    \
      nlohmann::json json =                                                    \
          nlohmann::json::parse(cmd->get_property_to_json());                  \
      if (cmd->get_name() == "hello_world") {                                  \
        auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd); \
        cmd_result->set_property("detail", "hello world from extension " #N);  \
        ten_env.return_result(std::move(cmd_result));                          \
      }                                                                        \
    }                                                                          \
  };

DEFINE_TEST_EXTENSION(2)
DEFINE_TEST_EXTENSION(3)
DEFINE_TEST_EXTENSION(4)
DEFINE_TEST_EXTENSION(5)
DEFINE_TEST_EXTENSION(6)
DEFINE_TEST_EXTENSION(7)
DEFINE_TEST_EXTENSION(8)
DEFINE_TEST_EXTENSION(9)
DEFINE_TEST_EXTENSION(10)
DEFINE_TEST_EXTENSION(11)
DEFINE_TEST_EXTENSION(12)
DEFINE_TEST_EXTENSION(13)
DEFINE_TEST_EXTENSION(14)
DEFINE_TEST_EXTENSION(15)
DEFINE_TEST_EXTENSION(16)
DEFINE_TEST_EXTENSION(17)
DEFINE_TEST_EXTENSION(18)
DEFINE_TEST_EXTENSION(19)
DEFINE_TEST_EXTENSION(20)
DEFINE_TEST_EXTENSION(21)
DEFINE_TEST_EXTENSION(22)
DEFINE_TEST_EXTENSION(23)
DEFINE_TEST_EXTENSION(24)
DEFINE_TEST_EXTENSION(25)
DEFINE_TEST_EXTENSION(26)
DEFINE_TEST_EXTENSION(27)
DEFINE_TEST_EXTENSION(28)
DEFINE_TEST_EXTENSION(29)
DEFINE_TEST_EXTENSION(30)
DEFINE_TEST_EXTENSION(31)
DEFINE_TEST_EXTENSION(32)
DEFINE_TEST_EXTENSION(33)
DEFINE_TEST_EXTENSION(34)
DEFINE_TEST_EXTENSION(35)

class test_app : public ten::app_t {
 public:
  void on_configure(ten::ten_env_t &ten_env) override {
    bool rc = ten_env.init_property_from_json(
        // clang-format off
        R"({
             "ten": {
               "uri": "msgpack://127.0.0.1:8001/",
               "log": {
                 "handlers": [
                   {
                     "matchers": [
                       {
                         "level": "debug"
                       }
                     ],
                     "formatter": {
                       "type": "plain",
                       "colored": true
                     },
                     "emitter": {
                       "type": "console",
                       "config": {
                         "stream": "stdout"
                       }
                     }
                   }
                 ]
               }
             }
           })",
        // clang-format on
        nullptr);
    ASSERT_EQ(rc, true);

    ten_env.on_configure_done();
  }
};

void *test_app_thread_main(TEN_UNUSED void *args) {
  auto *app = new test_app();
  app->run();
  delete app;

  return nullptr;
}

#define REGISTER_ADDON_AS_EXTENSION(N)                                      \
  TEN_CPP_REGISTER_ADDON_AS_EXTENSION(multi_dest_in_one_app__extension_##N, \
                                      test_extension_##N);

REGISTER_ADDON_AS_EXTENSION(1)
REGISTER_ADDON_AS_EXTENSION(2)
REGISTER_ADDON_AS_EXTENSION(3)
REGISTER_ADDON_AS_EXTENSION(4)
REGISTER_ADDON_AS_EXTENSION(5)
REGISTER_ADDON_AS_EXTENSION(6)
REGISTER_ADDON_AS_EXTENSION(7)
REGISTER_ADDON_AS_EXTENSION(8)
REGISTER_ADDON_AS_EXTENSION(9)
REGISTER_ADDON_AS_EXTENSION(10)
REGISTER_ADDON_AS_EXTENSION(11)
REGISTER_ADDON_AS_EXTENSION(12)
REGISTER_ADDON_AS_EXTENSION(13)
REGISTER_ADDON_AS_EXTENSION(14)
REGISTER_ADDON_AS_EXTENSION(15)
REGISTER_ADDON_AS_EXTENSION(16)
REGISTER_ADDON_AS_EXTENSION(17)
REGISTER_ADDON_AS_EXTENSION(18)
REGISTER_ADDON_AS_EXTENSION(19)
REGISTER_ADDON_AS_EXTENSION(20)
REGISTER_ADDON_AS_EXTENSION(21)
REGISTER_ADDON_AS_EXTENSION(22)
REGISTER_ADDON_AS_EXTENSION(23)
REGISTER_ADDON_AS_EXTENSION(24)
REGISTER_ADDON_AS_EXTENSION(25)
REGISTER_ADDON_AS_EXTENSION(26)
REGISTER_ADDON_AS_EXTENSION(27)
REGISTER_ADDON_AS_EXTENSION(28)
REGISTER_ADDON_AS_EXTENSION(29)
REGISTER_ADDON_AS_EXTENSION(30)
REGISTER_ADDON_AS_EXTENSION(31)
REGISTER_ADDON_AS_EXTENSION(32)
REGISTER_ADDON_AS_EXTENSION(33)
REGISTER_ADDON_AS_EXTENSION(34)
REGISTER_ADDON_AS_EXTENSION(35)

}  // namespace

TEST(MultiDestTest, MultiDestInOneApp) {  // NOLINT
  // Start app.
  auto *app_thread =
      ten_thread_create("app thread", test_app_thread_main, nullptr);

  // Create a client and connect to the app.
  auto *client = new ten::msgpack_tcp_client_t("msgpack://127.0.0.1:8001/");

  auto start_graph_cmd_content_str = R"({
             "nodes": [],
             "connections": [{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "test_extension_1",
               "cmd": [{
                 "name": "hello_world",
                 "dest": []
               }]
             }]
         })"_json;

  for (int i = 1; i <= DEST_EXTENSION_MAX_ID; i++) {
    start_graph_cmd_content_str["nodes"].push_back({
        {"type", "extension"},
        {"name", "test_extension_" + std::to_string(i)},
        {"addon", "multi_dest_in_one_app__extension_" + std::to_string(i)},
        {"app", "msgpack://127.0.0.1:8001/"},
        {"extension_group", "multi_dest_in_one_app__extension_group"},
    });
  }

  for (int i = DEST_EXTENSION_MIN_ID; i <= DEST_EXTENSION_MAX_ID; i++) {
    start_graph_cmd_content_str["connections"][0]["cmd"][0]["dest"].push_back({
        {"app", "msgpack://127.0.0.1:8001/"},  // app
        {"extension", "test_extension_" + std::to_string(i)},  // extension
    });
  }

  // Send graph.
  auto start_graph_cmd = ten::start_graph_cmd_t::create();
  start_graph_cmd->set_graph_from_json(
      start_graph_cmd_content_str.dump().c_str());

  auto cmd_result =
      client->send_cmd_and_recv_result(std::move(start_graph_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);

  // Send a user-defined 'hello world' command to 'extension 1'.
  auto hello_world_cmd = ten::cmd_t::create("hello_world");
  hello_world_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "test_extension_1"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(hello_world_cmd));

  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "return from extension 1");

  delete client;

  ten_thread_join(app_thread, -1);
}
