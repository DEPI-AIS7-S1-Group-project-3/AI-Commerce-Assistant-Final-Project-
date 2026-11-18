import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

// The initial theme is set in index.html (before React loads) to avoid a flash of the wrong colours.
const STORAGE_KEY = "dokkan.theme";
const THEME_COLOR: Record<Theme, string> = { dark: "#030407", light: "#F4F6EE" };

const current = (): Theme => (document.documentElement.dataset.theme === "light" ? "light" : "dark");

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(current);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[theme]);
  }, [theme]);

  // Save only when the user chooses; until then we follow the system setting.
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next: Theme = t === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
