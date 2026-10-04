import { api } from "../api.js";
import { cefrScale, findingRow, fmtDate, h, loading, rich } from "../ui.js";

const lessonsGen = (n) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? "уроку" : "уроків"}`;
const CONFIDENCE = { low: "мало даних", medium: "достатньо даних", high: "багато даних" };

export function assessButton(app, label = "Оцінити рівень") {
  const status = h("span");
  const button = h("button.primaryButton", {
    disabled: !app.state.claude.ok,
    onclick: async () => {
      button.replaceWith(loading("Агент аналізує твої відповіді, це 1–3 хвилини"));
      try {
        await api.assess();
        app.go("#/level");
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      } catch (err) {
        status.replaceChildren(h("div.noticeBanner", { style: "margin:14px 0 0" }, `Не вдалося оцінити: ${err.message}`));
      }
    },
  }, label);
  return h("div", {}, button, status);
}

export default function level(app) {
  const { assessments, profile, newLessonsSinceAssessment: fresh } = app.state;
  const goal = profile.goal || {};
  const latest = [...assessments].reverse().find((a) => a.strengths);
  const regularDone = app.state.lessons.filter((l) => l.status === "done" && l.kind !== "placement" && !l.imported).length;
  const plan = latest?.plan?.slice(regularDone) || [];
  const history = [...assessments].reverse();
  const card = (label, ...content) => h("div.softCard", {}, h("div.sectionLabel", {}, label), content);

  if (!latest) {
    return h("section", {}, h("h1.pageTitle", {}, "Рівень"),
      h("p.pageSubtitle", {}, "Агент оцінить рівень за твоїми реальними відповідями й покаже шлях до цілі."),
      card("Оцінка", assessments[0] ? h("p", {}, `Стартова точка з placement-тесту: ${assessments[0].overall}`) : null,
        h("div.buttonRow", {}, assessButton(app))));
  }

  return h("section", {},
    h("h1.pageTitle", {}, "Рівень"),
    h("p.pageSubtitle", {}, `${latest.source === "placement" ? "Placement-тест" : "Оцінка агента"} від ${fmtDate(latest.assessedAt)} · ${CONFIDENCE[latest.confidence] || ""}`),
    card("Зараз", h("div.goalHeader", { style: "margin-top:14px" },
      h("div", {}, h("div.levelBadge", {}, latest.overall), h("div.levelCaption", {}, "робочий рівень")),
      goal.milestone?.target ? h("div", {}, h("div.levelBadge", { style: "color:var(--g1)" }, goal.milestone.target),
        h("div.levelCaption", {}, `найближча ціль · до ${fmtDate(goal.milestone.deadline)}`)) : null,
      goal.target ? h("div", {}, h("div.levelBadge", { style: "color:var(--muted)" }, goal.target),
        h("div.levelCaption", {}, goal.deadline ? `ціль · до ${fmtDate(goal.deadline, true)}` : "ціль")) : null),
      cefrScale(latest.overall, goal.target, goal.milestone?.target), rich("p", latest.summary)),
    plan.length ? card("Перші уроки", plan.map((p, i) => findingRow(String(regularDone + i + 1), "correct", p.title, p.why)),
      h("div.buttonRow", {}, h("button.primaryButton", { onclick: () => app.go("#/") }, "До першого уроку →"))) : null,
    card("За напрямами", h("div.dimensionGrid", {}, latest.dimensions.map((d) =>
      h("div.dimensionTile", { class: d.measured ? null : "unmeasured" },
        h("span.sectionLabel", {}, d.name), h("b", {}, d.level), d.note ? rich("small", d.note) : null)))),
    h("div.cardGrid", {},
      card("Сильні сторони", latest.strengths.map((p) => findingRow("✓", "correct", p.area, p.text, p.example))),
      card("Слабкі сторони", latest.weaknesses.map((p) => findingRow("✗", "wrong", p.area, p.text, p.example)))),
    card(goal.milestone?.target ? `Шлях до ${goal.milestone.target}` : goal.target ? `Шлях до ${goal.target}` : "Що далі", rich("p", latest.toTarget.summary),
      latest.toTarget.steps.map((s, i) => findingRow(String(i + 1), "minor", s.title, s.text)),
      h("p.pageSubtitle", { style: "margin:14px 0 0" }, "Орієнтовно: ", rich("span", latest.toTarget.eta))),
    card("Прогрес", history.map((a) => h("div.historyLevelRow", {}, h("b", {}, a.overall),
      h("span", {}, fmtDate(a.assessedAt)), h("span.pageSubtitle", { style: "margin:0" },
        a.source === "placement" ? "placement-тест" : `після ${lessonsGen(a.lessonsDone)}`)))),
    h("div.buttonRow", {}, assessButton(app, fresh ? `Оновити оцінку (нових уроків: ${fresh})` : "Оцінити ще раз")));
}
