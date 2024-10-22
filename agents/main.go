/**
 *
 * Agora Real Time Engagement
 * Created by Wei Hu in 2022-10.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
package main

import (
	"flag"
	"log"
	"os"

	"ten_framework/ten"
)

type appConfig struct {
	PropertyFilePath string
}

type defaultApp struct {
	ten.DefaultApp

	cfg *appConfig
}

func (p *defaultApp) OnConfigure(
	tenEnv ten.TenEnv,
) {
	// Using the default property.json if not specified.
	if len(p.cfg.PropertyFilePath) > 0 {
		if b, err := os.ReadFile(p.cfg.PropertyFilePath); err != nil {
			log.Fatalf("Failed to read property file %s, err %v\n", p.cfg.PropertyFilePath, err)
		} else {
			tenEnv.InitPropertyFromJSONBytes(b)
		}
	}

	tenEnv.OnConfigureDone()
}

func startAppBlocking(cfg *appConfig) {
	appInstance, err := ten.NewApp(&defaultApp{
		cfg: cfg,
	})
	if err != nil {
		log.Fatalf("Failed to create the app, %v\n", err)
	}

	appInstance.Run(true)
	appInstance.Wait()

	ten.EnsureCleanupWhenProcessExit()
}

func setDefaultLog() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
}

func main() {
	// Set the default log format globally, users can use `log.Println()` directly.
	setDefaultLog()

	cfg := &appConfig{}

	flag.StringVar(&cfg.PropertyFilePath, "property", "", "The absolute path of property.json")
	flag.Parse()

	startAppBlocking(cfg)
}
