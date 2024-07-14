# RTE Platform API Specification

## C Core

### Error

> > Default errno, for those users only care error msgs.
>
> > Invalid json.
>
> > Invalid argument.
>
> > Invalid graph.
>
> > The RTE world is closed.

## C++

### Message

| Name                          | Link                                   |
|-------------------------------|----------------------------------------|
| msg_t::get_type               | `Link <msg_t::get_type>`               |
| cmd_t::get_name               | `Link <msg_t::get_name>`               |
| msg_t::set_dest               | `Link <msg_t::set_dest>`               |
| msg_t::from_json              | `Link <msg_t::from_json>`              |
| msg_t::to_json                | `Link <msg_t::to_json>`                |
| msg_t::is_property_exist      | `Link <msg_t::is_property_exist>`      |
| msg_t::get_property_uint8     | `Link <msg_t::get_property_uint8>`     |
| msg_t::get_property_uint16    | `Link <msg_t::get_property_uint16>`    |
| msg_t::get_property_uint32    | `Link <msg_t::get_property_uint32>`    |
| msg_t::get_property_uint64    | `Link <msg_t::get_property_uint64>`    |
| msg_t::get_property_int8      | `Link <msg_t::get_property_int8>`      |
| msg_t::get_property_int16     | `Link <msg_t::get_property_int16>`     |
| msg_t::get_property_int32     | `Link <msg_t::get_property_int32>`     |
| msg_t::get_property_int64     | `Link <msg_t::get_property_int64>`     |
| msg_t::get_property_float32   | `Link <msg_t::get_property_float32>`   |
| msg_t::get_property_float64   | `Link <msg_t::get_property_float64>`   |
| msg_t::get_property_string    | `Link <msg_t::get_property_string>`    |
| msg_t::get_property_bool      | `Link <msg_t::get_property_bool>`      |
| msg_t::get_property_ptr       | `Link <msg_t::get_property_ptr>`       |
| msg_t::get_property_buf       | `Link <msg_t::get_property_buf>`       |
| msg_t::get_property_to_json   | `Link <msg_t::get_property_to_json>`   |
| msg_t::set_property_uint8     | `Link <msg_t::set_property_uint8>`     |
| msg_t::set_property_uint16    | `Link <msg_t::set_property_uint16>`    |
| msg_t::set_property_uint32    | `Link <msg_t::set_property_uint32>`    |
| msg_t::set_property_uint64    | `Link <msg_t::set_property_uint64>`    |
| msg_t::set_property_int8      | `Link <msg_t::set_property_int8>`      |
| msg_t::set_property_int16     | `Link <msg_t::set_property_int16>`     |
| msg_t::set_property_int32     | `Link <msg_t::set_property_int32>`     |
| msg_t::set_property_int64     | `Link <msg_t::set_property_int64>`     |
| msg_t::set_property_float32   | `Link <msg_t::set_property_float32>`   |
| msg_t::set_property_float64   | `Link <msg_t::set_property_float64>`   |
| msg_t::set_property_string    | `Link <msg_t::set_property_string>`    |
| msg_t::set_property_bool      | `Link <msg_t::set_property_bool>`      |
| msg_t::set_property_ptr       | `Link <msg_t::set_property_ptr>`       |
| msg_t::set_property_buf       | `Link <msg_t::set_property_buf>`       |
| msg_t::set_property_from_json | `Link <msg_t::set_property_from_json>` |

C++ message API

> Get the message type.

> Get the message name.

> Set the destination of the message.

> Convert the message to JSON string.

> Convert the message from JSON string.

> Check if the property exists. <span class="title-ref">path</span> can
> not be empty.

> Get the property from the message in the specified type.
> <span class="title-ref">path</span> can not be empty.

> Get the property from the message in JSON format.
> <span class="title-ref">path</span> can not be empty.

> Set the property in the message from JSON string.
> <span class="title-ref">path</span> can not be empty.

### Command

| Name                         | Link                             |
|------------------------------|----------------------------------|
| cmd_t::create(const char \*) | `Link <cmd_t::create>`           |
| cmd_t::create_from_json      | `Link <cmd_t::create_from_json>` |

C++ command API

> Create a new command with the specified command name.

> Create a new command from a JSON string.

### Connect Command

| Name                    | Link                           |
|-------------------------|--------------------------------|
| cmd_connect_t::create() | `Link <cmd_connect_t::create>` |

C++ connect command API

> Create a new connect command.

### Status Command

| Name                                  | Link                                        |
|---------------------------------------|---------------------------------------------|
| cmd_result_t::create(RTE_STATUS_CODE) | `Link <cmd_result_t::cmd_result_t>`         |
| cmd_result_t::get_detail\<T\>         | `Link <cmd_result_t::get_detail>`           |
| cmd_result_t::get_detail_to_json      | `Link <cmd_result_t::get_detail_to_json>`   |
| cmd_result_t::set_detail\<T\>         | `Link <cmd_result_t::set_detail>`           |
| cmd_result_t::set_detail_from_json    | `Link <cmd_result_t::set_detail_from_json>` |
| cmd_result_t::get_status_code         | `Link <cmd_result_t::get_status_code>`      |

C++ status command API

> Create a new status command with the specified status code.

> Get the detail of the status command in JSON format.

> Set the detail of the status command from JSON string.

> Get the status code from the status command.

### Timeout Command

| Name                          | Link                                 |
|-------------------------------|--------------------------------------|
| cmd_timeout_t::create()       | `Link <cmd_timeout_t::create>`       |
| cmd_timeout_t::get_timer_id() | `Link <cmd_timeout_t::get_timer_id>` |

