#!/usr/bin/env bash

APP_HOME=$(cd $(dirname $0)/..; pwd)

cd $APP_HOME

rm -rf .release
mkdir .release

copy_extension() {
  local extension=$1
  mkdir -p .release/addon/extension/$extension

  if [[ -d addon/extension/$extension/lib ]]; then
    cp -r addon/extension/$extension/lib .release/addon/extension/$extension/
  fi

  if [[ -f addon/extension/$extension/manifest.json ]]; then
    cp addon/extension/$extension/manifest.json .release/addon/extension/$extension/
  fi

  if [[ -f addon/extension/$extension/property.json ]]; then
    cp addon/extension/$extension/property.json .release/addon/extension/$extension/
  fi
}

cp -r bin .release
cp -r lib .release
cp manifest.json .release
cp manifest.elevenlabs.json .release
cp property.json .release

mkdir .release/addon
cp -r addon/extension_group .release/addon/
cp -r session_control.conf .release/

mkdir -p .release/addon/extension

for extension in addon/extension/*
do
  extension_name=$(basename $extension)
  copy_extension $extension_name
done
