// src/app/api/get-heygen-access-token/route.ts

import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  const { HEYGEN_API_KEY, HEYGEN_TOKEN_ENDPOINT } = process.env;

  if (!HEYGEN_API_KEY || !HEYGEN_TOKEN_ENDPOINT) {
    return NextResponse.json(
      { error: 'HeyGen API key or token endpoint not configured.' },
      { status: 500 }
    );
  }

  console.error('YO', HEYGEN_API_KEY, HEYGEN_TOKEN_ENDPOINT);
  try {
    const res = await fetch(
      HEYGEN_TOKEN_ENDPOINT,
      {
        method: "POST",
        headers: {
          "x-api-key": HEYGEN_API_KEY,
          "Content-Type": "application/json",
        },
      }
    );

    if (!res.ok) {
      const errorData = await res.json();
      console.error('Error fetching HeyGen access token:', errorData);
      return NextResponse.json(
        { error: 'Failed to fetch access token from HeyGen.' },
        { status: res.status }
      );
    }


    const data = await res.json();
    console.error(data);
    const accessToken = data.data.token;
    console.error(accessToken);
    if (!accessToken) {
      return NextResponse.json(
        { error: 'Access token not found in HeyGen response.' },
        { status: 500 }
      );
    }

    return NextResponse.json({ accessToken }, { status: 200 });

  } catch (error: any) {
    console.error('Internal Server Error while fetching HeyGen access token:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}
