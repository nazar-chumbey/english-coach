import { api } from "../api.js";
import { h } from "../ui.js";

const MODELS = [["opus", "Opus — найкраща якість"], ["sonnet", "Sonnet — швидше"], ["haiku", "Haiku — найдешевше"]];
const TASKS = [["generate", "Генерація уроку"], ["check", "Перевірка відповідей"], ["review", "Розбір уроку"],
  ["assess", "Оцінка рівня"]];
const LEVELS = ["A2", "B1", "B1+", "B2", "B2+", "C1"];

export default function settings(app) {
  const current = app.state.profile.settings;
  const goal = app.state.profile.goal || {};
  const milestone = { ...(goal.milestone || {}) };
  const saveMilestone = (change) => save({ goal: { milestone: Object.assign(milestone, change) } });
  const saved = h("span.pageSubtitle", { style: "margin:0" });
  const save = async (changes) => {
    await api.settings(changes);
    saved.textContent = "Збережено ✓";
    setTimeout(() => (saved.textContent = ""), 1500);
  };
  const select = (options, value, onchange) => h("select.softSelect", { onchange: (e) => onchange(e.target.value) },
    options.map(([v, label]) => h("option", { value: v, selected: v === value || v === String(value) }, label)));

  return h("section", {},
    h("h1.pageTitle", {}, "Налаштування"), h("p.pageSubtitle", {}, "Тема перемикається вгорі праворуч."),
    h("div.softCard", {},
      h("div.formRow", {}, h("span", {}, "Ім'я"),
        h("input.answerInput", { value: app.state.profile.name || "", placeholder: "Як до тебе звертатись", style: "max-width:260px",
          onchange: (e) => save({ name: e.target.value }) })),
      h("div.formRow", {}, h("span", {}, "Головна ціль"),
        select([["", "—"], ...LEVELS.map((l) => [l, l])], goal.target || "", (v) => save({ goal: { target: v } }))),
      h("div.formRow", {}, h("span", {}, "Найближча ціль"),
        h("div", { style: "display:flex;gap:12px" },
          select([["", "—"], ...LEVELS.map((l) => [l, l])], milestone.target || "", (v) => saveMilestone({ target: v })),
          h("input.answerInput", { type: "date", value: milestone.deadline || "", style: "max-width:180px",
            onchange: (e) => saveMilestone({ deadline: e.target.value }) }))),
      h("div.formRow", {}, h("span", {}, "Для чого тобі англійська"),
        h("textarea.answerInput", { style: "max-width:420px;min-height:80px", placeholder: "Напр.: впевнено говорити на стендапі",
          onchange: (e) => save({ goal: { purpose: e.target.value.trim() } }) }, goal.purpose || "")),
      h("div.formRow", {}, h("span", {}, "Дедлайн головної цілі"),
        h("input.answerInput", { type: "date", value: goal.deadline || "", style: "max-width:200px",
          onchange: (e) => save({ goal: { deadline: e.target.value } }) })),
      h("div.formRow", {}, h("span", {}, "Тривалість уроку за замовчуванням"),
        select([10, 15, 20, 30].map((m) => [m, `${m} хв`]), current.defaultMinutes,
          (v) => save({ defaultMinutes: Number(v) }))),
      TASKS.map(([task, label]) => h("div.formRow", {}, h("span", {}, label),
        select(MODELS, current.models[task], (v) => save({ models: { [task]: v } }))))),
    saved, version());
}

function version() {
  const line = h("p.pageSubtitle", { style: "margin-top:24px" });
  api.ping().then((p) => { line.textContent = `Версія ${p.version}`; });
  return line;
}
