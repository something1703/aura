import type { NextConfig } from "next";

// The browser only ever calls same-origin `/api/*`; src/app/api/[...path]/
// route.ts is what actually forwards those to the real backend at request
// time, reading AURA_API_URL from the environment on every request. That
// has to be a real Route Handler and not this file's rewrites(): rewrites()
// is evaluated once during `next build` and its resolved destination gets
// baked into `.next/required-server-files.json`, so an env var read here
// would be fixed at build time no matter what's passed to `docker run -e` /
// an ECS task afterwards (confirmed against this exact Next.js version —
// the built output's rewrite destination did not follow a runtime env var
// change). Routing the proxy through a real request-time handler instead
// means no CORS configuration is needed for the deployed case either: the
// browser sees one origin.
const nextConfig: NextConfig = {
  // Standalone output for Docker (see ../Dockerfile.web): produces a
  // minimal server bundle with only the deps actually used, instead of
  // needing the full node_modules tree in the runtime image.
  output: "standalone",
};

export default nextConfig;
