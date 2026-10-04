import { api } from "./api.js";
import { h } from "./ui.js";

const MAX_LENGTH = 80;
const CONTEXT = "p, li, blockquote, .itemPrompt, .choiceOption, .insetPanel, .softCard";

export function toast(content, ms = 6000) {
  document.querySelector(".wordToast")?.remove();
  const el = h("div.wordToast", {}, content);
  document.body.append(el);
  setTimeout(() => el.remove(), ms);
}

export function attachWordPicker(view, lessonId) {
  const button = h("button.saveWordButton", { hidden: true, onmousedown: (e) => e.preventDefault() }, "+ У словник");
  document.body.append(button);
  let picked = null;

  button.addEventListener("click", async () => {
    button.hidden = true;
    const { word, context } = picked;
    getSelection().removeAllRanges();
    toast(`Зберігаю «${word}»…`, 60000);
    try {
      const saved = await api.saveWord(word, context, lessonId());
      toast([h("b", {}, saved.word), saved.meaning ? ` — ${saved.meaning}` : " збережено"]);
    } catch (err) {
      toast(`Не вдалося зберегти: ${err.message}`);
    }
  });

  document.addEventListener("selectionchange", () => {
    const sel = getSelection();
    const word = sel.toString().trim();
    const node = sel.anchorNode?.parentElement;
    if (!word || word.length > MAX_LENGTH || !view.contains(node) || node.closest("input, textarea")) {
      button.hidden = true;
      return;
    }
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    picked = { word, context: (node.closest(CONTEXT) || node).textContent.trim() };
    Object.assign(button.style, { top: `${rect.bottom + scrollY + 8}px`, left: `${rect.left + scrollX}px` });
    button.hidden = false;
  });
}