C++ timeout command API

> Create a new timeout command.

> Get the corresponding timer ID from the timeout command.

### Timer Command

| Name                  | Link                         |
|-----------------------|------------------------------|
| cmd_timer_t::create() | `Link <cmd_timer_t::create>` |

C++ timer command API

> Create a new timer command.

### Close App Command

| Name                      | Link                             |
|---------------------------|----------------------------------|
| cmd_close_app_t::create() | `Link <cmd_close_app_t::create>` |

C++ close app command API

> Create a new close app command.

### Close Engine Command

| Name                         | Link                                |
|------------------------------|-------------------------------------|
| cmd_close_engine_t::create() | `Link <cmd_close_engine_t::create>` |

C++ close engine command API

> Create a new close engine command.

### Data Message

| Name               | Link                        |
|--------------------|-----------------------------|
| data_t::create()   | `Link <data_t::create>`     |
| data_t::get_buf    | `Link <data_t::get_buf>`    |
| data_t::lock_buf   | `Link <data_t::lock_buf>`   |
| data_t::unlock_buf | `Link <data_t::unlock_buf>` |

C++ data message API

> Create a data message.

> Get the buffer of the data message. The operation is deep-copy.

> Borrow the ownership of the buffer from the data message.

> Give the ownership of the buffer back to the data message.

### Image frame Message

| Name                         | Link                                  |
|------------------------------|---------------------------------------|
| image_frame_t::create()      | `Link <image_frame_t::create>`        |
| image_frame_t::get_width     | `Link <image_frame_t::get_width>`     |
| image_frame_t::set_width     | `Link <image_frame_t::set_width>`     |
| image_frame_t::get_height    | `Link <image_frame_t::get_height>`    |
| image_frame_t::set_height    | `Link <image_frame_t::set_height>`    |
| image_frame_t::get_timestamp | `Link <image_frame_t::get_timestamp>` |
| image_frame_t::set_timestamp | `Link <image_frame_t::set_timestamp>` |
| image_frame_t::get_pixel_fmt | `Link <image_frame_t::get_pixel_fmt>` |
| image_frame_t::set_pixel_fmt | `Link <image_frame_t::set_pixel_fmt>` |
| image_frame_t::is_eof        | `Link <image_frame_t::is_eof>`        |
| image_frame_t::set_is_eof    | `Link <image_frame_t::set_is_eof>`    |
| image_frame_t::alloc_buf     | `Link <image_frame_t::alloc_buf>`     |
| image_frame_t::lock_buf      | `Link <image_frame_t::lock_buf>`      |
| image_frame_t::unlock_buf    | `Link <image_frame_t::unlock_buf>`    |

C++ image frame message API

> Create a image frame message.

> Get/set the width of the image frame.

> Get/set the height of the image frame.

> Get/set the timestamp of the image frame.

> Get/set the pixel format type of the image frame.

> Get/set the end of file flag of the image frame.

> Allocate a buffer for the image frame.

> Borrow the ownership of the buffer from the image frame message.

> Give the ownership of the buffer back to the image frame message.

### Pcm frame Message

| Name                                 | Link                                          |
|--------------------------------------|-----------------------------------------------|
| pcm_frame_t::create()                | `Link <pcm_frame_t::create>`                  |
| pcm_frame_t::get_timestamp           | `Link <pcm_frame_t::get_timestamp>`           |
| pcm_frame_t::set_timestamp           | `Link <pcm_frame_t::set_timestamp>`           |
| pcm_frame_t::get_sample_rate         | `Link <pcm_frame_t::get_sample_rate>`         |
| pcm_frame_t::set_sample_rate         | `Link <pcm_frame_t::set_sample_rate>`         |
| pcm_frame_t::get_channel_layout      | `Link <pcm_frame_t::get_channel_layout>`      |
| pcm_frame_t::set_channel_layout      | `Link <pcm_frame_t::set_channel_layout>`      |
| pcm_frame_t::get_samples_per_channel | `Link <pcm_frame_t::get_samples_per_channel>` |
| pcm_frame_t::set_samples_per_channel | `Link <pcm_frame_t::set_samples_per_channel>` |
| pcm_frame_t::get_bytes_per_sample    | `Link <pcm_frame_t::get_bytes_per_sample>`    |
| pcm_frame_t::set_bytes_per_sample    | `Link <pcm_frame_t::set_bytes_per_sample>`    |
| pcm_frame_t::get_number_of_channels  | `Link <pcm_frame_t::get_number_of_channels>`  |
| pcm_frame_t::set_number_of_channels  | `Link <pcm_frame_t::set_number_of_channels>`  |
| pcm_frame_t::get_data_fmt            | `Link <pcm_frame_t::get_data_fmt>`            |
| pcm_frame_t::set_data_fmt            | `Link <pcm_frame_t::set_data_fmt>`            |
| pcm_frame_t::get_line_size           | `Link <pcm_frame_t::get_line_size>`           |
| pcm_frame_t::set_line_size           | `Link <pcm_frame_t::set_line_size>`           |
| pcm_frame_t::is_eof                  | `Link <pcm_frame_t::is_eof>`                  |
| pcm_frame_t::set_is_eof              | `Link <pcm_frame_t::set_is_eof>`              |
| pcm_frame_t::alloc_buf               | `Link <pcm_frame_t::alloc_buf>`               |
| pcm_frame_t::lock_buf                | `Link <pcm_frame_t::lock_buf>`                |
| pcm_frame_t::unlock_buf              | `Link <pcm_frame_t::unlock_buf>`              |

C++ pcm frame message API

> Create a pcm frame message.

> Get/set the timestamp of the pcm frame.

