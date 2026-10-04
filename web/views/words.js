import { api } from "../api.js";
import { fmtDate, h, loading } from "../ui.js";
import { rerender } from "../app.js";
import { micButton, norm, typos } from "../answer.js";

const NEW_PER_DAY = 7;
const MAX_REVIEWS = 40;
const RATINGS = [[1, "Знову"], [2, "Важко"], [3, "Добре"], [4, "Легко"]];
const SOURCE = { saved: "збережене", lesson: "з уроку", work: "робоче", general: "загальне" };
const localDay = (d = new Date()) => d.toLocaleDateString("sv");
const when = (iso) => localDay(new Date(iso)) === localDay()
  ? `сьогодні о ${new Date(iso).toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" })}` : fmtDate(iso);
const isLearning = (w) => (w.status || "learning") === "learning";
const shuffle = (list) => list.map((v) => [Math.random(), v]).sort((a, b) => a[0] - b[0]).map(([, v]) => v);
const put = (el, ...kids) => el.append(...kids.flat(Infinity).filter((k) => k != null && k !== false));
const enrich = { tried: false, running: false, error: null };

function speak(text) {
  speechSynthesis.cancel();
  speechSynthesis.speak(Object.assign(new SpeechSynthesisUtterance(text), { lang: "en-US", rate: 0.9 }));
}

const speakButton = (text) => h("button.speakWordButton", { title: "Вимова", onclick: () => speak(text) }, "🔊");
const wordHead = (w) => h("div.drillWordHead", {}, h("span.drillWord", {}, w.word), w.ipa ? h("span.wordIpa", {}, w.ipa) : null, speakButton(w.word));
const hook = (w) => w.association ? h("div.insetPanel.associationPanel", {}, h("div.sectionLabel", {}, "💡 Як запамʼятати"), h("p", {}, w.association)) : null;
const details = (w) => h("div", {}, h("p", {}, h("b", {}, w.meaning)), w.example ? h("p", {}, h("i", {}, w.example)) : null,
  w.collocations?.length ? h("div.chipGroup", {}, w.collocations.map((c) => h("span.exampleChip", {}, c))) : null, hook(w));

function kindFor(w) {
  if (!w.srs || w.srs.stability < 2) return "recognize";
  return w.srs.stability >= 21 && w.srs.reps % 2 ? "produce" : "recall";
}

function plan(words) {
  const now = new Date();
  const learning = words.filter(isLearning);
  const due = learning.filter((w) => w.srs && new Date(w.srs.due) <= now)
    .sort((a, b) => a.srs.due.localeCompare(b.srs.due)).slice(0, MAX_REVIEWS);
  const introduced = words.filter((w) => w.introducedAt === localDay()).length;
  const fresh = learning.filter((w) => !w.srs)
    .sort((a, b) => (a.source !== "saved") - (b.source !== "saved") || a.addedAt.localeCompare(b.addedAt))
    .slice(0, Math.max(0, NEW_PER_DAY - introduced));
  const next = learning.filter((w) => w.srs && new Date(w.srs.due) > now).map((w) => w.srs.due).sort()[0];
  return { due, fresh, next };
}

function buildQueue({ due, fresh }) {
  const block = fresh.flatMap((w, i) => [{ w, kind: "intro" }, ...(i >= 2 ? [{ w: fresh[i - 2], kind: "recognize" }] : [])])
    .concat(fresh.slice(-2).map((w) => ({ w, kind: "recognize" })));
  const reviews = shuffle(due).map((w) => ({ w, kind: kindFor(w) }));
  return Array.from({ length: Math.max(block.length, reviews.length) }, (_, i) => [block[i], reviews[i]]).flat().filter(Boolean);
}

