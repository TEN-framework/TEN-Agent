/** @type {import('next').NextConfig} */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { withAvatarkitFixed } from "./avatarkit-next-fix.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const nextConfig = {
  output: "standalone",
  reactStrictMode: false,
  outputFileTracingRoot: path.join(__dirname, "./"),
};

export default withAvatarkitFixed(nextConfig);
