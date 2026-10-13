async function call(path, body) {
  const res = await fetch(path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Try again.");
  return data;
}

export const api = {
  examples: () => call("/api/examples"),
  stats: () => call("/api/stats"),
  ask: (body) => call("/api/ask", body),
  direct: (question) => call("/api/direct", { question }),
};

export const LANGS = { en: "English", hi: "Hindi", te: "Telugu", hinglish: "Hinglish" };

export function detectLanguage(text) {
  if (/[ఀ-౿]/.test(text)) return "te";
  if (/[ऀ-ॿ]/.test(text)) return "hi";
  const hits = (text.toLowerCase().match(/\b(mein|ka|ki|ke|kitna|kitni|kitne|kaun|kya|har|tha|thi|the|liye|sabse)\b/g) || []).length;
  return text.trim() ? (hits >= 2 ? "hinglish" : "en") : null;
}