function session(words, done) {
  const queue = buildQueue(plan(words));
  const stats = { reviewed: 0, first: 0, fresh: queue.filter((c) => c.kind === "intro").length };
  const root = h("section");
  let pos = 0;
  let answer = null;

  const onKey = (e) => {
    if (!root.isConnected) return document.removeEventListener("keydown", onKey);
    if (!answer || e.target.matches?.("textarea")) return;
    if (e.key === "Enter") { e.preventDefault(); rate(answer.suggested); }
    else if (/^[1-4]$/.test(e.key)) rate(Number(e.key));
  };
  document.addEventListener("keydown", onKey);

  async function rate(rating) {
    const card = queue[pos];
    answer = null;
    if (!card.practice) {
      stats.reviewed++;
      stats.first += rating > 1;
      card.w.srs = (await api.reviewWord(card.w.id, rating)).srs;
      if (rating === 1) queue.splice(Math.min(queue.length, pos + 4), 0, { w: card.w, kind: "recall", practice: true });
    } else if (rating === 1 && queue.filter((c) => c.w === card.w && c.practice).length < 3) {
      queue.splice(Math.min(queue.length, pos + 4), 0, { ...card });
    }
    pos++;
    draw();
  }

  function reveal(card, result, extra) {
    const suggested = { correct: 3, minor: 2, wrong: 1 }[result];
    setTimeout(() => { answer = { suggested }; });
    speak(card.w.word);
    return h("div", {},
      h("div.feedbackBox", { class: result }, extra, details(card.w)),
      h("div.sectionLabel", { style: "margin-top:20px" }, card.practice ? "Ще раз для закріплення" : "Наскільки легко згадав?"),
      h("div.buttonRow", {}, RATINGS.map(([value, label]) =>
        h(value === suggested ? "button.primaryButton" : "button.softButton", { onclick: () => rate(value) }, `${label} · ${value}`))));
  }

  const cards = {
    intro(card, slot) {
      speak(card.w.word);
      const next = h("button.primaryButton", { onclick: () => { pos++; draw(); } }, "Запамʼятав →");
      put(slot, h("div.sectionLabel", {}, `Нове слово · ${SOURCE[card.w.source] || SOURCE.saved}`), wordHead(card.w), details(card.w),
        h("div.buttonRow", {}, next));
      setTimeout(() => next.focus());
    },
    recognize(card, slot) {
      const others = shuffle(words.filter((w) => w !== card.w && w.meaning).map((w) => w.meaning));
      const wrong = (card.w.distractors?.length ? card.w.distractors : others).slice(0, 3);
      if (!wrong.length) return cards.recall(card, slot);
      const list = h("div.choiceList", {}, shuffle([card.w.meaning, ...wrong]).map((option) =>
        h("button.choiceOption", { onclick: (e) => {
          const ok = option === card.w.meaning;
          list.querySelectorAll("button").forEach((b) => { b.disabled = true; });
          e.currentTarget.classList.add("picked");
          list.after(reveal(card, ok ? "correct" : "wrong", h("p", {}, h("b", {}, ok ? "✓ Так" : "✗ Ні"))));
        } }, option)));
      speak(card.w.word);
      put(slot, h("div.sectionLabel", {}, "Що це означає?"), wordHead(card.w), list);
    },
    recall(card, slot) {
      const target = card.w.cloze ? card.w.clozeAnswer : card.w.word;
      let hinted = false;
      const input = h("input.answerInput", { placeholder: "Англійською…", autocomplete: "off",
        onkeydown: (e) => e.key === "Enter" && !input.disabled && (e.preventDefault(), e.stopPropagation(), check()) });
      const hintLine = h("p.hintBox");
      const showHint = () => {
        hinted = true;
        hintLine.textContent = `Підказка: ${target.replace(/\p{L}/gu, (c, i) => (i === 0 || target[i - 1] === " " ? c : "_"))}`;
        input.focus();
      };
      const controls = h("div.buttonRow", {},
        h("button.softButton", { onclick: showHint }, "Підказка"),
        h("button.softButton", { onclick: () => finish("wrong", `Правильно: ${target}`) }, "Не памʼятаю"),
        h("div.spacer"), h("button.primaryButton", { onclick: () => check() }, "Перевірити ↵"));
      function finish(result, verdict) {
        input.disabled = true;
        controls.remove();
        put(slot, reveal(card, result, [h("p", {}, h("b", {}, verdict)),
          card.w.cloze ? h("p", {}, card.w.cloze.replace("___", target)) : null]));
      }
      function check() {
        const given = norm(input.value);
        if (!given) return;
        const distance = Math.min(...[target, card.w.word].map((t) => typos(given, norm(t))));
        if (distance === 0) finish(hinted ? "minor" : "correct", "✓ Правильно");
        else if (distance === 1 && given.length >= 4) finish("minor", `≈ Майже: ${target}`);
        else finish("wrong", `✗ Правильно: ${target}`);
      }
      put(slot, h("div.sectionLabel", {}, "Згадай англійською"), h("p.itemPrompt", {}, h("b", {}, card.w.meaning)),
        card.w.cloze ? h("p.itemPrompt", {}, card.w.cloze) : null, h("div.quizAnswerRow", {}, input, micButton(input)), hintLine, controls);
      setTimeout(() => input.focus());
    },
    produce(card, slot) {
      const input = h("textarea.answerInput", { placeholder: "Твоє речення про роботу або життя…",
        onkeydown: (e) => e.key === "Enter" && (e.metaKey || e.ctrlKey) && send() });
      const controls = h("div.buttonRow", {},
        h("button.softButton", { onclick: () => { slot.replaceChildren(); cards.recall(card, slot); } }, "Пропустити"),
        h("div.spacer"), h("button.primaryButton", { onclick: () => send() }, "Перевірити ⌘↵"));
      async function send() {
        const text = input.value.trim();
        if (!text) return;
        controls.replaceChildren(loading("Перевіряю речення"));
        try {
          const v = await api.checkSentence(card.w.id, text);
          input.disabled = true;
          controls.remove();
          put(slot, reveal(card, v.result, [h("p", {}, v.feedback),
            v.corrected !== text ? h("p", {}, "Природніше: ", h("b", {}, v.corrected)) : null]));
        } catch (err) {
          controls.replaceChildren(h("div.noticeBanner", {}, `Не вдалося перевірити: ${err.message}`));
        }
      }
      put(slot, h("div.sectionLabel", {}, "Напиши своє речення"), wordHead(card.w), h("p", {}, card.w.meaning), input, controls);
      setTimeout(() => input.focus());
    },
  };

  function draw() {
    if (pos >= queue.length) {
      document.removeEventListener("keydown", onKey);
      return root.replaceChildren(h("div.softCard", {}, h("h2", {}, "Готово ✓"),
        h("div.cardGrid", {}, [[stats.reviewed, "перевірено"], [stats.first, "згадав"], [stats.fresh, "нових слів"]]
          .map(([v, l]) => h("div.statPill", {}, h("b", {}, v), h("span", {}, l)))),
        h("div.buttonRow", {}, h("button.primaryButton", { onclick: done }, "До словника"))));
    }
    const slot = h("div.softCard");
    root.replaceChildren(h("div.drillProgress", {}, h("i", { style: `width:${(pos / queue.length) * 100}%` })),
      h("div.buttonRow", { style: "margin:0 0 16px" }, h("span.skillMeta", {}, `${pos + 1} з ${queue.length}`), h("div.spacer"),
        h("button.softButton", { onclick: done }, "Завершити")), slot);
    cards[queue[pos].kind](queue[pos], slot);
  }

  draw();
  return root;
}

