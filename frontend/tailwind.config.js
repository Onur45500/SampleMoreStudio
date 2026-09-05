/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0c1210",
          900: "#121a17",
          800: "#1a2621",
          700: "#24332c",
        },
        moss: {
          400: "#7dba8a",
          500: "#4f9a62",
          600: "#3a7a4b",
        },
        ember: {
          400: "#e8a45c",
          500: "#d4843a",
        },
        chalk: "#e8efe9",
      },
      fontFamily: {
        display: ['"Fraunces"', "Georgia", "serif"],
        sans: ['"Source Sans 3"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
