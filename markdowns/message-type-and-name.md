# Message Type and Name
Below is an overview diagram of an RTE platform message.

``` text
┌── has response
│   └── command
│       ├── RTE platform built-in command
│       │    => message names start with `rte::`
│       └── Non-RTE platform built-in command
│            => message names do not start with `rte::`
└── no response
  ├── data
  │   ├── RTE platform built-in data
  │   │    => message names start with `rte::`
  │   └── Non-RTE platform built-in data
  │        => message names do not start with `rte::`
  ├── image_frame
  │   ├── RTE platform built-in image_frame
  │   │    => message names start with `rte::`
  │   └── Non-RTE platform built-in image_frame
  │        => message names do not start with `rte::`
  └── pcm_frame
    ├── RTE platform built-in pcm_frame
    │    => message names start with `rte::`
    └── Non-RTE platform built-in pcm_frame
       => message names do not start with `rte::`
```

## Differentiating Message Type and Message Name

When different messages have different functionalities, message types are used to differentiate them. Functionalities refer to what the RTE Platform provides for a message, and one of the functionalities is an API. For example, the RTE Platform provides an API for getting/setting image frame data. Other functionalities include whether the message has a response, etc. For instance:

- If a message has a response (referred to as a status command in the RTE Platform), there will be a message type representing this type of message.

- When a message has an image buffer (YUV422, RGB, etc.) that can be accessed, there will be a message type representing this message with the field. This message type provides the API for getting/setting image frame data.

- When a message has an audio buffer that can be accessed, a message type called pcm frame is created. This message type provides the API for getting/setting pcm frame data.

Message names are used to differentiate the different purposes of messages within the same message type.

## Message Type

The RTE Platform messages have four types:

1. command
2. data
3. image frame
4. pcm frame

The difference between commands and non-commands is that commands have a response (referred to as a status command in the RTE Platform), while non-commands do not have a response.

The corresponding extension message callbacks are:

1. OnCmd
2. OnData
3. OnImageFrame
4. OnPcmFrame

Although there are currently four message types, it is not certain if there will only be these four types in the future. There may be new types added. If we consider this, merging the four extension message callbacks into one OnMsg can avoid the issue of adding a new extension message callback for each new message type. However, this may inconvenience users, as it means they would have to handle different message types within the OnMsg function (pseudo code).

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

Additionally, in the RTE graph, there is a distinction between cmd_in, cmd_out, data_in, data_out, etc. So, following a unified approach, the interface of the extension should still maintain the differentiation of different message types.

<div class="note">


<div class="title">

Note

</div>

If no message type is specified, the default type is <span class="title-ref">cmd</span>.

</div>

## Message Name

Message Name is used within the RTE runtime to differentiate messages with different purposes under the same message type. The extension determines what actions to take based on the differentiation of message names.

The naming convention for message names is as follows:

1. The first character can only be <span class="title-ref">a-z</span>, <span class="title-ref">A-Z</span>, or <span class="title-ref">\_</span>.
2. Other characters can be <span class="title-ref">a-z</span>, <span class="title-ref">A-Z</span>, <span class="title-ref">0-9</span>, or <span class="title-ref">\_</span>.

## Creating Messages

<span class="title-ref">Non</span>-RTE platform built-in command:

``` json
{
  "rte": {
    "type": "cmd",           // mandatory
    "name": "hello_world"    // mandatory
  }
}
```

RTE platform built-in command:

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

## An Optimization in RTE Runtime for Message Names

Within the RTE runtime, each message is recorded with two fields:

1. Message type

   Enum.

2. Message name

   String.

Since message names are in string format, there is a certain performance overhead when comparing strings. Therefore, when the RTE runtime encounters certain <span class="title-ref">specific</span> message names, it can use a message type to represent that message. For example, when it sees a message name like <span class="title-ref">rte::connect</span>, the RTE runtime can optimize it from:

- Message type: <span class="title-ref">cmd</span> // mandatory
- Message name: <span class="title-ref">rte::connect</span> // mandatory

to:

- Message type: <span class="title-ref">connect</span> // mandatory
- Message name: <span class="title-ref">rte::connect</span> // optional

This optimization can only be applied to message names recognized by the RTE platform, so it is only possible for RTE platform built-in message names. Users cannot perform this optimization themselves, and new message types cannot be added by users. Since built-in messages are limited, the newly added message types are also limited, aligning with the enum type of message types.

In summary, message types other than <span class="title-ref">cmd</span>, <span class="title-ref">data</span>, <span class="title-ref">image_frame</span>, and <span class="title-ref">pcm_frame</span> are generated through this optimization, and these additional message types correspond to a special message name, which is always an RTE built-in message.

This optimization is not only applicable to commands but also to other message types. For example:

- Message type: <span class="title-ref">image_frame</span> // mandatory
- Message name: <span class="title-ref">rte::empty_image_frame</span> // mandatory

can be optimized to:

- Message type: <span class="title-ref">image_frame_empty</span> // mandatory
- Message name: <span class="title-ref">rte::empty_image_frame</span> // optional

Since the RTE platform modifies the type field of the message, users can also see and use this optimization. This is not a bad thing as users can leverage it to speed up message analysis. Therefore, users can use two methods to determine the message:

1. Using the message name

   ``` c++
   if (message_name == "rte::timer")
   ```

2. Using the message type

   ``` c++
   if (message_type == MSG_TYPE_TIMER)
   ```

## Creating Messages (with the mentioned optimization)

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

## When to Specify Message Type or Message Name

When it is not possible to determine the message type or message name in the context, it is necessary to specify the message type or message name.

For example:

- Message from JSON

  When the message type or message name is unknown, it is necessary to specify the message type and message name in the JSON.

- Command from JSON

  When it is known that the message is a command but the command name is unknown, it is necessary to specify the message name in the JSON.

- Connect command from JSON

  When it is known that the message is a connect command, the message name can only be <span class="title-ref">rte::connect</span>. Therefore, there is no need to specify the message type or message name in the JSON.

