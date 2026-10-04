import { api } from "../api.js";
import { chip, correctionList, findingRow, fmtDate, h, loading, rich } from "../ui.js";
import { norm } from "../answer.js";

const SECTION = { review: "Повторення", grammar: "Граматика", vocabulary: "Словосполучення", practice: "Практика",
  situation: "Робоча ситуація", test: "Міні-тест", reflection: "Рефлексія", writing: "Письмо", understanding: "Розуміння" };
const AI_TYPES = ["write", "explain"];
const DONT_KNOW = "не знаю";

function feedback(item, r) {
  if (!r || r.result === "noted") return r ? h("p.hintBox", {}, "Записано ✓") : null;
  const lines = [];
  if (r.ai) {
    lines.push(rich("p", r.feedback));
    if (r.corrected) lines.push(h("p", {}, "Природніше: ", h("b", {}, r.corrected)));
    if (r.corrections?.length) lines.push(correctionList(r.corrections));
  } else if (r.result === "correct") {
    lines.push(h("p", {}, h("b", {}, "✓ Правильно")), rich("p", item.why));
  } else if (r.result === "wrong") {
    lines.push(h("p", {}, h("b", {}, "✗ Правильно: "), item.accept[0]), rich("p", item.why));
  } else if (r.result === "mismatch") {
    lines.push(h("p", {}, h("b", {}, "Не збігається з очікуваним: "), item.accept.join(" / ")), rich("p", item.why));
  }
  return h("div.feedbackBox", { class: r.result }, lines);
}

function answerControl(item, response, submit, placement, draft) {
  const done = Boolean(response) && !placement;
  if (item.type === "choice" || item.type === "confidence") {
    const options = item.type === "confidence" ? ["1", "2", "3", "4", "5"] : item.options;
    return h(item.type === "confidence" ? "div.confidenceScale" : "div.choiceList", {}, options.map((o) =>
      h("button.choiceOption", { class: response?.text === o ? "picked" : null, disabled: done, onclick: () => submit(o) }, o))
      .concat(placement && item.type === "choice" ? [h("button.choiceOption", { class: response?.text === DONT_KNOW ? "picked" : null, onclick: () => submit(DONT_KNOW) }, "Не знаю")] : []));
  }
  const multiline = AI_TYPES.includes(item.type);
  const chips = (item.useChunks || []).map((c) => {
    const el = h("button.useChunkChip", { title: "Показати англійською", onclick: () => { el.textContent = c.chunk; } }, c.meaning);
    return [el, c];
  });
  const mark = () => chips.forEach(([el, c]) => {
    if (!` ${norm(input.value)} `.includes(` ${norm(c.chunk)} `)) return el.classList.remove("used");
    el.classList.add("used");
    el.textContent = `✓ ${c.chunk}`;
  });
  const input = h(multiline ? "textarea.answerInput" : "input.answerInput", {
    disabled: done, placeholder: multiline ? "Пиши англійською (для пояснення можна українською)…" : "Твоя відповідь…",
    value: draft ?? (item.type === "fix" && !done ? item.prompt : null),
    oninput: mark,
    onkeydown: (e) => {
      if (e.key === "Enter" && (!multiline || e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); }
    },
  });
  if (response && response.text !== DONT_KNOW) input.value = response.text;
  mark();
  const facts = item.facts ? h("div.insetPanel.situationFactsPanel", {}, h("div.sectionLabel", {}, "Що пояснити"), rich("p", item.facts)) : null;
  const useRow = chips.length ? h("div.useChunksRow", {}, h("span.sectionLabel", {}, "Використай"), chips.map(([el]) => el)) : null;
  const model = item.model && !done ? h("div.insetPanel.modelAnswerPanel", { hidden: true }, rich("p", item.model),
    h("button.softButton", { onclick: () => { model.hidden = true; input.focus(); } }, "Сховати й написати самому")) : null;
  const send = () => input.value.trim() && submit(input.value.trim());
  const hint = item.hint ? h("details.hintBox", {}, h("summary", {}, "Підказка"), rich("p", item.hint)) : null;
  const label = placement ? "Відповісти" : "Перевірити";
  return h("div", {}, facts, useRow, input, hint, model, done ? null : h("div.buttonRow", {},
    model ? h("button.softButton", { onclick: () => { model.hidden = false; } }, "Застряг") : null,
    h("button.softButton", { onclick: send }, multiline ? `${label} (⌘↵)` : `${label} (↵)`),
    placement ? h("button.softButton", { onclick: () => submit(DONT_KNOW) }, "Не знаю") : null));
}