> Get/set the sample rate of the pcm frame.

> Get/set the channel layout of the pcm frame.

> Get/set the samples per channel of the pcm frame.

> Get/set the bytes per sample of the pcm frame.

> Get/set the number of channels of the pcm frame.

> Get/set the data format of the pcm frame.

> Get/set line size of the pcm frame.

> Get/set the end of file flag of the pcm frame.

> Allocate a buffer for the pcm frame.

> Borrow the ownership of the buffer from the pcm frame message.

> Give the ownership of the buffer back to the pcm frame message.

### Addon

| Name                                      | Link                                               |
|-------------------------------------------|----------------------------------------------------|
| RTE_CPP_REGISTER_ADDON_AS_EXTENSION       | `Link <RTE_CPP_REGISTER_ADDON_AS_EXTENSION>`       |
| RTE_CPP_REGISTER_ADDON_AS_EXTENSION_GROUP | `Link <RTE_CPP_REGISTER_ADDON_AS_EXTENSION_GROUP>` |

C++ addon API

> Register a C++ class as an RTE extension addon.

> Register a C++ class as an RTE extension group addon.

### App

| Name                       | Link                      |
|----------------------------|---------------------------|
| app_t::run                 | `Link <app_t::run>`       |
| app_t::close               | `Link <app_t::close>`     |
| app_t::wait                | `Link <app_t::wait>`      |
| Callback: app_t::on_init   | `Link <app_t::on_init>`   |
| Callback: app_t::on_deinit | `Link <app_t::on_deinit>` |

C++ app API

> Run the app.

> Close the app.

> Wait for the app to close.

### Extension

| Name                        | Link                                 |
|-----------------------------|--------------------------------------|
| extension_t::on_init        | `Link <extension_t::on_init>`        |
| extension_t::on_deinit      | `Link <extension_t::on_deinit>`      |
| extension_t::on_start       | `Link <extension_t::on_start>`       |
| extension_t::on_stop        | `Link <extension_t::on_stop>`        |
| extension_t::on_cmd         | `Link <extension_t::on_cmd>`         |
| extension_t::on_data        | `Link <extension_t::on_data>`        |
| extension_t::on_pcm_frame   | `Link <extension_t::on_pcm_frame>`   |
| extension_t::on_image_frame | `Link <extension_t::on_image_frame>` |

C++ extension API

### Extension Group

| Name                                     | Link                                              |
|------------------------------------------|---------------------------------------------------|
| extension_group_t::on_init               | `Link <extension_group_t::on_init>`               |
| extension_group_t::on_deinit             | `Link <extension_group_t::on_deinit>`             |
| extension_group_t::on_create_extensions  | `Link <extension_group_t::on_create_extensions>`  |
| extension_group_t::on_destroy_extensions | `Link <extension_group_t::on_destroy_extensions>` |

C++ extension group API

### Metadata Info

| Name                 | Link                          |
|----------------------|-------------------------------|
| metadata_info_t::set | `Link <metadata_info_t::set>` |

C+ + metadata info API

> Set the metadata info.

### RTE Proxy

| Name                           | Link                                    |
|--------------------------------|-----------------------------------------|
| rte_proxy_t::rte_proxy_t       | `Link <rte_proxy_t::rte_proxy_t>`       |
| rte_proxy_t::acquire_lock_mode | `Link <rte_proxy_t::acquire_lock_mode>` |
| rte_proxy_t::release_lock_mode | `Link <rte_proxy_t::release_lock_mode>` |
| rte_proxy_t::notify            | `Link <rte_proxy_t::notify>`            |

C++ rte proxy API

> Create an RTE proxy instance from a RTE instance.

> Acquire the lock mode.

> Release the lock mode.

> Enable the `notify_func` to be called in the RTE extension thread.

### RTE

| Name                                 | Link                                          |
|--------------------------------------|-----------------------------------------------|
| rte_t::send_cmd                      | `Link <rte_t::send_cmd>`                      |
| rte_t::send_json                     | `Link <rte_t::send_json>`                     |
| rte_t::send_data                     | `Link <rte_t::send_data>`                     |
| rte_t::send_image_frame              | `Link <rte_t::send_image_frame>`              |
| rte_t::send_pcm_frame                | `Link <rte_t::send_pcm_frame>`                |
| rte_t::return_result_directly        | `Link <rte_t::return_result_directly>`        |
| rte_t::return_result                 | `Link <rte_t::return_result>`                 |
| rte_t::is_property_exist             | `Link <rte_t::is_property_exist>`             |
| rte_t::get_property_uint8            | `Link <rte_t::get_property_uint8>`            |
| rte_t::get_property_uint16           | `Link <rte_t::get_property_uint16>`           |
| rte_t::get_property_uint32           | `Link <rte_t::get_property_uint32>`           |
| rte_t::get_property_uint64           | `Link <rte_t::get_property_uint64>`           |
| rte_t::get_property_int8             | `Link <rte_t::get_property_int8>`             |
| rte_t::get_property_int16            | `Link <rte_t::get_property_int16>`            |
| rte_t::get_property_int32            | `Link <rte_t::get_property_int32>`            |
| rte_t::get_property_int64            | `Link <rte_t::get_property_int64>`            |
| rte_t::get_property_float32          | `Link <rte_t::get_property_float32>`          |
| rte_t::get_property_float64          | `Link <rte_t::get_property_float64>`          |
| rte_t::get_property_string           | `Link <rte_t::get_property_string>`           |
| rte_t::get_property_bool             | `Link <rte_t::get_property_bool>`             |
| rte_t::get_property_ptr              | `Link <rte_t::get_property_ptr>`              |
| rte_t::get_property_buf              | `Link <rte_t::get_property_buf>`              |
| rte_t::get_property_to_json          | `Link <rte_t::get_property_to_json>`          |
| rte_t::set_property_from_json        | `Link <rte_t::set_property_from_json>`        |
| rte_t::is_cmd_connected              | `Link <rte_t::is_cmd_connected>`              |
| rte_t::addon_create_extension_async  | `Link <rte_t::addon_create_extension_async>`  |
| rte_t::addon_destroy_extension_async | `Link <rte_t::addon_destroy_extension_async>` |
| rte_t::on_init_done                  | `Link <rte_t::on_init_done>`                  |
| rte_t::on_deinit_done                | `Link <rte_t::on_deinit_done>`                |
| rte_t::on_start_done                 | `Link <rte_t::on_start_done>`                 |
| rte_t::on_stop_done                  | `Link <rte_t::on_stop_done>`                  |
| rte_t::on_create_extensions_done     | `Link <rte_t::on_create_extensions_done>`     |
| rte_t::on_destroy_extensions_done    | `Link <rte_t::on_destroy_extensions_done>`    |
| rte_t::get_attached_target           | `Link <rte_t::get_attached_target>`           |

