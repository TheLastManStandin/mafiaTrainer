"use strict";

const screen = document.querySelector("#screen");
const notice = document.querySelector("#notice");
let bank;
let page;
let busy = false;
let training;
let lastTraining;
let lastDeleted;
let editorOrigin = "home";
const settings = {level: 1, topics: new Set(), count: 20};

const statusLabels = {
  correct: "Верно",
  wrong: "Ответ не совпал с эталоном",
  skipped: "Вопрос пропущен",
  review: "Сравни своё решение с разбором",
  review_good: "Разобрался",
  review_repeat: "Нужно повторить",
};

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function button(text, action, style = "") {
  const node = element("button", ("button " + style).trim(), text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

function link(text, url) {
  const node = element("a", "button", text);
  node.href = url;
  node.target = "_blank";
  node.rel = "noopener noreferrer";
  return node;
}

function template(id) {
  screen.append(document.querySelector("#" + id + "-template").content.cloneNode(true));
}

function message(text = "", near = notice) {
  near.hidden = !text;
  near.textContent = text;
}

async function request(path, data) {
  const options = data === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  };
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Связь с тренажёром прервалась. Проверь подключение и попробуй ещё раз.");
  }
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Не удалось выполнить запрос.");
  }
  return payload;
}

async function perform(action, errorTarget = notice) {
  if (busy) return;
  busy = true;
  screen.setAttribute("aria-busy", "true");
  message("", errorTarget);
  try {
    await action();
  } catch (error) {
    message(error.message || "Не удалось выполнить действие.", errorTarget.isConnected ? errorTarget : notice);
  } finally {
    busy = false;
    screen.setAttribute("aria-busy", "false");
  }
}

