package service

import (
	"app/internal/common"
	"fmt"
	"log/slog"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

type Worker struct {
	ChannelName        string
	LogFile            string
	ManifestJsonFile   string
	Pid                int
	QuitTimeoutSeconds int
	CreateTs           int64
	UpdateTs           int64
}

const (
	workerCleanSleepSeconds = 5
	workerExec              = "/app/agents/bin/worker"
)

func newWorker(channelName string, logFile string, manifestJsonFile string) *Worker {
	return &Worker{
		ChannelName:        channelName,
		LogFile:            logFile,
		ManifestJsonFile:   manifestJsonFile,
		QuitTimeoutSeconds: 60,
		CreateTs:           time.Now().Unix(),
		UpdateTs:           time.Now().Unix(),
	}
}

func (w *Worker) start(req *common.StartReq) (err error) {
	shell := fmt.Sprintf("cd /app/agents && nohup %s --manifest %s > %s 2>&1 &", workerExec, w.ManifestJsonFile, w.LogFile)
	slog.Info("Worker start", "requestId", req.RequestId, "shell", shell, logTag)
	if _, err = exec.Command("sh", "-c", shell).CombinedOutput(); err != nil {
		slog.Error("Worker start failed", "err", err, "requestId", req.RequestId, logTag)
		return
	}

	shell = fmt.Sprintf("ps aux | grep %s | grep -v grep | awk '{print $2}'", w.ManifestJsonFile)
	slog.Info("Worker get pid", "requestId", req.RequestId, "shell", shell, logTag)
	output, err := exec.Command("sh", "-c", shell).CombinedOutput()
	if err != nil {
		slog.Error("Worker get pid failed", "err", err, "requestId", req.RequestId, logTag)
		return
	}

	pid, err := strconv.Atoi(strings.TrimSpace(string(output)))
	if err != nil || pid <= 0 {
		slog.Error("Worker convert pid failed", "err", err, "pid", pid, "requestId", req.RequestId, logTag)
		return
	}

	w.Pid = pid
	return
}

func (w *Worker) stop(requestId string, channelName string) (err error) {
	slog.Info("Worker stop start", "channelName", channelName, "requestId", requestId, logTag)

	shell := fmt.Sprintf("kill -9 %d", w.Pid)
	output, err := exec.Command("sh", "-c", shell).CombinedOutput()
	if err != nil {
		slog.Error("Worker kill failed", "err", err, "output", output, "channelName", channelName, "worker", w, "requestId", requestId, logTag)
		return
	}

	slog.Info("Worker stop end", "channelName", channelName, "worker", w, "requestId", requestId, logTag)
	return
}
