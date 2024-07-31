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

    mkdir -p $app_dir/addon/extension/$extension_name/lib
    cp -r $extension/lib/* $app_dir/addon/extension/$extension_name/lib
  done
}

install_python_requirements() {
  local app_dir=$1

  if [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt
  fi

  # traverse the addon/extension directory to find the requirements.txt
  if [[ -d "addon/extension" ]]; then
    for extension in addon/extension/*; do
      if [[ -f "$extension/requirements.txt" ]]; then
        pip install -r $extension/requirements.txt
      fi
    done
  fi
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

  echo -e "#include <stdio.h>\n#include <immintrin.h>\nint main() { __m256d a = _mm256_set_pd(1.0, 2.0, 3.0, 4.0); return 0; }" > /tmp/test.c
  if gcc -mavx2 /tmp/test.c -o /tmp/test && ! /tmp/test; then
    echo "FATAL: unsupported platform."
    echo "       Please UNCHECK the 'Use Rosetta for x86_64/amd64 emulation on Apple Silicon' Docker Desktop setting if you're running on mac."

    exit 1
  fi

  if [[ ! -f $APP_HOME/manifest.json ]]; then
    echo "FATAL: manifest.json is required."
    exit 1
  fi

  # Install all dependencies specified in manifest.json.
  echo "install dependencies..."
  arpm install

  # build addons and app
  echo "build_cxx_addon..."
  build_cxx_addon $APP_HOME
  echo "build_go_app..."
  build_go_app $APP_HOME
  echo "install_python_requirements..."
  install_python_requirements $APP_HOME
}

main "$@"