C++ rte API

> Send the <span class="title-ref">cmd</span> with a response handler.
>
> When the sending action is successful, the
> <span class="title-ref">unique_ptr</span> will be released to
> represent that the ownership of the <span class="title-ref">cmd</span>
> has been transferred to the RTE runtime. Conversely, if the sending
> action fails, the <span class="title-ref">unique_ptr</span> will not
> perform any action, indicating that the ownership of the
> <span class="title-ref">cmd</span> remains with the user.
>
> The type of <span class="title-ref">response_handler_func_t</span> is
> <span class="title-ref">void(rte_t &,
> std::unique_ptr\<cmd_result_t\>)</span>

> Send the command created from the json string without a response
> handler.

> Send the command created from the json string with a response handler.
>
> The type of <span class="title-ref">response_handler_func_t</span> is
> <span class="title-ref">void(rte_t &,
> std::unique_ptr\<cmd_result_t\>)</span>

> Send the data message to the RTE.
>
> When the sending action is successful, the
> <span class="title-ref">unique_ptr</span> will be released to
> represent that the ownership of the
> <span class="title-ref">data</span> has been transferred to the RTE
> runtime. Conversely, if the sending action fails, the
> <span class="title-ref">unique_ptr</span> will not perform any action,
> indicating that the ownership of the
> <span class="title-ref">data</span> remains with the user.

> Send the image frame to the RTE.
>
> When the sending action is successful, the
> <span class="title-ref">unique_ptr</span> will be released to
> represent that the ownership of the
> <span class="title-ref">frame</span> has been transferred to the RTE
> runtime. Conversely, if the sending action fails, the
> <span class="title-ref">unique_ptr</span> will not perform any action,
> indicating that the ownership of the
> <span class="title-ref">frame</span> remains with the user.

> Send the PCM frame to the RTE.
>
> When the sending action is successful, the
> <span class="title-ref">unique_ptr</span> will be released to
> represent that the ownership of the
> <span class="title-ref">frame</span> has been transferred to the RTE
> runtime. Conversely, if the sending action fails, the
> <span class="title-ref">unique_ptr</span> will not perform any action,
> indicating that the ownership of the
> <span class="title-ref">frame</span> remains with the user.

> Return the status command directly.
>
> When the returning action is successful, the
> <span class="title-ref">unique_ptr</span> will be released to
> represent that the ownership of the <span class="title-ref">cmd</span>
> has been transferred to the RTE runtime. Conversely, if the sending
> action fails, the <span class="title-ref">unique_ptr</span> will not
> perform any action, indicating that the ownership of the
> <span class="title-ref">cmd</span> remains with the user.

> Return the status command corresponding to the target command.
>
> When the returning action is successful, the
> <span class="title-ref">unique_ptr</span> will be released to
> represent that the ownership of the <span class="title-ref">cmd</span>
> has been transferred to the RTE runtime. Conversely, if the sending
> action fails, the <span class="title-ref">unique_ptr</span> will not
> perform any action, indicating that the ownership of the
> <span class="title-ref">cmd</span> remains with the user.

> Check if the property exists. <span class="title-ref">path</span> can
> not be empty.

> Get the property from the RTE in JSON format.
> <span class="title-ref">path</span> can not be empty.

> Set the property in the RTE from JSON string.
> <span class="title-ref">path</span> can not be empty.

> Check if the command is connected in the graph.

> Create an RTE extension instance with the specified `instance_name`
> from the specified addon specified with the `addon_name`
> asynchronously.

> Destroy an RTE extension instance.

> Notify the RTE that the `on_init` callback is done.

> Notify the RTE that the `on_deinit` callback is done.

> Notify the RTE that the `on_start` callback is done.

> Notify the RTE that the `on_stop` callback is done.

> Notify the RTE that the `on_create_extensions` callback is done.

> Notify the RTE that the `on_destroy_extensions` callback is done.

> Get the attached target.

## Golang

### Message

