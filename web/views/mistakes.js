import { chip, h, rich } from "../ui.js";

const FILTERS = [["all", "Усі"], ["mistake", "Помилки"], ["grammar", "Граматика"], ["vocab", "Слова"]];
const ORDER = { weak: 0, improving: 1, stable: 2, mastered: 3 };
const UNDERSTANDING = { none: "не розумієш правило", partial: "розумієш частково", solid: "правило зрозуміле" };

function skillCard(app, skill) {
  const meta = [skill.count ? `${skill.count}× трапилось` : null, UNDERSTANDING[skill.understanding],
    skill.due ? `повторити ${skill.due}` : null,
    app.state.drills[skill.id] ? `тренажер: сходинка ${app.state.drills[skill.id].level} з 5` : null].filter(Boolean).join(" · ");
  return h("div.softCard", {},
    h("div.skillHeader", {}, h("h3", {}, skill.title || skill.id), chip(skill.status)),
    h("div.skillMeta", {}, meta),
    skill.examples?.length ? h("div.skillExamples", {}, skill.examples.map((e) =>
      h("div", {}, h("span.wrongSentence", {}, e.wrong), " → ", h("span.rightSentence", {}, e.right)))) : null,
    skill.notes ? h("details", { style: "margin-top:14px" }, h("summary", {}, "Нотатки коуча"),
      rich("p.pageSubtitle", skill.notes, { style: "margin:8px 0 0" })) : null,
    h("div.buttonRow", {}, h("button.primaryButton", {
      disabled: !app.state.claude.ok, onclick: () => app.go(`#/drill/${skill.id}`),
    }, "Тренажер"), h("button.softButton", {
      disabled: !app.state.claude.ok || Boolean(app.pending),
      onclick: () => app.startLesson(10, skill.id),
    }, "Потренувати це · 10 хв")));
}

export default function mistakes(app) {
  let filter = "all";
  const list = h("div");
  const sorted = [...app.state.skills].sort((a, b) =>
    (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9) || (b.count || 0) - (a.count || 0));
  const control = h("div.segmentedControl", { style: "margin-bottom:28px" });

  function draw() {
    control.replaceChildren(...FILTERS.map(([key, label]) => h("button.segmentOption", {
      class: key === filter ? "active" : null, onclick: () => { filter = key; draw(); },
    }, label)));
    const shown = sorted.filter((s) => filter === "all" || s.kind === filter);
    list.replaceChildren(...(shown.length ? shown.map((s) => skillCard(app, s)) : [h("div.emptyState", {}, "Тут поки порожньо.")]));
  }

  draw();
  return h("section", {}, h("h1.pageTitle", {}, "Тренажер"),
    h("p.pageSubtitle", {}, "Твої слабкі місця і тренажер на кожне: від простого речення по частинах до сказаного вголос."),
    control, list);
}
