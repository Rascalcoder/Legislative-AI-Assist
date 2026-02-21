/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./app.js",
    "./**/*.{js,html}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif']
      },
      colors: {
        brand: {
          50: '#EEF2FF',
          100: '#E0E7FF',
          500: '#4F46E5',
          600: '#4338CA',
          700: '#3730A3'
        },
        eu: {
          bg: '#DBEAFE',
          text: '#1E40AF',
          border: '#93C5FD'
        },
        sk: {
          bg: '#FEF3C7',
          text: '#92400E',
          border: '#FCD34D'
        }
      }
    }
  },
  plugins: []
}