const VERDICT = { good: ["✓", "correct"], mixed: ["≈", "minor"], weak: ["✗", "wrong"] };

export function reviewView(lesson) {
  const r = lesson.review || {};
  const block = (label, ...content) => content.some(Boolean) ? h("div.softCard", {}, h("div.sectionLabel", {}, label), content) : null;
  const u = typeof r.understanding === "string" ? { comment: r.understanding } : r.understanding || {};
  const answers = (lesson.items || []).filter((i) => lesson.responses?.[i.id]).map((item) => {
    const resp = lesson.responses[item.id];
    return h("div.insetPanel", { style: "margin-bottom:14px" },
      h("div.itemMeta", {}, h("span.sectionLabel", {}, SECTION[item.section] || item.section), chip(resp.result)),
      rich("p", item.prompt), h("p", {}, h("b", {}, "Ти: "), resp.text), feedback(item, resp));
  });
  return h("section", {},
    h("h1.pageTitle", {}, lesson.topic),
    h("p.pageSubtitle", {}, `${fmtDate(lesson.createdAt)} · ${lesson.minutes ? `${lesson.minutes} хв · ` : ""}результат ${lesson.score || "—"}`),
    block("Підсумок", r.summary && rich("p.reviewHeadline", r.summary),
      r.findings?.length && h("div", {}, r.findings.map((f) => findingRow(...(VERDICT[f.verdict] || VERDICT.mixed), f.area, f.text, f.example)))),
    block("Що покращилось", r.improved?.length && h("div", {}, r.improved.map((t) => findingRow("✓", "correct", null, t)))),
    block("Головні виправлення", r.corrections?.length && correctionList(r.corrections)),
    block("Розуміння правила", u.quote && h("blockquote.learnerQuote", {}, u.quote), u.comment && rich("p", u.comment)),
    block("Наступного разу", r.nextLesson && rich("p", r.nextLesson)),
    block("До наступного уроку", r.recommendation && rich("p", r.recommendation)),
    answers.length ? h("details.softCard", {}, h("summary", {}, `Усі відповіді (${answers.length})`),
      h("div", { style: "margin-top:16px" }, answers)) : null,
    h("div.buttonRow", {}, h("a.softButton", { href: "#/", style: "text-decoration:none" }, "← На головну")));
}

