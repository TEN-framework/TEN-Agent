import { NextRequest, NextResponse } from 'next/server';

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
      properties
    } = body;

    // Send a POST request to start the agent
    const response = await fetch(`${AGENT_SERVER_URL}/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        request_id,
        channel_name,
        user_uid,
        graph_name,
        // Get the graph properties based on the graph name, language, and voice type
        properties: properties,
      }),
    });

    const responseData = await response.json();

    return NextResponse.json(responseData, { status: response.status });
  } catch (error) {
    if (error instanceof Response) {
      const errorData = await error.json();
      return NextResponse.json(errorData, { status: error.status });
    } else {
      return NextResponse.json({ code: "1", data: null, msg: "Internal Server Error" }, { status: 500 });
    }
  }
}