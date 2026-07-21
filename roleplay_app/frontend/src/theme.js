const PALETTE = [
  ["#c9a227", "#7c5cbf"],
  ["#4f86c6", "#c9a227"],
  ["#b5495b", "#4f86c6"],
  ["#4f9d69", "#b5495b"],
  ["#9d5fc9", "#4f9d69"],
];

function hashName(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (h * 31 + name.charCodeAt(i)) >>> 0;
  }
  return h;
}

export function portraitStyle(name) {
  const [a, b] = PALETTE[hashName(name) % PALETTE.length];
  return { background: `linear-gradient(160deg, ${a} 0%, ${b} 100%)` };
}

export function initial(name) {
  return name.trim().charAt(0).toUpperCase() || "?";
}
