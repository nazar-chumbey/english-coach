import { chip, fmtDate, h } from "../ui.js";

export default function history(app) {
  const { lessons } = app.state;
  return h("section", {},
    h("h1.pageTitle", {}, "Історія"),
    h("p.pageSubtitle", {}, `${lessons.length} уроків`),
    lessons.length ? lessons.map((l) => h("a.softCard.historyRow", { href: `#/lesson/${l.id}` },
      h("span.historyDate", {}, fmtDate(l.createdAt)),
      h("span.historyTopic", {}, l.topic || "Урок"),
      h("span.historyScore", {}, [l.minutes ? `${l.minutes} хв` : null, l.score].filter(Boolean).join(" · ")),
      chip(l.status))) : h("div.emptyState", {}, "Ще немає уроків. Згенеруй перший на головній."));
}
