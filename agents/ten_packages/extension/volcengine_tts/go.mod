module volcengine_tts

go 1.20

replace ten_framework => ../../system/ten_runtime_go/interface

require ten_framework v0.0.0-00010101000000-000000000000

require gopkg.in/check.v1 v1.0.0-20201130134442-10cb98267c6c // indirect

require (
	github.com/google/uuid v1.6.0
	github.com/gorilla/websocket v1.5.3
	github.com/satori/go.uuid v1.2.0
)
