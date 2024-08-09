package internal

import (
	"crypto/tls"
	"time"

	"github.com/go-resty/resty/v2"
)

var (
	HttpClient = resty.New().
		SetRetryCount(0).
		SetTimeout(5 * time.Second).
		SetTLSClientConfig(&tls.Config{InsecureSkipVerify: true})
)
