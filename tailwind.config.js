/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        grid: {
          bg: '#0f172a',
          panel: '#1e293b',
          accent: '#f97316',
        },
      },
      boxShadow: {
        panel: '0 20px 45px rgba(15, 23, 42, 0.45)',
      },
    },
  },
  plugins: [],
};