| Name                          | Link                                     |
|-------------------------------|------------------------------------------|
| msg::GetType                  | `Link <go_msg_GetType>`                  |
| msg::GetName                  | `Link <go_msg_GetName>`                  |
| msg::ToJSON                   | `Link <go_msg_ToJSON>`                   |
| msg::GetPropertyInt8          | `Link <go_msg_GetPropertyInt8>`          |
| msg::GetPropertyInt16         | `Link <go_msg_GetPropertyInt16>`         |
| msg::GetPropertyInt32         | `Link <go_msg_GetPropertyInt32>`         |
| msg::GetPropertyInt64         | `Link <go_msg_GetPropertyInt64>`         |
| msg::GetPropertyUint8         | `Link <go_msg_GetPropertyUint8>`         |
| msg::GetPropertyUint16        | `Link <go_msg_GetPropertyUint16>`        |
| msg::GetPropertyUint32        | `Link <go_msg_GetPropertyUint32>`        |
| msg::GetPropertyUint64        | `Link <go_msg_GetPropertyUint64>`        |
| msg::GetPropertyBool          | `Link <go_msg_GetPropertyBool>`          |
| msg::GetPropertyPtr           | `Link <go_msg_GetPropertyPtr>`           |
| msg::GetPropertyString        | `Link <go_msg_GetPropertyString>`        |
| msg::GetPropertyBytes         | `Link <go_msg_GetPropertyBytes>`         |
| msg::GetPropertyToJSONBytes   | `Link <go_msg_GetPropertyToJSONBytes>`   |
| msg::SetPropertyString        | `Link <go_msg_SetPropertyString>`        |
| msg::SetPropertyBytes         | `Link <go_msg_SetPropertyBytes>`         |
| msg::SetProperty              | `Link <go_msg_SetProperty>`              |
| msg::SetPropertyFromJSONBytes | `Link <go_msg_SetPropertyFromJSONBytes>` |

Golang message API

<div id="go_msg_GetType">

**GetType() MsgType**

</div>

Get the message type.

<div id="go_msg_GetName">

**GetName() (string, error)**

</div>

Get the name of the message.

<div id="go_msg_ToJSON">

**ToJSON() string**

</div>

Get the JSON string of the message.

<div id="go_msg_GetPropertyInt8">

**GetPropertyInt8(path string) (int8, error)**

</div>

Get the property from the message in int8 type.

<div id="go_msg_GetPropertyInt16">

**GetPropertyInt16(path string) (int16, error)**

</div>

Get the property from the message in int16 type.

<div id="go_msg_GetPropertyInt32">

**GetPropertyInt32(path string) (int32, error)**

</div>

Get the property from the message in int32 type.

<div id="go_msg_GetPropertyInt64">

**GetPropertyInt64(path string) (int64, error)**

</div>

Get the property from the message in int64 type.

<div id="go_msg_GetPropertyUint8">

**GetPropertyUint8(path string) (uint8, error)**

</div>

Get the property from the message in uint8 type.

<div id="go_msg_GetPropertyUint16">

**GetPropertyUint16(path string) (uint16, error)**

</div>

Get the property from the message in uint16 type.

<div id="go_msg_GetPropertyUint32">

**GetPropertyUint32(path string) (uint32, error)**

</div>

Get the property from the message in uint32 type.

<div id="go_msg_GetPropertyUint64">

**GetPropertyUint64(path string) (uint64, error)**

</div>

Get the property from the message in uint64 type.

<div id="go_msg_GetPropertyBool">

**GetPropertyBool(path string) (bool, error)**

</div>

Get the property from the message in bool type.

<div id="go_msg_GetPropertyPtr">

**GetPropertyPtr(path string) (any, error)**

</div>

Get the property from the message in ptr type.

<div id="go_msg_GetPropertyString">

**GetPropertyString(path string) (string, error)**

</div>

Get the property from the message in string type.

<div id="go_msg_GetPropertyBytes">

**GetPropertyBytes(path string) (\[\]byte, error)**

</div>

Get the property from the message in bytes type.

<div id="go_msg_GetPropertyToJSONBytes">

**GetPropertyToJSONBytes(path string) (\[\]byte, error)**

</div>

Get the property from the message in JSON bytes type.

<div id="go_msg_SetPropertyString">

**SetPropertyString(path string, value string) error**

</div>

Set the property in string type.

<div id="go_msg_SetPropertyBytes">

**SetPropertyBytes(path string, value \[\]byte) error**

</div>

Set the property in bytes type.

<div id="go_msg_SetProperty">

**SetProperty(path string, value any) error**

</div>

Set the property.

<div id="go_msg_SetPropertyFromJSONBytes">

**SetPropertyFromJSONBytes(path string, value \[\]byte) error**

</div>

SEt the property from the JSON bytes.

### Command

| Name                | Link                                             |
|---------------------|--------------------------------------------------|
| NewCmd              | `Link <go_custom_cmd_NewCustomCmd>`              |
| NewCmdFromJSONBytes | `Link <go_custom_cmd_NewCustomCmdFromJSONBytes>` |

Golang custom command API

<div id="go_custom_cmd_NewCustomCmd">

**NewCmd(cmdName string) (Cmd, error)**

</div>

Create a new custom command width the specified command name.

<div id="go_custom_cmd_NewCustomCmdFromJSONBytes">

**NewCmdFromJSONBytes(data \[\]byte) (Cmd, error)**

</div>

Create a new custom command from the specified JSON bytes.

### Status Command

| Name                     | Link                                |
|--------------------------|-------------------------------------|
| NewCmdResult             | `Link <go_cmd_result_NewCmdResult>` |
| CmdResult::GetStatusCode | `Link <go_cmd_result_StatusCode>`   |

Golang status command API

<div id="go_cmd_result_NewCmdResult">

**NewCmdResult(statusCode StatusCode, detail any) (CmdResult, error)**

</div>

Create a new status command.

<div id="go_cmd_result_StatusCode">

**GetStatusCode() (StatusCode, error)**

</div>

Get the status code from the status command.

### Data Message

