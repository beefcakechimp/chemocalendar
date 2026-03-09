/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Required for the Docker multi-stage build (copies only what's needed to run)
  output: "standalone",

  async rewrites() {
    const raw = process.env.BACKEND_URL || "http://localhost:8000";
    // Ensure the URL always has a protocol prefix
    const backendUrl = raw.startsWith("http") ? raw : `http://${raw}`;
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
