/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ink: "#10251f",
        cream: "#f8f3ea",
        paper: "#fffdf8",
        sage: "#b9cfad",
        clay: "#f18455",
        lagoon: "#11675d",
        mist: "#e8eee7",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(16, 37, 31, 0.10)",
        lift: "0 10px 26px rgba(16, 37, 31, 0.14)",
      },
      borderRadius: {
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
    },
  },
  plugins: [],
}
