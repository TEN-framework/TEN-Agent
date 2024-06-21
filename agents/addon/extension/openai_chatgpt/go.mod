module openai_chatgpt

go 1.21

replace agora.io/rte => ../../../interface

require (
	agora.io/rte v0.0.0-00010101000000-000000000000
	github.com/sashabaranov/go-openai v1.24.1
	github.com/stretchr/testify v1.9.0
)

require (
	github.com/davecgh/go-spew v1.1.1 // indirect
	github.com/pmezard/go-difflib v1.0.0 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)
