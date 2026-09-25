/**
 * Tailwind build config. Same tokens the storefront used to declare inline for the
 * CDN build (`tailwind.config = {...}` in base.html), so nothing changes visually —
 * the CSS is just compiled once here instead of in every visitor's browser.
 *
 * Rebuild after adding or changing any utility class:   npm run build:css
 * (the compiled file, static/css/tailwind.css, is committed).
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    // Classes that live in Python: form widget attrs, status colours, etc.
    './accounts/**/*.py',
    './cart/**/*.py',
    './config/**/*.py',
    './console/**/*.py',
    './menu/**/*.py',
    './orders/**/*.py',
    './pages/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#141414', soft: '#1D1D1D', line: '#2A2A2A', mute: '#8A8A8A' },
        ember: { DEFAULT: '#C21807', dark: '#9C1205', light: '#E8402C' },
        bone: '#F4F2EF',
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
      },
      borderRadius: { xl2: '1.25rem' },
    },
  },
  plugins: [],
};
