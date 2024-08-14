package internal

import (
	"fmt"
	"log/slog"
	"net/http"
	"os/exec"
	"strconv"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/go-resty/resty/v2"
	"github.com/gogf/gf/container/gmap"
	"github.com/google/uuid"
)

type Worker struct {
	ChannelName        string
	HttpServerPort     int32
	LogFile            string
	PropertyJsonFile   string
	Pid                int
	QuitTimeoutSeconds int
	CreateTs           int64
	UpdateTs           int64
}

type WorkerUpdateReq struct {
	RequestId   string              `form:"request_id,omitempty" json:"request_id,omitempty"`
	ChannelName string              `form:"channel_name,omitempty" json:"channel_name,omitempty"`
	Collection  string              `form:"collection,omitempty" json:"collection"`
	FileName    string              `form:"filename,omitempty" json:"filename"`
	Path        string              `form:"path,omitempty" json:"path,omitempty"`
	Rte         *WorkerUpdateReqRte `form:"rte,omitempty" json:"rte,omitempty"`
}

type WorkerUpdateReqRte struct {
	Name string `form:"name,omitempty" json:"name,omitempty"`
	Type string `form:"type,omitempty" json:"type,omitempty"`
}

const (
	workerCleanSleepSeconds = 5
	workerExec              = "/app/agents/bin/worker"
	workerHttpServerUrl     = "http://127.0.0.1"
)

var (
	workers           = gmap.New(true)
	httpServerPort    = httpServerPortMin
	httpServerPortMin = int32(10000)
	httpServerPortMax = int32(30000)
)

func newWorker(channelName string, logFile string, propertyJsonFile string) *Worker {
	return &Worker{
		ChannelName:        channelName,
		LogFile:            logFile,
		PropertyJsonFile:   propertyJsonFile,
		QuitTimeoutSeconds: 60,
		CreateTs:           time.Now().Unix(),
		UpdateTs:           time.Now().Unix(),
	}
}

func getHttpServerPort() int32 {
	if atomic.LoadInt32(&httpServerPort) > httpServerPortMax {
		atomic.StoreInt32(&httpServerPort, httpServerPortMin)
	}

	atomic.AddInt32(&httpServerPort, 1)
	return httpServerPort
}

func (w *Worker) start(req *StartReq) (err error) {
	shell := fmt.Sprintf("cd /app/agents && nohup %s --property %s > %s 2>&1 &", workerExec, w.PropertyJsonFile, w.LogFile)
	slog.Info("Worker start", "requestId", req.RequestId, "shell", shell, logTag)
	if _, err = exec.Command("sh", "-c", shell).CombinedOutput(); err != nil {
		slog.Error("Worker start failed", "err", err, "requestId", req.RequestId, logTag)
		return
	}

	shell = fmt.Sprintf("ps aux | grep %s | grep -v grep | awk '{print $2}'", w.PropertyJsonFile)
	slog.Info("Worker get pid", "requestId", req.RequestId, "shell", shell, logTag)

	var pid int
    for i := 0; i < 3; i++ {  // retry for 3 times
        output, err := exec.Command("sh", "-c", shell).CombinedOutput()
        if err == nil {
            pid, err = strconv.Atoi(strings.TrimSpace(string(output)))
            if err == nil && pid > 0 {
                break  // if pid is successfully obtained, exit loop
            }
        }
        slog.Warn("Worker get pid failed, retrying...", "attempt", i+1, "requestId", req.RequestId, logTag)
        time.Sleep(500 * time.Millisecond)  // wait for 500ms
    }

    if pid <= 0 {
        slog.Error("Worker failed to obtain valid PID after 3 attempts", "requestId", req.RequestId, logTag)
        return fmt.Errorf("failed to obtain valid PID")
    }

	w.Pid = pid
	return
}

func (w *Worker) stop(requestId string, channelName string) (err error) {
	slog.Info("Worker stop start", "channelName", channelName, "requestId", requestId, logTag)

	err = syscall.Kill(w.Pid, syscall.SIGTERM)
	if err != nil {
		slog.Error("Worker kill failed", "err", err, "channelName", channelName, "worker", w, "requestId", requestId, logTag)
		return
	}

	workers.Remove(channelName)

	slog.Info("Worker stop end", "channelName", channelName, "worker", w, "requestId", requestId, logTag)
	return
}

func (w *Worker) update(req *WorkerUpdateReq) (err error) {
	slog.Info("Worker update start", "channelName", req.ChannelName, "requestId", req.RequestId, logTag)

	var res *resty.Response

	defer func() {
		if err != nil {
			slog.Error("Worker update error", "err", err, "channelName", req.ChannelName, "requestId", req.RequestId, logTag)
		}
	}()

	workerUpdateUrl := fmt.Sprintf("%s:%d/cmd", workerHttpServerUrl, w.HttpServerPort)
	res, err = HttpClient.R().
		SetHeader("Content-Type", "application/json").
		SetBody(req).
		Post(workerUpdateUrl)
	if err != nil {
		return
	}

	if res.StatusCode() != http.StatusOK {
		return fmt.Errorf("%s, status: %d", codeErrHttpStatusNotOk.msg, res.StatusCode())
	}

	slog.Info("Worker update end", "channelName", req.ChannelName, "worker", w, "requestId", req.RequestId, logTag)
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
