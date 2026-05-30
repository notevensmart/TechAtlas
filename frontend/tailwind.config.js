/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      colors: {
        ink: "#172033",
        line: "#d9e2ec",
        panel: "#ffffff",
        surface: "#f6f8fb"
      }
    }
  },
  plugins: []
};

