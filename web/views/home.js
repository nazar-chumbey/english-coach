import { cefrScale, fmtDate, h, loading, rich } from "../ui.js";
import { assessButton } from "./level.js";
import { api } from "../api.js";
import { rerender } from "../app.js";

const WEIGHT = { weak: 0.1, improving: 0.45, stable: 0.8, mastered: 1 };
const AREAS = [
  ["grammar", "Граматика", "#8FD3E8,#5FA8D8"],
  ["mistake", "Помилки", "#C7B5F5,#9A86E8"],
  ["vocab", "Слова", "#F4A9C0,#E77FA0"],
];
const MINUTES = [10, 15, 20, 30];

const progress = (skills) => skills.length ? skills.reduce((sum, s) => sum + (WEIGHT[s.status] ?? 0), 0) / skills.length : 0;

function durationPicker(value, onPick) {
  const control = h("div.segmentedControl", {});
  for (const m of MINUTES) {
    const button = h("button.segmentOption", {
      class: m === value ? "active" : null,
      onclick: () => {
        control.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === button));
        onPick(m);
      },
    }, `${m} хв`);
    control.append(button);
  }
  return control;
}

function startCard(app, placement) {
  if (app.pending) return h("div.softCard", {}, h("div.sectionLabel", {}, "Готуємо"), h("div", { style: "margin-top:14px" }, loading(app.pendingMessage)),
    app.error ? h("div.noticeBanner", {}, app.error) : null);
  const onboarded = Boolean(app.state.profile.onboardedAt);
  return h("div.softCard", {},
    h("div.sectionLabel", {}, onboarded ? "Крок 2 з 2" : "Крок 1 з 2"),
    h("h2", { style: "font-weight:400" }, onboarded ? "Placement-тест" : "Знайомство"),
    h("p.pageSubtitle", {}, onboarded
      ? "~48 завдань, 20–30 хвилин. Підказок немає: це діагностика, і «Не знаю» теж корисна відповідь. Потім агент покаже твій рівень і план перших уроків."
      : "5 хвилин про тебе, твою роботу і ціль. Потім тест визначить рівень, і уроки будуються під тебе."),
    app.error ? h("div.noticeBanner", {}, app.error) : null,
    placement
      ? h("button.primaryButton", { onclick: () => app.go(`#/lesson/${placement.id}`) }, `Продовжити тест (${placement.answered} з ${placement.total}) →`)
      : h("button.primaryButton", {
          disabled: !app.state.claude.ok,
          onclick: () => (onboarded ? app.startPlacement() : app.go("#/onboarding")),
        }, onboarded ? "Почати тест →" : "Почати →"));
}

function goalCard(app) {
  const { profile, assessments, newLessonsSinceAssessment: fresh } = app.state;
  const goal = profile.goal || {};
  const latest = assessments.at(-1);
  if (!goal.target && !latest) return null;
  const detailed = Boolean(latest?.strengths);
  const current = latest?.overall;
  const stale = detailed && fresh > 0;
  return h("div.softCard", {},
    h("div.sectionLabel", {}, "Мета"),
    h("div.goalHeader", { style: "margin-top:14px" },
      current ? h("div", {}, h("div.levelBadge", {}, current),
        h("div.levelCaption", {}, `${latest.source === "agent" ? "оцінка агента" : "placement-тест"} · ${fmtDate(latest.assessedAt)}`)) : null,
      goal.milestone?.target ? h("div", {}, h("div.levelBadge", { style: "color:var(--g1)" }, `→ ${goal.milestone.target}`),
        h("div.levelCaption", {}, `${goal.milestone.focus ? "у розмові · " : ""}до ${fmtDate(goal.milestone.deadline)}`)) : null,
      goal.target ? h("div", {}, h("div.levelBadge", { style: "color:var(--muted)" }, `→ ${goal.target}`),
        h("div.levelCaption", {}, goal.deadline ? `до ${fmtDate(goal.deadline, true)}` : "ціль")) : null,
      goal.purpose ? rich("div.goalPurpose", goal.purpose) : null),
    cefrScale(current, goal.target, goal.milestone?.target),
    h("div.buttonRow", {},
      detailed
        ? h("p.pageSubtitle", { style: "margin:0" }, stale ? `Після оцінки пройдено уроків: ${fresh}. Варто оновити.` : "Оцінка актуальна.")
        : h("p.pageSubtitle", { style: "margin:0" }, "Агент ще не оцінював рівень за уроками."),
      h("div.spacer"),
      detailed ? h("button.softButton", { onclick: () => app.go("#/level") }, "Детальніше →") : assessButton(app)));
}

function nextLessonCard(app, lessons) {
  const settings = app.state.profile.settings;
  let minutes = settings.defaultMinutes;
  const focus = lessons.find((l) => l.status === "done" && l.nextLesson)?.nextLesson;
  const body = app.pending
    ? loading(app.pendingMessage)
    : h("div.buttonRow", {},
        durationPicker(minutes, (m) => (minutes = m)),
        h("div.spacer"),
        h("button.primaryButton", {
          disabled: !app.state.claude.ok || !app.state.gate.ready,
          title: !app.state.gate.ready ? "Спершу пройди чекліст вище" : app.state.claude.ok ? null : app.state.claude.message,
          onclick: () => app.startLesson(minutes),
        }, "Згенерувати урок"));
  return h("div.softCard", {},
    h("div.sectionLabel", {}, "Наступний урок"),
    focus ? rich("p", focus) : h("p.pageSubtitle", {}, "Урок складеться з твоїх помилок і того, що пора повторити."),
    app.error ? h("div.noticeBanner", {}, `Не вдалося згенерувати: ${app.error}`) : null,
    body);
}

const EMPTY_NOTES = "Спершу напиши, що помітив або чому пропускаєш";

