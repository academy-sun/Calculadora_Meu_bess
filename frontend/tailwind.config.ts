import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#0ea5e9', dark: '#0284c7' },
        sidebar: '#1e293b',
      },
    },
  },
  plugins: [],
} satisfies Config