| Name            | Link                         |
|-----------------|------------------------------|
| <Data::NewData> | `Link <go_data_msg_NewData>` |
| <Data::GetBuf>  | `Link <go_data_msg_GetBuf>`  |

Golang data message API

<div id="go_data_msg_NewData">

**NewData(bytes \[\]byte) (Data, error)**

</div>

Create a new data message.

<div id="go_data_msg_GetBuf">

**GetBuf() (\[\]byte, error)**

</div>

Get the data buffer from the data message. Note that this function
performs a deep copy of the data buffer.

### Image Frame Message

### Pcm Frame Message

### Error

> Default errno, for those users only care error msgs.

> Invalid json.

> Invalid argument.

> Invalid type.

| Name             | Link                     |
|------------------|--------------------------|
| RteError::Error  | `Link <go_error_Error>`  |
| RteError::ErrNo  | `Link <go_error_ErrNo>`  |
| RteError::ErrMsg | `Link <go_error_ErrMsg>` |

Golang error API

<div id="go_error_Error">

**Error() string**

</div>

<div id="go_error_ErrNo">

**ErrNo() uint32**

</div>

Get the error number.

<div id="go_error_ErrMsg">

**ErrMsg() string**

</div>

Get the error message.

### Addon

| Name                          | Link                                            |
|-------------------------------|-------------------------------------------------|
| Addon::OnInit                 | `Link <go_addon_OnInit>`                        |
| Addon::OnDeinit               | `Link <go_addon_OnDeinit>`                      |
| Addon::OnCreateInstance       | `Link <go_addon_OnCreateInstance>`              |
| RegisterAddonAsExtension      | `Link <go_addon_RegisterAddonAsExtension>`      |
| RegisterAddonAsExtensionGroup | `Link <go_addon_RegisterAddonAsExtensionGroup>` |
| UnloadAllAddons               | `Link <go_addon_UnloadAllAddons>`               |
| NewDefaultExtensionAddon      | `Link <go_addon_NewDefaultExtensionAddon>`      |
| NewDefaultExtensionGroupAddon | `Link <go_addon_NewDefaultExtensionGroupAddon>` |

Golang addon API

<div id="go_addon_OnInit">

**OnInit(rte Rte, manifest MetadataInfo, property MetadataInfo)**

</div>

Initialize the addon.

<div id="go_addon_OnDeinit">

**OnDeinit(rte Rte)**

</div>

De-initialize the addon.

<div id="go_addon_OnCreateInstance">

**OnCreateInstance(rte Rte, name string) any**

</div>

Create an instance of the addon.

<div id="go_addon_RegisterAddonAsExtension">

**RegisterAddonAsExtension(name string, addon \*Addon) error**

</div>

Register the addon as an extension addon to the RTE runtime environment.

<div id="go_addon_RegisterAddonAsExtensionGroup">

**RegisterAddonAsExtensionGroup(name string, addon \*Addon) error**

</div>

Register the addon as an extension group addon to the RTE runtime
environment.

<div id="go_addon_UnloadAllAddons">

**UnloadAllAddons() error**

</div>

Un-register all the addons from the RTE runtime environment.

<div id="go_addon_NewDefaultExtensionAddon">

**NewDefaultExtensionAddon(constructor func(name string) Extension)
\*Addon**

</div>

Create a new default extension addon.

<div id="go_addon_NewDefaultExtensionGroupAddon">

**NewDefaultExtensionGroupAddon(constructor func(name string)
ExtensionGroup) \*Addon**

</div>

Create a new default extension group addon.

### App

| Name          | Link                     |
|---------------|--------------------------|
| NewApp        | `Link <go_app_NewApp>`   |
| App::OnInit   | `Link <go_app_OnInit>`   |
| App::OnDeinit | `Link <go_app_OnDeinit>` |
| App::Run      | `Link <go_app_Run>`      |
| App::Close    | `Link <go_app_Close>`    |
| App::Wait     | `Link <go_app_Wait>`     |

Golang app API

<div id="go_app_NewApp">

**NewApp(iApp IApp) (App, error)**

</div>

Create a new app.

<div id="go_app_OnInit">

**OnInit(rte Rte, manifest MetadataInfo, property MetadataInfo)**

</div>

Initialize the app.

<div id="go_app_OnDeinit">

**OnDeinit(rte Rte)**

</div>

De-initialize the app.

<div id="go_app_Run">

**Run(runInBackground bool)**

</div>

Run the app.

<div id="go_app_Close">

**Close()**

</div>

Close the app.

<div id="go_app_Wait">

**Wait()**

</div>

Wait the app to be closed.

### Extension

| Name                     | Link                               |
|--------------------------|------------------------------------|
| Extension::OnInit        | `Link <go_extension_OnInit>`       |
| Extension::OnStart       | `Link <go_extension_OnStart>`      |
| Extension::OnStop        | `Link <go_extension_OnStop>`       |
| Extension::OnDeinit      | `Link <go_extension_OnDeinit>`     |
| Extension::OnCmd         | `Link <go_extension_OnCmd>`        |
| Extension::OnData        | `Link <go_extension_OnData>`       |
| Extension::OnImageFrame  | `Link <go_extension_OnImageFrame>` |
| Extension::OnPcmFrame    | `Link <go_extension_OnPcmFrame>`   |
| Extension::WrapExtension | `Link <go_extension_NewExtension>` |

Golang extension API

<div id="go_extension_OnInit">

**OnInit(rte Rte, manifest MetadataInfo, property MetadataInfo)**

</div>

<div id="go_extension_OnStart">

**OnStart(rte Rte)**

</div>

<div id="go_extension_OnStop">

**OnStop(rte Rte)**

</div>

