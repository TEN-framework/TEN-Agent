import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// 配置匹配路径
export const config = {
  matcher: ['/api/:path*']
};

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 如果环境变量未设置，返回错误响应
  if (!process.env.AGENT_SERVER_URL) {
    console.error('AGENT_SERVER_URL is not defined');
    return NextResponse.json(
      { error: 'Server configuration error' },
      { status: 500 }
    );
  }

  try {
    const url = request.nextUrl.clone();

    if (pathname.startsWith('/api/token/')) {
      url.href = `${process.env.AGENT_SERVER_URL}${pathname.replace('/api/token/', '/token/')}`;
      console.log(`Rewriting ${pathname} to ${url.href}`);
      return NextResponse.rewrite(url);
    }

    if (pathname.startsWith('/api/agents/')) {
      url.href = `${process.env.AGENT_SERVER_URL}${pathname.replace('/api/agents/', '/')}`;
      console.log(`Rewriting ${pathname} to ${url.href}`);
      return NextResponse.rewrite(url);
    }

    // 对于其他 API 路径，返回 404
    if (pathname.startsWith('/api/')) {
      return NextResponse.json(
        { error: 'Not Found' },
        { status: 404 }
      );
    }

    return NextResponse.next();
  } catch (error) {
    console.error('Middleware error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
} 