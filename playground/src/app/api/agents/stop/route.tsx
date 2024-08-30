import { REQUEST_URL } from '@/common/constant';
import { NextRequest, NextResponse } from 'next/server';

/**
 * Handles the POST request to stop an agent.
 * 
 * @param request - The NextRequest object representing the incoming request.
 * @returns A NextResponse object representing the response to be sent back to the client.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      channel_name,
      request_id,
    } = body;

    // Send a POST request to stop the agent
    const response = await fetch(`${REQUEST_URL}/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        request_id,
        channel_name
      }),
    });

    // Get the response data
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