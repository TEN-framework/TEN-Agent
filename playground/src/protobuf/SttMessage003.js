/* eslint-disable block-scoped-var, id-length, no-control-regex, no-magic-numbers, no-prototype-builtins, no-redeclare, no-shadow, no-var, sort-vars */
import * as $protobuf from "protobufjs/minimal"

// Common aliases
const $Reader = $protobuf.Reader
const $Writer = $protobuf.Writer
const $util = $protobuf.util

// Exported root namespace
const $root = $protobuf.roots.default || ($protobuf.roots.default = {})

export const Agora = ($root.Agora = (() => {
  /**
   * Namespace Agora.
   * @exports Agora
   * @namespace
   */
  const Agora = {}

  Agora.SpeechToText = (function () {
    /**
     * Namespace SpeechToText.
     * @memberof Agora
     * @namespace
     */
    const SpeechToText = {}

    SpeechToText.Text = (function () {
      /**
       * Properties of a Text.
       * @memberof Agora.SpeechToText
       * @interface IText
       * @property {number|null} [vendor] Text vendor
       * @property {number|null} [version] Text version
       * @property {number|null} [seqnum] Text seqnum
       * @property {number|Long|null} [uid] Text uid
       * @property {number|null} [flag] Text flag
       * @property {number|Long|null} [time] Text time
       * @property {number|null} [lang] Text lang
       * @property {number|null} [starttime] Text starttime
       * @property {number|null} [offtime] Text offtime
       * @property {Array.<Agora.SpeechToText.IWord>|null} [words] Text words
       * @property {boolean|null} [endOfSegment] Text endOfSegment
       * @property {number|null} [durationMs] Text durationMs
       * @property {string|null} [dataType] Text dataType
       * @property {Array.<Agora.SpeechToText.ITranslation>|null} [trans] Text trans
       * @property {string|null} [culture] Text culture
       */

      /**
       * Constructs a new Text.
       * @memberof Agora.SpeechToText
       * @classdesc Represents a Text.
       * @implements IText
       * @constructor
       * @param {Agora.SpeechToText.IText=} [properties] Properties to set
       */
      function Text(properties) {
        this.words = []
        this.trans = []
        if (properties)
          for (let keys = Object.keys(properties), i = 0; i < keys.length; ++i)
            if (properties[keys[i]] != null) this[keys[i]] = properties[keys[i]]
      }

      /**
       * Text vendor.
       * @member {number} vendor
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.vendor = 0

      /**
       * Text version.
       * @member {number} version
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.version = 0

      /**
       * Text seqnum.
       * @member {number} seqnum
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.seqnum = 0

      /**
       * Text uid.
       * @member {number|Long} uid
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.uid = $util.Long ? $util.Long.fromBits(0, 0, false) : 0

      /**
       * Text flag.
       * @member {number} flag
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.flag = 0

      /**
       * Text time.
       * @member {number|Long} time
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.time = $util.Long ? $util.Long.fromBits(0, 0, false) : 0

      /**
       * Text lang.
       * @member {number} lang
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.lang = 0

      /**
       * Text starttime.
       * @member {number} starttime
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.starttime = 0

      /**
       * Text offtime.
       * @member {number} offtime
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.offtime = 0

      /**
       * Text words.
       * @member {Array.<Agora.SpeechToText.IWord>} words
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.words = $util.emptyArray

      /**
       * Text endOfSegment.
       * @member {boolean} endOfSegment
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.endOfSegment = false

      /**
       * Text durationMs.
       * @member {number} durationMs
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.durationMs = 0

      /**
       * Text dataType.
       * @member {string} dataType
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.dataType = ""

      /**
       * Text trans.
       * @member {Array.<Agora.SpeechToText.ITranslation>} trans
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.trans = $util.emptyArray

      /**
       * Text culture.
       * @member {string} culture
       * @memberof Agora.SpeechToText.Text
       * @instance
       */
      Text.prototype.culture = ""

      /**
       * Creates a new Text instance using the specified properties.
       * @function create
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {Agora.SpeechToText.IText=} [properties] Properties to set
       * @returns {Agora.SpeechToText.Text} Text instance
       */
      Text.create = function create(properties) {
        return new Text(properties)
      }

      /**
       * Encodes the specified Text message. Does not implicitly {@link Agora.SpeechToText.Text.verify|verify} messages.
       * @function encode
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {Agora.SpeechToText.IText} message Text message or plain object to encode
       * @param {$protobuf.Writer} [writer] Writer to encode to
       * @returns {$protobuf.Writer} Writer
       */
      Text.encode = function encode(message, writer) {
        if (!writer) writer = $Writer.create()
        if (message.vendor != null && Object.hasOwnProperty.call(message, "vendor"))
          writer.uint32(/* id 1, wireType 0 = */ 8).int32(message.vendor)
        if (message.version != null && Object.hasOwnProperty.call(message, "version"))
          writer.uint32(/* id 2, wireType 0 = */ 16).int32(message.version)
        if (message.seqnum != null && Object.hasOwnProperty.call(message, "seqnum"))
          writer.uint32(/* id 3, wireType 0 = */ 24).int32(message.seqnum)
        if (message.uid != null && Object.hasOwnProperty.call(message, "uid"))
          writer.uint32(/* id 4, wireType 0 = */ 32).int64(message.uid)
        if (message.flag != null && Object.hasOwnProperty.call(message, "flag"))
          writer.uint32(/* id 5, wireType 0 = */ 40).int32(message.flag)
        if (message.time != null && Object.hasOwnProperty.call(message, "time"))
          writer.uint32(/* id 6, wireType 0 = */ 48).int64(message.time)
        if (message.lang != null && Object.hasOwnProperty.call(message, "lang"))
          writer.uint32(/* id 7, wireType 0 = */ 56).int32(message.lang)
        if (message.starttime != null && Object.hasOwnProperty.call(message, "starttime"))
          writer.uint32(/* id 8, wireType 0 = */ 64).int32(message.starttime)
        if (message.offtime != null && Object.hasOwnProperty.call(message, "offtime"))
          writer.uint32(/* id 9, wireType 0 = */ 72).int32(message.offtime)
        if (message.words != null && message.words.length)
          for (let i = 0; i < message.words.length; ++i)
            $root.Agora.SpeechToText.Word.encode(
              message.words[i],
              writer.uint32(/* id 10, wireType 2 = */ 82).fork(),
            ).ldelim()
        if (message.endOfSegment != null && Object.hasOwnProperty.call(message, "endOfSegment"))
          writer.uint32(/* id 11, wireType 0 = */ 88).bool(message.endOfSegment)
        if (message.durationMs != null && Object.hasOwnProperty.call(message, "durationMs"))
          writer.uint32(/* id 12, wireType 0 = */ 96).int32(message.durationMs)
        if (message.dataType != null && Object.hasOwnProperty.call(message, "dataType"))
          writer.uint32(/* id 13, wireType 2 = */ 106).string(message.dataType)
        if (message.trans != null && message.trans.length)
          for (let i = 0; i < message.trans.length; ++i)
            $root.Agora.SpeechToText.Translation.encode(
              message.trans[i],
              writer.uint32(/* id 14, wireType 2 = */ 114).fork(),
            ).ldelim()
        if (message.culture != null && Object.hasOwnProperty.call(message, "culture"))
          writer.uint32(/* id 15, wireType 2 = */ 122).string(message.culture)
        return writer
      }

      /**
       * Encodes the specified Text message, length delimited. Does not implicitly {@link Agora.SpeechToText.Text.verify|verify} messages.
       * @function encodeDelimited
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {Agora.SpeechToText.IText} message Text message or plain object to encode
       * @param {$protobuf.Writer} [writer] Writer to encode to
       * @returns {$protobuf.Writer} Writer
       */
      Text.encodeDelimited = function encodeDelimited(message, writer) {
        return this.encode(message, writer).ldelim()
      }

      /**
       * Decodes a Text message from the specified reader or buffer.
       * @function decode
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
       * @param {number} [length] Message length if known beforehand
       * @returns {Agora.SpeechToText.Text} Text
       * @throws {Error} If the payload is not a reader or valid buffer
       * @throws {$protobuf.util.ProtocolError} If required fields are missing
       */
      Text.decode = function decode(reader, length) {
        if (!(reader instanceof $Reader)) reader = $Reader.create(reader)
        const end = length === undefined ? reader.len : reader.pos + length
        const message = new $root.Agora.SpeechToText.Text()
        while (reader.pos < end) {
          const tag = reader.uint32()
          switch (tag >>> 3) {
            case 1: {
              message.vendor = reader.int32()
              break
            }
            case 2: {
              message.version = reader.int32()
              break
            }
            case 3: {
              message.seqnum = reader.int32()
              break
            }
            case 4: {
              message.uid = reader.int64()
              break
            }
            case 5: {
              message.flag = reader.int32()
              break
            }
            case 6: {
              message.time = reader.int64()
              break
            }
            case 7: {
              message.lang = reader.int32()
              break
            }
            case 8: {
              message.starttime = reader.int32()
              break
            }
            case 9: {
              message.offtime = reader.int32()
              break
            }
            case 10: {
              if (!(message.words && message.words.length)) message.words = []
              message.words.push($root.Agora.SpeechToText.Word.decode(reader, reader.uint32()))
              break
            }
            case 11: {
              message.endOfSegment = reader.bool()
              break
            }
            case 12: {
              message.durationMs = reader.int32()
              break
            }
            case 13: {
              message.dataType = reader.string()
              break
            }
            case 14: {
              if (!(message.trans && message.trans.length)) message.trans = []
              message.trans.push(
                $root.Agora.SpeechToText.Translation.decode(reader, reader.uint32()),
              )
              break
            }
            case 15: {
              message.culture = reader.string()
              break
            }
            default:
              reader.skipType(tag & 7)
              break
          }
        }
        return message
      }

      /**
       * Decodes a Text message from the specified reader or buffer, length delimited.
       * @function decodeDelimited
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
       * @returns {Agora.SpeechToText.Text} Text
       * @throws {Error} If the payload is not a reader or valid buffer
       * @throws {$protobuf.util.ProtocolError} If required fields are missing
       */
      Text.decodeDelimited = function decodeDelimited(reader) {
        if (!(reader instanceof $Reader)) reader = new $Reader(reader)
        return this.decode(reader, reader.uint32())
      }

      /**
       * Verifies a Text message.
       * @function verify
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {Object.<string,*>} message Plain object to verify
       * @returns {string|null} `null` if valid, otherwise the reason why it is not
       */
      Text.verify = function verify(message) {
        if (typeof message !== "object" || message === null) return "object expected"
        if (message.vendor != null && message.hasOwnProperty("vendor"))
          if (!$util.isInteger(message.vendor)) return "vendor: integer expected"
        if (message.version != null && message.hasOwnProperty("version"))
          if (!$util.isInteger(message.version)) return "version: integer expected"
        if (message.seqnum != null && message.hasOwnProperty("seqnum"))
          if (!$util.isInteger(message.seqnum)) return "seqnum: integer expected"
        if (message.uid != null && message.hasOwnProperty("uid"))
          if (
            !$util.isInteger(message.uid) &&
            !(message.uid && $util.isInteger(message.uid.low) && $util.isInteger(message.uid.high))
          )
            return "uid: integer|Long expected"
        if (message.flag != null && message.hasOwnProperty("flag"))
          if (!$util.isInteger(message.flag)) return "flag: integer expected"
        if (message.time != null && message.hasOwnProperty("time"))
          if (
            !$util.isInteger(message.time) &&
            !(
              message.time &&
              $util.isInteger(message.time.low) &&
              $util.isInteger(message.time.high)
            )
          )
            return "time: integer|Long expected"
        if (message.lang != null && message.hasOwnProperty("lang"))
          if (!$util.isInteger(message.lang)) return "lang: integer expected"
        if (message.starttime != null && message.hasOwnProperty("starttime"))
          if (!$util.isInteger(message.starttime)) return "starttime: integer expected"
        if (message.offtime != null && message.hasOwnProperty("offtime"))
          if (!$util.isInteger(message.offtime)) return "offtime: integer expected"
        if (message.words != null && message.hasOwnProperty("words")) {
          if (!Array.isArray(message.words)) return "words: array expected"
          for (let i = 0; i < message.words.length; ++i) {
            const error = $root.Agora.SpeechToText.Word.verify(message.words[i])
            if (error) return "words." + error
          }
        }
        if (message.endOfSegment != null && message.hasOwnProperty("endOfSegment"))
          if (typeof message.endOfSegment !== "boolean") return "endOfSegment: boolean expected"
        if (message.durationMs != null && message.hasOwnProperty("durationMs"))
          if (!$util.isInteger(message.durationMs)) return "durationMs: integer expected"
        if (message.dataType != null && message.hasOwnProperty("dataType"))
          if (!$util.isString(message.dataType)) return "dataType: string expected"
        if (message.trans != null && message.hasOwnProperty("trans")) {
          if (!Array.isArray(message.trans)) return "trans: array expected"
          for (let i = 0; i < message.trans.length; ++i) {
            const error = $root.Agora.SpeechToText.Translation.verify(message.trans[i])
            if (error) return "trans." + error
          }
        }
        if (message.culture != null && message.hasOwnProperty("culture"))
          if (!$util.isString(message.culture)) return "culture: string expected"
        return null
      }

      /**
       * Creates a Text message from a plain object. Also converts values to their respective internal types.
       * @function fromObject
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {Object.<string,*>} object Plain object
       * @returns {Agora.SpeechToText.Text} Text
       */
      Text.fromObject = function fromObject(object) {
        if (object instanceof $root.Agora.SpeechToText.Text) return object
        const message = new $root.Agora.SpeechToText.Text()
        if (object.vendor != null) message.vendor = object.vendor | 0
        if (object.version != null) message.version = object.version | 0
        if (object.seqnum != null) message.seqnum = object.seqnum | 0
        if (object.uid != null)
          if ($util.Long) (message.uid = $util.Long.fromValue(object.uid)).unsigned = false
          else if (typeof object.uid === "string") message.uid = parseInt(object.uid, 10)
          else if (typeof object.uid === "number") message.uid = object.uid
          else if (typeof object.uid === "object")
            message.uid = new $util.LongBits(object.uid.low >>> 0, object.uid.high >>> 0).toNumber()
        if (object.flag != null) message.flag = object.flag | 0
        if (object.time != null)
          if ($util.Long) (message.time = $util.Long.fromValue(object.time)).unsigned = false
          else if (typeof object.time === "string") message.time = parseInt(object.time, 10)
          else if (typeof object.time === "number") message.time = object.time
          else if (typeof object.time === "object")
            message.time = new $util.LongBits(
              object.time.low >>> 0,
              object.time.high >>> 0,
            ).toNumber()
        if (object.lang != null) message.lang = object.lang | 0
        if (object.starttime != null) message.starttime = object.starttime | 0
        if (object.offtime != null) message.offtime = object.offtime | 0
        if (object.words) {
          if (!Array.isArray(object.words))
            throw TypeError(".Agora.SpeechToText.Text.words: array expected")
          message.words = []
          for (let i = 0; i < object.words.length; ++i) {
            if (typeof object.words[i] !== "object")
              throw TypeError(".Agora.SpeechToText.Text.words: object expected")
            message.words[i] = $root.Agora.SpeechToText.Word.fromObject(object.words[i])
          }
        }
        if (object.endOfSegment != null) message.endOfSegment = Boolean(object.endOfSegment)
        if (object.durationMs != null) message.durationMs = object.durationMs | 0
        if (object.dataType != null) message.dataType = String(object.dataType)
        if (object.trans) {
          if (!Array.isArray(object.trans))
            throw TypeError(".Agora.SpeechToText.Text.trans: array expected")
          message.trans = []
          for (let i = 0; i < object.trans.length; ++i) {
            if (typeof object.trans[i] !== "object")
              throw TypeError(".Agora.SpeechToText.Text.trans: object expected")
            message.trans[i] = $root.Agora.SpeechToText.Translation.fromObject(object.trans[i])
          }
        }
        if (object.culture != null) message.culture = String(object.culture)
        return message
      }

      /**
       * Creates a plain object from a Text message. Also converts values to other types if specified.
       * @function toObject
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {Agora.SpeechToText.Text} message Text
       * @param {$protobuf.IConversionOptions} [options] Conversion options
       * @returns {Object.<string,*>} Plain object
       */
      Text.toObject = function toObject(message, options) {
        if (!options) options = {}
        const object = {}
        if (options.arrays || options.defaults) {
          object.words = []
          object.trans = []
        }
        if (options.defaults) {
          object.vendor = 0
          object.version = 0
          object.seqnum = 0
          if ($util.Long) {
            const long = new $util.Long(0, 0, false)
            object.uid =
              options.longs === String
                ? long.toString()
                : options.longs === Number
                  ? long.toNumber()
                  : long
          } else object.uid = options.longs === String ? "0" : 0
          object.flag = 0
          if ($util.Long) {
            const long = new $util.Long(0, 0, false)
            object.time =
              options.longs === String
                ? long.toString()
                : options.longs === Number
                  ? long.toNumber()
                  : long
          } else object.time = options.longs === String ? "0" : 0
          object.lang = 0
          object.starttime = 0
          object.offtime = 0
          object.endOfSegment = false
          object.durationMs = 0
          object.dataType = ""
          object.culture = ""
        }
        if (message.vendor != null && message.hasOwnProperty("vendor"))
          object.vendor = message.vendor
        if (message.version != null && message.hasOwnProperty("version"))
          object.version = message.version
        if (message.seqnum != null && message.hasOwnProperty("seqnum"))
          object.seqnum = message.seqnum
        if (message.uid != null && message.hasOwnProperty("uid"))
          if (typeof message.uid === "number")
            object.uid = options.longs === String ? String(message.uid) : message.uid
          else
            object.uid =
              options.longs === String
                ? $util.Long.prototype.toString.call(message.uid)
                : options.longs === Number
                  ? new $util.LongBits(message.uid.low >>> 0, message.uid.high >>> 0).toNumber()
                  : message.uid
        if (message.flag != null && message.hasOwnProperty("flag")) object.flag = message.flag
        if (message.time != null && message.hasOwnProperty("time"))
          if (typeof message.time === "number")
            object.time = options.longs === String ? String(message.time) : message.time
          else
            object.time =
              options.longs === String
                ? $util.Long.prototype.toString.call(message.time)
                : options.longs === Number
                  ? new $util.LongBits(message.time.low >>> 0, message.time.high >>> 0).toNumber()
                  : message.time
        if (message.lang != null && message.hasOwnProperty("lang")) object.lang = message.lang
        if (message.starttime != null && message.hasOwnProperty("starttime"))
          object.starttime = message.starttime
        if (message.offtime != null && message.hasOwnProperty("offtime"))
          object.offtime = message.offtime
        if (message.words && message.words.length) {
          object.words = []
          for (let j = 0; j < message.words.length; ++j)
            object.words[j] = $root.Agora.SpeechToText.Word.toObject(message.words[j], options)
        }
        if (message.endOfSegment != null && message.hasOwnProperty("endOfSegment"))
          object.endOfSegment = message.endOfSegment
        if (message.durationMs != null && message.hasOwnProperty("durationMs"))
          object.durationMs = message.durationMs
        if (message.dataType != null && message.hasOwnProperty("dataType"))
          object.dataType = message.dataType
        if (message.trans && message.trans.length) {
          object.trans = []
          for (let j = 0; j < message.trans.length; ++j)
            object.trans[j] = $root.Agora.SpeechToText.Translation.toObject(
              message.trans[j],
              options,
            )
        }
        if (message.culture != null && message.hasOwnProperty("culture"))
          object.culture = message.culture
        return object
      }

      /**
       * Converts this Text to JSON.
       * @function toJSON
       * @memberof Agora.SpeechToText.Text
       * @instance
       * @returns {Object.<string,*>} JSON object
       */
      Text.prototype.toJSON = function toJSON() {
        return this.constructor.toObject(this, $protobuf.util.toJSONOptions)
      }

      /**
       * Gets the default type url for Text
       * @function getTypeUrl
       * @memberof Agora.SpeechToText.Text
       * @static
       * @param {string} [typeUrlPrefix] your custom typeUrlPrefix(default "type.googleapis.com")
       * @returns {string} The default type url
       */
      Text.getTypeUrl = function getTypeUrl(typeUrlPrefix) {
        if (typeUrlPrefix === undefined) {
          typeUrlPrefix = "type.googleapis.com"
        }
        return typeUrlPrefix + "/Agora.SpeechToText.Text"
      }

      return Text
    })()

    SpeechToText.Word = (function () {
      /**
       * Properties of a Word.
       * @memberof Agora.SpeechToText
       * @interface IWord
       * @property {string|null} [text] Word text
       * @property {number|null} [startMs] Word startMs
       * @property {number|null} [durationMs] Word durationMs
       * @property {boolean|null} [isFinal] Word isFinal
       * @property {number|null} [confidence] Word confidence
       */

      /**
       * Constructs a new Word.
       * @memberof Agora.SpeechToText
       * @classdesc Represents a Word.
       * @implements IWord
       * @constructor
       * @param {Agora.SpeechToText.IWord=} [properties] Properties to set
       */
      function Word(properties) {
        if (properties)
          for (let keys = Object.keys(properties), i = 0; i < keys.length; ++i)
            if (properties[keys[i]] != null) this[keys[i]] = properties[keys[i]]
      }

      /**
       * Word text.
       * @member {string} text
       * @memberof Agora.SpeechToText.Word
       * @instance
       */
      Word.prototype.text = ""

      /**
       * Word startMs.
       * @member {number} startMs
       * @memberof Agora.SpeechToText.Word
       * @instance
       */
      Word.prototype.startMs = 0

      /**
       * Word durationMs.
       * @member {number} durationMs
       * @memberof Agora.SpeechToText.Word
       * @instance
       */
      Word.prototype.durationMs = 0

      /**
       * Word isFinal.
       * @member {boolean} isFinal
       * @memberof Agora.SpeechToText.Word
       * @instance
       */
      Word.prototype.isFinal = false

      /**
       * Word confidence.
       * @member {number} confidence
       * @memberof Agora.SpeechToText.Word
       * @instance
       */
      Word.prototype.confidence = 0

      /**
       * Creates a new Word instance using the specified properties.
       * @function create
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {Agora.SpeechToText.IWord=} [properties] Properties to set
       * @returns {Agora.SpeechToText.Word} Word instance
       */
      Word.create = function create(properties) {
        return new Word(properties)
      }

      /**
       * Encodes the specified Word message. Does not implicitly {@link Agora.SpeechToText.Word.verify|verify} messages.
       * @function encode
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {Agora.SpeechToText.IWord} message Word message or plain object to encode
       * @param {$protobuf.Writer} [writer] Writer to encode to
       * @returns {$protobuf.Writer} Writer
       */
      Word.encode = function encode(message, writer) {
        if (!writer) writer = $Writer.create()
        if (message.text != null && Object.hasOwnProperty.call(message, "text"))
          writer.uint32(/* id 1, wireType 2 = */ 10).string(message.text)
        if (message.startMs != null && Object.hasOwnProperty.call(message, "startMs"))
          writer.uint32(/* id 2, wireType 0 = */ 16).int32(message.startMs)
        if (message.durationMs != null && Object.hasOwnProperty.call(message, "durationMs"))
          writer.uint32(/* id 3, wireType 0 = */ 24).int32(message.durationMs)
        if (message.isFinal != null && Object.hasOwnProperty.call(message, "isFinal"))
          writer.uint32(/* id 4, wireType 0 = */ 32).bool(message.isFinal)
        if (message.confidence != null && Object.hasOwnProperty.call(message, "confidence"))
          writer.uint32(/* id 5, wireType 1 = */ 41).double(message.confidence)
        return writer
      }

      /**
       * Encodes the specified Word message, length delimited. Does not implicitly {@link Agora.SpeechToText.Word.verify|verify} messages.
       * @function encodeDelimited
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {Agora.SpeechToText.IWord} message Word message or plain object to encode
       * @param {$protobuf.Writer} [writer] Writer to encode to
       * @returns {$protobuf.Writer} Writer
       */
      Word.encodeDelimited = function encodeDelimited(message, writer) {
        return this.encode(message, writer).ldelim()
      }

      /**
       * Decodes a Word message from the specified reader or buffer.
       * @function decode
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
       * @param {number} [length] Message length if known beforehand
       * @returns {Agora.SpeechToText.Word} Word
       * @throws {Error} If the payload is not a reader or valid buffer
       * @throws {$protobuf.util.ProtocolError} If required fields are missing
       */
      Word.decode = function decode(reader, length) {
        if (!(reader instanceof $Reader)) reader = $Reader.create(reader)
        const end = length === undefined ? reader.len : reader.pos + length
        const message = new $root.Agora.SpeechToText.Word()
        while (reader.pos < end) {
          const tag = reader.uint32()
          switch (tag >>> 3) {
            case 1: {
              message.text = reader.string()
              break
            }
            case 2: {
              message.startMs = reader.int32()
              break
            }
            case 3: {
              message.durationMs = reader.int32()
              break
            }
            case 4: {
              message.isFinal = reader.bool()
              break
            }
            case 5: {
              message.confidence = reader.double()
              break
            }
            default:
              reader.skipType(tag & 7)
              break
          }
        }
        return message
      }

      /**
       * Decodes a Word message from the specified reader or buffer, length delimited.
       * @function decodeDelimited
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
       * @returns {Agora.SpeechToText.Word} Word
       * @throws {Error} If the payload is not a reader or valid buffer
       * @throws {$protobuf.util.ProtocolError} If required fields are missing
       */
      Word.decodeDelimited = function decodeDelimited(reader) {
        if (!(reader instanceof $Reader)) reader = new $Reader(reader)
        return this.decode(reader, reader.uint32())
      }

      /**
       * Verifies a Word message.
       * @function verify
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {Object.<string,*>} message Plain object to verify
       * @returns {string|null} `null` if valid, otherwise the reason why it is not
       */
      Word.verify = function verify(message) {
        if (typeof message !== "object" || message === null) return "object expected"
        if (message.text != null && message.hasOwnProperty("text"))
          if (!$util.isString(message.text)) return "text: string expected"
        if (message.startMs != null && message.hasOwnProperty("startMs"))
          if (!$util.isInteger(message.startMs)) return "startMs: integer expected"
        if (message.durationMs != null && message.hasOwnProperty("durationMs"))
          if (!$util.isInteger(message.durationMs)) return "durationMs: integer expected"
        if (message.isFinal != null && message.hasOwnProperty("isFinal"))
          if (typeof message.isFinal !== "boolean") return "isFinal: boolean expected"
        if (message.confidence != null && message.hasOwnProperty("confidence"))
          if (typeof message.confidence !== "number") return "confidence: number expected"
        return null
      }

      /**
       * Creates a Word message from a plain object. Also converts values to their respective internal types.
       * @function fromObject
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {Object.<string,*>} object Plain object
       * @returns {Agora.SpeechToText.Word} Word
       */
      Word.fromObject = function fromObject(object) {
        if (object instanceof $root.Agora.SpeechToText.Word) return object
        const message = new $root.Agora.SpeechToText.Word()
        if (object.text != null) message.text = String(object.text)
        if (object.startMs != null) message.startMs = object.startMs | 0
        if (object.durationMs != null) message.durationMs = object.durationMs | 0
        if (object.isFinal != null) message.isFinal = Boolean(object.isFinal)
        if (object.confidence != null) message.confidence = Number(object.confidence)
        return message
      }

      /**
       * Creates a plain object from a Word message. Also converts values to other types if specified.
       * @function toObject
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {Agora.SpeechToText.Word} message Word
       * @param {$protobuf.IConversionOptions} [options] Conversion options
       * @returns {Object.<string,*>} Plain object
       */
      Word.toObject = function toObject(message, options) {
        if (!options) options = {}
        const object = {}
        if (options.defaults) {
          object.text = ""
          object.startMs = 0
          object.durationMs = 0
          object.isFinal = false
          object.confidence = 0
        }
        if (message.text != null && message.hasOwnProperty("text")) object.text = message.text
        if (message.startMs != null && message.hasOwnProperty("startMs"))
          object.startMs = message.startMs
        if (message.durationMs != null && message.hasOwnProperty("durationMs"))
          object.durationMs = message.durationMs
        if (message.isFinal != null && message.hasOwnProperty("isFinal"))
          object.isFinal = message.isFinal
        if (message.confidence != null && message.hasOwnProperty("confidence"))
          object.confidence =
            options.json && !isFinite(message.confidence)
              ? String(message.confidence)
              : message.confidence
        return object
      }

      /**
       * Converts this Word to JSON.
       * @function toJSON
       * @memberof Agora.SpeechToText.Word
       * @instance
       * @returns {Object.<string,*>} JSON object
       */
      Word.prototype.toJSON = function toJSON() {
        return this.constructor.toObject(this, $protobuf.util.toJSONOptions)
      }

      /**
       * Gets the default type url for Word
       * @function getTypeUrl
       * @memberof Agora.SpeechToText.Word
       * @static
       * @param {string} [typeUrlPrefix] your custom typeUrlPrefix(default "type.googleapis.com")
       * @returns {string} The default type url
       */
      Word.getTypeUrl = function getTypeUrl(typeUrlPrefix) {
        if (typeUrlPrefix === undefined) {
          typeUrlPrefix = "type.googleapis.com"
        }
        return typeUrlPrefix + "/Agora.SpeechToText.Word"
      }

      return Word
    })()

    SpeechToText.Translation = (function () {
      /**
       * Properties of a Translation.
       * @memberof Agora.SpeechToText
       * @interface ITranslation
       * @property {boolean|null} [isFinal] Translation isFinal
       * @property {string|null} [lang] Translation lang
       * @property {Array.<string>|null} [texts] Translation texts
       */

      /**
       * Constructs a new Translation.
       * @memberof Agora.SpeechToText
       * @classdesc Represents a Translation.
       * @implements ITranslation
       * @constructor
       * @param {Agora.SpeechToText.ITranslation=} [properties] Properties to set
       */
      function Translation(properties) {
        this.texts = []
        if (properties)
          for (let keys = Object.keys(properties), i = 0; i < keys.length; ++i)
            if (properties[keys[i]] != null) this[keys[i]] = properties[keys[i]]
      }

      /**
       * Translation isFinal.
       * @member {boolean} isFinal
       * @memberof Agora.SpeechToText.Translation
       * @instance
       */
      Translation.prototype.isFinal = false

      /**
       * Translation lang.
       * @member {string} lang
       * @memberof Agora.SpeechToText.Translation
       * @instance
       */
      Translation.prototype.lang = ""

      /**
       * Translation texts.
       * @member {Array.<string>} texts
       * @memberof Agora.SpeechToText.Translation
       * @instance
       */
      Translation.prototype.texts = $util.emptyArray

      /**
       * Creates a new Translation instance using the specified properties.
       * @function create
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {Agora.SpeechToText.ITranslation=} [properties] Properties to set
       * @returns {Agora.SpeechToText.Translation} Translation instance
       */
      Translation.create = function create(properties) {
        return new Translation(properties)
      }

      /**
       * Encodes the specified Translation message. Does not implicitly {@link Agora.SpeechToText.Translation.verify|verify} messages.
       * @function encode
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {Agora.SpeechToText.ITranslation} message Translation message or plain object to encode
       * @param {$protobuf.Writer} [writer] Writer to encode to
       * @returns {$protobuf.Writer} Writer
       */
      Translation.encode = function encode(message, writer) {
        if (!writer) writer = $Writer.create()
        if (message.isFinal != null && Object.hasOwnProperty.call(message, "isFinal"))
          writer.uint32(/* id 1, wireType 0 = */ 8).bool(message.isFinal)
        if (message.lang != null && Object.hasOwnProperty.call(message, "lang"))
          writer.uint32(/* id 2, wireType 2 = */ 18).string(message.lang)
        if (message.texts != null && message.texts.length)
          for (let i = 0; i < message.texts.length; ++i)
            writer.uint32(/* id 3, wireType 2 = */ 26).string(message.texts[i])
        return writer
      }

      /**
       * Encodes the specified Translation message, length delimited. Does not implicitly {@link Agora.SpeechToText.Translation.verify|verify} messages.
       * @function encodeDelimited
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {Agora.SpeechToText.ITranslation} message Translation message or plain object to encode
       * @param {$protobuf.Writer} [writer] Writer to encode to
       * @returns {$protobuf.Writer} Writer
       */
      Translation.encodeDelimited = function encodeDelimited(message, writer) {
        return this.encode(message, writer).ldelim()
      }

      /**
       * Decodes a Translation message from the specified reader or buffer.
       * @function decode
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
       * @param {number} [length] Message length if known beforehand
       * @returns {Agora.SpeechToText.Translation} Translation
       * @throws {Error} If the payload is not a reader or valid buffer
       * @throws {$protobuf.util.ProtocolError} If required fields are missing
       */
      Translation.decode = function decode(reader, length) {
        if (!(reader instanceof $Reader)) reader = $Reader.create(reader)
        const end = length === undefined ? reader.len : reader.pos + length
        const message = new $root.Agora.SpeechToText.Translation()
        while (reader.pos < end) {
          const tag = reader.uint32()
          switch (tag >>> 3) {
            case 1: {
              message.isFinal = reader.bool()
              break
            }
            case 2: {
              message.lang = reader.string()
              break
            }
            case 3: {
              if (!(message.texts && message.texts.length)) message.texts = []
              message.texts.push(reader.string())
              break
            }
            default:
              reader.skipType(tag & 7)
              break
          }
        }
        return message
      }

      /**
       * Decodes a Translation message from the specified reader or buffer, length delimited.
       * @function decodeDelimited
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
       * @returns {Agora.SpeechToText.Translation} Translation
       * @throws {Error} If the payload is not a reader or valid buffer
       * @throws {$protobuf.util.ProtocolError} If required fields are missing
       */
      Translation.decodeDelimited = function decodeDelimited(reader) {
        if (!(reader instanceof $Reader)) reader = new $Reader(reader)
        return this.decode(reader, reader.uint32())
      }

      /**
       * Verifies a Translation message.
       * @function verify
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {Object.<string,*>} message Plain object to verify
       * @returns {string|null} `null` if valid, otherwise the reason why it is not
       */
      Translation.verify = function verify(message) {
        if (typeof message !== "object" || message === null) return "object expected"
        if (message.isFinal != null && message.hasOwnProperty("isFinal"))
          if (typeof message.isFinal !== "boolean") return "isFinal: boolean expected"
        if (message.lang != null && message.hasOwnProperty("lang"))
          if (!$util.isString(message.lang)) return "lang: string expected"
        if (message.texts != null && message.hasOwnProperty("texts")) {
          if (!Array.isArray(message.texts)) return "texts: array expected"
          for (let i = 0; i < message.texts.length; ++i)
            if (!$util.isString(message.texts[i])) return "texts: string[] expected"
        }
        return null
      }

      /**
       * Creates a Translation message from a plain object. Also converts values to their respective internal types.
       * @function fromObject
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {Object.<string,*>} object Plain object
       * @returns {Agora.SpeechToText.Translation} Translation
       */
      Translation.fromObject = function fromObject(object) {
        if (object instanceof $root.Agora.SpeechToText.Translation) return object
        const message = new $root.Agora.SpeechToText.Translation()
        if (object.isFinal != null) message.isFinal = Boolean(object.isFinal)
        if (object.lang != null) message.lang = String(object.lang)
        if (object.texts) {
          if (!Array.isArray(object.texts))
            throw TypeError(".Agora.SpeechToText.Translation.texts: array expected")
          message.texts = []
          for (let i = 0; i < object.texts.length; ++i) message.texts[i] = String(object.texts[i])
        }
        return message
      }

      /**
       * Creates a plain object from a Translation message. Also converts values to other types if specified.
       * @function toObject
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {Agora.SpeechToText.Translation} message Translation
       * @param {$protobuf.IConversionOptions} [options] Conversion options
       * @returns {Object.<string,*>} Plain object
       */
      Translation.toObject = function toObject(message, options) {
        if (!options) options = {}
        const object = {}
        if (options.arrays || options.defaults) object.texts = []
        if (options.defaults) {
          object.isFinal = false
          object.lang = ""
        }
        if (message.isFinal != null && message.hasOwnProperty("isFinal"))
          object.isFinal = message.isFinal
        if (message.lang != null && message.hasOwnProperty("lang")) object.lang = message.lang
        if (message.texts && message.texts.length) {
          object.texts = []
          for (let j = 0; j < message.texts.length; ++j) object.texts[j] = message.texts[j]
        }
        return object
      }

      /**
       * Converts this Translation to JSON.
       * @function toJSON
       * @memberof Agora.SpeechToText.Translation
       * @instance
       * @returns {Object.<string,*>} JSON object
       */
      Translation.prototype.toJSON = function toJSON() {
        return this.constructor.toObject(this, $protobuf.util.toJSONOptions)
      }

      /**
       * Gets the default type url for Translation
       * @function getTypeUrl
       * @memberof Agora.SpeechToText.Translation
       * @static
       * @param {string} [typeUrlPrefix] your custom typeUrlPrefix(default "type.googleapis.com")
       * @returns {string} The default type url
       */
      Translation.getTypeUrl = function getTypeUrl(typeUrlPrefix) {
        if (typeUrlPrefix === undefined) {
          typeUrlPrefix = "type.googleapis.com"
        }
        return typeUrlPrefix + "/Agora.SpeechToText.Translation"
      }

      return Translation
    })()

    return SpeechToText
  })()

  return Agora
})())

export { $root as default }
