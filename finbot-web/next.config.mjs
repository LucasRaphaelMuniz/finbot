/** @type {import('next').NextConfig} */
const nextConfig = {
  compiler: {
    // styled-components precisa disso para SSR correto (evita FOUC/hydration mismatch)
    styledComponents: true,
  },
};

export default nextConfig;
