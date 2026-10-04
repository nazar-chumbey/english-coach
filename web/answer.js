import { h } from "./ui.js";

const CONTRACTIONS = [[/won't/g, "will not"], [/can't/g, "cannot"], [/n't/g, " not"], [/'re/g, " are"],
  [/'ve/g, " have"], [/'ll/g, " will"], [/'m/g, " am"], [/'d/g, " would"]];

export const norm = (s) => CONTRACTIONS.reduce((t, [re, full]) => t.replace(re, full), String(s).toLowerCase().replace(/[’`]/g, "'"))
  .replace(/[^\p{L}\p{N}' ]/gu, " ").split(/\s+/).filter(Boolean).join(" ");

export function typos(a, b) {
  const row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0]++;
    for (let j = 1; j <= b.length; j++) [prev, row[j]] = [row[j], Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] !== b[j - 1]))];
  }
  return row[b.length];
}

export const close = (given, target) => typos(norm(given), norm(target)) <= Math.floor(norm(target).length / 6);

export const recalled = (given, target) => close(given, target) || ` ${norm(given)} `.includes(` ${norm(target)} `);

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export function micButton(input) {
  if (!Recognition) return null;
  let rec = null;
  const button = h("button.dictateAnswerButton", { title: "Сказати голосом, ще раз — зупинити", onclick: () => {
    if (rec) return rec.stop();
    const before = input.value.trim();
    rec = Object.assign(new Recognition(), { lang: "en-US", continuous: true, interimResults: true });
    rec.onresult = (e) => {
      input.value = [before, ...[...e.results].map((r) => r[0].transcript.trim())].filter(Boolean).join(" ");
      input.dispatchEvent(new Event("input"));
    };
    rec.onend = () => { rec = null; button.classList.remove("listening"); input.focus(); };
    button.classList.add("listening");
    rec.start();
  } }, "🎤");
  return button;
}
