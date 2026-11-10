// Invites (invites.html): ask for new people to be let in, see your own requests,
// and - for the administrator - decide on everyone's. The server enforces who may do
// what (403 for anyone else); this page just hides what a person can't use.

const emailEl = document.getElementById("invite-email");
const sendBtn = document.getElementById("invite-send");
const problemEl = document.getElementById("invite-problem");
const leftEl = document.getElementById("invites-left");
const mineEl = document.getElementById("my-requests");
const adminSection = document.getElementById("admin-section");
const requestsEl = document.getElementById("invite-requests");
const STATUS_TEXT = { pending: "Awaiting approval", approved: "Approved", declined: "Declined" };

function showProblem(text) {
  problemEl.textContent = text;
  problemEl.classList.toggle("hidden", !text);
}

async function ask() {
  const email = emailEl.value.trim();
  if (!email) return;
  showProblem("");
  sendBtn.disabled = true;
  try {
    const invite = await Global.fetchJSON("/api/invites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    emailEl.value = "";
    Global.showMessage(
      invite.status === "approved" ? `${invite.email} has been let in.` : `Requested. ${invite.email} will be let in once it's approved.`,
      "success"
    );
  } catch (err) {
    showProblem(err.message);
  }
  sendBtn.disabled = false;
  load();
}

async function withdraw(invite) {
  try {
    await Global.fetchJSON(`/api/invites/${invite.id}`, { method: "DELETE" });
  } catch (err) {
    showProblem(err.message);
  }
  load();
}

function myRow(invite) {
  const row = Global.el("div", { class: "member-row" }, [
    Global.el("span", { class: "member-email", text: invite.email }),
    Global.el("span", { class: "item-badge item-badge-muted", text: STATUS_TEXT[invite.status] }),
  ]);
  if (invite.status === "pending") {
    const button = Global.el("button", { type: "button", class: "cancel-btn", text: "Withdraw" });
    button.addEventListener("click", () => withdraw(invite));
    row.appendChild(button);
  }
  return row;
}

async function decide(invite, action, buttons) {
  buttons.forEach((b) => (b.disabled = true));
  try {
    await Global.fetchJSON(`/api/admin/invites/${invite.id}/${action}`, { method: "POST" });
    Global.showMessage(action === "approve" ? `${invite.email} can now sign in.` : `Declined ${invite.email}.`, "success");
  } catch (err) {
    // e.g. Cloudflare refused: the request stays in the queue.
    Global.showMessage(err.message, "error");
  }
  load();
}

function requestCard(invite) {
  const approve = Global.el("button", { type: "button", class: "save-btn", text: "Approve" });
  const decline = Global.el("button", { type: "button", class: "cancel-btn", text: "Decline" });
  const buttons = [approve, decline];
  approve.addEventListener("click", () => decide(invite, "approve", buttons));
  decline.addEventListener("click", () => decide(invite, "decline", buttons));
  const asked = new Date(`${invite.created_at}Z`).toLocaleString();
  return Global.el("div", { class: "request-card" }, [
    Global.el("div", { class: "request-info" }, [
      Global.el("strong", { text: invite.email }),
      Global.el("div", { class: "field-hint", text: `Asked for by ${invite.invited_by_email} - ${asked}` }),
    ]),
    Global.el("div", { class: "request-actions" }, buttons),
  ]);
}

async function load() {
  // Fresh each time (not Global.currentUser(), which is cached for the page): the
  // number of invites left changes as people are asked for.
  let me;
  try {
    me = await Global.fetchJSON("/api/me");
  } catch (err) {
    return;
  }
  leftEl.textContent =
    me.invites_left === null ? "You can invite as many people as you like." : `You have ${me.invites_left} invite${me.invites_left === 1 ? "" : "s"} left.`;
  try {
    const mine = await Global.withLoading(mineEl, Global.fetchJSON("/api/invites"));
    mineEl.replaceChildren(...(mine.length ? mine.map(myRow) : [Global.el("p", { class: "field-hint", text: "You haven't asked for anyone yet." })]));
  } catch (err) {
    mineEl.replaceChildren(Global.el("p", { class: "field-hint", text: err.message }));
  }
  adminSection.classList.toggle("hidden", !me.is_admin);
  if (!me.is_admin) return;
  try {
    const waiting = await Global.withLoading(requestsEl, Global.fetchJSON("/api/admin/invites"));
    requestsEl.replaceChildren(...(waiting.length ? waiting.map(requestCard) : [Global.el("p", { class: "field-hint", text: "Nothing is waiting." })]));
  } catch (err) {
    requestsEl.replaceChildren(Global.el("p", { class: "field-hint", text: err.message }));
  }
}

sendBtn.addEventListener("click", ask);
emailEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    ask();
  }
});
emailEl.addEventListener("input", () => showProblem(""));
load();
