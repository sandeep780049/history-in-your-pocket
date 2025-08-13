// quiz.js - fetch /api/quiz and render a simple MCQ quiz on the page
async function loadQuiz(mmdd=null, count=5) {
  const url = new URL("/api/quiz", window.location.origin);
  if (mmdd) url.searchParams.set("mmdd", mmdd);
  url.searchParams.set("count", count);
  const res = await fetch(url);
  if (!res.ok) {
    document.getElementById("quiz-area").innerText = "Could not load quiz.";
    return;
  }
  const data = await res.json();
  renderQuiz(data.questions || []);
}

function renderQuiz(questions) {
  const container = document.getElementById("quiz-area");
  if (!container) return;
  container.innerHTML = "";
  if (!questions.length) {
    container.innerHTML = "<div class='small'>No quiz questions found for this selection.</div>";
    return;
  }
  const form = document.createElement("form");
  form.id = "quizForm";
  questions.forEach((q, idx) => {
    const qbox = document.createElement("div");
    qbox.className = "card";
    const qtitle = document.createElement("div");
    qtitle.className = "title";
    qtitle.innerText = `${idx+1}. ${q.question}`;
    qbox.appendChild(qtitle);

    const desc = document.createElement("div");
    desc.className = "small";
    desc.style.marginBottom = "8px";
    desc.innerText = q.description || "";
    qbox.appendChild(desc);

    q.options.forEach(opt => {
      const id = `${q.id}-${opt}`;
      const label = document.createElement("label");
      label.style.display = "block";
      label.style.marginBottom = "6px";
      const inp = document.createElement("input");
      inp.type = "radio";
      inp.name = q.id;
      inp.value = opt;
      inp.id = id;
      label.appendChild(inp);
      const span = document.createElement("span");
      span.style.marginLeft = "8px";
      span.innerText = opt;
      label.appendChild(span);
      qbox.appendChild(label);
    });

    // store correct answer as data attribute
    qbox.dataset.correct = q.correct;
    form.appendChild(qbox);
  });

  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "primary";
  submit.innerText = "Submit Quiz";
  submit.onclick = () => gradeQuiz(questions);
  form.appendChild(submit);

  container.appendChild(form);
}

function gradeQuiz(questions) {
  let score = 0;
  questions.forEach(q => {
    const sel = document.querySelector(`input[name="${q.id}"]:checked`);
    if (sel && parseInt(sel.value) === q.correct) score += 1;
  });
  const out = document.createElement("div");
  out.className = "card";
  out.innerHTML = `<div class="title">Your score: ${score} / ${questions.length}</div>
                   <div class="small">You can try again or export results.</div>`;
  const container = document.getElementById("quiz-area");
  container.appendChild(out);
}

