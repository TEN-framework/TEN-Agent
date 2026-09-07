# iFLYTEK ASR Production Readiness

This checklist applies to `iflytek_asr_python` version `0.2.0`. It complements
the automated tests; deployment-specific networking, credentials, privacy,
capacity, and monitoring remain operator responsibilities.

## Source Baseline

- [TEN ASR Extension development guide](https://theten.ai/cn/docs/ten_agent_examples/extension_dev/create_asr_extension)
- iFLYTEK realtime transcription interface v3-4.0.0.2003, converted in the
  workspace from `实时转写接口文档v3-4.0.0.2004.pdf`
- [websockets 14.2 asyncio client API](https://websockets.readthedocs.io/en/14.2/reference/asyncio/client.html)
- [Pydantic 2.13 configuration API](https://docs.pydantic.dev/2.13/api/config/)

## Automated Gates

- [x] Offline tests cover Basic behavior and Advanced error, reconnect,
  finalize, dump, metrics, connection-status, concurrency, and protocol cases.
- [x] Runnable TEN ASR Guarder default tests pass against a real iFLYTEK
  service; upstream capability-gated skips are reported separately.
- [x] The Guarder long-duration test runs separately and passes beyond five
  minutes without a maximum-duration error.
- [x] Black formatting, Python compilation, TMan metadata validation, static
  analysis, dependency audit, and package-content checks are release gates.
- [x] Before opening or updating a PR, validate its title with
  `echo "${PR_TITLE}" | npx --yes commitlint --default-config`.
- [x] Every runnable Guarder case runs across the default and dedicated
  long-duration invocations; skips and deselections are reported and never
  counted as passes.

## Deployment Gate

- [ ] Inject `IFLYTEK_ASR_URL`, `IFLYTEK_APP_ID`, and
  `IFLYTEK_BIZ_ID` from a managed secret or configuration service.
- [ ] Use `wss://` outside trusted development networks and validate the
  service certificate and DNS route from the workload environment.
- [ ] Confirm the input is mono 16-bit PCM and its sample rate matches
  `sample_rate`; keep each audio frame at or below 16 KiB.
- [ ] Size `buffer_max_bytes` from a documented memory and recovery-latency
  budget. The 10 MiB default represents about 327 seconds at 16 kHz.
- [ ] Keep `dump=false` unless access control, retention, disk quota, and secure
  deletion are defined for raw user audio.
- [ ] Run the complete Guarder suite with production-equivalent networking and
  credentials before promotion.

## Monitoring

Alert on the following TEN outputs and logs:

- FATAL `error` messages: invalid configuration or exhausted reconnect
  attempts.
- Sustained NON_FATAL error growth, repeated initial connection failures,
  repeated `disconnected -> connecting` transitions, or reconnect attempts
  reaching the configured limit.
- Missing `connect_delay`, TTFW, TTLW, or actual-send metrics after traffic
  starts.
- P95 connect/finalize latency regression against the deployment baseline.
- Buffer pressure, process memory, and disk growth when PCM Dump is enabled.

Recommended rollout: staging, internal canary, limited traffic, then full
traffic. Hold promotion when error rate or P95 latency rises materially from
the established baseline.

## Rollback

Rollback triggers include a new FATAL error pattern, repeated reconnect
exhaustion, missing final results, incorrect session metadata, data exposure,
or a material latency regression.

1. Stop routing audio to the new extension or restore the previous graph.
2. Pin and redeploy the last verified extension package version.
3. Verify the previous connection-status and ASR-result flow.
4. Preserve sanitized TEN logs and metrics for diagnosis. Handle PCM dumps
   according to the configured privacy and retention policy.
