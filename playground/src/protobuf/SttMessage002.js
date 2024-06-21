/* eslint-disable block-scoped-var, id-length, no-control-regex, no-magic-numbers, no-prototype-builtins, no-redeclare, no-shadow, no-var, sort-vars */
import * as $protobuf from "protobufjs/light"

const $root = ($protobuf.roots.default || ($protobuf.roots.default = new $protobuf.Root())).addJSON(
  {
    Agora: {
      nested: {
        SpeechToText: {
          options: {
            objc_class_prefix: "Stt",
            csharp_namespace: "AgoraSTTSample.Protobuf",
            java_package: "io.agora.rtc.speech2text",
            java_outer_classname: "AgoraSpeech2TextProtobuffer",
          },
          nested: {
            Text: {
              fields: {
                vendor: {
                  type: "int32",
                  id: 1,
                },
                version: {
                  type: "int32",
                  id: 2,
                },
                seqnum: {
                  type: "int32",
                  id: 3,
                },
                uid: {
                  type: "int64",
                  id: 4,
                },
                flag: {
                  type: "int32",
                  id: 5,
                },
                time: {
                  type: "int64",
                  id: 6,
                },
                lang: {
                  type: "int32",
                  id: 7,
                },
                starttime: {
                  type: "int32",
                  id: 8,
                },
                offtime: {
                  type: "int32",
                  id: 9,
                },
                words: {
                  rule: "repeated",
                  type: "Word",
                  id: 10,
                },
                endOfSegment: {
                  type: "bool",
                  id: 11,
                },
                durationMs: {
                  type: "int32",
                  id: 12,
                },
                dataType: {
                  type: "string",
                  id: 13,
                },
                trans: {
                  rule: "repeated",
                  type: "Translation",
                  id: 14,
                },
                culture: {
                  type: "string",
                  id: 15,
                },
              },
            },
            Word: {
              fields: {
                text: {
                  type: "string",
                  id: 1,
                },
                startMs: {
                  type: "int32",
                  id: 2,
                },
                durationMs: {
                  type: "int32",
                  id: 3,
                },
                isFinal: {
                  type: "bool",
                  id: 4,
                },
                confidence: {
                  type: "double",
                  id: 5,
                },
              },
            },
            Translation: {
              fields: {
                isFinal: {
                  type: "bool",
                  id: 1,
                },
                lang: {
                  type: "string",
                  id: 2,
                },
                texts: {
                  rule: "repeated",
                  type: "string",
                  id: 3,
                },
              },
            },
          },
        },
      },
    },
  },
)

export { $root as default }
