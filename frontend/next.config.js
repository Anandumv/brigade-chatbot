/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,

    // Enable bundle optimization
    swcMinify: true,
    compiler: {
        removeConsole: process.env.NODE_ENV === 'production',
    },

    // Tree-shake icon library
    experimental: {
        optimizePackageImports: ['lucide-react'],
    },

    env: {
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    },
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
            },
        ];
    },
};

module.exports = nextConfig;