function suggestions(words, app) {
  const box = h("div.softCard");
  const ask = async (kind, button) => {
    box.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    button.replaceChildren(loading("Claude підбирає слова"));
    try {
      await api.suggestWords(kind);
      rerender();
    } catch (err) {
      box.append(h("div.noticeBanner", {}, `Не вдалося підібрати: ${err.message}`));
    }
  };
  const decide = (w, status) => api.setWord(w.id, { status }).then(rerender);
  put(box, [h("div.sectionLabel", {}, "Нові слова для тебе"),
    h("p.hintBox", {}, "Відсій ті, що вже знаєш: вчити варто лише нове."),
    words.filter((w) => w.status === "suggested").map((w) => h("div.insetPanel.suggestedWordRow", {},
      h("div.suggestedWordText", {}, h("b", {}, w.word), speakButton(w.word), h("span.skillMeta", {}, `${SOURCE[w.source]} · ${w.meaning}`),
        w.example ? h("div", {}, h("i", {}, w.example)) : null),
      h("button.softButton", { onclick: () => decide(w, "known") }, "Вже знаю"),
      h("button.primaryButton", { onclick: () => decide(w, "learning") }, "Вчити"))),
    app.state.claude.ok ? h("div.buttonRow", {},
      h("button.softButton", { onclick: (e) => ask("work", e.currentTarget) }, "+ Робочі слова"),
      h("button.softButton", { onclick: (e) => ask("general", e.currentTarget) }, "+ Загальні слова")) : null]);
  return box;
}

