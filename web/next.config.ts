import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Bu uygulama model/veri dosyası barındırmaz; yüklenen medya yalnızca tarayıcıda (blob URL) tutulur.
  poweredByHeader: false,
};

export default nextConfig;
