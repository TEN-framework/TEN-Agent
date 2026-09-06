//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#include <memory>
#include <nlohmann/json.hpp>
#include <string>

#include "gtest/gtest.h"
#include "include_internal/ten_runtime/binding/cpp/ten.h"
#include "ten_utils/lib/thread.h"
#include "ten_utils/lib/time.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
#include "tests/common/constant.h"
#include "tests/ten_runtime/smoke/util/binding/cpp/check.h"

namespace {

class test_extension_1 : public ten::extension_t {
 public:
  explicit test_extension_1(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      ten_env.send_cmd(std::move(cmd));
      return;
    }
  }
};

class test_extension_2 : public ten::extension_t {
 public:
  explicit test_extension_2(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "hello world, too");
      ten_env.return_result(std::move(cmd_result));
    }
  }
};

class test_app_1 : public ten::app_t {
 public:
  void on_configure(ten::ten_env_t &ten_env) override {
    // In a scenario which contains multiple TEN app, the construction of a
    // graph might failed because not all TEN app has already been launched
    // successfully.
    //
    //     client -> (connect cmd) -> TEN app 1 ... TEN app 2
    //                                    o             x
    //
    // In this case, the newly constructed engine in the app 1 would be closed,
    // and the client would see that the connection has be dropped. After that,
    // the client could retry to send the 'start_graph' command again to inform
    // the TEN app to build the graph again.
    //
    // Therefore, the closing of an engine could _not_ cause the closing of the
    // app, and that's why the following 'long_running_mode' has been set.
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
        ,
        nullptr);
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
        ,
        nullptr);
    ASSERT_EQ(rc, true);

    ten_env.on_configure_done();
  }
};

void *app_thread_1_main(TEN_UNUSED void *args) {
  auto *app = new test_app_1();
  app->run();
  delete app;

  return nullptr;
}

void *app_thread_2_main(TEN_UNUSED void *args) {
  auto *app = new test_app_2();
  app->run();
  delete app;

  return nullptr;
}

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(basic_multi_app__extension_1,
                                    test_extension_1);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(basic_multi_app__extension_2,
                                    test_extension_2);

}  // namespace

TEST(BasicTest, MultiApp) {  // NOLINT
  ten_thread_t *app1_thread = nullptr;
  ten_thread_t *app2_thread = nullptr;
  std::unique_ptr<ten::msgpack_tcp_client_t> client = nullptr;

  try {
    // Start app.
    app2_thread = ten_thread_create("app thread 2", app_thread_2_main, nullptr);
    app1_thread = ten_thread_create("app thread 1", app_thread_1_main, nullptr);

    // In a scenario which contains multiple TEN app, the construction of a
    // graph might failed because not all TEN app has already been launched
    // successfully.
    //
    //     client -> (connect cmd) -> TEN app 1 ... TEN app 2
    //                                    o             x
    //
    // In this case, the newly constructed engine in the app 1 would be closed,
    // and the client would see that the connection has be dropped. After that,
    // the client could retry to send the 'start_graph' command again to inform
    // the TEN app to build the graph again.
    for (size_t i = 0; i < MULTIPLE_APP_SCENARIO_GRAPH_CONSTRUCTION_RETRY_TIMES;
         ++i) {
      // Create a client and connect to the app.
      client = std::make_unique<ten::msgpack_tcp_client_t>(
          "msgpack://127.0.0.1:8001/");

      // Send graph.

      auto start_graph_cmd = ten::start_graph_cmd_t::create();
      start_graph_cmd->set_graph_from_json(R"({
           "nodes": [{
                   "type": "extension",
                   "name": "test_extension_1",
                   "addon": "basic_multi_app__extension_1",
                   "app": "msgpack://127.0.0.1:8001/",
                   "extension_group": "test_extension_group_1"
                 },{
                   "type": "extension",
                   "name": "test_extension_2",
                   "addon": "basic_multi_app__extension_2",
                   "app": "msgpack://127.0.0.1:8002/",
                   "extension_group": "test_extension_group_2"
                 }],
                 "connections": [{
                   "app": "msgpack://127.0.0.1:8001/",
                   "extension": "test_extension_1",
                   "cmd": [{
                     "name": "hello_world",
                     "dest": [{
                       "app": "msgpack://127.0.0.1:8002/",
                       "extension": "test_extension_2"
                     }]
                   }]
                 }]
               })");
      auto cmd_result =
          client->send_cmd_and_recv_result(std::move(start_graph_cmd));

      if (cmd_result) {
        ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
        break;
      } else {
        client.reset();

        // To prevent from busy re-trying.
        ten_random_sleep_range_ms(10, 20);
      }
    }

    TEN_ASSERT(client, "Failed to connect to the TEN app.");

    // Send a user-defined 'hello world' command.
    auto hello_world_cmd = ten::cmd_t::create("hello_world");
    hello_world_cmd->set_dests(
        {{"msgpack://127.0.0.1:8001/", "", "test_extension_1"}});

    auto cmd_result =
        client->send_cmd_and_recv_result(std::move(hello_world_cmd));

    ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
    ten_test::check_detail_with_string(cmd_result, "hello world, too");

    // Because the closing of an engine would _not_ cause the closing of the
    // app, so we have to explicitly close the app.
    ten::msgpack_tcp_client_t::close_app("msgpack://127.0.0.1:8001/");

    // Because the closing of an engine would _not_ cause the closing of the
    // app, so we have to explicitly close the app.
    ten::msgpack_tcp_client_t::close_app("msgpack://127.0.0.1:8002/");
  } catch (...) {
    // Do nothing.
  }

  ten_thread_join(app1_thread, -1);
  ten_thread_join(app2_thread, -1);
}
