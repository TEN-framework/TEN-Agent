
#include "tts.h"

#include <sys/types.h>

#include <cstring>
#include <memory>
#include <mutex>

namespace azure_tts_extension {

bool AzureTTS::Start() {
  try {
    auto config = Microsoft::CognitiveServices::Speech::SpeechConfig::FromSubscription(key_, region_);
    config->SetSpeechSynthesisVoiceName(voice_name_);
    config->SetSpeechSynthesisOutputFormat(format_);

    speech_synthesizer_ = Microsoft::CognitiveServices::Speech::SpeechSynthesizer::FromConfig(config, nullptr);
    AZURE_TTS_LOGI("speech_synthesizer created");

    // pre-connect and reuse SpeechSynthesizer to avoid first time connection latency 
    connection_ = Microsoft::CognitiveServices::Speech::Connection::FromSpeechSynthesizer(speech_synthesizer_);
    connection_->Open(true);
    AZURE_TTS_LOGI("speech_synthesizer opened");
  } catch (const std::exception& e) {
    AZURE_TTS_LOGE("speech_synthesizer exception catched: %s", e.what());
    return false;
  }

  // start thread to process tts tasks one by one
  thread_ = std::thread([this]() {
    AZURE_TTS_LOGI("tts_thread started");

    while (!stop_.load()) {
      std::unique_ptr<Task> task = nullptr;

      {
        std::unique_lock<std::mutex> lk(tasks_mutex_);
        tasks_cv_.wait(lk, [this]() { return stop_.load() || !tasks_.empty(); });
        if (stop_.load()) {
          break;
        }
        task = std::move(tasks_.front());
        tasks_.pop();
      }

      SpeechText(task->text, task->ts, task->ssml);
    }

    AZURE_TTS_LOGI("tts_thread stopped");
  });

  return true;
}

bool AzureTTS::Stop() {
  stop_.store(true);

  {
    std::lock_guard<std::mutex> lk(tasks_mutex_);
    tasks_cv_.notify_one();
  }

  if (thread_.joinable()) {
    thread_.join();
  }
  return true;
}

void AzureTTS::Push(const std::string& text, bool ssml) noexcept {
  auto ts = time_since_epoch_in_us();

  {
    std::unique_lock<std::mutex> lock(tasks_mutex_);
    tasks_.emplace(std::make_unique<Task>(text, ts, ssml));
    tasks_cv_.notify_one();

    AZURE_TTS_LOGD("task pushed for text: [%s], ssml: %d, text_recv_ts: %" PRId64 ", queue size %d",
                   text.c_str(),
                   ssml,
                   ts,
                   int(tasks_.size()));
  }
}

void AzureTTS::Flush() noexcept {
  outdate_ts_.store(time_since_epoch_in_us());

  {
    std::lock_guard<std::mutex> lock(tasks_mutex_);

    auto q = std::queue<std::unique_ptr<Task>>();
    tasks_.swap(q);
    AZURE_TTS_LOGI("tasks flushed, size %d", int(q.size()));
  }
}

void AzureTTS::SpeechText(const std::string& text, int64_t text_recv_ts, bool ssml) {
  auto start_time = time_since_epoch_in_us();
  AZURE_TTS_LOGD("task starting for text: [%s], ssml: %d text_recv_ts: %" PRId64, text.c_str(), ssml, text_recv_ts);

  if (text_recv_ts < outdate_ts_.load()) {
    AZURE_TTS_LOGI("task discard for text: [%s], text_recv_ts: %" PRId64 ", outdate_ts: %" PRId64,
                   text.c_str(),
                   text_recv_ts,
                   outdate_ts_.load());
    return;
  }

  using namespace Microsoft::CognitiveServices;

  std::shared_ptr<Speech::SpeechSynthesisResult> result;
  // async mode
  if (ssml) {
    result = speech_synthesizer_->StartSpeakingSsmlAsync(text).get();
    if (result->Reason == Speech::ResultReason::Canceled) {
      auto cancellation = Speech::SpeechSynthesisCancellationDetails::FromResult(result);
      AZURE_TTS_LOGW("task canceled for ssml: [%s], text_recv_ts: %" PRId64 ", reason: %d",
                    text.c_str(),
                    text_recv_ts,
                    (int)cancellation->Reason);

      if (cancellation->Reason == Speech::CancellationReason::Error) {
        AZURE_TTS_LOGW("task canceled on error for ssml: [%s], text_recv_ts: %" PRId64
                      ", errorcode: %d, details: %s, did you update the subscription info?",
                      text.c_str(),
                      text_recv_ts,
                      (int)cancellation->ErrorCode,
                      cancellation->ErrorDetails.c_str());
      }
      return;
    }
  } else {
    result = speech_synthesizer_->StartSpeakingTextAsync(text).get();
    if (result->Reason == Speech::ResultReason::Canceled) {
      auto cancellation = Speech::SpeechSynthesisCancellationDetails::FromResult(result);
      AZURE_TTS_LOGW("task canceled for text: [%s], text_recv_ts: %" PRId64 ", reason: %d",
                    text.c_str(),
                    text_recv_ts,
                    (int)cancellation->Reason);

      if (cancellation->Reason == Speech::CancellationReason::Error) {
        AZURE_TTS_LOGW("task canceled on error for text: [%s], text_recv_ts: %" PRId64
                      ", errorcode: %d, details: %s, did you update the subscription info?",
                      text.c_str(),
                      text_recv_ts,
                      (int)cancellation->ErrorCode,
                      cancellation->ErrorDetails.c_str());
      }
      return;
    }
  }

  auto audioDataStream = Speech::AudioDataStream::FromResult(result);

  auto buffer = pcm_frame_buffer_.get();
  memset(buffer, 0, pcm_frame_size_);

  int64_t read_bytes = 0, sent_frames = 0;
  int64_t first_frame_time = 0, first_frame_latency = 0;
  uint32_t filledSize = 0;
  while ((filledSize = audioDataStream->ReadData(buffer, pcm_frame_size_)) > 0) {
    read_bytes += int64_t(filledSize);
    if (text_recv_ts < outdate_ts_.load()) {
      speech_synthesizer_->StopSpeakingAsync();

      AZURE_TTS_LOGI("task discard for text: [%s], text_recv_ts: %" PRId64 ", outdate_ts: %" PRId64
                     ", read_bytes: %" PRId64 ", sent_frames: %" PRId64,
                     text.c_str(),
                     text_recv_ts,
                     outdate_ts_.load(),
                     read_bytes,
                     sent_frames);
      break;
    }

    if (first_frame_time == 0) {
      first_frame_time = time_since_epoch_in_us();
      first_frame_latency = (first_frame_time - start_time) / 1000;
      AZURE_TTS_LOGD("task first frame available for text: [%s], text_recv_ts: %" PRId64 ", first_frame_latency: %" PRId64
                     "ms",
                     text.c_str(),
                     text_recv_ts,
                     first_frame_latency);
    }

    if (filledSize != pcm_frame_size_) {
      AZURE_TTS_LOGD("read data size %d != pcm_frame_size %d", filledSize, pcm_frame_size_);
    }

    if (pcm_frame_callback_ != nullptr) {
      pcm_frame_callback_(buffer, filledSize);
    }
    memset(buffer, 0, pcm_frame_size_);
    sent_frames++;
  }

  auto synthesis_first_byte_latency =
      std::stoi(result->Properties.GetProperty(Speech::PropertyId::SpeechServiceResponse_SynthesisFirstByteLatencyMs));
  auto synthesis_finish_latency =
      std::stoi(result->Properties.GetProperty(Speech::PropertyId::SpeechServiceResponse_SynthesisFinishLatencyMs));

  auto finish_latency = (time_since_epoch_in_us() - start_time) / 1000;

  AZURE_TTS_LOGI("task finished for text: [%s], text_recv_ts: %" PRId64 ", read_bytes: %" PRId64 ", sent_frames: %" PRId64
                 ", first_frame_latency: %" PRId64 "ms, finish_latency: %" PRId64
                 "ms, synthesis_first_byte_latency: %dms, synthesis_finish_latency: %dms",
                 text.c_str(),
                 text_recv_ts,
                 read_bytes,
                 sent_frames,
                 first_frame_latency,
                 finish_latency,
                 synthesis_first_byte_latency,
                 synthesis_finish_latency);
}

int64_t AzureTTS::time_since_epoch_in_us() const {
  return std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::system_clock::now().time_since_epoch())
      .count();
}

}  // namespace azure_tts_extension