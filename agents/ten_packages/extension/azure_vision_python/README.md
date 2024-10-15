# azure_vision_python

This is the extension calling azure ai vision.

The document is as follow: https://learn.microsoft.com/zh-cn/azure/ai-services/computer-vision/overview

## Properties

- key 
- endpoint

## Features

- Only support one frame of image
- No customization for feature
- By default will include `TAGS`, `CAPTION`, `READ`, `PEOPLE`, `OBJECTS`

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

Other extensions can call `analyze_image` cmd and will get all analyze result from result in `response` property, the result will looks like this:

``` json
{
    "modelVersion": "2023-10-01",
    "captionResult": {
        "text": "a group of toys on a table",
        "confidence": 0.7558467388153076
    },
    "metadata": {
        "width": 320,
        "height": 240
    },
    "objectsResult": {},
    "readResult": {},
    "peopleResult": {}
}
```

## Misc

- Video analyze
- Multi-frame analyze