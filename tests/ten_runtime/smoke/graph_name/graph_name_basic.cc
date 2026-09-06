//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#include <nlohmann/json.hpp>

#include "gtest/gtest.h"
#include "include_internal/ten_runtime/binding/cpp/ten.h"
#include "ten_utils/lib/thread.h"
#include "ten_utils/lib/time.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
#include "tests/common/constant.h"
#include "tests/ten_runtime/smoke/util/binding/cpp/check.h"

namespace {

class test_extension : public ten::extension_t {
 public:
  explicit test_extension(const char *name)
      : ten::extension_t(name), name_(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    nlohmann::json data = nlohmann::json::parse(cmd->get_property_to_json());

    data["send_from"] = name_;

    TEN_UNUSED bool const rc =
        cmd->set_property_from_json(nullptr, data.dump().c_str());
    TEN_ASSERT(rc, "Should not happen.");

    // extension1(app1) -> extension3(app2) -> extension2(app1) -> return
    if (name_ == "extension2") {
      const nlohmann::json detail = {{"id", 1}, {"name", "aa"}};

      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property_from_json("detail", detail.dump().c_str());

      ten_env.return_result(std::move(cmd_result));
    } else {
      ten_env.send_cmd(
          std::move(cmd),
          [](ten::ten_env_t &ten_env,
             std::unique_ptr<ten::cmd_result_t> cmd_result, ten::error_t *err) {
            ten_env.return_result(std::move(cmd_result));
          });
    }
  }

 private:
  std::string name_;
};

class test_app_1 : public ten::app_t {
 public:
  void on_configure(ten::ten_env_t &ten_env) override {
    bool rc = ten_env.init_property_from_json(
        // clang-format off
                 R"({
                      "ten": {
                        "uri": "msgpack://127.0.0.1:8001/",
                        "long_running_mode": true,
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
                    })"
        // clang-format on
    );
    ASSERT_EQ(rc, true);

    ten_env.on_configure_done();
  }
};

class test_app_2 : public ten::app_t {
 public:
  void on_configure(ten::ten_env_t &ten_env) override {
    bool rc = ten_env.init_property_from_json(
        // clang-format off
                 R"({
                      "ten": {
                        "uri": "msgpack://127.0.0.1:8002/",
                        "long_running_mode": true,
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
                    })"
        // clang-format on
    );
    ASSERT_EQ(rc, true);

    ten_env.on_configure_done();
  }
};

ten::app_t *app1 = nullptr;
ten::app_t *app2 = nullptr;

void *app_thread_1_main(TEN_UNUSED void *args) {
  app1 = new test_app_1();
  app1->run(true);
  TEN_LOGD("Wait app1 thread");
  app1->wait();
  delete app1;
  app1 = nullptr;

  return nullptr;
}

void *app_thread_2_main(TEN_UNUSED void *args) {
  app2 = new test_app_2();
  app2->run(true);
  TEN_LOGD("Wait app2 thread");
  app2->wait();
  delete app2;
  app2 = nullptr;

  return nullptr;
}

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(graph_id_basic__extension, test_extension);

}  // namespace

TEST(ExtensionTest, GraphNameBasic) {  // NOLINT
  auto *app_thread_2 =
      ten_thread_create("app thread 2", app_thread_2_main, nullptr);
  auto *app_thread_1 =
      ten_thread_create("app thread 1", app_thread_1_main, nullptr);

  // extension1(app1) --> extension3(app2) --> extension2(app1) --> return
  ten::msgpack_tcp_client_t *client = nullptr;
  std::string graph_id;

  for (size_t i = 0; i < MULTIPLE_APP_SCENARIO_GRAPH_CONSTRUCTION_RETRY_TIMES;
       ++i) {
    client = new ten::msgpack_tcp_client_t("msgpack://127.0.0.1:8001/");

    auto start_graph_cmd = ten::start_graph_cmd_t::create();
    start_graph_cmd->set_dests(
        {{"msgpack://127.0.0.1:8001/", nullptr, nullptr}});
    start_graph_cmd->set_graph_from_json(R"({
               "nodes": [{
                 "type": "extension",
                 "name": "extension1",
                 "addon": "graph_id_basic__extension",
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension_group": "graph_id_basic__extension_group_1"
               },{
                 "type": "extension",
                 "name": "extension2",
                 "addon": "graph_id_basic__extension",
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension_group": "graph_id_basic__extension_group_1"
               },{
                 "type": "extension",
                 "name": "extension3",
                 "addon": "graph_id_basic__extension",
                 "app": "msgpack://127.0.0.1:8002/",
                 "extension_group": "graph_id_basic__extension_group_2"
               }],
               "connections": [{
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension": "extension1",
                 "cmd": [{
                   "name": "send_message",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8002/",
                     "extension": "extension3"
                   }]
                 }]
               },{
                 "app": "msgpack://127.0.0.1:8002/",
                 "extension": "extension3",
                 "cmd": [{
                   "name": "send_message",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8001/",
                     "extension": "extension2"
                   }]
                 }]
               }]
           })");

    auto cmd_result =
        client->send_cmd_and_recv_result(std::move(start_graph_cmd));

    if (cmd_result) {
      ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
      graph_id = cmd_result->get_property_string("graph_id");

      break;
    } else {
      delete client;
      client = nullptr;

      // To prevent from busy re-trying.
      ten_random_sleep_range_ms(10, 20);
    }
  }

  TEN_ASSERT(client, "Failed to connect to the TEN app.");

  // Send data to extension_1, it will return from extension_2 with json
  // result.
  auto send_message_cmd = ten::cmd_t::create("send_message");
  send_message_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "extension1"}});

  auto cmd_result =
      client->send_cmd_and_recv_result(std::move(send_message_cmd));

  ten_test::check_detail_with_json(cmd_result, R"({"id": 1, "name": "aa"})");

  // Send data to extension_3, it will return from extension_2 with json
  // result.
  auto *client2 = new ten::msgpack_tcp_client_t("msgpack://127.0.0.1:8002/");

  send_message_cmd = ten::cmd_t::create("send_message");
  send_message_cmd->set_dests(
      {{"msgpack://127.0.0.1:8002/", graph_id.c_str(), "extension3"}});

  // It must be sent directly to 127.0.0.1:8002, not 127.0.0.1:8001
  cmd_result = client2->send_cmd_and_recv_result(std::move(send_message_cmd));

  ten_test::check_detail_with_json(cmd_result, R"({"id": 1, "name": "aa"})");

  send_message_cmd = ten::cmd_t::create("send_message");
  send_message_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", graph_id.c_str(), "extension2"}});

  cmd_result = client->send_cmd_and_recv_result(std::move(send_message_cmd));

  ten_test::check_detail_with_json(cmd_result, R"({"id": 1, "name": "aa"})");

  delete client;
  delete client2;

  if (app1 != nullptr) {
    app1->close();
  }

  if (app2 != nullptr) {
    app2->close();
  }

  ten_thread_join(app_thread_1, -1);
  ten_thread_join(app_thread_2, -1);
}
