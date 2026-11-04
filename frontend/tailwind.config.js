/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#030407", // page background
        surface: "#0D1424", // cards
        sand: "#070B15", // recessed areas
        ink: "#F4F6EE", // text
        "ink-soft": "#A9B4CC",
        line: "#1E3A78", // borders
        navy: "#030407",
        power: "#1558C9",
        neon: { DEFAULT: "#D4FF24", deep: "#B8E000" },
        // Legacy name "green" = secondary accent, now BLUE. Rename later.
        green: {
          DEFAULT: "#1558C9",
          deep: "#0F449C",
          tint: "#0F2350",
        },
        danger: "#FF6B7F",
        warn: "#FFB84D",
      },
      fontFamily: {
        display: ['"Lalezar"', "system-ui", "sans-serif"],
        body: ['"Readex Pro"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: {
        ctl: "10px",
        card: "16px",
      },
      boxShadow: {
        pop: "3px 3px 0 0 #1558C9",
      },
    },
  },
  plugins: [],
};