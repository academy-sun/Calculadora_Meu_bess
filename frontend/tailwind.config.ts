import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#0f766e', dark: '#0b5a54', light: '#13a99b' }, // teal/esmeralda — energia/armazenamento
        accent: { DEFAULT: '#f59e0b', dark: '#d97706' },                    // âmbar solar
        ink: '#15130f',                                                     // tinta quase-preta (quente)
        paper: '#f7f5f0',                                                   // fundo papel quente
        sidebar: '#0e1512',                                                 // ink esverdeado profundo
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', 'system-ui', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(21,19,15,0.04), 0 8px 24px -12px rgba(21,19,15,0.12)',
      },
    },
  },
  plugins: [],
} satisfies Config
