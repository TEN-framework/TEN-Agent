#!/usr/bin/env bash

# mac, linux
OS="linux"

# x64, arm64
CPU="x64"

build_cxx_addon() {
  local app_dir=$1

  if [[ ! -f $app_dir/scripts/BUILD.gn ]]; then
    echo "FATAL: the scripts/BUILD.gn is required to build cxx addons."
    exit 1
  fi

  cp $app_dir/scripts/BUILD.gn $app_dir

  ag gen $OS $CPU release -- is_clang=false
  ag build $OS $CPU release

  local ret=$?

  cd $app_dir

  if [[ $ret -ne 0 ]]; then
    echo "FATAL: failed to build cxx addons, see logs for detail."
    exit 1
  fi

  # Copy the output of addons to the addon/extension/xx/lib.

  local out="out/$OS/$CPU"
  for extension in $out/addon/extension/*; do
    local extension_name=$(basename $extension)
    if [[ ! -d $extension/lib ]]; then
      echo "No output for extension $extension_name."
      exit 1
    fi

    cp -r $extension/lib/* $app_dir/addon/extension/$extension_name/lib
  done
}

build_go_app() {
  local app_dir=$1
  cd $app_dir

  go run scripts/build/main.go --verbose
}

clean() {
  local app_dir=$1
  rm -rf BUILD.gn out
}

main() {
  APP_HOME=$(
    cd $(dirname $0)/..
    pwd
  )

  if [[ $1 == "-clean" ]]; then
    clean $APP_HOME
    exit 0
  fi

  if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <os> <cpu>"
    exit 1
  fi

  OS=$1
  CPU=$2

  if [[ ! -f $APP_HOME/manifest.json ]]; then
    echo "FATAL: manifest.json is required."
    exit 1
  fi

  # Install all dependencies specified in manifest.json.
  echo "install dependencies..."
  arpm install

  # Install azure speechsdk
  export SPEECHSDK_ROOT=speechsdk
  mkdir -p "$SPEECHSDK_ROOT"
  wget -O SpeechSDK-Linux.tar.gz https://aka.ms/csspeech/linuxbinary
  tar --strip 1 -xzf SpeechSDK-Linux.tar.gz -C "$SPEECHSDK_ROOT"
  cp -r "$SPEECHSDK_ROOT"/include/* addon/extension/azure_tts/include/microsoft/
  cp "$SPEECHSDK_ROOT"/lib/x64/lib* addon/extension/azure_tts/lib/

  # build addons and app
  build_cxx_addon $APP_HOME
  build_go_app $APP_HOME
}

main "$@"
