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
#include "ten_runtime/binding/cpp/ten.h"
#include "ten_utils/macro/check.h"
#include "tts.h"

namespace azure_tts_extension {

class azure_tts_extension_t : public ten::extension_t {
 public:
  explicit azure_tts_extension_t(const std::string &name) : extension_t(name) {}

  // on_start will be called when the extension is starting,
  // properies can be read here to initialize and start the extension.
  // current supported properties:
  //   - azure_subscription_key
  //   - azure_subscription_region
  //   - azure_synthesis_voice_name
  void on_start(ten::ten_env_t &ten) override {
    AZURE_TTS_LOGI("start");

    // read properties
    auto key = ten.get_property_string("azure_subscription_key");
    auto region = ten.get_property_string("azure_subscription_region");
    auto voice_name = ten.get_property_string("azure_synthesis_voice_name");
    if (key.empty() || region.empty() || voice_name.empty()) {
      AZURE_TTS_LOGE(
          "azure_subscription_key, azure_subscription_region, azure_synthesis_voice_name should not be empty, start "
          "failed");
      return;
    }

    ten_proxy_ = std::unique_ptr<ten::ten_env_proxy_t>(ten::ten_env_proxy_t::create(ten));
    TEN_ASSERT(ten_proxy_ != nullptr, "ten_proxy should not be nullptr");

    // pcm parameters
    auto sample_rate = 16000;
    auto samples_per_10ms = sample_rate / 100;
    auto channel = 1;
    auto bytes_per_sample = 2;
    auto pcm_frame_size = samples_per_10ms * channel * bytes_per_sample;  // per 10ms

    // initialize the callback to send pcm to RTC extension
    auto pcm_callback =
        [ten_proxy = ten_proxy_.get(), sample_rate, bytes_per_sample, samples_per_10ms, channel, pcm_frame_size](
            const uint8_t *data,
            size_t size) {
          auto pcm_frame = ten::audio_frame_t::create("pcm_frame");
          pcm_frame->set_bytes_per_sample(bytes_per_sample);
          pcm_frame->set_sample_rate(sample_rate);
          pcm_frame->set_channel_layout(1);
          pcm_frame->set_number_of_channels(channel);
          pcm_frame->set_timestamp(0);
          pcm_frame->set_data_fmt(TEN_AUDIO_FRAME_DATA_FMT_INTERLEAVE);
          pcm_frame->set_samples_per_channel(samples_per_10ms);
          pcm_frame->alloc_buf(pcm_frame_size);
          ten::buf_t borrowed_buf = pcm_frame->lock_buf(0);
          auto *buf = borrowed_buf.data();
          if (buf != nullptr) {
            memset(buf, 0, pcm_frame_size);  // fill empty if size is not enough for 10ms
            memcpy(buf, data, size);
          }
          pcm_frame->unlock_buf(borrowed_buf);

          auto pcm_frame_shared = std::make_shared<std::unique_ptr<ten::audio_frame_t>>(std::move(pcm_frame));
          ten_proxy->notify(
              [frame = std::move(pcm_frame_shared)](ten::ten_env_t &ten) { ten.send_audio_frame(std::move(*frame)); });
        };

    // initialize Azure TTS
    azure_tts_ = std::make_unique<AzureTTS>(
        key,
        region,
        voice_name,
        Microsoft::CognitiveServices::Speech::SpeechSynthesisOutputFormat::Raw16Khz16BitMonoPcm,
        pcm_frame_size,
        std::move(pcm_callback));
    TEN_ASSERT(azure_tts_ != nullptr, "azure_tts should not be nullptr");

    azure_tts_->Start();

    ten.on_start_done();
    AZURE_TTS_LOGI("start done");
  }

  // on_cmd receives cmd from ten graph.
  // current supported cmd:
  //  - name: flush
  //    example:
  //      {"name": "flush"}
  void on_cmd(ten::ten_env_t &ten, std::unique_ptr<ten::cmd_t> cmd) override {
    std::string command = cmd->get_name();
    AZURE_TTS_LOGI("%s", command.c_str());

    if (command == kCmdNameFlush) {
      // flush here
      azure_tts_->Flush();

      // passthrough cmd
      auto ret = ten.send_cmd(ten::cmd_t::create(kCmdNameFlush.c_str()));
      if (!ret) {
        AZURE_TTS_LOGE("Failed to send cmd %s", kCmdNameFlush.c_str());
        ten.return_result(ten::cmd_result_t::create(TEN_STATUS_CODE_ERROR), std::move(cmd));
      } else {
        ten.return_result(ten::cmd_result_t::create(TEN_STATUS_CODE_OK), std::move(cmd));
      }
    } else {
      ten.return_result(ten::cmd_result_t::create(TEN_STATUS_CODE_OK), std::move(cmd));
    }
  }

  // on_data receives data from ten graph.
  // current supported data:
  //  - name: text_data
  //    example:
  //      {"name": "text_data", "properties": {"text": "hello"}
  void on_data(ten::ten_env_t &ten, std::unique_ptr<ten::data_t> data) override {
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
  void on_stop(ten::ten_env_t &ten) override {
    AZURE_TTS_LOGI("stop");
    if (azure_tts_) {
      azure_tts_->Stop();
      azure_tts_ = nullptr;
    }
    ten_proxy_.reset();

    // Extension stop.
    ten.on_stop_done();
    AZURE_TTS_LOGI("stop done");
  }

 private:
  std::unique_ptr<ten::ten_env_proxy_t> ten_proxy_;

  std::unique_ptr<AzureTTS> azure_tts_;

  const std::string kCmdNameFlush{"flush"};
  const std::string kDataFieldText{"text"};
};

TEN_CPP_REGISTER_ADDON_AS_EXTENSION(azure_tts, azure_tts_extension_t);

}  // namespace azure_tts_extension
