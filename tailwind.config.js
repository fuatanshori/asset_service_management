/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./templates/**/*.html",
    "./equipment/templates/**/*.html",
    "./maintenance/templates/**/*.html",
    "./dashboard/templates/**/*.html",
    "./reports/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        ink:   '#14213D',
        bg:    '#F1F4F8',
        brand: {
          DEFAULT: '#2A5C8A',
          dark: '#1E4265'
        },
        amber: '#C97A2E',
        red: '#C0483F',
        green: '#328A63',
        line: '#DCE3EA',
        muted: '#5E6B7C',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        xl2: '14px',
      },
    }
  },
  plugins: [],
}