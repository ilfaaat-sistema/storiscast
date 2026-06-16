// Design tokens — exact values from storiscast-prototype.jsx
export const T = {
  canvas:  "#E9E7E0",
  ink:     "#16181D",
  sub:     "#6B7078",
  line:    "#D7D3CA",
  surface: "#FFFFFF",
  primary: "#1B3A8F",
  live:    "#EC8B2B",
  ok:      "#2F9E44",
};

export const SANS = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
export const MONO = "ui-monospace, SFMono-Regular, Menlo, 'Roboto Mono', monospace";

export const PLATFORMS = [
  { id: "vk", name: "ВКонтакте",     color: "#0077FF", mode: "direct", note: "Прямая публикация" },
  { id: "tg", name: "Telegram",       color: "#29A9EB", mode: "direct", note: "Личный профиль · лимит 3/день" },
  { id: "ig", name: "Instagram",      color: "#E1306C", mode: "direct", note: "Graph API" },
  { id: "fb", name: "Facebook",       color: "#1877F2", mode: "auto",   note: "Прицепом через Instagram" },
  { id: "wa", name: "WhatsApp Status",color: "#25D366", mode: "manual", note: "Личный профиль · вручную" },
];

export const P = (id) => PLATFORMS.find((p) => p.id === id);
