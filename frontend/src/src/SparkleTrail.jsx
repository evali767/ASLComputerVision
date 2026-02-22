import { useEffect } from "react";

export default function SparkleTrail() {
  useEffect(() => {
    let last = 0;

    const spawn = (x, y) => {
      const s = document.createElement("div");
      s.className = "sparkle";

      const glyphs = ["✨", "⭐", "✦", "✧", "💫"];
      s.textContent = glyphs[Math.floor(Math.random() * glyphs.length)];

      const size = 12 + Math.random() * 14; // 12–26px
      s.style.setProperty("--x", `${x}px`);
      s.style.setProperty("--y", `${y}px`);
      s.style.setProperty("--size", `${size}px`);

      document.body.appendChild(s);
      setTimeout(() => s.remove(), 750);
    };

    const onMove = (e) => {
      // throttle so it doesn't melt laptops
      const now = performance.now();
      if (now - last < 35) return; // ~28 sparkles/sec max
      last = now;

      spawn(e.clientX, e.clientY);
    };

    // pointermove works for mouse + trackpad
    window.addEventListener("pointermove", onMove, { passive: true });

    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  return null; // no JSX, we inject sparkles into <body>
}