import type { NextRequest } from "next/server";

// Runtime proxy to the real AURA API. This is NOT next.config.ts's
// rewrites(): that config is evaluated once during `next build` and its
// resolved destination is baked into `.next/required-server-files.json`, so
// an env var read there is fixed at build time no matter what you pass to
// `docker run -e` / an ECS task later. A Route Handler body, by contrast,
// runs fresh on every request in the live server process, so
// AURA_API_URL here is genuinely read at request time — one built image
// can be pointed at any backend.
const AURA_API_URL = () => process.env.AURA_API_URL ?? "http://127.0.0.1:8000";

// Hop-by-hop headers that must not be forwarded (they describe the
// connection to *this* server, not the one we're proxying to).
const STRIPPED_REQUEST_HEADERS = new Set(["host", "connection", "content-length"]);
const STRIPPED_RESPONSE_HEADERS = new Set(["connection", "transfer-encoding", "content-encoding"]);

async function proxy(request: NextRequest, path: string[]): Promise<Response> {
  const target = new URL(`/api/${path.join("/")}${request.nextUrl.search}`, AURA_API_URL());

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!STRIPPED_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      redirect: "manual",
    });
  } catch {
    return Response.json({ error: "Could not reach the AURA API. Is it running?" }, { status: 502 });
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!STRIPPED_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

async function handle(request: NextRequest, ctx: RouteContext<"/api/[...path]">): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(request, path);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
