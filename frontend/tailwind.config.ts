import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      borderRadius: {
        lg: "8px",
        md: "6px",
        sm: "4px",
      },
      fontFamily: {
        sans: [
          "Source Han Sans SC",
          "Noto Sans CJK SC",
          "Noto Sans SC",
          "Microsoft YaHei UI",
          "Microsoft YaHei",
          "system-ui",
          "sans-serif",
        ],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        surface: "var(--surface)",
        muted: "var(--surface-muted)",
        border: "var(--border)",
        primary: "var(--primary)",
        "muted-foreground": "var(--muted-foreground)",
      },
    },
  },
  plugins: [],
};

export default config;
