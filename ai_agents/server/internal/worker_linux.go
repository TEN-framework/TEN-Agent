//go:build linux || darwin
// +build linux darwin

package internal

import (
	"bytes"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// init registers a SIGCHLD handler to reap zombie child processes.
//
// TEN workers are spawned via tman, which forks a [main] subprocess.
// When tman receives SIGKILL during stop(), it has no chance to wait()
// for [main]. [main] becomes an orphan, re-parented to the api process
// (PID 1 in the container). Without this handler, those orphans
// accumulate as zombies.
func init() {
	c := make(chan os.Signal, 1)
	signal.Notify(c, syscall.SIGCHLD)
	go func() {
		for range c {
			for {
				var wstatus syscall.WaitStatus
				pid, err := syscall.Wait4(-1, &wstatus, syscall.WNOHANG, nil)
				if pid <= 0 || err != nil {
					break
				}
			}
		}
	}()
}

// Function to check if a PID is in the correct process group
func isInProcessGroup(pid, pgid int) bool {
	actualPgid, err := syscall.Getpgid(pid)
	if err != nil {
		// If an error occurs, the process might not exist anymore
		return false
	}
	return actualPgid == pgid
}

func (w *Worker) start(req *StartReq) (err error) {
	// Use separate arguments to avoid shell injection
	slog.Info("Worker start", "requestId", req.RequestId, "property", w.PropertyJsonFile, "tenappDir", w.TenappDir, logTag)
	cmd := exec.Command("tman", "run", "start", "--", "--property", w.PropertyJsonFile)
	var shell string // Used for pgrep commands below
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid: true, // Start a new process group
	}

	// Set working directory if tenapp_dir is specified
	if w.TenappDir != "" {
		cmd.Dir = w.TenappDir
		slog.Info("Worker start with tenapp_dir", "requestId", req.RequestId, "tenappDir", w.TenappDir, logTag)
	}

	var stdoutWriter, stderrWriter = os.Stdout, os.Stderr
	var logFile *os.File

	if !w.Log2Stdout {
		// Open the log file for writing
		var openErr error
		logFile, openErr = os.OpenFile(w.LogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if openErr != nil {
			slog.Error("Failed to open log file", "err", openErr, "requestId", req.RequestId, logTag)
		} else {
			stdoutWriter = logFile
			stderrWriter = logFile
		}
	}

	// Create PrefixWriter instances with appropriate writers
	stdoutPrefixWriter := &PrefixWriter{
		prefix: "-", // Initial prefix, will update after process starts
		writer: stdoutWriter,
	}
	stderrPrefixWriter := &PrefixWriter{
		prefix: "-", // Initial prefix, will update after process starts
		writer: stderrWriter,
	}

	cmd.Stdout = stdoutPrefixWriter
	cmd.Stderr = stderrPrefixWriter

	if err = cmd.Start(); err != nil {
		slog.Error("Worker start failed", "err", err, "requestId", req.RequestId, logTag)
		return
	}

	pid := cmd.Process.Pid

	// Ensure the process has fully started
	shell = fmt.Sprintf("pgrep -P %d", pid)
	slog.Info("Worker get pid", "requestId", req.RequestId, "shell", shell, logTag)

	var subprocessPid int
	for i := 0; i < 10; i++ { // retry for 10 times
		output, err := exec.Command("sh", "-c", shell).CombinedOutput()
		if err == nil {
			subprocessPid, err = strconv.Atoi(strings.TrimSpace(string(output)))
			if err == nil && subprocessPid > 0 && isInProcessGroup(subprocessPid, cmd.Process.Pid) {
				break // if pid is successfully obtained, exit loop
			}
		}
		slog.Warn("Worker get pid failed, retrying...", "attempt", i+1, "pid", pid, "subpid", subprocessPid, "requestId", req.RequestId, logTag)
		time.Sleep(1000 * time.Millisecond) // wait for 1000ms
	}

	// Update the prefix with the actual PID
	stdoutPrefixWriter.prefix = w.ChannelName
	stderrPrefixWriter.prefix = w.ChannelName
	w.Pid = pid

	// Monitor the background process in a separate goroutine
	go func() {
		err := cmd.Wait() // Wait for the command to exit
		if err != nil {
			slog.Error("Worker process failed", "err", err, "requestId", req.RequestId, logTag)
		} else {
			slog.Info("Worker process completed successfully", "requestId", req.RequestId, logTag)
		}
		// Close the log file when the command finishes
		if logFile != nil {
			logFile.Close()
		}

		// Remove the worker from the map (defensive check for concurrent stop)
		if workers.Contains(w.ChannelName) {
			workers.Remove(w.ChannelName)
		}

	}()

	return
}

func (w *Worker) stop(requestId string, channelName string) (err error) {
	slog.Info("Worker stop start", "channelName", channelName, "requestId", requestId, "pid", w.Pid, logTag)

	// First try graceful shutdown with SIGTERM
	err = syscall.Kill(-w.Pid, syscall.SIGTERM)
	if err != nil {
		slog.Error("Worker SIGTERM failed, trying SIGKILL", "err", err, "channelName", channelName, "worker", w, "requestId", requestId, logTag)
		// Fall back to SIGKILL
		err = syscall.Kill(-w.Pid, syscall.SIGKILL)
		if err != nil {
			slog.Error("Worker SIGKILL failed", "err", err, "channelName", channelName, "worker", w, "requestId", requestId, logTag)
			return
		}
		if workers.Contains(channelName) {
			workers.Remove(channelName)
		}
		slog.Info("Worker stop end (forced)", "channelName", channelName, "worker", w, "requestId", requestId, logTag)
		return
	}

	// Wait up to 2 seconds for graceful shutdown
	for i := 0; i < 20; i++ {
		// Check if process is still running
		err = syscall.Kill(-w.Pid, 0)
		if err != nil {
			// Process no longer exists - graceful shutdown succeeded
			if workers.Contains(channelName) {
				workers.Remove(channelName)
			}
			slog.Info("Worker stop end (graceful)", "channelName", channelName, "worker", w, "requestId", requestId, logTag)
			return nil
		}
		time.Sleep(100 * time.Millisecond)
	}

	// Graceful shutdown timed out, force kill
	slog.Warn("Worker graceful shutdown timed out, using SIGKILL", "channelName", channelName, "requestId", requestId, logTag)
	err = syscall.Kill(-w.Pid, syscall.SIGKILL)
	if err != nil {
		slog.Error("Worker SIGKILL failed after timeout", "err", err, "channelName", channelName, "worker", w, "requestId", requestId, logTag)
		return
	}

	if workers.Contains(channelName) {
		workers.Remove(channelName)
	}
	slog.Info("Worker stop end (forced after timeout)", "channelName", channelName, "worker", w, "requestId", requestId, logTag)
	return
}

// Function to get the PIDs of running workers
func getRunningWorkerPIDs() map[int]struct{} {
	// Define the command to find processes
	cmd := exec.Command("sh", "-c", `ps aux | grep "bin/worker --property" | grep -v grep`)

	// Run the command and capture the output
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return nil
	}

	// Parse the PIDs from the output
	lines := strings.Split(out.String(), "\n")
	runningPIDs := make(map[int]struct{})
	for _, line := range lines {
		fields := strings.Fields(line)
		if len(fields) > 1 {
			pid, err := strconv.Atoi(fields[1]) // PID is typically the second field
			if err == nil {
				runningPIDs[pid] = struct{}{}
			}
		}
	}
	return runningPIDs
}

// Function to kill a process by PID
func killProcess(pid int) {
	err := syscall.Kill(pid, syscall.SIGKILL)
	if err != nil {
		slog.Info("Failed to kill process", "pid", pid, "error", err)
	} else {
		slog.Info("Successfully killed process", "pid", pid)
	}
}