<div id="go_extension_OnDeinit">

**OnDeinit(rte Rte)**

</div>

<div id="go_extension_OnCmd">

**OnCmd(rte Rte, cmd Cmd)**

</div>

<div id="go_extension_OnData">

**OnData(rte Rte, data Data)**

</div>

<div id="go_extension_OnImageFrame">

**OnImageFrame(rte Rte, imageFrame ImageFrame)**

</div>

<div id="go_extension_OnPcmFrame">

**OnPcmFrame(rte Rte, pcmFrame PcmFrame)**

</div>

<div id="go_extension_NewExtension">

**WrapExtension(ext Extension, name string) \*extension**

</div>

Create a new extension instance with the specified name.

### Extension Group

| Name                                | Link                                            |
|-------------------------------------|-------------------------------------------------|
| ExtensionGroup::OnInit              | `Link <go_extension_group_OnInit>`              |
| ExtensionGroup::OnDeinit            | `Link <go_extension_group_OnDeinit>`            |
| ExtensionGroup::OnCreateExtensions  | `Link <go_extension_group_OnCreateExtensions>`  |
| ExtensionGroup::OnDestroyExtensions | `Link <go_extension_group_OnDestroyExtensions>` |
| WrapExtensionGroup                  | `Link <go_extension_group_NewExtensionGroup>`   |

Golang extension group API

<div id="go_extension_group_OnInit">

**OnInit(rte Rte, manifest MetadataInfo, property MetadataInfo)**

</div>

<div id="go_extension_group_OnDeinit">

**OnDeinit(rte Rte)**

</div>

<div id="go_extension_group_OnCreateExtensions">

**OnCreateExtensions(rte Rte)**

</div>

<div id="go_extension_group_OnDestroyExtensions">

**OnDestroyExtensions(rte Rte, extensions \[\]Extension)**

</div>

<div id="go_extension_group_NewExtensionGroup">

**WrapExtensionGroup(extGroup ExtensionGroup, name string)
\*extensionGroup**

</div>

Create a new extension group instance with the specified name.

### Metadata Info

| Name              | Link                          |
|-------------------|-------------------------------|
| MetadataInfo::Set | `Link <go_metadata_info_Set>` |

Golang metadata info API

<div id="go_metadata_info_Set">

**Set(metadataType MetadataType, value string)**

</div>

Set the metadata info.

### Rte

| Name                            | Link                                       |
|---------------------------------|--------------------------------------------|
| rte::GetPropertyInt8            | `Link <go_rte_GetPropertyInt8>`            |
| rte::GetPropertyInt16           | `Link <go_rte_GetPropertyInt16>`           |
| rte::GetPropertyInt32           | `Link <go_rte_GetPropertyInt32>`           |
| rte::GetPropertyInt64           | `Link <go_rte_GetPropertyInt64>`           |
| rte::GetPropertyUint8           | `Link <go_rte_GetPropertyUint8>`           |
| rte::GetPropertyUint16          | `Link <go_rte_GetPropertyUint16>`          |
| rte::GetPropertyUint32          | `Link <go_rte_GetPropertyUint32>`          |
| rte::GetPropertyUint64          | `Link <go_rte_GetPropertyUint64>`          |
| rte::GetPropertyBool            | `Link <go_rte_GetPropertyBool>`            |
| rte::GetPropertyPtr             | `Link <go_rte_GetPropertyPtr>`             |
| rte::GetPropertyString          | `Link <go_rte_GetPropertyString>`          |
| rte::GetPropertyBytes           | `Link <go_rte_GetPropertyBytes>`           |
| rte::GetPropertyToJSONBytes     | `Link <go_rte_GetPropertyToJSONBytes>`     |
| rte::SetPropertyString          | `Link <go_rte_SetPropertyString>`          |
| rte::SetPropertyBytes           | `Link <go_rte_SetPropertyBytes>`           |
| rte::SetProperty                | `Link <go_rte_SetProperty>`                |
| rte::SetPropertyAsync           | `Link <go_rte_SetPropertyAsync>`           |
| rte::SetPropertyFromJSONBytes   | `Link <go_rte_SetPropertyFromJSONBytes>`   |
| rte::ReturnResult               | `Link <go_rte_ReturnResult>`               |
| rte::ReturnResultDirectly       | `Link <go_rte_ReturnResultDirectly>`       |
| rte::SendJSON                   | `Link <go_rte_SendJSON>`                   |
| rte::SendJSONBytes              | `Link <go_rte_SendJSONBytes>`              |
| rte::SendCmd                    | `Link <go_rte_SendCmd>`                    |
| rte::SendData                   | `Link <go_rte_SendData>`                   |
| rte::SendImageFrame             | `Link <go_rte_SendImageFrame>`             |
| rte::SendPcmFrame               | `Link <go_rte_SendPcmFrame>`               |
| rte::OnStartDone                | `Link <go_rte_OnStartDone>`                |
| rte::OnStopDone                 | `Link <go_rte_OnStopDone>`                 |
| rte::OnInitDone                 | `Link <go_rte_OnInitDone>`                 |
| rte::OnDeinitDone               | `Link <go_rte_OnDeinitDone>`               |
| rte::OnCreateExtensionsDone     | `Link <go_rte_OnCreateExtensionsDone>`     |
| rte::OnDestroyExtensionsDone    | `Link <go_rte_OnDestroyExtensionsDone>`    |
| rte::OnCreateInstanceDone       | `Link <go_rte_OnCreateInstanceDone>`       |
| rte::IsCmdConnected             | `Link <go_rte_IsCmdConnected>`             |
| rte::AddonCreateExtensionAsync  | `Link <go_rte_AddonCreateExtensionAsync>`  |
| rte::AddonDestroyExtensionAsync | `Link <go_rte_AddonDestroyExtensionAsync>` |

