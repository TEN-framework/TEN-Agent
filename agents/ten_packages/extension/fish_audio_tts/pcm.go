/**
 *
 * Agora Real Time Engagement
 * Created by Hai Guo in 2024-08.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
// An extension written by Go for TTS
package extension

import (
	"fmt"

	"ten_framework/ten"
)

type pcm struct {
	config *pcmConfig
}

type pcmConfig struct {
	BytesPerSample    int32
	Channel           int32
	ChannelLayout     uint64
	Name              string
	SampleRate        int32
	SamplesPerChannel int32
	Timestamp         int64
}

func defaultPcmConfig() *pcmConfig {
	return &pcmConfig{
		BytesPerSample:    2,
		Channel:           1,
		ChannelLayout:     1,
		Name:              "pcm_frame",
		SampleRate:        44100,
		SamplesPerChannel: 44100 / 100,
		Timestamp:         0,
	}
}

func newPcm(config *pcmConfig) *pcm {
	return &pcm{
		config: config,
	}
}

func (p *pcm) getPcmFrame(tenEnv ten.TenEnv, buf []byte) (pcmFrame ten.AudioFrame, err error) {
	pcmFrame, err = ten.NewAudioFrame(p.config.Name)
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("NewPcmFrame failed, err: %v", err))
		return
	}

	// set pcm frame
	pcmFrame.SetBytesPerSample(p.config.BytesPerSample)
	pcmFrame.SetSampleRate(p.config.SampleRate)
	pcmFrame.SetChannelLayout(p.config.ChannelLayout)
	pcmFrame.SetNumberOfChannels(p.config.Channel)
	pcmFrame.SetTimestamp(p.config.Timestamp)
	pcmFrame.SetDataFmt(ten.AudioFrameDataFmtInterleave)
	pcmFrame.SetSamplesPerChannel(p.config.SamplesPerChannel)
	pcmFrame.AllocBuf(p.getPcmFrameSize())

	borrowedBuf, err := pcmFrame.LockBuf()
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("LockBuf failed, err: %v", err))
		return
	}

	// copy data
	copy(borrowedBuf, buf)

	pcmFrame.UnlockBuf(&borrowedBuf)
	return
}

func (p *pcm) getPcmFrameSize() int {
	return int(p.config.SamplesPerChannel * p.config.Channel * p.config.BytesPerSample)
}

func (p *pcm) newBuf() []byte {
	return make([]byte, p.getPcmFrameSize())
}

func (p *pcm) send(tenEnv ten.TenEnv, buf []byte) (err error) {
	pcmFrame, err := p.getPcmFrame(tenEnv, buf)
	if err != nil {
		tenEnv.LogError(fmt.Sprintf("getPcmFrame failed, err: %v", err))
		return
	}

	// send pcm
	if err = tenEnv.SendAudioFrame(pcmFrame, nil); err != nil {
		tenEnv.LogError(fmt.Sprintf("SendPcmFrame failed, err: %v", err))
		return
	}

	return
}
