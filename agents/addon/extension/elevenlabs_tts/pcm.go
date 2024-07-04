/**
 *
 * Agora Real Time Engagement
 * Created by XinHui Li in 2024-07.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
// Note that this is just an example extension written in the GO programming
// language, so the package name does not equal to the containing directory
// name. However, it is not common in Go.
package extension

import (
	"fmt"
	"log/slog"

	"agora.io/rte/rtego"
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
		SampleRate:        16000,
		SamplesPerChannel: 16000 / 100,
		Timestamp:         0,
	}
}

func newPcm(config *pcmConfig) *pcm {
	return &pcm{
		config: config,
	}
}

func (p *pcm) getPcmFrame(buf []byte) (pcmFrame rtego.PcmFrame, err error) {
	pcmFrame, err = rtego.NewPcmFrame(p.config.Name)
	if err != nil {
		slog.Error(fmt.Sprintf("NewPcmFrame failed, err: %v", err), logTag)
		return
	}

	// set pcm frame
	pcmFrame.SetBytesPerSample(p.config.BytesPerSample)
	pcmFrame.SetSampleRate(p.config.SampleRate)
	pcmFrame.SetChannelLayout(p.config.ChannelLayout)
	pcmFrame.SetNumberOfChannels(p.config.Channel)
	pcmFrame.SetTimestamp(p.config.Timestamp)
	pcmFrame.SetDataFmt(rtego.PcmFrameDataFmtInterleave)
	pcmFrame.SetSamplesPerChannel(p.config.SamplesPerChannel)
	pcmFrame.AllocBuf(p.getPcmFrameSize())

	borrowedBuf, err := pcmFrame.BorrowBuf()
	if err != nil {
		slog.Error(fmt.Sprintf("BorrowBuf failed, err: %v", err), logTag)
		return
	}

	// copy data
	copy(borrowedBuf, buf)

	pcmFrame.GiveBackBuf(&borrowedBuf)
	return
}

func (p *pcm) getPcmFrameSize() int {
	return int(p.config.SamplesPerChannel * p.config.Channel * p.config.BytesPerSample)
}

func (p *pcm) newBuf() []byte {
	return make([]byte, p.getPcmFrameSize())
}

func (p *pcm) send(rte rtego.Rte, buf []byte) (err error) {
	pcmFrame, err := p.getPcmFrame(buf)
	if err != nil {
		slog.Error(fmt.Sprintf("getPcmFrame failed, err: %v", err), logTag)
		return
	}

	// send pcm
	if err = rte.SendPcmFrame(pcmFrame); err != nil {
		slog.Error(fmt.Sprintf("SendPcmFrame failed, err: %v", err), logTag)
		return
	}

	return
}
