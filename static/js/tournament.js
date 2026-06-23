// Tournament Setup UI logic — calls tournament-service through the API Gateway (port 8000)
const API_BASE = "/api/tournaments"; // gateway routes /api/tournaments -> tournament-service

let currentTournamentId = null;

function authHeaders(extra = {}) {
  const token = localStorage.getItem("access_token");
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

document.getElementById("createBtn").addEventListener("click", async () => {
  const name = document.getElementById("tName").value.trim();
  const sport = document.getElementById("tSport").value;
  const start_date = document.getElementById("tStartDate").value || null;
  const end_date = document.getElementById("tEndDate").value || null;
  if (!name) return alert("Please enter a tournament name");

  const res = await fetch(API_BASE, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ name, sport, start_date, end_date }),
  });
  const data = await res.json();
  if (!res.ok) return alert(data.error || "Failed to create tournament");

  currentTournamentId = data.id;
  document.getElementById("participantsCard").style.display = "block";
});

document.getElementById("addParticipantBtn").addEventListener("click", async () => {
  const name = document.getElementById("pName").value.trim();
  if (!name || !currentTournamentId) return;

  const res = await fetch(`${API_BASE}/${currentTournamentId}/participants`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ name }),
  });
  const data = await res.json();
  if (!res.ok) return alert(data.error || "Failed to add participant");

  const li = document.createElement("li");
  li.className = "list-group-item";
  li.textContent = data.name;
  document.getElementById("participantList").appendChild(li);
  document.getElementById("pName").value = "";
});

document.getElementById("generateBtn").addEventListener("click", async () => {
  if (!currentTournamentId) return;

  const res = await fetch(`${API_BASE}/${currentTournamentId}/generate-bracket`, {
    method: "POST",
    headers: authHeaders(),
  });
  const matches = await res.json();
  if (!res.ok) return alert(matches.error || "Failed to generate bracket");

  renderBracket(matches);
});

function renderBracket(matches) {
  const view = document.getElementById("bracketView");
  view.innerHTML = "";

  const rounds = {};
  matches.forEach((m) => {
    rounds[m.round] = rounds[m.round] || [];
    rounds[m.round].push(m);
  });

  Object.keys(rounds)
    .sort((a, b) => a - b)
    .forEach((roundNum) => {
      const col = document.createElement("div");
      col.className = "mb-3";
      col.innerHTML = `<strong>Round ${roundNum}</strong>`;
      rounds[roundNum].forEach((m) => {
        const row = document.createElement("div");
        row.className = "border rounded p-2 mb-1";
        row.textContent = `${m.participant_a_id || "BYE"} vs ${m.participant_b_id || "BYE"} — ${m.status}`;
        col.appendChild(row);
      });
      view.appendChild(col);
    });

  document.getElementById("bracketCard").style.display = "block";
}
