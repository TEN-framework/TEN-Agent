# Message Type and Name (简体中文)

底下是一个 RTE platform 的 message 的概述图.

``` text
┌── has response
│   └── command
│       ├── RTE platform 的 built-in command
│       │    => message name 以 `rte::` 开头
│       └── `非` RTE platform 的 built-in command
│            => message name 不以 `rte::` 开头
└── no response
    ├── data
    │   ├── RTE platform 的 built-in data
    │   │    => message name 以 `rte::` 开头
    │   └── `非` RTE platform 的 built-in data
    │        => message name 不以 `rte::` 开头
    ├── image_frame
    │   ├── RTE platform 的 built-in image_frame
    │   │    => message name 以 `rte::` 开头
    │   └── `非` RTE platform 的 built-in image_frame
    │        => message name 不以 `rte::` 开头
    └── pcm_frame
        ├── RTE platform 的 built-in pcm_frame
        │    => message name 以 `rte::` 开头
        └── `非` RTE platform 的 built-in pcm_frame
             => message name 不以 `rte::` 开头
```

## 区分 Message Type 及 Message Name 的原因

当不同的 messages 有不同的 <span class="title-ref">功能</span> 时, 使用
message type 来区分. <span class="title-ref">功能</span> 指的是 RTE
Platform 对 message 提供了什么功能, 其中一种功能是 API, 例如 RTE
Platform 对该 message 提供了什么 API. 例如提供了 get/set image frame
data 的功能 (API). 其他的功能还有该 message 是否有 response 等等. 例如:

- 有一种 message 会有 response (RTE platform 称为 status command),
  则会有一种 message type 代表这种行为的 message.

- 当一种 message 有 image buffer (YUV422, RGB, etc.) 可供存取时,
  则会有一种 message type 代表这种内含字段的 message.

  相当于这种 message type 提供了 get/set image frame data 的 API.

- 当一种 message 有 audio buffer 可供存取时, 因此产生一种 message type
  叫做 pcm frame.

  相当于这种 message type 提供了 get/set pcm frame data 的 API.

而当用户需要区分同一个 message type 的 messages 的不同用途时, 可以使用
message name 来区分.

## Message Type

RTE platform 的 message 的对外的呈现形式, 有四种 type:

1.  command
2.  data
3.  image frame
4.  pcm frame

Command 跟非 command 的差异在于, command 会有 response (在 RTE platform
中称为 status command), 而非 command 不会有 response.

对应 extension 的四个 message callbacks:

1.  OnCmd
2.  OnData
3.  OnImageFrame
4.  OnPcmFrame

虽然现在 message 有 4 种 type, 但是未来是不是只有这 4 种 type 则不一定,
有可能会新增出新的 type. 如果从这一点来看, 把 extension 的四个 message
callbacks 合并成为一个 OnMsg, 可以避免以后新增一个 message type
就要新增一个 extension message callbacks 的问题.
但这个对用户来说会有一些不方便, 这代表用户在 extension 的 OnMsg
内要做底下的事情 (pseudo codes).

> ``` c++
> OnMsg(msg) {
>   switch (msg->type) {
>   case command || connect || timer || ...:
>     OnCmd(msg);
>     break;
>   case data:
>     OnData(msg);
>     break;
>   case image_frame:
>     OnImageFrame(msg);
>     break;
>   case pcm_frame:
>     OnPcmFrame(msg);
>     break;
>   }
> }
> ```

另外在 RTE graph 内是区分 <span class="title-ref">cmd_in</span>,
<span class="title-ref">cmd_out</span>,
<span class="title-ref">data_in</span>,
<span class="title-ref">data_out</span> 等, 所以按照统一思维下,
extension 的界面仍维持区分不同 message type 的形式.

<div class="note">

<div class="title">

Note

</div>

如果没有指定 message type, 则默认是 <span class="title-ref">cmd</span>
type.

</div>

## Message Name

Message Name 是在 RTE runtime 里面用来区分同一个 message type
下的不同用途的 message 的名字. extension 借由区分不同的 message name
来决定要做什么事情.

message name 的命名归则是:

1.  第一个字元只能是 <span class="title-ref">a-z</span>,
    <span class="title-ref">A-Z</span>, 以及
    <span class="title-ref">\_</span>.