function show(nextPage, render) {
  page = nextPage;
  screen.dataset.page = page;
  message();
  screen.replaceChildren();
  const navPage = ["game", "results"].includes(page) ? "home" : page === "editor" ? editorOrigin : page;
  for (const item of document.querySelectorAll("nav [data-page]")) {
    if (item.dataset.page === navPage) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  render();
  window.scrollTo(0, 0);
  const title = screen.querySelector("h1");
  if (title) {
    title.tabIndex = -1;
    title.focus({preventScroll: true});
  }
}

function go(nextPage) {
  if (!bank || busy) return;
  if (page === "game" && !window.confirm("Закончить текущую тренировку?")) return;
  if (nextPage === "home" || nextPage === "library") {
    perform(async () => {
      bank = await request("/api/bank");
      training = null;
      if (nextPage === "home") show("home", renderHome);
      else show("library", renderLibrary);
    });
  } else {
    training = null;
    if (nextPage === "glossary") show("glossary", renderGlossary);
    if (nextPage === "sources") show("sources", renderSources);
  }
}

for (const item of document.querySelectorAll(".site-header [data-page]")) {
  item.addEventListener("click", event => {
    event.preventDefault();
    go(item.dataset.page);
  });
}

function topicOptions(container, selected, descriptions = false) {
  const inputs = [];
  for (const [key, [title, description]] of Object.entries(bank.topics)) {
    const label = element("label", "topic");
    const input = element("input");
    input.type = "checkbox";
    input.name = "topics";
    input.value = key;
    input.checked = selected.has(key);
    const copy = element("span");
    copy.append(element("strong", "", title));
    if (descriptions) copy.append(element("small", "muted", description));
    label.append(input, copy);
    container.append(label);
    inputs.push(input);
  }
  return inputs;
}

function renderHome() {
  template("home");
  const start = screen.querySelector("#start");
  const availability = screen.querySelector("#availability");
  const toggle = screen.querySelector("#toggle-topics");
  const count = screen.querySelector("#question-count");
  const levels = screen.querySelector("#levels");
  const topics = topicOptions(screen.querySelector("#topics"), settings.topics, true);

  function updateAvailability() {
    const available = bank.active.filter(q => q.level === settings.level && q.topics.some(t => settings.topics.has(t))).length;
    const size = settings.count ? Math.min(available, settings.count) : available;
    toggle.textContent = settings.topics.size === topics.length ? "Снять все" : "Выбрать все";
    availability.textContent = settings.topics.size ? "В сессии " + size + " из " + available : "Выбери тему";
    start.disabled = size === 0;
  }

  for (const [key, title] of Object.entries(bank.levels)) {
    const input = element("input");
    input.type = "radio";
    input.name = "level";
    input.checked = Number(key) === settings.level;
    input.addEventListener("change", () => {
      settings.level = Number(key);
      updateAvailability();
    });
    const label = element("label", "level");
    label.append(input, element("span", "", title));
    levels.append(label);
  }
  for (const topic of topics) {
    topic.addEventListener("change", () => {
      if (topic.checked) settings.topics.add(topic.value);
      else settings.topics.delete(topic.value);
      updateAvailability();
    });
  }
  toggle.addEventListener("click", () => {
    const checked = settings.topics.size !== topics.length;
    settings.topics = new Set(checked ? topics.map(topic => topic.value) : []);
    for (const topic of topics) topic.checked = checked;
    updateAvailability();
  });
  count.value = settings.count;
  count.addEventListener("change", () => {
    settings.count = Number(count.value);
    updateAvailability();
  });
  start.addEventListener("click", () => startTraining({...settings, topics: [...settings.topics]}));
  screen.querySelector("#add-question").addEventListener("click", () => openEditor("home"));
  if (lastTraining) {
    screen.querySelector("#home-actions").append(button("Последние результаты", () => show("results", renderResults)));
  }
  screen.querySelector("#home-undo").append(undoNotice());
  updateAvailability();
}

function startTraining(selection) {
  perform(async () => {
    const {questions} = await request("/api/training", selection);
    if (!questions.length) {
      bank = await request("/api/bank");
      show("home", renderHome);
      message("По этому выбору больше нет доступных вопросов.");
      return;
    }
    lastTraining = null;
    training = {questions, total: questions.length, results: [], pending: null, hint: null};
    show("game", renderGame);
  });
}

function questionAction(question, action, data) {
  return request("/api/questions/" + encodeURIComponent(question.id) + "/" + action, data);
}

function media(question) {
  const figure = element("figure", "media");
  const image = element("img");
  image.alt = "Изображение жеста или игровой ситуации";
  if (page === "glossary") image.loading = "lazy";
  image.addEventListener("error", () => {
    image.hidden = true;
    figure.replaceChildren(element("figcaption", "muted", "Изображение недоступно."));
  });
  image.src = question.media;
  figure.append(image);
  if (question.animated) {
    let replay = 0;
    figure.append(button("Повторить анимацию", () => {
      replay += 1;
      image.src = question.media + "?replay=" + replay;
    }, "compact"));
  }
  return figure;
}

function tableBoard(numbers) {
  const board = element("div", "board");
  board.setAttribute("role", "img");
  board.setAttribute("aria-label", "Игровой стол. Номера игроков по кругу: " + numbers.join(", "));
  board.append(element("span", "board-title", "Игровой стол"));
  numbers.forEach((number, index) => {
    const angle = 2 * Math.PI * index / numbers.length;
    const seat = element("span", "seat", number);
    seat.style.setProperty("--seat-left", (50 + 41 * Math.sin(angle)) + "%");
    seat.style.setProperty("--seat-top", (50 - 39 * Math.cos(angle)) + "%");
    board.append(seat);
  });
  return board;
}

function renderGame() {
  const question = training.questions[0];
  const top = element("div", "between");
  top.append(
    element("p", "progress-count", "Вопрос " + (training.results.length + 1) + " из " + training.total),
    button("Завершить", () => {
      if (!busy) finishTraining();
    }, "quiet"),
  );
  const progress = element("progress");
  progress.max = training.total;
  progress.value = training.results.length;
  progress.setAttribute("aria-label", "Прогресс тренировки");
  const card = element("article", "panel training");
  card.append(
    element("p", "training-label", question.topics.map(topic => bank.topics[topic][0]).join(" · ")),
    element("h1", "prompt", question.prompt),
  );
  if (question.board.length) card.append(tableBoard(question.board));
  if (question.media) card.append(media(question));

  const form = element("form", "stack");
  form.id = "response";
  if (question.kind === "choice") {
    const choices = element("fieldset", "choices");
    choices.append(element("legend", "field-help muted", "Выбери один ответ"));
    for (const option of question.options) {
      const input = element("input");
      input.name = "response";
      input.type = "radio";
      input.value = option;
      const label = element("label", "choice");
      label.append(input, element("span", "", option));
      choices.append(label);
    }
    form.append(choices);
  } else {
    const label = element("label", "field", question.kind === "review" ? "Твоё решение и аргументы" : "Твой ответ");
    const input = element("textarea");
    input.name = "response";
    input.maxLength = 12000;
    input.rows = question.kind === "review" ? 4 : 2;
    label.append(input);
    form.append(label);
  }
  const hintPanel = element("div", "panel stack");
  hintPanel.id = "hint-panel";
  hintPanel.hidden = true;
  const error = element("p", "training-label");
  error.setAttribute("role", "alert");
  error.hidden = true;
  const controls = element("div", "actions");
  const submit = element("button", "button primary", question.kind === "review" ? "Показать разбор" : "Проверить ответ");
  submit.type = "submit";
  const hint = button("Подсказка", () => {
    if (busy) return;
    if (training.hint !== null) {
      hintPanel.hidden = !hintPanel.hidden;
      hint.setAttribute("aria-expanded", String(!hintPanel.hidden));
      return;
    }
    perform(async () => {
      const {explanation} = await questionAction(question, "feedback", {action: "hint"});
      training.hint = explanation;
      hintPanel.append(element("p", "prose", explanation), element("p", "muted", "Ответ будет отмечен как решённый с подсказкой."));
      hintPanel.hidden = false;
      hint.setAttribute("aria-expanded", "true");
    }, error);
  }, "quiet");
  hint.setAttribute("aria-controls", hintPanel.id);
  hint.setAttribute("aria-expanded", "false");

  function sendAnswer(action) {
    if (busy || training.pending) return;
    const response = (new FormData(form).get("response") || "").trim();
    if (action === "answer" && !response) {
      message("Выбери или введи ответ либо нажми «Не знаю».", error);
      return;
    }
    perform(async () => {
      const result = await questionAction(question, "feedback", {action, response});
      training.pending = {...result, question, hinted: training.hint !== null, manual: false};
      for (const input of form.querySelectorAll("input")) input.disabled = true;
      const textarea = form.querySelector("textarea");
      if (textarea) textarea.readOnly = true;
      controls.hidden = true;
      hintPanel.hidden = true;
      renderFeedback(true);
    }, error);
  }

  controls.append(submit, button("Не знаю", () => sendAnswer("skip")), hint);
  form.addEventListener("submit", event => {
    event.preventDefault();
    sendAnswer("answer");
  });
  form.append(error, controls, hintPanel);
  const feedback = element("section", "panel stack feedback");
  feedback.id = "feedback";
  feedback.hidden = true;
  card.append(form, feedback);
  const remove = button("Удалить вопрос", () => {
    perform(async () => {
      bank = await questionAction(question, "visibility", {deleted: true});
      lastDeleted = question;
      training.questions.shift();
      training.total -= 1;
      training.pending = null;
      training.hint = null;
      if (training.questions.length) show("game", renderGame);
      else finishTraining();
    });
  }, "quiet danger");
  const layout = element("div", "stack");
  const undo = element("div");
  undo.id = "game-undo";
  undo.append(undoNotice());
  layout.append(top, progress, card, remove, undo);
  screen.append(layout);
}

function resultTitle(result) {
  const title = result.manual ? "Зачтено вручную" : statusLabels[result.status];
  return result.hinted ? title + " · с подсказкой" : title;
}

function renderFeedback(moveFocus = false) {
  const panel = screen.querySelector("#feedback");
  const result = training.pending;
  panel.hidden = false;
  panel.classList.toggle("good", ["correct", "review_good"].includes(result.status));
  const title = element("h2", "", resultTitle(result));
  title.tabIndex = -1;
  panel.replaceChildren(
    title,
    element("p", "prose", (result.question.kind === "review" ? "Возможное решение: " : "Ответ: ") + result.answer),
    element("p", "prose", result.explanation),
    element("p", "muted", result.source),
  );
  if (result.sourceUrl) panel.append(link("Открыть источник", result.sourceUrl));
  const actions = element("div", "actions");
  if (result.status === "review") {
    const assess = status => {
      result.status = status;
      renderFeedback(true);
    };
    actions.append(
      button("Разобрался", () => assess("review_good"), "primary"),
      button("Нужно повторить", () => assess("review_repeat")),
    );
  } else {
    actions.append(button(training.questions.length === 1 ? "К результатам" : "Следующий вопрос", nextQuestion, "primary"));
    if (result.status === "wrong" && result.question.kind === "short") {
      actions.append(button("Мой ответ верный по смыслу", () => {
        result.status = "correct";
        result.manual = true;
        renderFeedback(true);
      }));
    }
  }
  panel.append(actions);
  if (moveFocus) title.focus();
}

function recordAnswer() {
  if (training.pending && training.pending.status !== "review") {
    training.results.push(training.pending);
  }
}

function finishTraining() {
  recordAnswer();
  lastTraining = training;
  training = null;
  show("results", renderResults);
}

function nextQuestion() {
  if (busy || !training.pending || training.pending.status === "review") return;
  if (training.questions.length === 1) {
    finishTraining();
    return;
  }
  recordAnswer();
  training.questions.shift();
  training.pending = null;
  training.hint = null;
  show("game", renderGame);
}

document.addEventListener("keydown", event => {
  if (page !== "game" || busy || event.defaultPrevented) return;
  const form = screen.querySelector("#response");
  if (event.ctrlKey && event.key === "Enter") {
    event.preventDefault();
    if (!training.pending) form.requestSubmit();
    else nextQuestion();
  } else if (!training.pending && /^[1-4]$/.test(event.key) && !event.target.closest("input, textarea, select, button, a")) {
    const option = form.querySelectorAll("input[type='radio']")[Number(event.key) - 1];
    if (option) option.checked = true;
  }
});

function undoNotice() {
  if (!lastDeleted) return document.createDocumentFragment();
  const question = lastDeleted;
  const panel = element("div", "panel inline-note");
  panel.append(element("p", "", "Вопрос удалён из базы."), button("Отменить удаление", () => {
    perform(async () => {
      bank = await questionAction(question, "visibility", {deleted: false});
      lastDeleted = null;
      if (page === "game") panel.remove();
      else if (page === "home") show("home", renderHome);
      else if (page === "results") show("results", renderResults);
    });
  }));
  return panel;
}

function score(results) {
  const automatic = results.filter(r => r.question.kind !== "review");
  const correct = automatic.filter(r => r.status === "correct" && !r.hinted).length;
  return correct + " / " + automatic.length;
}

function renderResults() {
  const results = lastTraining.results;
  const reviews = results.filter(result => result.question.kind === "review");
  const retry = results.filter(result => result.hinted || ["wrong", "skipped", "review_repeat"].includes(result.status));
  const stats = element("div", "stats");
  for (const [value, label] of [
    [score(results), "верно без подсказок"],
    [results.filter(result => result.hinted).length, "с подсказкой"],
    [reviews.length, "с самооценкой"],
  ]) {
    const stat = element("div", "panel stat");
    stat.append(element("strong", "", value), element("span", "muted", label));
    stats.append(stat);
  }
  const actions = element("div", "actions");
  actions.append(button("Новая тренировка", () => go("home"), "primary"));
  if (retry.length) {
    actions.append(button("Повторить ошибки (" + retry.length + ")", () => {
      startTraining({retry: retry.map(result => result.question.id)});
    }));
  }
  const layout = element("div", "stack");
  layout.append(element("h1", "", "Результаты тренировки"), stats, actions, undoNotice());
  if (!results.length) layout.append(element("p", "muted", "В этой тренировке ещё нет проверенных ответов."));
  if (results.length) {
    const breakdown = element("section", "panel stack");
    breakdown.append(element("h2", "", "По темам"));
    for (const [key, [name]] of Object.entries(bank.topics)) {
      const subset = results.filter(result => result.question.topics.includes(key));
      if (!subset.length) continue;
      const assessed = subset.filter(result => ["review_good", "review_repeat"].includes(result.status));
      const scores = [];
      if (subset.some(result => result.question.kind !== "review")) scores.push(score(subset) + " без подсказок");
      if (assessed.length) {
        scores.push(assessed.filter(result => result.status === "review_good").length + " / " + assessed.length + " разобрался");
      }
      if (scores.length) breakdown.append(element("p", "", name + " · " + scores.join(" · ")));
    }
    layout.append(breakdown, element("h2", "", "Разбор ответов"));
    const list = element("div", "listing");
    for (const result of results) {
      const card = element("article", "panel");
      card.append(
        element("p", "training-label", resultTitle(result)),
        element("h3", "prose", result.question.prompt),
        element("p", "muted prose", "Твой ответ: " + (result.response || "Не знаю")),
        element("p", "prose", "Эталон: " + result.answer),
        element("p", "muted prose", result.explanation),
      );
      list.append(card);
    }
    layout.append(list);
  }
  screen.append(layout);
}

function renderGlossary() {
  const input = element("input");
  input.type = "search";
  input.placeholder = "Например, попил или договорка";
  const label = element("label", "field", "Поиск по названию и описанию");
  label.append(input);
  const list = element("div", "listing");
  const normalize = value => value.toLowerCase().replaceAll("ё", "е").trim();
  function filter() {
    const query = normalize(input.value);
    list.replaceChildren();
    for (const entry of bank.glossary) {
      if (!normalize(entry.title + " " + entry.explanation).includes(query)) continue;
      const card = element("article", "panel");
      card.append(element("h2", "", entry.title), element("p", "prose", entry.explanation));
      const details = element("details");
      details.append(element("summary", "", entry.media ? "Показать жест" : "Источник"));
      details.addEventListener("toggle", () => {
        const contents = details.querySelector(".details-body");
        if (contents) contents.remove();
        if (details.open) {
          const body = element("div", "details-body");
          if (entry.media) body.append(media(entry));
          body.append(element("p", "muted", entry.source));
          if (entry.sourceUrl) body.append(link("Открыть источник", entry.sourceUrl));
          details.append(body);
        }
      });
      card.append(details);
      list.append(card);
    }
    if (!list.children.length) list.append(element("p", "muted", "Ничего не найдено."));
  }
  input.addEventListener("input", filter);
  const layout = element("div", "stack");
  layout.append(element("h1", "", "Справочник"), label, list);
  screen.append(layout);
  filter();
}

function renderLibrary() {
  const layout = element("div", "stack");
  const summary = "Активно: " + bank.active.length + " · своих: " + bank.customCount +
    " · удалено: " + bank.library.filter(q => q.deleted).length;
  layout.append(
    element("h1", "", "Моя база"),
    element("p", "muted", summary),
    button("Добавить свой вопрос", () => openEditor("library"), "primary"),
  );
  const list = element("div", "listing");
  for (const question of bank.library) {
    const card = element("article", "panel");
    card.append(
      element("p", "training-label", (question.deleted ? "Удалён" : "Свой вопрос") + " · " + bank.levels[question.level]),
      element("p", "prose", question.prompt),
      button(question.deleted ? "Восстановить" : "Удалить из базы", () => {
        perform(async () => {
          bank = await questionAction(question, "visibility", {deleted: !question.deleted});
          if (lastDeleted?.id === question.id && question.deleted) lastDeleted = null;
          show("library", renderLibrary);
        });
      }),
    );
    list.append(card);
  }
  if (!list.children.length) list.append(element("p", "muted", "Здесь появятся свои и удалённые вопросы."));
  layout.append(list);
  screen.append(layout);
}

function openEditor(origin) {
  if (busy) return;
  editorOrigin = origin;
  show("editor", renderEditor);
}

function closeEditor() {
  if (editorOrigin === "library") show("library", renderLibrary);
  else show("home", renderHome);
}

function encodeImage(file) {
  if (file.size > 30 * 1024 * 1024) throw new Error("Максимальный размер изображения — 30 МБ.");
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(reader.result.split(",")[1]));
    reader.addEventListener("error", () => reject(new Error("Не удалось прочитать изображение.")));
    reader.readAsDataURL(file);
  });
}

