package common

type Code struct {
	Code string
	Msg  string
}

var (
	CodeOk      = NewCode("0", "ok")
	CodeSuccess = NewCode("0", "success")

	CodeErrParamsInvalid       = NewCode("10000", "params invalid")
	CodeErrWorkersLimit        = NewCode("10001", "workers limit")
	CodeErrChannelNotExisted   = NewCode("10002", "channel not existed")
	CodeErrChannelExisted      = NewCode("10003", "channel existed")
	CodeErrChannelEmpty        = NewCode("10004", "channel empty")
	CodeErrGenerateTokenFailed = NewCode("10005", "generate token failed")

	CodeErrProcessManifestFailed = NewCode("10100", "process manifest json failed")
	CodeErrStartWorkerFailed     = NewCode("10101", "start worker failed")
	CodeErrStopAppFailed         = NewCode("10102", "stop worker failed")
)

func NewCode(code string, msg string) *Code {
	return &Code{
		Code: code,
		Msg:  msg,
	}
}