Golang rte API

<div id="go_rte_GetPropertyInt8">

**GetPropertyInt8(path string) (int8, error)**

</div>

Get the property from the RTE in int8 type.

<div id="go_rte_GetPropertyInt16">

**GetPropertyInt16(path string) (int16, error)**

</div>

Get the property from the RTE in int16 type.

<div id="go_rte_GetPropertyInt32">

**GetPropertyInt32(path string) (int32, error)**

</div>

Get the property from the RTE in int32 type.

<div id="go_rte_GetPropertyInt64">

**GetPropertyInt64(path string) (int64, error)**

</div>

Get the property from the RTE in int64 type.

<div id="go_rte_GetPropertyUint8">

**GetPropertyUint8(path string) (uint8, error)**

</div>

Get the property from the RTE in uint8 type.

<div id="go_rte_GetPropertyUint16">

**GetPropertyUint16(path string) (uint16, error)**

</div>

Get the property from the RTE in uint16 type.

<div id="go_rte_GetPropertyUint32">

**GetPropertyUint32(path string) (uint32, error)**

</div>

Get the property from the RTE in uint32 type.

<div id="go_rte_GetPropertyUint64">

**GetPropertyUint64(path string) (uint64, error)**

</div>

Get the property from the RTE in uint64 type.

<div id="go_rte_GetPropertyBool">

**GetPropertyBool(path string) (bool, error)**

</div>

Get the property from the RTE in bool type.

<div id="go_rte_GetPropertyPtr">

**GetPropertyPtr(path string) (any, error)**

</div>

Get the property from the RTE in ptr type.

<div id="go_rte_GetPropertyString">

**GetPropertyString(path string) (string, error)**

</div>

Get the property from the RTE in string type.

<div id="go_rte_GetPropertyBytes">

**GetPropertyBytes(path string) (\[\]byte, error)**

</div>

Get the property from the RTE in bytes type.

<div id="go_rte_GetPropertyToJSONBytes">

**GetPropertyToJSONBytes(path string) (\[\]byte, error)**

</div>

Get the property from the RTE in JSON bytes type.

<div id="go_rte_SetProperty">

**SetProperty(path string, value any) error**

</div>

Set the property to the RTE.

<div id="go_rte_SetPropertyString">

**SetPropertyString(path string, value string) error**

</div>

Set the property to the RTE in string type.

<div id="go_rte_SetPropertyBytes">

**SetPropertyBytes(path string, value \[\]byte) error**

</div>

Set the property to the RTE in bytes type.

<div id="go_rte_SetPropertyFromJSONBytes">

**SetPropertyFromJSONBytes(path string, value \[\]byte) error**

</div>

Set the property to the RTE from the JSON bytes.

<div id="go_rte_SetPropertyAsync">

**SetPropertyAsync(path string, v any, callback func(Rte, error))
error**

</div>

Set the property to the RTE asynchronously.

<div id="go_rte_ReturnResult">

**ReturnResult(statusCmd CmdResult, cmd Cmd) error**

</div>

Return the result.

<div id="go_rte_ReturnResultDirectly">

**ReturnResultDirectly(statusCmd CmdResult) error**

</div>

Return the result directly.

<div id="go_rte_SendJSON">

**SendJSON(json string, handler ResponseHandler) error**

</div>

Send the JSON.

<div id="go_rte_SendJSONBytes">

**SendJSONBytes(json \[\]byte, handler ResponseHandler) error**

</div>

Send the JSON bytes.

<div id="go_rte_SendCmd">

**SendCmd(cmd Cmd, handler ResponseHandler) error**

</div>

Send the command.

<div id="go_rte_SendData">

**SendData(data Data) error**

</div>

Send the data.

<div id="go_rte_SendImageFrame">

**SendImageFrame(imageFrame ImageFrame) error**

</div>

Send the image frame.

<div id="go_rte_SendPcmFrame">

**SendPcmFrame(pcmFrame PcmFrame) error**

</div>

Send the PCM frame.

<div id="go_rte_OnInitDone">

**OnInitDone(manifest MetadataInfo, property MetadataInfo) error**

</div>

OnInit done.

<div id="go_rte_OnStartDone">

**OnStartDone() error**

</div>

OnStart done.

<div id="go_rte_OnStopDone">

**OnStopDone() error**

</div>

OnStop done.

<div id="go_rte_OnDeinitDone">

**OnDeinitDone() error**

</div>

OnDeinit done.

<div id="go_rte_OnCreateExtensionsDone">

**OnCreateExtensionsDone(extensions ...Extension) error**

</div>

OnCreateExtensions done.

<div id="go_rte_OnDestroyExtensionsDone">

**OnDestroyExtensionsDone() error**

</div>

OnDestroyExtensions done.

<div id="go_rte_OnCreateInstanceDone">

**OnCreateInstanceDone(instance any) error**

</div>

OnCreateInstance done.

<div id="go_rte_IsCmdConnected">

**IsCmdConnected(cmdName string) (bool, error)**

</div>

Is the command connected.

<div id="go_rte_AddonCreateExtensionAsync">

**AddonCreateExtensionAsync(addonName string, instanceName string,
callback func(rte Rte, p Extension)) error**

</div>

Create an extension from the addon specified by the addon name and
instance name.

<div id="go_rte_AddonDestroyExtensionAsync">

**AddonDestroyExtensionAsync(ext Extension, callback func(rte Rte))
error**

</div>

Destroy a specified extension.
