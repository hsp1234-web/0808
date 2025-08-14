/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/frontend/**/*.{html,js}",
  ],
  theme: {
    extend: {
      colors: {
        customBg: 'var(--custom-bg)',
        customText: 'var(--custom-text)',
        cardBg: 'var(--card-bg)',
        cardBorder: 'var(--card-border)',
        btnBg: 'var(--btn-bg)',
        btnHover: 'var(--btn-hover)',
        disabledBg: 'var(--disabled-bg)',
        progressBg: 'var(--progress-bg)',
        success: 'var(--success)',
        statusGreen: 'var(--status-green)',
        statusYellow: 'var(--status-yellow)',
      },
      borderRadius: {
        card: 'var(--rounded-card)',
        btn: 'var(--rounded-btn)',
        input: 'var(--rounded-input)',
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        statusGreen: '0 0 6px var(--status-green)',
        statusYellow: '0 0 6px var(--status-yellow)',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', '"Noto Sans"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