const strength = (w) => !w.srs ? "ще не вчив"
  : `${w.srs.stability < 1 ? "ще закріплюється" : `памʼятаєш ~${Math.round(w.srs.stability)} дн`} · повтор ${when(w.srs.due)}`;

function wordRow(w) {
  const edit = () => {
    const text = prompt("Своя асоціація (власна запамʼятовується краще):", w.association || "");
    if (text != null) api.setWord(w.id, { association: text.trim() }).then(rerender);
  };
  return h("details.softCard", {},
    h("summary.wordRowSummary", {}, h("div.skillHeader", {}, h("h3", {}, w.word), h("span.skillMeta", {}, `${SOURCE[w.source] || SOURCE.saved} · ${strength(w)}`))),
    h("div", { style: "margin-top:12px" }, w.ipa ? h("span.wordIpa", {}, w.ipa) : null, speakButton(w.word), details(w),
      w.context ? h("p.hintBox", {}, `Де трапилось: ${w.context}`) : null,
      h("div.buttonRow", {},
        h("button.softButton", { onclick: edit }, "Своя асоціація"),
        w.status === "known" ? h("button.softButton", { onclick: () => api.setWord(w.id, { status: "learning" }).then(rerender) }, "Вчити") : null,
        h("button.softButton", { onclick: () => api.deleteWord(w.id).then(rerender) }, "Видалити"))));
}

export default function words(app) {
  const all = app.state.words;
  const root = h("section");
  const { due, fresh, next } = plan(all);
  const minutes = Math.max(1, Math.round((due.length * 12 + fresh.length * 30) / 60));
  const input = h("input.answerInput", { placeholder: "Слово або фраза англійською…", onkeydown: (e) => e.key === "Enter" && add() });
  const addButton = h("button.primaryButton", { onclick: () => add() }, "Додати");
  async function add() {
    if (!input.value.trim()) return;
    addButton.disabled = true;
    await api.saveWord(input.value.trim(), "", null).finally(() => { addButton.disabled = false; });
    rerender();
  }
  const missing = all.some((w) => isLearning(w) && !w.cloze);
  if (missing && app.state.claude.ok && !enrich.tried) {
    Object.assign(enrich, { tried: true, running: true });
    api.enrichWords().catch((err) => { enrich.error = err.message; }).finally(() => { enrich.running = false; rerender(); });
  }
  const learning = all.filter(isLearning).reverse();
  const known = all.filter((w) => w.status === "known");
  put(root, [h("h1.pageTitle", {}, "Словник"),
    h("p.pageSubtitle", {}, "Інтервальні повторення: слово повертається саме тоді, коли ти вже майже його забув."),
    h("div.softCard", {},
      h("div.sectionLabel", {}, "Тренування"),
      enrich.running ? h("div.hintBox", {}, loading("Claude готує картки для нових слів")) : null,
      enrich.error ? h("div.noticeBanner", {}, `Не вдалося підготувати картки: ${enrich.error}`) : null,
      h("div.cardGrid", { style: "margin:16px 0 0" }, [[due.length, "на повтор"], [fresh.length, "нових сьогодні"], [learning.length, "у вивченні"]]
        .map(([v, l]) => h("div.statPill", {}, h("b", {}, v), h("span", {}, l)))),
      h("div.buttonRow", {}, due.length + fresh.length
        ? h("button.primaryButton", { disabled: enrich.running, onclick: () => root.replaceChildren(session(all, rerender)) }, `Почати · ~${minutes} хв`)
        : h("span.skillMeta", {}, next ? `На сьогодні все ✓ Наступний повтор ${when(next)}` : "Додай слова, щоб почати"))),
    suggestions(all, app),
    h("div.softCard", {}, h("div.sectionLabel", {}, "Додати своє"), h("div", { style: "margin-top:12px" }, input), h("div.buttonRow", {}, addButton),
      h("p.hintBox", {}, "Або виділи слово на будь-якому екрані й натисни «+ У словник».")),
    learning.length ? [h("div.sectionLabel", { style: "margin:8px 0 14px" }, `У вивченні (${learning.length})`), learning.map(wordRow)] : null,
    known.length ? h("details", {}, h("summary", {}, `Вже знаю (${known.length})`), h("div", { style: "margin-top:14px" }, known.map(wordRow))) : null]);
  return root;
}
