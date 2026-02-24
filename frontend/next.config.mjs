/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const raw = process.env.BACKEND_URL || "http://localhost:8000";
    // Ensure the URL always has a protocol so Next.js accepts it as a valid destination
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
