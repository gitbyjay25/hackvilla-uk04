/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  output: 'standalone',
  env: {
    NEXT_PUBLIC_ENV_VAR_USER:
      process.env.NEXT_PUBLIC_ENV_VAR_USER ||
      process.env.env_var_user ||
      process.env.ENV_VAR_USER ||
      'kashifalikhan093@gmail.com',
  },
  turbopack: {
    root: __dirname,
  },
};

module.exports = nextConfig;
