// middleware.js
import { NextRequest, NextResponse } from 'next/server';


const { AGENT_SERVER_URL } = process.env;

// Check if environment variables are available
if (!AGENT_SERVER_URL) {
  throw "Environment variables AGENT_SERVER_URL are not available";
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

    if (pathname.startsWith('/api/agents/')) {
        if (!pathname.startsWith('/api/agents/start')) {

            // Proxy all other agents API requests
            const url = req.nextUrl.clone();
            url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/agents/', '/')}`;

            // console.log(`Rewriting request to ${url.href}`);
            return NextResponse.rewrite(url);
        }
    } else if (pathname.startsWith('/api/vector/')) {

        // Proxy all other documents requests
        const url = req.nextUrl.clone();
        url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/vector/', '/vector/')}`;

        // console.log(`Rewriting request to ${url.href}`);
        return NextResponse.rewrite(url);
    } else if (pathname.startsWith('/api/token/')) {
        // Proxy all other documents requests
        const url = req.nextUrl.clone();
        url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/token/', '/token/')}`;

        // console.log(`Rewriting request to ${url.href}`);
        return NextResponse.rewrite(url);
    } else {
        return NextResponse.next();
    }

}