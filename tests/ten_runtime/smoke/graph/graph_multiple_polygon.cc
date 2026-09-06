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
#include "ten_utils/lib/time.h"
#include "tests/common/client/cpp/msgpack_tcp.h"
#include "tests/common/constant.h"
#include "tests/ten_runtime/smoke/util/binding/cpp/check.h"

namespace {

/**
 *                     |--> B(1) --|
 *                  |--|           |--> F(3) --|
 *                  |  |--> C(1) --|           |
 * client --> A(1) -|                          |--> H(3)
 *                  |  |--> D(1) --|           |
 *                  |--|           |--> G(2) --|
 *                     |--> E(2) --|
 *
 * App 8001 : A,B,C,D
 * App 8002 : E,G
 * App 8003 : F,H
 */
class test_extension : public ten::extension_t {
 public:
  explicit test_extension(const char *name)
      : ten::extension_t(name), name_(name) {}

  void on_init(ten::ten_env_t &ten_env) override {
    is_leaf_node_ = ten_env.get_property_bool("is_leaf");
    ten_env.on_init_done();
  }

  void on_cmd(ten::ten_env_t &ten_env,
              std::unique_ptr<ten::cmd_t> cmd) override {
    nlohmann::json json = nlohmann::json::parse(cmd->get_property_to_json());

    if (is_leaf_node_) {
      json["return_from"] = name_;

      auto cmd_result = ten::cmd_result_t::create(TEN_STATUS_CODE_OK, *cmd);
      cmd_result->set_property_from_json("detail", json.dump().c_str());

      ten_env.return_result(std::move(cmd_result));
      return;
    }

    std::vector<std::string> edges = {"B", "C", "D", "E", "F", "G"};
    if (cmd->get_name() == "send") {
      json["from"] = name_;
      if (std::find(edges.begin(), edges.end(), name_) != edges.end()) {
        json[name_] = name_;
      }

      TEN_UNUSED bool const rc =
          cmd->set_property_from_json(nullptr, json.dump().c_str());
      TEN_ASSERT(rc, "Should not happen.");

      ten_env.send_cmd(
          std::move(cmd),
          [this, edges](ten::ten_env_t &ten_env,
                        std::unique_ptr<ten::cmd_result_t> cmd_result,
                        ten::error_t *err) {
            nlohmann::json json =
                nlohmann::json::parse(cmd_result->get_property_to_json());

            nlohmann::json detail = json["detail"];

            if (detail.type() == nlohmann::json::value_t::string) {
              detail = nlohmann::json::parse(json.value("detail", "{}"));
            }

            if (name_ == "A") {
              received_count++;
              if (detail["success"]) {
                received_success_count++;
              }
            }

            if (name_ == "A" && received_count < 1) {
              return;
            }

            detail["received_count"] = received_count;
            detail["received_success_count"] = received_success_count;

            if (name_ == "B" || name_ == "C") {
              detail["success"] =
                  (name_ == detail[name_] && detail["return_from"] == "F");
            } else if (name_ == "D" || name_ == "E") {
              detail["success"] =
                  (name_ == detail[name_] && detail["return_from"] == "G");
            } else {
              if (std::find(edges.begin(), edges.end(), name_) != edges.end()) {
                detail["success"] = (name_ == detail[name_]);
              }
            }

            detail["return_from"] = name_;

            cmd_result->set_property_from_json("detail", detail.dump().c_str());

            ten_env.return_result(std::move(cmd_result));
          });
    }
  }

