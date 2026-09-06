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
#include "ten_runtime/binding/cpp/detail/ten_env.h"
#include "ten_utils/lib/thread.h"
#include "ten_utils/lib/time.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
#include "tests/ten_runtime/smoke/util/binding/cpp/check.h"

namespace {

class test_extension_1 : public ten::extension_t {
 public:
  explicit test_extension_1(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      TEN_ENV_LOG_INFO(ten_env, "on_cmd: hello_world");
      ten_env.send_cmd(std::move(cmd));
    }
  }

  void on_stop(ten::ten_env_t &ten_env) override {
    TEN_ENV_LOG_INFO(ten_env, "on_stop");

    auto cmd = ten::cmd_t::create("extension_1_stop");
    ten_env.send_cmd(std::move(cmd));

    // Don't care about the result of the `extension_1_stop` command; just
    // declare "stop done." It's equivalent to treating the `extension_1_stop`
    // command as an event.

    ten_env.on_stop_done();
  }
};

class test_extension_2 : public ten::extension_t {
 public:
  explicit test_extension_2(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      ten_sleep_ms(500);

      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "hello world, too");
      TEN_ENV_LOG_INFO(ten_env, "on_cmd: hello_world, return result.");
      ten_env.return_result(std::move(cmd_result));
    } else if (cmd->get_name() == "extension_1_stop") {
      // Ensure that extension 2 receives the `extension_1_stop` command and
      // returns a result. However, since extension 1 does not wait for the
      // result of the `extension_1_stop` command, it may or may not receive
      // this result.

      ten_sleep_ms(500);

      TEN_ENV_LOG_INFO(ten_env, "got extension_1_stop.");

      received_extension_1_stop_cmd = true;

      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "extension_1_stop, too");
      ten_env.return_result(std::move(cmd_result));

      if (have_called_on_stop) {
        ten_env.on_stop_done();
      }
    }
  }

  void on_stop(ten::ten_env_t &ten_env) override {
    have_called_on_stop = true;

    if (received_extension_1_stop_cmd) {
      ten_env.on_stop_done();
    }
  }

 private:
  bool received_extension_1_stop_cmd = false;
  bool have_called_on_stop = false;
};

class test_extension_3 : public ten::extension_t {
 public:
  explicit test_extension_3(const char *name) : ten::extension_t(name) {}

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "hello world, too");
      TEN_ENV_LOG_INFO(ten_env, "on_cmd: hello_world, return result.");
      ten_env.return_result(std::move(cmd_result));
    } else if (cmd->get_name() == "extension_1_stop") {
      // It's possible that the `extension_1_stop` command was received, but
      // it's also possible that it wasn't received, and the extension thread 3
      // has already ended.

      ten_sleep_ms(500);

      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "extension_1_stop, too");
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

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(
    multi_dest_send_in_stop_period_1__extension_1, test_extension_1);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(
    multi_dest_send_in_stop_period_1__extension_2, test_extension_2);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(
    multi_dest_send_in_stop_period_1__extension_3, test_extension_3);

}  // namespace

TEST(MultiDestTest, MultiDestSendInStopPeriod1) {  // NOLINT
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
               "name": "extension_1",
               "addon": "multi_dest_send_in_stop_period_1__extension_1",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "test_extension_group1"
             },{
               "type": "extension",
               "name": "extension_2",
               "addon": "multi_dest_send_in_stop_period_1__extension_2",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "test_extension_group2"
             },{
               "type": "extension",
               "name": "extension_3",
               "addon": "multi_dest_send_in_stop_period_1__extension_3",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "test_extension_group3"
             }],
             "connections": [{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "extension_1",
               "cmd": [{
                 "name": "hello_world",
                 "dest": [{
                   "app": "msgpack://127.0.0.1:8001/",
                   "extension": "extension_2"
                 },{
                   "app": "msgpack://127.0.0.1:8001/",
                   "extension": "extension_3"
                 }]
               },{
                 "name": "extension_1_stop",
                 "dest": [{
                   "app": "msgpack://127.0.0.1:8001/",
                   "extension": "extension_2"
                 },{
                   "app": "msgpack://127.0.0.1:8001/",
                   "extension": "extension_3"
                 }]
               }]
             }]
           })");
  auto cmd_result =
      client->send_cmd_and_recv_result(std::move(start_graph_cmd));
  TEN_LOGI("start_graph_cmd completed");
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);

  // Send a user-defined 'hello world' command.
  auto hello_world_cmd = ten::cmd_t::create("hello_world");
  hello_world_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "extension_1"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(hello_world_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "hello world, too");

  TEN_LOGI("delete client");
  delete client;

  ten_thread_join(app_thread, -1);
}
