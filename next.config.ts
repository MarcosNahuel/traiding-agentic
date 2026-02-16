import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // Para Docker/VPS deployment
  serverExternalPackages: ["@supabase/supabase-js", "ws"],
};

export default nextConfig;
