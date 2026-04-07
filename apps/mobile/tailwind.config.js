/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,jsx,ts,tsx}',
    './components/**/*.{js,jsx,ts,tsx}',
  ],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#0F0D2E',
          card: 'rgba(30,27,75,0.5)',
          primary: '#6366F1',
          secondary: '#8B5CF6',
          text: '#E0E7FF',
          muted: '#94A3B8',
          dim: '#64748B',
        },
      },
    },
  },
  plugins: [],
};
