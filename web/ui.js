export function h(tag, attrs = {}, ...children) {
  const [name, ...classes] = tag.split(".");
  const el = document.createElement(name || "div");
  if (classes.length) el.className = classes.join(" ");
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className += ` ${value}`;
    else el.setAttribute(key, value === true ? "" : value);
  }
  el.append(...children.flat(Infinity).filter((c) => c != null && c !== false));
  return el;
}

const INLINE = /(\*\*.+?\*\*|`.+?`|\n)/;

export const md = (text) =>
  String(text ?? "").split(INLINE).filter(Boolean).map((part) => {
    if (part === "\n") return h("br");
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return h("b", {}, part.slice(2, -2));
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return h("code", {}, part.slice(1, -1));
    return part;
  });

export const rich = (tag, text, attrs = {}) => h(tag, attrs, md(text));

export const fmtDate = (iso, withYear = false) =>
  iso ? new Date(iso).toLocaleDateString("uk-UA", { day: "numeric", month: "short", ...(withYear && { year: "numeric" }) }) : "";

export const STATUS = { weak: "слабко", improving: "покращується", stable: "стабільно", mastered: "засвоєно",
  done: "завершено", in_progress: "в процесі", correct: "правильно", minor: "майже", wrong: "помилка",
  mismatch: "не збіглося", skipped: "пропущено", noted: "записано" };

export const chip = (status) => h("span.statusChip", { class: status }, STATUS[status] || status);

export const loading = (text) => h("div.loadingState", {}, h("span.loadingDots", {}, text));

export function correctionList(items = []) {
  return h("ul.correctionList", {}, items.map((c) =>
    h("li", {}, h("span.wrongSentence", {}, c.wrong), " → ", h("span.rightSentence", {}, c.right),
      c.why ? rich("small", c.why) : null)));
}

export const findingRow = (icon, tone, title, text, example) => h("div.findingRow", {},
  h("span.verdictIcon", { class: tone }, icon),
  h("div", {}, title ? h("div.findingArea", {}, title) : null, rich("div", text),
    example ? h("div.exampleChip", {}, example) : null));

const CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"];

export function cefrValue(label = "") {
  const parts = String(label).match(/[ABC][12]\+?/g) || [];
  if (!parts.length) return null;
  const values = parts.map((p) => CEFR.indexOf(p.slice(0, 2)) + (p.endsWith("+") ? 0.5 : 0));
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export function cefrScale(current, target, milestone) {
  const pos = (v) => `${(v / (CEFR.length - 1)) * 100}%`;
  const now = cefrValue(current);
  const goal = cefrValue(target);
  const step = cefrValue(milestone);
  return h("div.cefrScale", {},
    h("div.cefrTrack", {},
      now != null ? h("i.cefrFill", { style: `width:${pos(now)}` }) : null,
      now != null ? h("span.cefrMarker.current", { style: `left:${pos(now)}`, title: `Зараз: ${current}` }) : null,
      step != null ? h("span.cefrMarker.milestone", { style: `left:${pos(step)}`, title: `Найближча ціль: ${milestone}` }) : null,
      goal != null ? h("span.cefrMarker.target", { style: `left:${pos(goal)}`, title: `Ціль: ${target}` }) : null),
    h("div.cefrLabels", {}, CEFR.map((l) => h("span", {}, l))));
}