2.  其他字元可以是 <span class="title-ref">a-z</span>,
    <span class="title-ref">A-Z</span>,
    <span class="title-ref">0-9</span> 以及
    <span class="title-ref">\_</span>.

## 创建 Message 的方法

<span class="title-ref">非</span> RTE platform 的 built-in command:

``` json
{
  "rte": {
    "type": "cmd",           // mandatory
    "name": "hello_world"    // mandatory
  }
}
```

RTE platform 的 built-in command:

``` json
{
  "rte": {
    "type": "cmd",           // mandatory
    "name": "rte::connect"   // mandatory
  }
}
```

Data:

``` json
{
  "rte": {
    "type": "data",          // mandatory
    "name": "foo"            // optional
  }
}
```

Image Frame:

``` json
{
  "rte": {
    "type": "image_frame",   // mandatory
    "name": "foo"            // optional
  }
}
```

PCM Frame:

``` json
{
  "rte": {
    "type": "pcm_frame",    // mandatory
    "name": "foo"           // optional
  }
}
```

## RTE runtime 针对 message name 的一个加速优化

RTE runtime 内部有替每个 message 纪录两个字段:

1.  message type

    枚举.

2.  message name

    字串.

而因为 message name 是字串型态, 每次比对字串会有一定的 performance
overhead, 因此当 RTE runtime 看到某些
<span class="title-ref">特定的</span> message name 的时候, RTE runtime
可以使用一个 message type 来代表该 message. 例如当看到一个 message name
是 <span class="title-ref">rte::connect</span> 的时候, RTE runtime
会把原本是

- message type: <span class="title-ref">cmd</span> // mandatory
- message name: <span class="title-ref">rte::connect</span> // mandatory

提升成

- message type: <span class="title-ref">connect</span> // mandatory
- message name: <span class="title-ref">rte::connect</span> // optional

这种优化的场景只有在 RTE platform 认得的 message name 才能这样做,
因此只有对 RTE platform built-in message name 才有可能做这样的优化,
也就是说用户没办法自行做这种优化, message type
的新枚举值不能由用户自行扩充. 也由于 built-in message 是有限的,
因此而新增的 new message type 也是有限的, 与 message type 是
<span class="title-ref">枚举</span> 类型相吻合.

总的来说, 除了 <span class="title-ref">cmd</span>,
<span class="title-ref">data</span>,
<span class="title-ref">image_frame</span>,
<span class="title-ref">pcm_frame</span> 之外的 message type,
一定是由这种优化而产生的, 且这些额外的 message type 会 1-1
对应一个特殊的 message name, 而这个 message name 一定是一种 RTE built-in
message.

这种优化不仅适合于 command, 也适合于其他 message type, 例如:

- message type: <span class="title-ref">image_frame</span> // mandatory
- message name: <span class="title-ref">rte::empty_image_frame</span> //
  mandatory

提升成

- message type: <span class="title-ref">image_frame_empty</span> //
  mandatory
- message name: <span class="title-ref">rte::empty_image_frame</span> //
  optional

由于 RTE platform 会修改 message 的 type 字段,
因此这种优化也可以被用户看到跟使用, 这到也不是坏事, 用户可以借此来加速
message 的分析. 因此用户可以使用两种方式来判断 message:

1.  使用 message name

    ``` c++
    if (message_name == "rte::timer")
    ```

2.  使用 message type

    ``` c++
    if (message_type == MSG_TYPE_TIMER)
    ```

## 创建 Message 的方法 (加入上述的优化)

RTE platform 的 built-in command:

``` json
{
  "rte": {
    "type": "cmd",          // mandatory
    "name": "rte::connect"  // mandatory
  }
}
```

<span class="title-ref">或</span>

``` json
{
  "rte": {
    "type": "connect"       // mandatory
  }
}
```

## 什么时候需要指定 message type 或 message name

当在上下文中, 无法知道该 message 是什么 message type 或是什么 message
name 的时候, 就需要指定 message type 或 message name.

例如:

- message from json

  不知道是什么 message, 因此在 json 内需要指定 message type 及 message
  name.

- command from json

  知道是 command, 但不知道 command name, 因此在 json 内需要指定 message
  name.

- connect command from json

  知道是 connect command, message name 只能是
  <span class="title-ref">rte::connect</span>, 因此在 json
  内部不需要指定 message type, 也不需要指定 message name.
