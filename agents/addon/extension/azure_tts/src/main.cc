/**
 *
 * Agora Real Time Engagement
 * Created by Wei Hu in 2022-02.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <memory>

#include "log.h"
#include "macro/check.h"
#include "rte_runtime/binding/cpp/internal/msg/cmd/cmd.h"
#include "rte_runtime/binding/cpp/internal/msg/cmd_result.h"
#include "rte_runtime/binding/cpp/internal/msg/pcm_frame.h"
#include "rte_runtime/binding/cpp/internal/rte_proxy.h"
#include "rte_runtime/binding/cpp/rte.h"
#include "tts.h"

namespace azure_tts_extension {

class azure_tts_extension_t : public rte::extension_t {
 public:
  explicit azure_tts_extension_t(const std::string &name) : extension_t(name) {}

  // on_start will be called when the extension is starting, 
  // properies can be read here to initialize and start the extension.
  // current supported properties: 
  //   - azure_subscription_key
  //   - azure_subscription_region
  //   - azure_synthesis_voice_name
  void on_start(rte::rte_t &rte) override {
    AZURE_TTS_LOGI("start");

    // read properties
    auto key = rte.get_property_string("azure_subscription_key");
    auto region = rte.get_property_string("azure_subscription_region");
    auto voice_name = rte.get_property_string("azure_synthesis_voice_name");
    if (key.empty() || region.empty() || voice_name.empty()) {
      AZURE_TTS_LOGE(
          "azure_subscription_key, azure_subscription_region, azure_synthesis_voice_name should not be empty, start "
          "failed");
      return;
    }

    rte_proxy_ = std::unique_ptr<rte::rte_proxy_t>(rte::rte_proxy_t::create(rte));
    RTE_ASSERT(rte_proxy_ != nullptr, "rte_proxy should not be nullptr");

    // pcm parameters
    auto sample_rate = 16000;
    auto samples_per_10ms = sample_rate / 100;
    auto channel = 1;
    auto bytes_per_sample = 2;
    auto pcm_frame_size = samples_per_10ms * channel * bytes_per_sample;  // per 10ms

    // initialize the callback to send pcm to RTC extension
    auto pcm_callback =
        [rte_proxy = rte_proxy_.get(), sample_rate, bytes_per_sample, samples_per_10ms, channel, pcm_frame_size](
            const uint8_t *data,
            size_t size) {
          auto pcm_frame = rte::pcm_frame_t::create("pcm_frame");
          pcm_frame->set_bytes_per_sample(bytes_per_sample);
          pcm_frame->set_sample_rate(sample_rate);
          pcm_frame->set_channel_layout(1);
          pcm_frame->set_number_of_channels(channel);
          pcm_frame->set_timestamp(0);
          pcm_frame->set_data_fmt(RTE_PCM_FRAME_DATA_FMT_INTERLEAVE);
          pcm_frame->set_samples_per_channel(samples_per_10ms);
          pcm_frame->alloc_buf(pcm_frame_size);
          rte::buf_t borrowed_buf = pcm_frame->lock_buf(0);
          auto *buf = borrowed_buf.data();
          if (buf != nullptr) {
            memset(buf, 0, pcm_frame_size);  // fill empty if size is not enough for 10ms
            memcpy(buf, data, size);
          }
          pcm_frame->unlock_buf(borrowed_buf);

          auto pcm_frame_shared = std::make_shared<std::unique_ptr<rte::pcm_frame_t>>(std::move(pcm_frame));
          rte_proxy->notify(
              [frame = std::move(pcm_frame_shared)](rte::rte_t &rte) { rte.send_pcm_frame(std::move(*frame)); });
        };


    // initialize Azure TTS
    azure_tts_ = std::make_unique<AzureTTS>(
        key,
        region,
        voice_name,
        Microsoft::CognitiveServices::Speech::SpeechSynthesisOutputFormat::Raw16Khz16BitMonoPcm,
        pcm_frame_size,
        std::move(pcm_callback));
    RTE_ASSERT(azure_tts_ != nullptr, "azure_tts should not be nullptr");

    azure_tts_->Start();

    rte.on_start_done();
    AZURE_TTS_LOGI("start done");
  }

  // on_cmd receives cmd from rte graph. 
  // current supported cmd:
  //  - name: flush
  //    example:
  //      {"name": "flush"}
  void on_cmd(rte::rte_t &rte, std::unique_ptr<rte::cmd_t> cmd) override {

    std::string command = cmd->get_name();
    AZURE_TTS_LOGI("%s", command.c_str());

    if (command == kCmdNameFlush) {
      // flush here
      azure_tts_->Flush();

      // passthrough cmd
      auto ret = rte.send_cmd(rte::cmd_t::create(kCmdNameFlush.c_str()));
      if (ret != RTE_STATUS_CODE_OK) {
        AZURE_TTS_LOGE("Failed to send cmd %s, ret:%d", kCmdNameFlush.c_str(), int(ret));
        rte.return_result(rte::cmd_result_t::create(RTE_STATUS_CODE_ERROR), std::move(cmd));
      } else {
        rte.return_result(rte::cmd_result_t::create(RTE_STATUS_CODE_OK), std::move(cmd));
      }
    } else {
      rte.return_result(rte::cmd_result_t::create(RTE_STATUS_CODE_OK), std::move(cmd));
    }
  }

  // on_data receives data from rte graph. 
  // current supported data:
  //  - name: text_data
  //    example:
  //      {"name": "text_data", "properties": {"text": "hello"}
  void on_data(rte::rte_t &rte, std::unique_ptr<rte::data_t> data) override {

    auto text = data->get_property_string(kDataFieldText.c_str());
    if (text.empty()) {
      AZURE_TTS_LOGD("input text is empty, ignored");
      return;
    }
    AZURE_TTS_LOGI("input text: [%s]", text.c_str());

    // push received text to tts queue for synthesis
    azure_tts_->Push(text);
  }

  // on_stop will be called when the extension is stopping.
  void on_stop(rte::rte_t &rte) override {
    AZURE_TTS_LOGI("stop");
    if (azure_tts_) {
      azure_tts_->Stop();
      azure_tts_ = nullptr;
    }
    rte_proxy_.reset();

    // Extension stop.
    rte.on_stop_done();
    AZURE_TTS_LOGI("stop done");
  }

 private:
  std::unique_ptr<rte::rte_proxy_t> rte_proxy_;

  std::unique_ptr<AzureTTS> azure_tts_;

  const std::string kCmdNameFlush{"flush"};
  const std::string kDataFieldText{"text"};
};

RTE_CXX_REGISTER_ADDON_AS_EXTENSION(azure_tts, azure_tts_extension_t);

}  // namespace azure_tts_extension
