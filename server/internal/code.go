package internal

type Code struct {
	code string
	msg  string
}

var (
	codeOk      = NewCode("0", "ok")
	codeSuccess = NewCode("0", "success")

	codeErrParamsInvalid       = NewCode("10000", "params invalid")
	codeErrWorkersLimit        = NewCode("10001", "workers limit")
	codeErrChannelNotExisted   = NewCode("10002", "channel not existed")
	codeErrChannelExisted      = NewCode("10003", "channel existed")
	codeErrChannelEmpty        = NewCode("10004", "channel empty")
	codeErrGenerateTokenFailed = NewCode("10005", "generate token failed")
	codeErrSaveFileFailed      = NewCode("10006", "save file failed")
	codeErrParseJsonFailed     = NewCode("10007", "parse json failed")

	codeErrProcessPropertyFailed = NewCode("10100", "process property json failed")
	codeErrStartWorkerFailed     = NewCode("10101", "start worker failed")
	codeErrStopWorkerFailed      = NewCode("10102", "stop worker failed")
	codeErrHttpStatusNotOk       = NewCode("10103", "http status not 200")
	codeErrUpdateWorkerFailed    = NewCode("10104", "update worker failed")
	codeErrReadDirectoryFailed   = NewCode("10105", "read directory failed")
	codeErrReadFileFailed        = NewCode("10106", "read file failed")
)

func NewCode(code string, msg string) *Code {
	return &Code{
		code: code,
		msg:  msg,
	}
}
