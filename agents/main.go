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

	"agora.io/rte/rtego"
)

type appConfig struct {
	Manifest string
}

type defaultApp struct {
	rtego.DefaultApp

	cfg *appConfig
}

func (p *defaultApp) OnInit(
	rte rtego.Rte,
	manifest rtego.MetadataInfo,
	property rtego.MetadataInfo,
) {
	// Using the default manifest.json if not specified.
	if len(p.cfg.Manifest) > 0 {
		manifest.Set(rtego.MetadataTypeJSONFileName, p.cfg.Manifest)
	}

	rte.OnInitDone(manifest, property)
}

func startAppBlocking(cfg *appConfig) {
	appInstance, err := rtego.NewApp(&defaultApp{
		cfg: cfg,
	})
	if err != nil {
		log.Fatalf("Failed to create the app, %v\n", err)
	}

	appInstance.Run(true)
	appInstance.Wait()
	rtego.UnloadAllAddons()

	rtego.EnsureCleanupWhenProcessExit()
}

func setDefaultLog() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
}

func main() {
	// Set the default log format globally, users can use `log.Println()` directly.
	setDefaultLog()

	cfg := &appConfig{}

	flag.StringVar(&cfg.Manifest, "manifest", "", "The absolute path of manifest.json")
	flag.Parse()

	startAppBlocking(cfg)
}
