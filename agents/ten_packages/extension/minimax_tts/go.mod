module minimax_tts

go 1.20

replace ten_framework => ../../system/ten_runtime_go/interface

require (
	github.com/go-resty/resty/v2 v2.16.0
	ten_framework v0.0.0-00010101000000-000000000000
)

require golang.org/x/net v0.27.0 // indirect
