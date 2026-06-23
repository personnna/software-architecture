// User Management UI logic — calls auth-service through the API Gateway (port 8000)
const API_BASE = "/api/auth"; // gateway routes /api/auth -> auth-service

let token = null;

document.getElementById("loginBtn").addEventListener("click", async () => {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    document.getElementById("loginError").textContent = data.error || "Login failed";
    return;
  }

  if (data.user.role !== "admin") {
    document.getElementById("loginError").textContent = "Admin access required";
    return;
  }

  token = data.token;
  document.getElementById("loginCard").style.display = "none";
  document.getElementById("usersCard").style.display = "block";
  loadUsers();
});

document.getElementById("logoutBtn").addEventListener("click", () => {
  token = null;
  document.getElementById("usersCard").style.display = "none";
  document.getElementById("loginCard").style.display = "block";
});

async function loadUsers() {
  const res = await fetch(`${API_BASE}/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const users = await res.json();
  if (!res.ok) return alert(users.error || "Failed to load users");

  const tbody = document.getElementById("userTableBody");
  tbody.innerHTML = "";

  for (const u of users) {
    const tr = document.createElement("tr");

    // Email + name
    const tdEmail = document.createElement("td");
    tdEmail.textContent = u.email;
    const tdName = document.createElement("td");
    tdName.textContent = u.full_name || "—";

    // Role dropdown — changing it calls the admin-only role endpoint
    const tdRole = document.createElement("td");
    const select = document.createElement("select");
    select.className = "form-select form-select-sm";
    for (const role of ["admin", "trainer", "member"]) {
      const opt = document.createElement("option");
      opt.value = role;
      opt.textContent = role;
      if (role === u.role) opt.selected = true;
      select.appendChild(opt);
    }
    select.addEventListener("change", () => changeRole(u.id, select.value));
    tdRole.appendChild(select);

    // Active/disabled toggle
    const tdStatus = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "btn btn-sm " + (u.is_active ? "btn-success" : "btn-secondary");
    btn.textContent = u.is_active ? "Active" : "Disabled";
    btn.addEventListener("click", () => toggleStatus(u.id, !u.is_active));
    tdStatus.appendChild(btn);

    tr.append(tdEmail, tdName, tdRole, tdStatus);
    tbody.appendChild(tr);
  }
}

async function changeRole(userId, role) {
  const res = await fetch(`${API_BASE}/users/${userId}/role`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    const data = await res.json();
    alert(data.error || "Failed to change role");
  }
}

async function toggleStatus(userId, isActive) {
  const res = await fetch(`${API_BASE}/users/${userId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ is_active: isActive }),
  });
  if (!res.ok) {
    const data = await res.json();
    return alert(data.error || "Failed to change status");
  }
  loadUsers(); // refresh the row's button state
}
