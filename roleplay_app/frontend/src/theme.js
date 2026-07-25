const PALETTE = [
  ["#e8934a", "#3a2a1c"],
  ["#c96b3e", "#2a2035"],
  ["#b5703f", "#1f2a38"],
  ["#8a5a4a", "#2a1c2e"],
  ["#a8763e", "#22303c"],
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

export function portraitImageSrc(name) {
  const slug = name.toLowerCase().replace(/[^a-z0-9]/g, "");
  return `/portraits/${slug}.png`;
}

export function blurbFromPersona(name, persona) {
  if (!persona) return "";
  const stripped = persona.replace(new RegExp(`^You are ${name},?\\s*`, "i"), "");
  const sentence = stripped.split(/(?<=[.!?])\s/)[0] || stripped;
  if (sentence.length <= 130) return sentence;
  return `${sentence.slice(0, 127).trimEnd()}...`;
}
