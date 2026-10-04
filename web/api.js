async function call(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export const api = {
  state: () => call("GET", "/api/state"),
  lesson: (id) => call("GET", `/api/lessons/${id}`),
  generate: (minutes, focusSkill) => call("POST", "/api/lessons", { minutes, focusSkill }),
  respond: (id, itemId, text) => call("POST", `/api/lessons/${id}/responses`, { itemId, text }),
  finish: (id) => call("POST", `/api/lessons/${id}/finish`, {}),
  passQuiz: (id, results) => call("POST", `/api/lessons/${id}/quiz`, { results }),
  homework: (id, status, notes) => call("POST", `/api/lessons/${id}/homework`, { status, notes }),
  saveWord: (word, context, lessonId) => call("POST", "/api/words", { word, context, lessonId }),
  deleteWord: (id) => call("POST", `/api/words/${id}/delete`, {}),
  setWord: (id, changes) => call("POST", `/api/words/${id}`, changes),
  reviewWord: (id, rating) => call("POST", `/api/words/${id}/review`, { rating }),
  checkRecall: (id, text) => call("POST", `/api/words/${id}/recall`, { text }),
  checkSentence: (id, text) => call("POST", `/api/words/${id}/sentence`, { text }),
  enrichWords: () => call("POST", "/api/words/enrich", {}),
  suggestWords: (kind) => call("POST", "/api/words/suggest", { kind }),
  drill: (skillId) => call("POST", "/api/drills", { skillId }),
  checkDrill: (skillId, exercise, pattern, text) => call("POST", `/api/drills/${skillId}/check`, { exercise, pattern, text }),
  finishDrill: (skillId, result) => call("POST", `/api/drills/${skillId}/finish`, result),
  ping: () => call("GET", "/api/ping"),
  checkUpdate: () => call("GET", "/api/update"),
  installUpdate: () => call("POST", "/api/update", {}),
  settings: (changes) => call("POST", "/api/settings", changes),
  onboard: (answers) => call("POST", "/api/onboarding", answers),
  placement: () => call("POST", "/api/placement", {}),
  assess: () => call("POST", "/api/assessment", {}),
  importVault: (vaultPath) => call("POST", "/api/import", { vaultPath }),
};
