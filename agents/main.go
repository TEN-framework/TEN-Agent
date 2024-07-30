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

	"agora.io/rte/rte"
)

type appConfig struct {
	Manifest string
}

type defaultApp struct {
	rte.DefaultApp

	cfg *appConfig
}

func (p *defaultApp) OnInit(
	rteEnv rte.RteEnv,
	property rte.MetadataInfo,
) {
	// TODO: fix predefined graph
	// Using the default manifest.json if not specified.
	// if len(p.cfg.Manifest) > 0 {
	// 	property.Set(rte.MetadataTypeJSONStr, p.cfg.Manifest)
	// }

	rteEnv.OnInitDone(property)
}

func startAppBlocking(cfg *appConfig) {
	appInstance, err := rte.NewApp(&defaultApp{
		cfg: cfg,
	})
	if err != nil {
		log.Fatalf("Failed to create the app, %v\n", err)
	}

	appInstance.Run(true)
	appInstance.Wait()
	rte.UnloadAllAddons()

	rte.EnsureCleanupWhenProcessExit()
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
