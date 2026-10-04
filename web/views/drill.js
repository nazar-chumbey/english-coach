import { api } from "../api.js";
import { h, loading, rich } from "../ui.js";
import { micButton, norm } from "../answer.js";

const LEVELS = { 1: "Розбери", 2: "По частинах", 3: "Разом", 4: "Складніше", 5: "Скажи" };
const TRIES = 3;
const shuffle = (list) => list.map((v) => [Math.random(), v]).sort((a, b) => a[0] - b[0]).map(([, v]) => v);
const tidy = (text) => text.replace(/\s+([,.?!])/g, "$1").replace(/\s+/g, " ").trim();

function pieces(pattern, ex) {
  let slot = 0;
  return pattern.parts.map((p) => (p.kind === "fixed" ? p.text : ex.slots[slot++] || "").trim()).filter(Boolean);
}

function patternView(pattern, faded) {
  return h("div.drillPatternRow", { class: faded ? "faded" : null }, pattern.parts.map((p) => p.kind === "fixed"
    ? h("span.drillFixedPart", {}, p.text)
    : h("span.drillSlotPart", { title: p.hint }, p.label)));
}

export default function drill(app, skillId) {
  const skill = app.state.skills.find((s) => s.id === skillId);
  if (!skill) return h("div.noticeBanner", {}, "Такої навички немає.");
  const root = h("section", {}, h("h1.pageTitle", {}, `Тренажер: ${skill.title || skill.id}`));
  const body = h("div.softCard", {}, loading("Claude готує речення під тебе, до хвилини"));
  root.append(body);

  api.drill(skillId).then(run).catch((err) => body.replaceChildren(h("div.noticeBanner", {}, `Не вдалося підготувати: ${err.message}`)));

  function run(session) {
    const { pattern, exercises, start } = session;
    const state = { level: start, tries: 0, levels: [], clean: true, answers: [] };
    root.append(h("div.softCard", {}, h("div.sectionLabel", {}, "Структура"), patternView(pattern), rich("p.hintBox", session.explanation)));
    root.append(body);

    function next(ok) {
      if (ok) {
        state.levels.push(state.level);
        state.level++;
        state.tries = 0;
      } else {
        state.tries++;
        if (state.level >= 4) state.clean = false;
      }
      const exercise = exercises.filter((e) => e.level === state.level)[state.tries];
      return state.level > 5 || !exercise ? done(state.level > 5) : draw(exercise);
    }

    async function done(passed) {
      body.replaceChildren(loading("Зберігаю"));
      const gate = await api.finishDrill(skillId, { start, levels: state.levels, passed, clean: state.clean, answers: state.answers });
      const counted = gate.drill?.skillId === skillId ? ` Для пропуску до уроку: ${Math.min(gate.drill.done, gate.drill.required)} з ${gate.drill.required}.` : "";
      body.replaceChildren(h("h2", {}, passed ? "Сесію пройдено ✓" : "Цього разу не вийшло"),
        h("p", {}, passed ? `Усі сходинки пройдено.${counted}` : `Три помилки на сходинці «${LEVELS[state.level]}». Нова сесія дасть нові речення.`),
        h("div.buttonRow", {}, h("button.softButton", { onclick: () => app.go("#/") }, "На головну"), h("div.spacer"),
          h("button.primaryButton", { onclick: () => app.go(`#/drill/${skillId}?${Date.now()}`) }, "Ще сесія →")));
    }

    function verdictView(exercise, verdict, onNext) {
      const ok = verdict.result !== "wrong";
      const next = h("button.primaryButton", { onclick: onNext }, "Далі →");
      setTimeout(() => next.focus());
      return h("div", {}, h("div.feedbackBox", { class: verdict.result },
        h("p", {}, h("b", {}, { correct: "✓ Правильно", minor: "≈ Майже, зараховано" }[verdict.result] || "✗ Ще не так")), verdict.feedback ? rich("p", verdict.feedback) : null,
        h("p", {}, h("i", {}, verdict.corrected || exercise.answer))), h("div.buttonRow", {}, h("div.spacer"), next));
    }

    async function judge(exercise, text, local, slot) {
      state.answers.push(exercise.answer);
      let verdict = local ? { result: "correct" } : null;
      if (!verdict) {
        slot.replaceChildren(loading("Перевіряю"));
        verdict = await api.checkDrill(skillId, exercise, pattern, text).catch((err) => ({ result: "wrong", feedback: `Не вдалося перевірити: ${err.message}` }));
      }
      slot.replaceChildren(verdictView(exercise, verdict, () => next(verdict.result !== "wrong")));
    }

    function draw(exercise) {
      const level = state.level;
      const slot = h("div");
      const head = h("div.buttonRow", { style: "margin:0 0 12px" }, h("span.sectionLabel", {}, `Сходинка ${level} з 5 · ${LEVELS[level]}`),
        h("div.spacer"), state.tries ? h("span.skillMeta", {}, `спроба ${state.tries + 1} з ${TRIES}`) : null);
      const content = h("p.itemPrompt", {}, h("b", {}, exercise.content));
      const check = (fn) => h("button.primaryButton", { onclick: fn }, "Перевірити");

      if (level === 1) {
        const expected = pieces(pattern, exercise);
        const bank = shuffle(expected.map((text) => ({ text, used: false })));
        const picked = [];
        const line = h("div.drillAssembledLine");
        const pool = h("div.drillPieceBank");
        const answer = () => picked.map((p) => p.text).join(" ");
        const button = check(() => judge(exercise, tidy(answer()), answer() === expected.join(" "), slot));
        const redraw = () => {
          line.replaceChildren(...picked.map((p, i) => h("button.drillPieceButton", { onclick: () => { p.used = false; picked.splice(i, 1); redraw(); } }, p.text)));
          pool.replaceChildren(...bank.filter((p) => !p.used).map((p) => h("button.drillPieceButton", { onclick: () => { p.used = true; picked.push(p); redraw(); } }, p.text)));
          button.disabled = picked.length !== expected.length;
        };
        redraw();
        slot.append(h("div.buttonRow", {}, h("div.spacer"), button));
        return body.replaceChildren(head, content, h("p.hintBox", {}, "Натискай частини по порядку. Натиснеш на зібрану — повернеться назад."), line, pool, slot);
      }

      if (level === 2) {
        let index = 0;
        const inputs = [];
        const row = h("div.drillSlotsRow", {}, pattern.parts.map((p) => {
          if (p.kind === "fixed") return h("span.drillFixedPart", {}, p.text);
          const input = h("input.answerInput", { placeholder: "…", autocomplete: "off" });
          inputs.push([input, exercise.slots[index++] || ""]);
          return h("label.drillSlotField", {}, h("span.drillSlotLabel", {}, p.label), h("small", {}, p.hint), input);
        }));
        const submit = () => {
          if (inputs.some(([i]) => !i.value.trim())) return;
          let k = 0;
          const text = tidy(pattern.parts.map((p) => (p.kind === "fixed" ? p.text : inputs[k++][0].value)).join(" "));
          judge(exercise, text, inputs.every(([i, want]) => norm(i.value) === norm(want)), slot);
        };
        slot.append(h("div.buttonRow", {}, h("div.spacer"), check(submit)));
        body.replaceChildren(head, content, row, slot);
        return setTimeout(() => inputs[0]?.[0].focus());
      }

      const input = h("textarea.answerInput", { placeholder: level === 5 ? "Натисни 🎤 і скажи речення…" : "Речення англійською…",
        onkeydown: (e) => e.key === "Enter" && (e.metaKey || e.ctrlKey) && submit() });
      const submit = () => input.value.trim() && judge(exercise, input.value, norm(input.value) === norm(exercise.answer), slot);
      slot.append(h("div.buttonRow", {}, h("div.spacer"), check(submit)));
      body.replaceChildren(head, level === 3 ? patternView(pattern, true) : null, content,
        h("div.quizAnswerRow", {}, input, micButton(input)), slot);
      setTimeout(() => input.focus());
    }

    draw(exercises.filter((e) => e.level === start)[0]);
  }

  return root;
}
