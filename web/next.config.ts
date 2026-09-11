import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for Docker (see ../Dockerfile.web): produces a
  // minimal server bundle with only the deps actually used, instead of
  // needing the full node_modules tree in the runtime image.
  output: "standalone",
};

export default nextConfig;
