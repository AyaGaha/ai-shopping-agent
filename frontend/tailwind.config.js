/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: 'var(--brand)',
        canvas: 'var(--canvas)',
        panel: 'var(--panel)',
        ink: 'var(--ink)',
        muted: 'var(--muted)',
      },
      fontFamily: { sans: ['Inter', 'sans-serif'] },
    },
  },
  plugins: [],
};
