"use client";

import { IMicrophoneAudioTrack } from "agora-rtc-sdk-ng";
import { normalizeFrequencies } from "./utils";
import { useState, useEffect } from "react";
// import { Grid } from "antd"

export const useMultibandTrackVolume = (
  track?: IMicrophoneAudioTrack | MediaStreamTrack,
  bands: number = 5,
  loPass: number = 100,
  hiPass: number = 600
) => {
  const [frequencyBands, setFrequencyBands] = useState<Float32Array[]>([]);
  const [isActive, setIsActive] = useState(false);

  useEffect(() => {
    if (!track) {
      return setFrequencyBands(new Array(bands).fill(new Float32Array(0)));
    }

    const ctx = new AudioContext();
    let finTrack =
      track instanceof MediaStreamTrack ? track : track.getMediaStreamTrack();
    const mediaStream = new MediaStream([finTrack]);
    const source = ctx.createMediaStreamSource(mediaStream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;

    source.connect(analyser);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Float32Array(bufferLength);

    const updateVolume = () => {
      analyser.getFloatFrequencyData(dataArray);
      let frequencies: Float32Array = new Float32Array(dataArray.length);
      for (let i = 0; i < dataArray.length; i++) {
        frequencies[i] = dataArray[i];
      }
      frequencies = frequencies.slice(loPass, hiPass);

      const normalizedFrequencies = normalizeFrequencies(frequencies);
      const chunkSize = Math.ceil(normalizedFrequencies.length / bands);
      const chunks: Float32Array[] = [];
      for (let i = 0; i < bands; i++) {
        chunks.push(
          normalizedFrequencies.slice(i * chunkSize, (i + 1) * chunkSize)
        );
      }

      // 计算音频活跃度
      const averageVolume = chunks.reduce((sum, chunk) => {
        return sum + chunk.reduce((a, b) => a + b, 0) / chunk.length;
      }, 0) / chunks.length;

      setIsActive(averageVolume > 0.1); // 设置阈值
      setFrequencyBands(chunks);
    };

    const interval = setInterval(updateVolume, 10);

    return () => {
      source.disconnect();
      clearInterval(interval);
    };
  }, [track, loPass, hiPass, bands]);

  return { frequencyBands, isActive };
};
