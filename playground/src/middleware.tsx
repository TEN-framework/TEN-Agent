// middleware.js
import { NextRequest, NextResponse } from 'next/server';
import { startAgent } from './apis/routes';


const { AGENT_SERVER_URL, TEN_DEV_SERVER_URL } = process.env;

// Check if environment variables are available
if (!AGENT_SERVER_URL) {
    throw "Environment variables AGENT_SERVER_URL are not available";
}

if (!TEN_DEV_SERVER_URL) {
    throw "Environment variables TEN_DEV_SERVER_URL are not available";
}

export function middleware(req: NextRequest) {
    const { pathname } = req.nextUrl;
    const url = req.nextUrl.clone();

    if (pathname.startsWith(`/api/agents/`)) {
        if (!pathname.startsWith('/api/agents/start')) {
            // Proxy all other agents API requests
            url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/agents/', '/')}`;

            // console.log(`Rewriting request to ${url.href}`);
            return NextResponse.rewrite(url);
        } else {
            return NextResponse.next();
        }
    } else if (pathname.startsWith(`/api/vector/`)) {

        // Proxy all other documents requests
        url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/vector/', '/vector/')}`;

        // console.log(`Rewriting request to ${url.href}`);
        return NextResponse.rewrite(url);
    } else if (pathname.startsWith(`/api/token/`)) {
        // Proxy all other documents requests
        url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/token/', '/token/')}`;

        // console.log(`Rewriting request to ${url.href}`);
        return NextResponse.rewrite(url);
    } else if (pathname.startsWith('/api/dev/')) {

        // Proxy all other documents requests
        const url = req.nextUrl.clone();
        url.href = `${TEN_DEV_SERVER_URL}${pathname.replace('/api/dev/', '/api/dev-server/')}`;

        // console.log(`Rewriting request to ${url.href}`);
        return NextResponse.rewrite(url);
    } else if (pathname.startsWith('/api/dev/')) {

        // Proxy all other documents requests
        const url = req.nextUrl.clone();
        url.href = `${TEN_DEV_SERVER_URL}${pathname.replace('/api/dev/', '/api/dev-server/')}`;

        // console.log(`Rewriting request to ${url.href}`);
        return NextResponse.rewrite(url);
    } else {
        return NextResponse.next();
    }

}