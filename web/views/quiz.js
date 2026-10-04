import { api } from "../api.js";
import { h, loading, rich } from "../ui.js";
import { micButton, recalled } from "../answer.js";

export default function quiz(app, lessonId) {
  const { gate, words } = app.state;
  const cards = gate.lessonId === lessonId ? gate.words.map((id) => words.find((w) => w.id === id)) : [];
  if (!cards.length) return h("div.noticeBanner", {}, "Для цього уроку квізу немає.");
  const queue = [...cards].sort(() => Math.random() - 0.5);
  const missed = new Set();
  const bar = h("i");
  const slot = h("div.softCard");

  async function finish() {
    slot.replaceChildren(loading("Зберігаю результат"));
    try {
      await api.passQuiz(lessonId, cards.map((w) => ({ wordId: w.id, firstTry: !missed.has(w.id) })));
      app.go("#/");
    } catch (err) {
      slot.replaceChildren(h("div.noticeBanner", {}, `Не вдалося зберегти: ${err.message}`));
    }
  }

  function draw() {
    if (!queue.length) return finish();
    const left = new Set(queue).size;
    bar.style.width = `${((cards.length - left) / cards.length) * 100}%`;
    const w = queue[0];
    const input = h("input.answerInput", { placeholder: "Англійською…", autocomplete: "off",
      onkeydown: (e) => e.key === "Enter" && (e.preventDefault(), check()) });
    const button = h("button.primaryButton", { onclick: () => check() }, "Перевірити ↵");
    async function check() {
      if (!input.value.trim() || input.disabled) return;
      input.disabled = true;
      const row = button.parentElement;
      let verdict = recalled(input.value, w.word) ? { result: "correct" } : null;
      if (!verdict) {
        row.replaceChildren(loading("Перевіряю"));
        verdict = await api.checkRecall(w.id, input.value).catch(() => ({ result: "wrong" }));
      }
      const ok = verdict.result !== "wrong";
      queue.shift();
      if (!ok) { missed.add(w.id); queue.push(w); }
      const next = h("button.primaryButton", { onclick: draw }, "Далі →");
      row.replaceWith(h("div", {},
        h("div.feedbackBox", { class: verdict.result }, h("p", {}, h("b", {}, ok ? "✓ Правильно" : `✗ Правильно: ${w.word}`)),
          verdict.feedback ? rich("p", verdict.feedback) : null,
          h("p", {}, h("i", {}, verdict.corrected || w.example))),
        h("div.buttonRow", {}, next)));
      setTimeout(() => next.focus());
    }
    slot.replaceChildren(h("div.sectionLabel", {}, `Залишилось: ${left}`), h("p.itemPrompt", {}, h("b", {}, w.meaning)),
      w.cloze ? h("p.itemPrompt", {}, w.cloze) : null,
      h("div.quizAnswerRow", {}, input, micButton(input)), h("div.buttonRow", {}, h("div.spacer"), button));
    setTimeout(() => input.focus());
  }

  draw();
  return h("section", {}, h("h1.pageTitle", {}, "Квіз словосполучень"),
    h("p.pageSubtitle", {}, "Надрукуй або скажи фразу англійською. Помилка повертає картку в кінець черги."),
    h("div.drillProgress", {}, bar), slot);
}