 private:
  const std::string name_;
  bool is_leaf_node_{};
  int received_count = 0;
  int received_success_count = 0;
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

class test_app_3 : public ten::app_t {
 public:
  void on_configure(ten::ten_env_t &ten_env) override {
    bool rc = ten_env.init_property_from_json(
        // clang-format off
                 R"({
                      "ten": {
                        "uri": "msgpack://127.0.0.1:8003/",
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

void *app_thread_3_main(TEN_UNUSED void *args) {
  auto *app = new test_app_3();
  app->run();
  delete app;

  return nullptr;
}

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(graph_multiple_polygon__extension,
                                    test_extension);

}  // namespace

TEST(ExtensionTest, GraphMultiplePolygon) {  // NOLINT
  // Start app.
  auto *app_thread3 =
      ten_thread_create("app thread 3", app_thread_3_main, nullptr);
  auto *app_thread2 =
      ten_thread_create("app thread 2", app_thread_2_main, nullptr);
  auto *app_thread1 =
      ten_thread_create("app thread 1", app_thread_1_main, nullptr);

  // Create a client and connect to the app.
  ten::msgpack_tcp_client_t *client = nullptr;

  for (size_t i = 0; i < MULTIPLE_APP_SCENARIO_GRAPH_CONSTRUCTION_RETRY_TIMES;
       ++i) {
    client = new ten::msgpack_tcp_client_t("msgpack://127.0.0.1:8001/");

    auto start_graph_cmd = ten::start_graph_cmd_t::create();
    start_graph_cmd->set_dests(
        {{"msgpack://127.0.0.1:8001/", nullptr, nullptr}});
    start_graph_cmd->set_graph_from_json(R"({
               "nodes": [{
                 "type": "extension",
                 "name": "A",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension_group": "graph_multiple_polygon_1",
                 "property": {
                   "is_leaf": false
                  }
               },{
                 "type": "extension",
                 "name": "B",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension_group": "graph_multiple_polygon_1",
                 "property": {
                   "is_leaf": false
                  }
               },{
                 "type": "extension",
                 "name": "C",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension_group": "graph_multiple_polygon_1",
                 "property": {
                   "is_leaf": false
                  }
               },{
                 "type": "extension",
                 "name": "D",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension_group": "graph_multiple_polygon_1",
                 "property": {
                   "is_leaf": false
                  }
               },{
                 "type": "extension",
                 "name": "E",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8002/",
                 "extension_group": "graph_multiple_polygon_2",
                 "property": {
                   "is_leaf": false
                  }
               },{
                 "type": "extension",
                 "name": "G",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8002/",
                 "extension_group": "graph_multiple_polygon_2",
                 "property": {
                   "is_leaf": false
                  }
               },{
                 "type": "extension",
                 "name": "F",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8003/",
                 "extension_group": "graph_multiple_polygon_3",
                 "property": {
                   "is_leaf": false
                  }
               },{
                 "type": "extension",
                 "name": "H",
                 "addon": "graph_multiple_polygon__extension",
                 "app": "msgpack://127.0.0.1:8003/",
                 "extension_group": "graph_multiple_polygon_3",
                 "property": {
                   "is_leaf": true
                  }
               }],
               "connections": [{
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension": "A",
                 "cmd": [{
                   "name": "send",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8001/",
                     "extension": "B"
                   },{
                     "app": "msgpack://127.0.0.1:8001/",
                     "extension": "C"
                   },{
                     "app": "msgpack://127.0.0.1:8001/",
                     "extension": "D"
                   },{
                     "app": "msgpack://127.0.0.1:8002/",
                     "extension": "E"
                   }]
                 }]
               },{
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension": "B",
                 "cmd": [{
                   "name": "send",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8003/",
                     "extension": "F"
                   }]
                 }]
               },{
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension": "C",
                 "cmd": [{
                   "name": "send",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8003/",
                     "extension": "F"
                   }]
                 }]
               },{
                 "app": "msgpack://127.0.0.1:8001/",
                 "extension": "D",
                 "cmd": [{
                   "name": "send",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8002/",
                     "extension": "G"
                   }]
                 }]
               },{
                 "app": "msgpack://127.0.0.1:8002/",
                 "extension": "E",
                 "cmd": [{
                   "name": "send",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8002/",
                     "extension": "G"
                   }]
                 }]
               },{
                 "app": "msgpack://127.0.0.1:8003/",
                 "extension": "F",
                 "cmd": [{
                   "name": "send",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8003/",
                     "extension": "H"
                   }]
                 }]
               },{
                 "app": "msgpack://127.0.0.1:8002/",
                 "extension": "G",
                 "cmd": [{
                   "name": "send",
                   "dest": [{
                     "app": "msgpack://127.0.0.1:8003/",
                     "extension": "H"
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
      delete client;
      client = nullptr;

      // To prevent from busy re-trying.
      ten_random_sleep_range_ms(10, 20);
    }
  }

  TEN_ASSERT(client, "Failed to connect to the TEN app.");

  auto send_cmd = ten::cmd_t::create("send");
  send_cmd->set_dests({{"msgpack://127.0.0.1:8001/", "", "A"}});

  auto cmd_result = client->send_cmd_and_recv_result(std::move(send_cmd));

  nlohmann::json detail =
      nlohmann::json::parse(cmd_result->get_property_to_json("detail"));
  EXPECT_EQ(detail["return_from"], "A");
  EXPECT_EQ(detail["success"], true);
  EXPECT_EQ(detail["received_count"], 1);
  EXPECT_EQ(detail["received_success_count"], 1);

  delete client;

  ten::msgpack_tcp_client_t::close_app("msgpack://127.0.0.1:8001/");
  ten::msgpack_tcp_client_t::close_app("msgpack://127.0.0.1:8002/");
  ten::msgpack_tcp_client_t::close_app("msgpack://127.0.0.1:8003/");

  ten_thread_join(app_thread1, -1);
  ten_thread_join(app_thread2, -1);
  ten_thread_join(app_thread3, -1);
}
