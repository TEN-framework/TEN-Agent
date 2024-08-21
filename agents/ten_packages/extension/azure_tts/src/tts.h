
#include <speechapi_cxx.h>

#include <atomic>
#include <cassert>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <queue>
#include <string>
#include <thread>

#include "log.h"

namespace azure_tts_extension {

using PCMFrameCallback = std::function<void(const uint8_t *data, size_t size)>;

class AzureTTS {
 public:
  explicit AzureTTS(const std::string &key,
                    const std::string &region,
                    const std::string &voice_name,
                    const Microsoft::CognitiveServices::Speech::SpeechSynthesisOutputFormat format,
                    const uint32_t pcm_frame_size,
                    PCMFrameCallback &&callback)
      : key_(key),
        region_(region),
        voice_name_(voice_name),
        format_(format),
        pcm_frame_callback_(std::move(callback)),
        pcm_frame_size_(pcm_frame_size),
        pcm_frame_buffer_(std::make_unique<uint8_t[]>(pcm_frame_size_)) {
    assert(pcm_frame_size_ > 0);
    assert(pcm_frame_buffer_);
  }

  bool Start();
  bool Stop();

  void Flush() noexcept;

  void Push(const std::string &text) noexcept;

 private:
  void SpeechText(const std::string &text, int64_t text_recv_ts);

  int64_t time_since_epoch_in_us() const;

 private:
  const std::string key_;
  const std::string region_;
  const std::string voice_name_;
  const Microsoft::CognitiveServices::Speech::SpeechSynthesisOutputFormat format_;

  std::shared_ptr<Microsoft::CognitiveServices::Speech::SpeechSynthesizer> speech_synthesizer_;
  std::shared_ptr<Microsoft::CognitiveServices::Speech::Connection> connection_;

  std::atomic_int64_t outdate_ts_{0};  // for flushing

  struct Task {
    Task(const std::string &t, int64_t ts) : ts(ts), text(t) {}

    int64_t ts{0};
    std::string text;
  };

  std::queue<std::unique_ptr<Task>> tasks_;
  std::mutex tasks_mutex_;
  std::condition_variable tasks_cv_;

  std::thread thread_;
  std::atomic_bool stop_{false};

  PCMFrameCallback pcm_frame_callback_{nullptr};
  const uint32_t pcm_frame_size_{0};
  std::unique_ptr<uint8_t[]> pcm_frame_buffer_;
};

}  // namespace azure_tts_extension