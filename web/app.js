import { api } from "./api.js";
import { h } from "./ui.js";
import home from "./views/home.js";
import lesson from "./views/lesson.js";
import history from "./views/history.js";
import mistakes from "./views/mistakes.js";
import settings from "./views/settings.js";
import level from "./views/level.js";
import onboarding from "./views/onboarding.js";
import words from "./views/words.js";
import quiz from "./views/quiz.js";
import drill from "./views/drill.js";
import { attachWordPicker } from "./wordPicker.js";

const routes = [
  [/^#?\/?$/, home, "#/"],
  [/^#\/lesson\/([\w-]+)$/, lesson, null],
  [/^#\/history$/, history, "#/history"],
  [/^#\/mistakes$/, mistakes, "#/mistakes"],
  [/^#\/level$/, level, "#/level"],
  [/^#\/words$/, words, "#/words"],
  [/^#\/quiz\/([\w-]+)$/, quiz, null],
  [/^#\/drill\/([\w-]+)(?:\?\d+)?$/, drill, "#/mistakes"],
  [/^#\/onboarding$/, onboarding, null],
  [/^#\/settings$/, settings, "#/settings"],
];

export const app = {
  state: null,
  pending: null,
  error: null,
  async refresh() {
    this.state = await api.state();
    return this.state;
  },
  go(hash) {
    location.hash = hash;
  },
  startPlacement() {
    return this.run(api.placement(), "Claude складає placement-тест під твою роль, це 2–3 хвилини");
  },
  startLesson(minutes, focusSkill) {
    return this.run(api.generate(minutes, focusSkill), "Claude складає урок під тебе, це до 2 хвилин");
  },
  async run(request, message) {
    this.pending = request;
    this.pendingMessage = message;
    this.error = null;
    this.go("#/");
    render();
    try {
      const created = await this.pending;
      this.go(`#/lesson/${created.id}`);
      this.pending = null;
    } catch (err) {
      this.pending = null;
      this.error = err.message;
      render();
    }
  },
};

const view = document.getElementById("view");
attachWordPicker(view, () => location.hash.match(/^#\/lesson\/([\w-]+)/)?.[1]);

async function render() {
  const [[, fn, tab], match] = routes.map((r) => [r, location.hash.match(r[0])]).find(([, m]) => m) || [routes[0], []];
  const params = match.slice(1);
  document.querySelectorAll(".navTab").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === tab));
  try {
    await app.refresh();
    const node = await fn(app, ...params);
    view.replaceChildren(node);
  } catch (err) {
    view.replaceChildren(h("div.noticeBanner", {}, `Помилка: ${err.message}`));
  }
}

function applyTheme(choice) {
  localStorage.setItem("theme", choice);
  const dark = choice === "dark" || (choice === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.querySelectorAll(".themeOption").forEach((b) => b.classList.toggle("active", b.dataset.theme === choice));
}

document.getElementById("themeSwitch").addEventListener("click", (e) => {
  if (e.target.dataset.theme) applyTheme(e.target.dataset.theme);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => applyTheme(localStorage.getItem("theme") || "auto"));
applyTheme(localStorage.getItem("theme") || "auto");

export const rerender = render;
const ping = () => fetch("/api/ping").catch(() => {});
ping();
setInterval(ping, 30000);
window.addEventListener("hashchange", render);
render();
