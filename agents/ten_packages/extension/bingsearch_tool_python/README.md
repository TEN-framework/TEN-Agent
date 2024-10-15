# bingsearch_tool_python

This is tool for bing search, the document link is as follow: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/quickstarts/rest/python

It is built using TEN Tool Call Protocol (Beta).

## Features

It is the bing search tool that will auto register to any llm extension.

The tool description is as follow: 

*Use Bing.com to search for latest information. Call this function if you are not sure about the answer.*

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

- out: tool_register
- in: tool_call

## Misc

- use Tool Call Protocol Standard
- support async call
- apply asyncio template