function renderEditor() {
  template("editor");
  const form = screen.querySelector("#editor");
  const {level, kind} = form.elements;
  for (const [key, title] of Object.entries(bank.levels)) level.add(new Option(title, key));
  level.value = settings.level;
  topicOptions(screen.querySelector("#editor-topics"), new Set());
  const setKindFields = () => {
    screen.querySelector("#options-field").hidden = kind.value !== "choice";
    screen.querySelector("#aliases-field").hidden = kind.value !== "short";
    screen.querySelector("#numeric-field").hidden = kind.value !== "short";
  };
  const setDefaultKind = () => {
    kind.value = level.value === "1" ? "choice" : "short";
    setKindFields();
  };
  level.addEventListener("change", setDefaultKind);
  kind.addEventListener("change", setKindFields);
  setDefaultKind();
  const error = element("p", "training-label");
  error.setAttribute("role", "alert");
  error.hidden = true;
  form.querySelector(".actions").before(error);
  screen.querySelector("#cancel-editor").addEventListener("click", () => {
    if (!busy) closeEditor();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    perform(async () => {
      const submit = form.querySelector("button[type='submit']");
      submit.disabled = true;
      try {
        const fields = new FormData(form);
        const image = fields.get("image");
        const topics = fields.getAll("topics");
        if (!topics.length) throw new Error("Выбери хотя бы одну тему.");
        const data = {
          ...Object.fromEntries(fields),
          level: Number(level.value),
          topics,
          numeric_set: fields.has("numeric_set"),
          image: image.size ? await encodeImage(image) : null,
        };
        bank = await request("/api/questions", data);
        closeEditor();
      } finally {
        submit.disabled = false;
      }
    }, error);
  });
}

function renderSources() {
  const layout = element("div", "stack");
  layout.append(element("h1", "", "Источники"));
  for (const [title, text, url, action] of [
    ["Правила Школы 21", "Регламент классической мафии, по которому составлены вопросы о правилах.", "/rules.pdf", "Открыть PDF"],
    ["Словарь MSU Mafia", "Жесты, фотографии и анимации из «Словаря по жестикуляции» MSU Mafia, 2022.", bank.dictionaryUrl, "Открыть словарь"],
  ]) {
    const card = element("article", "panel stack");
    card.append(element("h2", "", title), element("p", "", text), link(action, url));
    layout.append(card);
  }
  screen.append(layout);
}

async function initialize() {
  await perform(async () => {
    bank = await request("/api/bank");
    settings.topics = new Set(Object.keys(bank.topics));
    show("home", renderHome);
  });
  if (!bank) screen.replaceChildren(button("Попробовать снова", initialize, "primary"));
}

initialize();
