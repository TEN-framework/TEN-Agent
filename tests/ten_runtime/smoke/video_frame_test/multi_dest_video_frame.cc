//
// Copyright © 2025 Agora
// This file is part of TEN Framework, an open source project.
// Licensed under the Apache License, Version 2.0, with certain conditions.
// Refer to the "LICENSE" file in the root directory for more information.
//
#include <cstdlib>
#include <nlohmann/json.hpp>
#include <string>

#include "gtest/gtest.h"
#include "include_internal/ten_runtime/binding/cpp/ten.h"
#include "ten_utils/lib/thread.h"
#include "ten_utils/macro/check.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
#include "tests/ten_runtime/smoke/util/binding/cpp/check.h"

#define WIDTH 640
#define HEIGHT 480

namespace {

class test_extension_1 : public ten::extension_t {
 public:
  explicit test_extension_1(const char *name) : ten::extension_t(name) {}

  static std::unique_ptr<ten::video_frame_t> create420Buffer(int width,
                                                             int height) {
    auto video_frame = ten::video_frame_t::create("video_frame");
    video_frame->set_pixel_fmt(TEN_PIXEL_FMT_I420);
    video_frame->set_width(width);
    video_frame->set_height(height);

    auto buf_size = width * height * 3 / 2;
    video_frame->alloc_buf(buf_size + 32);

    return video_frame;
  }

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "dispatch_data") {
      auto video_frame = create420Buffer(WIDTH, HEIGHT);
      video_frame->set_property("test_prop", "test_prop_value");

      ten_env.send_video_frame(std::move(video_frame));

      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property("detail", "done");
      ten_env.return_result(std::move(cmd_result));
    }
  }
};

class test_extension_2 : public ten::extension_t {
 public:
  explicit test_extension_2(const char *name) : ten::extension_t(name) {}

  void on_video_frame(
      TEN_UNUSED ten::ten_env_t &ten_env,
      std::unique_ptr<ten::video_frame_t> video_frame) override {
    auto test_value = video_frame->get_property_string("test_prop");
    TEN_ASSERT(test_value == "test_prop_value", "test_prop_value not match");

    if (video_frame->get_width() == WIDTH &&
        video_frame->get_height() == HEIGHT) {
      received = true;
    }
  }

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "check_received") {
      if (received) {
        auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
        cmd_result->set_property("detail", "received confirmed");
        ten_env.return_result(std::move(cmd_result));
      } else {
        auto cmd_result =
            ten::cmd_result_t::create(TEN_STATUS_CODE_ERROR, *cmd);
        cmd_result->set_property("detail", "received failed");
        ten_env.return_result(std::move(cmd_result));
      }
    }
  }

 private:
  bool received{false};
};

class test_extension_3 : public ten::extension_t {
 public:
  explicit test_extension_3(const char *name) : ten::extension_t(name) {}

  void on_video_frame(
      TEN_UNUSED ten::ten_env_t &ten_env,
      std::unique_ptr<ten::video_frame_t> video_frame) override {
    auto test_value = video_frame->get_property_string("test_prop");
    TEN_ASSERT(test_value == "test_prop_value", "test_prop_value not match");

    if (video_frame->get_width() == WIDTH &&
        video_frame->get_height() == HEIGHT) {
      received = true;
    }
  }

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    if (cmd->get_name() == "check_received") {
      if (received) {
        auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
        cmd_result->set_property("detail", "received confirmed");
        ten_env.return_result(std::move(cmd_result));
      } else {
        auto cmd_result =
            ten::cmd_result_t::create(TEN_STATUS_CODE_ERROR, *cmd);
        cmd_result->set_property("detail", "received failed");
        ten_env.return_result(std::move(cmd_result));
      }
    }
  }

 private:
  bool received{false};
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

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(multi_dest_video_frame__extension_1,
                                    test_extension_1);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(multi_dest_video_frame__extension_2,
                                    test_extension_2);
TEN_CPP_REGISTER_ADDON_AS_EXTENSION(multi_dest_video_frame__extension_3,
                                    test_extension_3);

}  // namespace

TEST(VideoFrameTest, MultiDestVideoFrame) {  // NOLINT
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
               "addon": "multi_dest_video_frame__extension_1",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "test_extension_group"
             },{
               "type": "extension",
               "name": "extension_2",
               "addon": "multi_dest_video_frame__extension_2",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "test_extension_group"
             },{
               "type": "extension",
               "name": "extension_3",
               "addon": "multi_dest_video_frame__extension_3",
               "app": "msgpack://127.0.0.1:8001/",
               "extension_group": "test_extension_group"
             }],
             "connections": [{
               "app": "msgpack://127.0.0.1:8001/",
               "extension": "extension_1",
               "video_frame": [{
                 "name": "video_frame",
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
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);

  // Send a user-defined 'dispatch_data' command.
  auto dispatch_data_cmd = ten::cmd_t::create("dispatch_data");
  dispatch_data_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "extension_1"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(dispatch_data_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "done");

  auto check_received_cmd = ten::cmd_t::create("check_received");
  check_received_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "extension_2"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(check_received_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "received confirmed");

  check_received_cmd = ten::cmd_t::create("check_received");
  check_received_cmd->set_dests(
      {{"msgpack://127.0.0.1:8001/", "", "extension_3"}});
  cmd_result = client->send_cmd_and_recv_result(std::move(check_received_cmd));
  ten_test::check_status_code(cmd_result, TEN_STATUS_CODE_OK);
  ten_test::check_detail_with_string(cmd_result, "received confirmed");

  delete client;

  ten_thread_join(app_thread, -1);
}
