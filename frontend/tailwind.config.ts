import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
    },
    extend: {
      colors: {
        // Sci-fi HUD palette — deep navy/black with emerald-teal neon
        hud: {
          void: "#03070f",
          deep: "#050a16",
          panel: "#0a1224",
          panelHi: "#0e1830",
          line: "#13243f",
          glow: "#00ffc8",
          glow2: "#00e5ff",
          accent: "#14f1d9",
          warn: "#ffb547",
          text: "#dff5ff",
          textDim: "#7f9bb3",
          textFaint: "#41607e",
        },
      },
      fontFamily: {
        display: ["Orbitron", "Rajdhani", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 24px rgba(0,255,200,0.18), inset 0 0 0 1px rgba(0,255,200,0.18)",
        glowSoft: "0 0 14px rgba(0,229,255,0.18)",
        panel: "0 0 0 1px rgba(20,241,217,0.10), 0 30px 60px -30px rgba(0,229,255,0.15)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(20,241,217,0.06) 1px, transparent 1px),linear-gradient(90deg, rgba(20,241,217,0.06) 1px, transparent 1px)",
        scan: "linear-gradient(180deg, transparent 0%, rgba(0,255,200,0.04) 50%, transparent 100%)",
      },
      animation: {
        "pulse-glow": "pulseGlow 3s ease-in-out infinite",
        "scan": "scan 8s linear infinite",
      },
      keyframes: {
        pulseGlow: {
          "0%,100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
      },
    },
  },
  plugins: [animate],
};

export default config;
