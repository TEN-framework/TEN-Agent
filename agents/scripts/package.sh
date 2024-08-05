#!/usr/bin/env bash

APP_HOME=$(
    cd $(dirname $0)/..
    pwd
)

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

        # package .py for python extensions
        EXTENSION_LANGUAGE=$(jq -r '.language' addon/extension/$extension/manifest.json)
        if [[ $EXTENSION_LANGUAGE == "python" ]]; then
            # TODO: package 'publish' contents only
            cp addon/extension/$extension/*.py .release/addon/extension/$extension/
            if [[ -f addon/extension/$extension/requirements.txt ]]; then
                cp addon/extension/$extension/requirements.txt .release/addon/extension/$extension/
            fi

            # TODO: copy specific contents
            if [[ -d addon/extension/$extension/pb ]]; then
                cp -r addon/extension/$extension/pb .release/addon/extension/$extension/
            fi
        fi
    fi

    if [[ -f addon/extension/$extension/property.json ]]; then
        cp addon/extension/$extension/property.json .release/addon/extension/$extension/
    fi
}

cp -r bin .release
cp -r lib .release
cp manifest.json .release
cp property.json .release

# python deps
if [[ -d interface/rte ]]; then
    mkdir -p .release/interface
    cp -r interface/rte .release/interface
fi

# extension group
mkdir -p .release/addon
cp -r addon/extension_group .release/addon/

# extensions
mkdir -p .release/addon/extension
for extension in addon/extension/*; do
    extension_name=$(basename $extension)
    copy_extension $extension_name
done

if [[ -f session_control.conf ]]; then
    cp -r session_control.conf .release/
fi