export default async function lessonView(app, id) {
  const lesson = await api.lesson(id);
  if (lesson.status === "done") return reviewView(lesson);

  const items = lesson.items;
  const placement = lesson.kind === "placement";
  const steps = [{ kind: "intro" }, ...(placement ? [] : [{ kind: "explanation" }]), ...(lesson.chunks?.length ? [{ kind: "chunks" }] : []),
    ...items.map((item) => ({ kind: "item", item })), { kind: "finish" }];
  const firstOpen = steps.findIndex((s) => s.kind === "item" && !lesson.responses[s.item.id]);
  let pos = Object.keys(lesson.responses).length ? (firstOpen === -1 ? steps.length - 1 : firstOpen) : 0;
  let busy = null;
  const drafts = {};
  const root = h("section");

  const nav = (canNext, nextLabel = "Далі →") => h("div.buttonRow", {},
    pos > 0 ? h("button.softButton", { onclick: () => { pos--; draw(); } }, "← Назад") : null,
    h("div.spacer"),
    h("button.primaryButton", { disabled: !canNext, onclick: () => { pos++; draw(); } }, nextLabel));

  async function submit(item, text) {
    drafts[item.id] = text;
    busy = !placement && item.type !== "choice" ? "Перевіряю відповідь" : "…";
    draw();
    try {
      lesson.responses[item.id] = await api.respond(id, item.id, text);
      busy = null;
      if (placement) pos++;
    } catch (err) {
      busy = null;
      draw();
      root.append(h("div.noticeBanner", {}, `Не вдалося перевірити: ${err.message}`));
      return;
    }
    draw();
  }

  async function finish() {
    busy = placement ? "Агент перевіряє тест і визначає рівень, це 2–4 хвилини" : "Claude готує розбір уроку, це 1–2 хвилини";
    draw();
    try {
      const done = await api.finish(id);
      if (placement) return app.go("#/level");
      root.replaceChildren(reviewView(done));
    } catch (err) {
      busy = null;
      draw();
      root.append(h("div.noticeBanner", {}, `Не вдалося завершити: ${err.message}`));
    }
  }

  function card(step) {
    if (step.kind === "intro") {
      return h("div.softCard", {}, h("div.sectionLabel", {}, `${lesson.minutes} хв · ${items.length} завдань`),
        h("h1.pageTitle", {}, lesson.topic), rich("p", lesson.rationale), nav(true, "Почати →"));
    }
    if (step.kind === "explanation") {
      const e = lesson.explanation;
      return h("div.softCard", {}, h("div.sectionLabel", {}, "Правило"), h("h2", { style: "font-weight:400" }, e.title),
        rich("p", e.body), e.analogy ? h("div.insetPanel", {}, h("b", {}, "Аналогія: "), rich("span", e.analogy)) : null,
        h("div", { style: "margin-top:16px;display:grid;gap:6px" },
          e.wrong.map((s) => h("div", {}, "✗ ", h("span.wrongSentence", {}, s))),
          e.right.map((s) => h("div", {}, "✓ ", h("span.rightSentence", {}, s)))),
        nav(true));
    }
    if (step.kind === "chunks") {
      return h("div.softCard", {}, h("div.sectionLabel", {}, "Словосполучення уроку"),
        h("div.chunkList", { style: "margin-top:14px" }, lesson.chunks.map((c) => h("div.insetPanel", {},
          h("div.chunkPhrase", {}, c.chunk), h("div.pageSubtitle", { style: "margin:2px 0" }, c.meaning), h("i", {}, c.example)))),
        nav(true));
    }
    if (step.kind === "finish") {
      const answered = items.filter((i) => lesson.responses[i.id]).length;
      return h("div.softCard", {}, h("div.sectionLabel", {}, "Кінець уроку"),
        h("h2", { style: "font-weight:400" }, `Відповідей: ${answered} з ${items.length}`),
        h("p.pageSubtitle", {}, placement
          ? "Агент перевірить усі відповіді, визначить рівень за напрямами й складе план перших уроків."
          : "Claude розбере відповіді, оновить твої помилки й підкаже фокус наступного уроку."),
        busy ? loading(busy) : h("div.buttonRow", {},
          h("button.softButton", { onclick: () => { pos--; draw(); } }, "← Назад"), h("div.spacer"),
          h("button.primaryButton", { onclick: finish, disabled: !app.state.claude.ok }, placement ? "Завершити тест" : "Завершити урок")));
    }
    const { item } = step;
    const response = lesson.responses[item.id];
    const number = items.indexOf(item) + 1;
    return h("div.softCard", {},
      h("div.itemMeta", {}, h("span.sectionLabel", {}, SECTION[item.section] || item.section),
        h("span.sectionLabel", {}, `${number} / ${items.length}`)),
      rich("div.itemPrompt", item.type === "fix" ? `Виправ: ${item.prompt}` : item.prompt),
      answerControl(item, response, (text) => submit(item, text), placement, drafts[item.id]),
      busy ? h("div", { style: "margin-top:16px" }, loading(busy)) : placement ? null : feedback(item, response),
      busy ? null : nav(placement || Boolean(response), placement && !response ? "Пропустити →" : "Далі →"));
  }

  function draw() {
    const done = items.filter((i) => lesson.responses[i.id]).length;
    root.replaceChildren(
      h("div.lessonProgress", {}, h("i", { style: `width:${(done / items.length) * 100}%` })),
      card(steps[pos]));
    root.querySelector("input.answerInput:not([disabled]), textarea.answerInput:not([disabled])")?.focus();
  }

  draw();
  return root;
}
