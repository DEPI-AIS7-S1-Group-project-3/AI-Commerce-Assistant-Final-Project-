/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Values live in src/index.css (dark = default, [data-theme="light"] = light mode).
      colors: {
        paper: "rgb(var(--c-paper) / <alpha-value>)", // page background
        surface: "rgb(var(--c-surface) / <alpha-value>)", // cards
        sand: "rgb(var(--c-sand) / <alpha-value>)", // recessed areas
        ink: "rgb(var(--c-ink) / <alpha-value>)", // text
        "ink-soft": "rgb(var(--c-ink-soft) / <alpha-value>)",
        line: "rgb(var(--c-line) / <alpha-value>)", // borders
        navy: "#030407",
        power: "#1558C9",
        // Lime: use for FILLS only (buttons, badges). Text on it = on-neon.
        neon: { DEFAULT: "rgb(var(--c-neon) / <alpha-value>)", deep: "rgb(var(--c-neon-deep) / <alpha-value>)" },
        "on-neon": "rgb(var(--c-on-neon) / <alpha-value>)",
        // Accent for TEXT, links, icons, accent borders: lime in dark mode, blue in light mode.
        accent: { DEFAULT: "rgb(var(--c-accent) / <alpha-value>)", deep: "rgb(var(--c-accent-deep) / <alpha-value>)" },
        // Legacy name "green" = secondary accent, now BLUE. Rename later.
        green: {
          DEFAULT: "rgb(var(--c-blue) / <alpha-value>)",
          deep: "rgb(var(--c-blue-deep) / <alpha-value>)",
          tint: "rgb(var(--c-blue-tint) / <alpha-value>)",
        },
        danger: "rgb(var(--c-danger) / <alpha-value>)",
        warn: "rgb(var(--c-warn) / <alpha-value>)",
      },
      fontFamily: {
        display: ['"Kufam"', '"Changa"', "system-ui", "sans-serif"], // Kufam = Arabic, Changa = Latin (see index.css)
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