#!/usr/bin/env bash

# mac, linux
OS="linux"

# x64, arm64
CPU="x64"

# debug, release
BUILD_TYPE="release"

PIP_INSTALL_CMD=${PIP_INSTALL_CMD:-"uv pip install --system"}

build_cxx_extensions() {
  local app_dir=$1

  if [[ ! -f $app_dir/scripts/BUILD.gn ]]; then
    echo "FATAL: the scripts/BUILD.gn is required to build cxx extensions."
    exit 1
  fi

  cp $app_dir/scripts/BUILD.gn $app_dir

  tgn gen $OS $CPU $BUILD_TYPE -- is_clang=false enable_sanitizer=false
  tgn build $OS $CPU $BUILD_TYPE

  local ret=$?

  cd $app_dir

  if [[ $ret -ne 0 ]]; then
    echo "FATAL: failed to build cxx extensions, see logs for detail."
    exit 1
  fi

  # Copy the output of ten_packages to the ten_packages/extension/xx/lib.
  local out="out/$OS/$CPU"
  for extension in $out/ten_packages/extension/*; do
    local extension_name=$(basename $extension)
    if [[ $extension_name == "*" ]]; then
      echo "No cxx extension, nothing to copy."
      break
    fi
    if [[ ! -d $extension/lib ]]; then
      echo "No output for extension $extension_name."
      continue
    fi

    mkdir -p $app_dir/ten_packages/extension/$extension_name/lib
    cp -r $extension/lib/* $app_dir/ten_packages/extension/$extension_name/lib
  done
}

install_python_requirements() {
  local app_dir=$1

  if [[ -f "requirements.txt" ]]; then
    ${PIP_INSTALL_CMD} install -r requirements.txt
  fi

  # traverse the ten_packages/extension directory to find the requirements.txt
  if [[ -d "ten_packages/extension" ]]; then
    for extension in ten_packages/extension/*; do
      if [[ -f "$extension/requirements.txt" ]]; then
        ${PIP_INSTALL_CMD} -r $extension/requirements.txt
      fi
    done
  fi

  # traverse the ten_packages/system directory to find the requirements.txt
  if [[ -d "ten_packages/system" ]]; then
    for extension in ten_packages/system/*; do
      if [[ -f "$extension/requirements.txt" ]]; then
        ${PIP_INSTALL_CMD} -r $extension/requirements.txt
      fi
    done
  fi

  # pre-import llama-index as it cloud download additional resources during the first import
  echo "pre-import python modules..."
  python3.10 -c "import llama_index.core;"
}

build_go_app() {
  local app_dir=$1
  cd $app_dir

  go run ten_packages/system/ten_runtime_go/tools/build/main.go --verbose
  if [[ $? -ne 0 ]]; then
    echo "FATAL: failed to build go app, see logs for detail."
    exit 1
  fi
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

  echo -e "#include <stdio.h>\n#include <immintrin.h>\nint main() { __m256 a = _mm256_setzero_ps(); return 0; }" > /tmp/test.c
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
  tman install

  # build extensions and app
  echo "build_cxx_extensions..."
  build_cxx_extensions $APP_HOME
  echo "build_go_app..."
  build_go_app $APP_HOME
  echo "install_python_requirements..."
  install_python_requirements $APP_HOME
}

main "$@"