function gateCard(app) {
  const { gate } = app.state;
  if (gate.ready) return null;
  const row = (ok, label, action) => h("div.gateChecklistRow", {},
    h("span.verdictIcon", { class: ok ? "correct" : null }, ok ? "✓" : "○"), label, h("div.spacer"), ok ? null : action);
  const notes = h("textarea.answerInput", { placeholder: "Зроблено: що помітив (2–3 приклади). Пропуск: чому.",
    oninput: () => buttons.forEach((b) => { b.disabled = !notes.value.trim(); b.title = b.disabled ? EMPTY_NOTES : ""; }) });
  const error = h("div");
  const send = (status) => api.homework(gate.lessonId, status, notes.value).then(rerender)
    .catch((err) => error.replaceChildren(h("div.noticeBanner", {}, `Не вдалося зберегти: ${err.message}`)));
  const buttons = [h("button.softButton", { onclick: () => send("skipped") }, "Пропустити"),
    h("button.primaryButton", { onclick: () => send("done") }, "Зроблено")];
  buttons.forEach((b) => Object.assign(b, { disabled: true, title: EMPTY_NOTES }));
  return h("div.softCard", {},
    h("div.sectionLabel", {}, "Пропуск до уроку"),
    row(gate.quiz, h("div", {}, `Квіз: ${gate.words.length} словосполучень з минулого уроку`),
      h("button.primaryButton", { onclick: () => app.go(`#/quiz/${gate.lessonId}`) }, "Пройти →")),
    row(!gate.dueChunks, h("div", {}, gate.dueChunks ? `Повторити словосполучення: ${gate.dueChunks}` : "Повторення словосполучень"),
      h("button.softButton", { onclick: () => app.go("#/words") }, "До словника →")),
    gate.drill ? row(gate.drill.done >= gate.drill.required, h("div", {}, `Тренажер «${gate.drill.title}»: ${Math.min(gate.drill.done, gate.drill.required)} з ${gate.drill.required} сесій`),
      h("button.primaryButton", { onclick: () => app.go(`#/drill/${gate.drill.skillId}`) }, "Пройти →")) : null,
    gate.recommendation ? [row(Boolean(gate.homework), rich("div", gate.recommendation), null),
      gate.homework ? null : h("div", {}, notes, error, h("div.buttonRow", {}, buttons[0], h("div.spacer"), buttons[1]))] : null);
}

function statsCards(skills, lessons) {
  const pct = Math.round(progress(skills) * 100);
  const today = new Date().toISOString().slice(0, 10);
  const ring = h("div.progressRing", {
    style: `background: conic-gradient(var(--g1) 0, var(--g2) ${pct}%, var(--track) ${pct}% 100%)`,
  }, h("div", {}, `${pct}%`));
  const bars = h("div.skillBars", {}, AREAS.map(([kind, label, colors]) => {
    const group = skills.filter((s) => s.kind === kind);
    const value = Math.round(progress(group) * 100);
    return h("div.skillBar", {},
      h("div.barTrack", {}, h("div.barFill", { style: `height:${Math.max(value, 6)}%;background:linear-gradient(${colors})` })),
      label, h("br"), group.length ? `${value}%` : "—");
  }));
  const done = lessons.filter((l) => l.status === "done");
  return h("div.cardGrid", {},
    h("div.softCard", {}, h("div.sectionLabel", {}, "Прогрес навичок"), ring,
      h("p.pageSubtitle", { style: "text-align:center;margin:0" }, `${skills.length} навичок у пам'яті`)),
    h("div.softCard", {}, h("div.sectionLabel", {}, "За напрямами"), h("div", { style: "height:14px" }), bars),
    h("div.softCard", {}, h("div.sectionLabel", {}, "Статистика"), h("div", { style: "height:14px" }),
      h("div.statPills", {},
        h("div.statPill", {}, h("b", {}, done.length), h("span", {}, "уроків")),
        h("div.statPill", {}, h("b", {}, skills.filter((s) => s.status === "weak").length), h("span", {}, "слабких місць")),
        h("div.statPill", {}, h("b", {}, skills.filter((s) => s.due && s.due <= today && s.status !== "mastered").length),
          h("span", {}, "на повторення")))));
}

export default function home(app) {
  const { skills, lessons, claude, profile } = app.state;
  const inProgress = lessons.find((l) => l.status === "in_progress" && l.kind !== "placement");
  const placementDone = lessons.some((l) => l.kind === "placement" && l.status === "done") || lessons.some((l) => l.imported);
  const placement = lessons.find((l) => l.kind === "placement" && l.status === "in_progress");
  if (!placementDone) {
    return h("section", {},
      h("h1.pageTitle", {}, profile.name ? `Привіт, ${profile.name}` : "Привіт"),
      h("p.pageSubtitle", {}, "IT English, під тебе."),
      claude.ok ? null : h("div.noticeBanner", {}, claude.message),
      startCard(app, placement));
  }
  return h("section", {},
    h("h1.pageTitle", {}, profile.name ? `Привіт, ${profile.name}` : "Привіт"),
    h("p.pageSubtitle", {}, "IT English, під тебе."),
    claude.ok ? null : h("div.noticeBanner", {}, claude.message),
    goalCard(app),
    inProgress ? h("div.softCard", {},
      h("div.sectionLabel", {}, "Незавершений урок"),
      h("h3", {}, inProgress.topic),
      h("p.pageSubtitle", {}, `Відповідей: ${inProgress.answered} з ${inProgress.total}`),
      h("button.primaryButton", { onclick: () => app.go(`#/lesson/${inProgress.id}`) }, "Продовжити →")) : null,
    gateCard(app),
    nextLessonCard(app, lessons),
    statsCards(skills, lessons));
}
