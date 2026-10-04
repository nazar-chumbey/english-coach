import { api } from "../api.js";
import { h } from "../ui.js";

const ROLES = ["Frontend", "Backend", "Full-stack", "Mobile", "QA", "DevOps / SRE", "Data / ML", "PM / BA", "Designer",
  "Tech Lead / Manager", "Інше"];
const SENIORITY = ["Junior", "Middle", "Senior", "Lead"];
const PURPOSES = ["Робота в міжнародній команді", "Співбесіди й нова робота", "Релокація", "Конференції й виступи",
  "Навчання й документація", "Подорожі", "Фільми, книги, подкасти"];
const USAGE = ["Стендапи", "Мітинги й обговорення", "Slack / чати", "Code review", "Jira / тікети", "Документація",
  "Дзвінки з клієнтами", "Презентації", "Співбесіди"];
const HARDEST = ["Граматика", "Словник", "Говоріння", "Письмо", "Слухання", "Розуміти швидку мову"];
const LEVELS = ["A1", "A2", "B1", "B2", "C1", "Не знаю"];
const TARGETS = ["B1", "B1+", "B2", "B2+", "C1"];
const MINUTES = [10, 15, 20, 30];

function chips(options, selected, multi, onChange) {
  const box = h("div.chipGroup");
  const draw = () => box.replaceChildren(...options.map((o) => h("button.choiceChip", {
    class: (multi ? selected.includes(o) : selected[0] === o) ? "picked" : null,
    onclick: () => {
      if (multi) selected.includes(o) ? selected.splice(selected.indexOf(o), 1) : selected.push(o);
      else selected.splice(0, selected.length, o);
      draw();
      onChange?.();
    },
  }, typeof o === "number" ? `${o} хв` : o)));
  draw();
  return box;
}

const field = (label, hint, ...control) => h("div.onboardingField", {},
  h("div.findingArea", {}, label), hint ? h("div.pageSubtitle", { style: "margin:0 0 10px" }, hint) : null, control);

export default function onboarding(app) {
  const a = { role: [], seniority: [], purposes: [], usage: [], hardest: [], selfLevel: [], target: ["B2"], minutes: [15] };
  const text = (placeholder, multiline) => h(multiline ? "textarea.answerInput" : "input.answerInput", { placeholder });
  const name = text("Як до тебе звертатись");
  const otherRole = text("Твоя професія");
  const stack = text("Напр.: React, TypeScript, NX; аналітика в healthcare", true);
  const ownPurpose = text("Своїми словами: що хочеш уміти англійською", true);
  const dreaded = text("Напр.: пояснити менеджеру, чому таска затягується", true);
  const deadline = h("input.answerInput", { type: "date", style: "max-width:200px" });
  const otherRoleWrap = h("div", { style: "margin-top:12px;display:none" }, otherRole);
  const error = h("div");
  let step = 0;
  const root = h("section");

  const steps = [
    ["Про тебе", () => [
      field("Ім'я", null, name),
      field("Професія", "Більшість прикладів у тесті й уроках буде з твоєї роботи.",
        chips(ROLES, a.role, false, () => (otherRoleWrap.style.display = a.role[0] === "Інше" ? "block" : "none")), otherRoleWrap),
      field("Рівень у професії", null, chips(SENIORITY, a.seniority, false)),
      field("Над чим працюєш", "Технології, домен, продукт.", stack),
      field("Для чого тобі англійська", "Можна кілька.", chips(PURPOSES, a.purposes, true), h("div", { style: "margin-top:12px" }, ownPurpose)),
    ]],
    ["Англійська зараз", () => [
      field("Де вживаєш англійську", "Можна кілька.", chips(USAGE, a.usage, true)),
      field("Що найважче", "Можна кілька.", chips(HARDEST, a.hardest, true)),
      field("Як оцінюєш свій рівень", "Тест перевірить, тож точність тут не важлива.", chips(LEVELS, a.selfLevel, false)),
    ]],
    ["Ціль", () => [
      field("Якого рівня хочеш досягти", null, chips(TARGETS, a.target, false)),
      field("До якої дати", "Необов'язково. Агент скаже, чи це реально.", deadline),
      field("Яка розмова англійською напружує найбільше", "Та, яку прокручуєш у голові заздалегідь. З неї почнемо.", dreaded),
      field("Скільки часу на урок", null, chips(MINUTES, a.minutes, false)),
    ]],
  ];

  async function submit() {
    const role = a.role[0] === "Інше" ? otherRole.value.trim() : a.role[0];
    const purpose = [...a.purposes, ownPurpose.value.trim()].filter(Boolean).join("; ");
    await api.onboard({
      name: name.value.trim(), role: [role, a.seniority[0]].filter(Boolean).join(", "), stack: stack.value.trim(),
      usage: a.usage, hardest: a.hardest, selfLevel: a.selfLevel[0] || "Не знаю", dreaded: dreaded.value.trim(),
      minutes: a.minutes[0], goal: { target: a.target[0], purpose, deadline: deadline.value },
    });
    app.startPlacement();
  }

  function draw() {
    const [title, body] = steps[step];
    const last = step === steps.length - 1;
    root.replaceChildren(
      h("h1.pageTitle", {}, "Знайомство"),
      h("p.pageSubtitle", {}, `Крок ${step + 1} з ${steps.length} · потім placement-тест на 20–30 хвилин`),
      h("div.lessonProgress", {}, h("i", { style: `width:${((step + 1) / steps.length) * 100}%` })),
      h("div.softCard", {}, h("div.sectionLabel", {}, title), body(), error,
        h("div.buttonRow", {},
          step ? h("button.softButton", { onclick: () => { step--; draw(); } }, "← Назад") : null,
          h("div.spacer"),
          h("button.primaryButton", {
            onclick: () => {
              if (step === 0 && (!name.value.trim() || !a.role.length)) {
                error.replaceChildren(h("div.noticeBanner", { style: "margin:16px 0 0" }, "Вкажи ім'я і професію."));
                return;
              }
              error.replaceChildren();
              if (last) submit(); else { step++; draw(); }
            },
          }, last ? "Почати тест →" : "Далі →"))));
  }

  draw();
  return root;
}
