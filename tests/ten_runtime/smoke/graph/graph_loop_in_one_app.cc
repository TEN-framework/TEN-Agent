//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#include <nlohmann/json.hpp>
#include <string>

#include "gtest/gtest.h"
#include "include_internal/ten_runtime/binding/cpp/ten.h"
#include "ten_utils/lib/thread.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
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

class test_extension_3 : public ten::extension_t {
 public:
  explicit test_extension_3(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      ten_env.send_cmd(std::move(cmd));
      return;
    }
  }
};

class test_extension_4 : public ten::extension_t {
 public:
  explicit test_extension_4(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "hello world, too");
      ten_env.return_result(std::move(cmd_result));
    }
  }
};

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

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(graph_loop_in_one_app__extension_1,
                                    test_extension_1);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(graph_loop_in_one_app__extension_2,
                                    test_extension_2);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(graph_loop_in_one_app__extension_3,
                                    test_extension_3);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(graph_loop_in_one_app__extension_4,
                                    test_extension_4);

}  // namespace

TEST(ExtensionTest, GraphLoopInOneApp) {
  // Start app.
  auto *app_thread =
      ten_thread_create("app thread", test_app_thread_main, nullptr);

  // Create a client and connect to the app.
  auto *client = new ten::msgpack_tcp_client_t("msgpack://127.0.0.1:8001/");

  // Send graph.
  auto start_graph_cmd = ten::start_graph_cmd_t::create();
  start_graph_cmd->set_graph_from_json(R"({
           "nodes": [{
               "type": "extension",
               "name": "test_extension_1",
               "addon": "graph_loop_in_one_app__extension_1",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "graph_loop_in_one_app__extension_group"
             },{
               "type": "extension",
               "name": "test_extension_2",
               "addon": "graph_loop_in_one_app__extension_2",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "graph_loop_in_one_app__extension_group"
             },{
               "type": "extension",
               "name": "test_extension_3",
               "addon": "graph_loop_in_one_app__extension_3",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "graph_loop_in_one_app__extension_group"
             },{
               "type": "extension",
               "name": "test_extension_4",
               "addon": "graph_loop_in_one_app__extension_4",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "graph_loop_in_one_app__extension_group"
             }],
             "connections": [{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "test_extension_1",
               "cmd": [{
                  "name": "hello_world",
                  "dest": [{
                    "app": "msgpack://127.0.0.1:8001/",
                    "extension": "test_extension_3"
                  }]
                }]
              },{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "test_extension_2",
               "cmd": [{
                  "name": "hello_world",
                  "dest": [{
                    "app": "msgpack://127.0.0.1:8001/",
                    "extension": "test_extension_3"
                  }]
                }]
              },{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "test_extension_3",
               "cmd": [{
                  "name": "hello_world",
                  "dest": [{
                    "app": "msgpack://127.0.0.1:8001/",
                    "extension": "test_extension_4"
                  }]
                }]
              },{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "test_extension_4",
               "cmd": [{
                  "name": "hello_world",
                  "dest": [{
                    "app": "msgpack://127.0.0.1:8001/",
                    "extension": "test_extension_2"
                  }]
                }]
              }]
            })");
  auto cmd_result =
      client->send_cmd_and_recv_result(std::move(start_graph_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);

  // Send a user-defined 'hello world' command to 'extension 1'.
  auto hello_world_cmd = ten::cmd_t::create("hello_world");
  hello_world_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "test_extension_1"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(hello_world_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "hello world, too");

  // Send a user-defined 'hello world' command to 'extension 2'.
  hello_world_cmd = ten::cmd_t::create("hello_world");
  hello_world_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "test_extension_2"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(hello_world_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "hello world, too");

  // Destroy the client.
  delete client;

  ten_thread_join(app_thread, -1);
}
