const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const modelSelect = document.getElementById("model-select");

function addMessage(role, content) {
  const item = document.createElement("div");
  item.className = `msg ${role}`;
  item.innerHTML = `<div class="role">${role}</div><div class="content"></div>`;
  item.querySelector(".content").textContent = content;
  chatLog.appendChild(item);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function loadPersona() {
  const response = await fetch("/api/persona");
  const data = await response.json();
  document.getElementById("persona-name").textContent = data.name;
  document.getElementById("persona-tagline").textContent = data.tagline;
  document.getElementById("persona-topics").innerHTML = data.topics
    .map((topic) => `<span>${topic}</span>`)
    .join("");
  addMessage("assistant", data.first_message);
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  addMessage("user", message);
  chatInput.value = "";
  addMessage("assistant", "...");

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      model: modelSelect.value,
    }),
  });
  const data = await response.json();
  chatLog.lastChild.remove();
  addMessage("assistant", data.reply || data.error || "No response");
});

loadPersona();

