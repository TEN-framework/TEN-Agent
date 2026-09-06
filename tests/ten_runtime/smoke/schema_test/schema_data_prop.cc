//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#include <condition_variable>
#include <memory>
#include <mutex>
#include <nlohmann/json.hpp>
#include <string>
#include <utility>

#include "gtest/gtest.h"
#include "include_internal/ten_runtime/binding/cpp/ten.h"
#include "ten_runtime/common/status_code.h"
#include "ten_utils/lib/thread.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
#include "tests/ten_runtime/smoke/util/binding/cpp/check.h"

namespace {

std::mutex mutex_lock;
std::condition_variable cv;  // NOLINT
int data_received = 0;

class test_extension_1 : public ten::extension_t {
 public:
  explicit test_extension_1(const char *name) : ten::extension_t(name) {}

  void on_configure(ten::ten_env_t &ten_env) override {
    // clang-format off

    bool rc = ten::ten_env_internal_accessor_t::init_manifest_from_json(ten_env,
                 R"({
                      "type": "extension",
                      "name": "schema_data_prop__test_extension_1",
                      "version": "0.1.0",
                      "api": {
                        "data_out": [
                          {
                            "name": "data",
                            "property": {
                              "properties": {
                                "foo": {
                                  "type": "int32"
                                }
                              }
                            }
                          }
                        ]
                      }
                    })");
    // clang-format on
    ASSERT_EQ(rc, true);

    ten_env.on_configure_done();
  }

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "hello_world") {
      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "success");
      ten_env.return_result(std::move(cmd_result));

      // Send data.
      auto data = ten::data_t::create("data");
      data->alloc_buf(1);

      bool rc = data->set_property("foo", "122");
      ASSERT_EQ(rc, true);

      rc = ten_env.send_data(std::move(data));
      ASSERT_EQ(rc, false);

      rc = data->set_property("foo", 12345);
      ASSERT_EQ(rc, true);

      // The `send_data` will be successful as the `data` matches the schema of
      // test_extension_1. But the `on_data` of test_extension_2 will not be
      // called as `12345` is out of range of `int8`.
      rc = ten_env.send_data(std::move(data));
      ASSERT_EQ(rc, true);

      // Expected to be received by test_extension_2.
      auto data2 = ten::data_t::create("data");
      data2->alloc_buf(1);

      rc = data2->set_property("foo", 123);
      ASSERT_EQ(rc, true);

      rc = ten_env.send_data(std::move(data2));
      ASSERT_EQ(rc, true);
    }
  }
};

class test_extension_2 : public ten::extension_t {
 public:
  explicit test_extension_2(const char *name) : ten::extension_t(name) {}

  void on_configure(ten::ten_env_t &ten_env) override {
    bool rc = ten::ten_env_internal_accessor_t::init_manifest_from_json(
        ten_env,
        // clang-format off
                 R"({
                      "type": "extension",
                      "name": "schema_data_prop__test_extension_2",
                      "version": "0.1.0",
                      "api": {
                        "data_in": [
                          {
                            "name": "data",
                            "property": {
                              "properties": {
                                "foo": {
                                  "type": "int8"
                                }
                              }
                            }
                          }
                        ]
                      }
                    })"
        // clang-format on
    );
    ASSERT_EQ(rc, true);

    ten_env.on_configure_done();
  }

  // NOLINTNEXTLINE(misc-unused-parameters)
  void on_data(ten::ten_env_t &ten_env,
               std::unique_ptr<ten::data_t> data) override {
    std::unique_lock<std::mutex> lock(mutex_lock);

    ASSERT_EQ(0, data_received);

    data_received++;
    cv.notify_all();
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

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(schema_data_prop__test_extension_1,
                                    test_extension_1);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(schema_data_prop__test_extension_2,
                                    test_extension_2);

}  // namespace

TEST(SchemaTest, DataProp) {  // NOLINT
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
                "addon": "schema_data_prop__test_extension_1",
                "extension_group": "basic_extension_group",
                "app": "msgpack://127.0.0.1:8001/"
             },{
                "type": "extension",
                "name": "test_extension_2",
                "addon": "schema_data_prop__test_extension_2",
                "extension_group": "basic_extension_group",
                "app": "msgpack://127.0.0.1:8001/"
             }],
             "connections": [{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "test_extension_1",
               "data": [{
                 "name": "data",
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

  // Send a user-defined 'hello world' command.
  auto hello_world_cmd = ten::cmd_t::create("hello_world");
  hello_world_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "test_extension_1"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(hello_world_cmd));

  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "success");

  {
    std::unique_lock<std::mutex> lock(mutex_lock);
    cv.wait(lock, [] { return data_received == 1; });
  }

  delete client;

  ten_thread_join(app_thread, -1);
}
