# weatherapi_tool_python

This is the tool for weather query, including current weather, broadcast and history weather check, the document link is as follow: https://www.weatherapi.com/docs/

It is built using TEN Tool Call Protocol (Beta).

## Features

For free plan:
- Fetch today's weather.
- Search for history weather within 7 days.
- Forcast weather in 3 days.

You can extend by using other plan in your project.

https://www.weatherapi.com/pricing.aspx

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

- out: tool_register
- in: tool_call
