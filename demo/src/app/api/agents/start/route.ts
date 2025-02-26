import { NextRequest, NextResponse } from 'next/server';
import { getGraphProperties } from './graph';
import axios from 'axios';
/**
 * Handles the POST request to start an agent.
 * 
 * @param request - The NextRequest object representing the incoming request.
 * @returns A NextResponse object representing the response to be sent back to the client.
 */
export async function POST(request: NextRequest) {
  try {
    const { AGENT_SERVER_URL } = process.env;

    // Check if environment variables are available
    if (!AGENT_SERVER_URL) {
      throw "Environment variables are not available";
    }

    const body = await request.json();
    const {
      request_id,
      channel_name,
      user_uid,
      graph_name,
      language,
      voice_type,
      prompt,
      greeting,
      coze_token,
      coze_bot_id,
      coze_base_url,
      dify_api_key,
    } = body;

    let properties: any = getGraphProperties(graph_name, language, voice_type, prompt, greeting);
    if (graph_name.includes("coze")) {
      properties["coze_python_async"]["token"] = coze_token;
      properties["coze_python_async"]["bot_id"] = coze_bot_id;
      properties["coze_python_async"]["base_url"] = coze_base_url;
    }
    if (graph_name.includes("dify")) {
      properties["llm"]["api_key"] = dify_api_key;
    }

    console.log(`Starting agent for request ID: ${JSON.stringify({
      request_id,
      channel_name,
      user_uid,
      graph_name,
      // Get the graph properties based on the graph name, language, and voice type
      properties,
    })}`);

    console.log(`AGENT_SERVER_URL: ${AGENT_SERVER_URL}/start`);

    // Send a POST request to start the agent
    const response = await axios.post(`${AGENT_SERVER_URL}/start`, {
      request_id,
      channel_name,
      user_uid,
      graph_name,
      // Get the graph properties based on the graph name, language, and voice type
      properties,
    });

    const responseData = response.data;

    return NextResponse.json(responseData, { status: response.status });
  } catch (error) {
    if (error instanceof Response) {
      const errorData = await error.json();
      return NextResponse.json(errorData, { status: error.status });
    } else {
      console.error(`Error starting agent: ${error}`);
      return NextResponse.json({ code: "1", data: null, msg: "Internal Server Error" }, { status: 500 });
    }
  }
}