package internal

import (
	"fmt"
	"log/slog"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/gogf/gf/container/gmap"
	"github.com/google/uuid"
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

var (
	workers = gmap.New(true)
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

func (w *Worker) start(req *StartReq) (err error) {
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

	workers.Remove(channelName)

	slog.Info("Worker stop end", "channelName", channelName, "worker", w, "requestId", requestId, logTag)
	return
}

func cleanWorker() {
	for {
		for _, channelName := range workers.Keys() {
			worker := workers.Get(channelName).(*Worker)

			nowTs := time.Now().Unix()
			if worker.UpdateTs+int64(worker.QuitTimeoutSeconds) < nowTs {
				if err := worker.stop(uuid.New().String(), channelName.(string)); err != nil {
					slog.Error("Worker cleanWorker failed", "err", err, "channelName", channelName, logTag)
					continue
				}

				slog.Info("Worker cleanWorker success", "channelName", channelName, "worker", worker, "nowTs", nowTs, logTag)
			}
		}

		slog.Debug("Worker cleanWorker sleep", "sleep", workerCleanSleepSeconds, logTag)
		time.Sleep(workerCleanSleepSeconds * time.Second)
	}
}
