/**
 * Shopee Tools Universal — Frontend Application Controller
 * Handles Telegram Auth, WebSockets, Live Streaming, Data Filtering & Exports
 */

document.addEventListener("DOMContentLoaded", () => {
  // ===================================================================
  // STATE MANAGEMENT
  // ===================================================================
  const state = {
    sessionId: getOrCreateSessionId(),
    telegramUser: null,
    stringSession: localStorage.getItem("shopee_string_session") || "",
    apiId: localStorage.getItem("shopee_api_id") || "",
    apiHash: localStorage.getItem("shopee_api_hash") || "",
    phone: localStorage.getItem("shopee_phone") || "",
    isChecking: false,
    results: [],
    filter: "all",
    searchQuery: "",
    ws: null,
    wsConnected: false,
    autoScrollLog: true,
  };

  // ===================================================================
  // DOM ELEMENT REFERENCES
  // ===================================================================
  const el = {
    // Header & Status
    wsStatus: document.getElementById("ws-status"),
    wsStatusText: document.getElementById("ws-status-text"),
    authContainer: document.getElementById("auth-status-container"),
    authLabel: document.getElementById("auth-status-label"),
    btnAuthToggle: document.getElementById("btn-auth-toggle"),

    // Connected Banner
    bannerConnected: document.getElementById("banner-connected"),
    userAvatarText: document.getElementById("user-avatar-text"),
    tgUserName: document.getElementById("tg-user-name"),
    tgUserUsername: document.getElementById("tg-user-username"),
    tgUserPhone: document.getElementById("tg-user-phone"),
    btnCopySession: document.getElementById("btn-copy-session"),
    btnLogout: document.getElementById("btn-logout"),

    sectionAuth: document.getElementById("section-auth"),
    tabLoginBtn: document.getElementById("tab-login-btn"),
    tabRestoreBtn: document.getElementById("tab-restore-btn"),
    tabGuideBtn: document.getElementById("tab-guide-btn"),
    tabLoginContent: document.getElementById("tab-login-content"),
    tabRestoreContent: document.getElementById("tab-restore-content"),
    tabGuideContent: document.getElementById("tab-guide-content"),
    btnBackToLogin: document.getElementById("btn-back-to-login"),
    formSendOtp: document.getElementById("form-send-otp"),
    inputApiId: document.getElementById("input-api-id"),
    inputApiHash: document.getElementById("input-api-hash"),
    inputPhone: document.getElementById("input-phone"),
    btnSendOtp: document.getElementById("btn-send-otp"),
    otpContainer: document.getElementById("otp-container"),
    otpMessageInfo: document.getElementById("otp-message-info"),
    formVerifyOtp: document.getElementById("form-verify-otp"),
    inputOtp: document.getElementById("input-otp"),
    input2fa: document.getElementById("input-2fa"),
    btnVerifyOtp: document.getElementById("btn-verify-otp"),
    formRestoreSession: document.getElementById("form-restore-session"),
    restoreApiId: document.getElementById("restore-api-id"),
    restoreApiHash: document.getElementById("restore-api-hash"),
    restoreString: document.getElementById("restore-string"),
    btnRestoreSession: document.getElementById("btn-restore-session"),

    // Account Inputs
    textareaUsernames: document.getElementById("textarea-usernames"),
    accountCountBadge: document.getElementById("account-count-badge"),
    fileUploadInput: document.getElementById("file-upload-input"),
    btnSampleData: document.getElementById("btn-sample-data"),
    btnClearAccounts: document.getElementById("btn-clear-accounts"),

    // Config & Actions
    inputDelay: document.getElementById("input-delay"),
    delayValueLabel: document.getElementById("delay-value-label"),
    btnStartCheck: document.getElementById("btn-start-check"),
    btnStopCheck: document.getElementById("btn-stop-check"),

    // Stats & Progress
    statTotal: document.getElementById("stat-total"),
    statProcessed: document.getElementById("stat-processed"),
    statValid: document.getElementById("stat-valid"),
    statInvalid: document.getElementById("stat-invalid"),
    progressBarFill: document.getElementById("progress-bar-fill"),
    progressStatusText: document.getElementById("progress-status-text"),
    progressPercentText: document.getElementById("progress-percent-text"),

    // Console Log
    logBox: document.getElementById("log-box"),
    checkAutoscroll: document.getElementById("check-autoscroll"),
    btnClearLog: document.getElementById("btn-clear-log"),

    // Table & Filter
    resultsTable: document.getElementById("results-table"),
    tableBody: document.getElementById("table-body"),
    rowEmpty: document.getElementById("row-empty"),
    inputSearchTable: document.getElementById("input-search-table"),
    filterPills: document.querySelectorAll(".filter-pills .pill"),
    countAll: document.getElementById("count-all"),
    countValid: document.getElementById("count-valid"),
    countQris: document.getElementById("count-qris"),
    countFood: document.getElementById("count-food"),
    countFailed: document.getElementById("count-failed"),

    // Exports
    btnExportCsv: document.getElementById("btn-export-csv"),
    btnExportValidTxt: document.getElementById("btn-export-valid-txt"),
    btnCopyValid: document.getElementById("btn-copy-valid"),

    // Modals & Toasts
    modalSession: document.getElementById("modal-session"),
    modalSessionClose: document.getElementById("modal-session-close"),
    modalSessionText: document.getElementById("modal-session-text"),
    btnCopyModalSession: document.getElementById("btn-copy-modal-session"),
    toastContainer: document.getElementById("toast-container"),
  };

  // ===================================================================
  // HELPER UTILITIES
  // ===================================================================
  function getOrCreateSessionId() {
    let id = localStorage.getItem("shopee_session_id");
    if (!id || !/^[a-zA-Z0-9_\-]{16,64}$/.test(id)) {
      if (window.crypto && crypto.randomUUID) {
        id = "usr_" + crypto.randomUUID().replace(/-/g, "");
      } else {
        const arr = new Uint8Array(16);
        window.crypto.getRandomValues(arr);
        id = "usr_" + Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
      }
      localStorage.setItem("shopee_session_id", id);
    }
    return id;
  }

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    let icon = "i";
    if (type === "success") icon = "✓";
    if (type === "error") icon = "✕";
    if (type === "warning") icon = "!";

    toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-text">${escapeHtml(message)}</span>`;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-10px) scale(0.95)";
      setTimeout(() => toast.remove(), 250);
    }, 3800);
  }

  function appendLog(message, level = "info") {
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement("div");
    entry.className = `log-entry log-${level}`;
    entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-msg">${escapeHtml(message)}</span>`;
    el.logBox.appendChild(entry);

    if (state.autoScrollLog) {
      el.logBox.scrollTop = el.logBox.scrollHeight;
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function parseUsernamesFromText(text) {
    if (!text) return [];
    const tokens = text.split(/[\r\n,;\t\s]+/);
    const seen = new Set();
    const result = [];
    for (const token of tokens) {
      const clean = token.trim().replace(/^['"]|['"]$/g, "");
      if (clean && !clean.startsWith("#") && !seen.has(clean)) {
        result.push(clean);
        seen.add(clean);
      }
    }
    return result;
  }

  function updateAccountCount() {
    const list = parseUsernamesFromText(el.textareaUsernames.value);
    el.accountCountBadge.textContent = `${list.length} Akun`;
    el.statTotal.textContent = list.length;
  }

  // ===================================================================
  // AUTHENTICATION CONTROLLER
  // ===================================================================
  function setAuthState(user, stringSession = null) {
    state.telegramUser = user;
    if (stringSession) {
      state.stringSession = stringSession;
      localStorage.setItem("shopee_string_session", stringSession);
    }

    if (user) {
      // User is authenticated
      el.authContainer.className = "auth-pill authenticated";
      el.authLabel.textContent = `@${user.username || user.phone || "Telegram"}`;
      el.btnAuthToggle.textContent = "Ubah";

      el.sectionAuth.classList.add("hidden");
      el.bannerConnected.classList.remove("hidden");

      el.userAvatarText.textContent = (user.first_name || "T").substring(0, 2).toUpperCase();
      el.tgUserName.textContent = `${user.first_name} ${user.last_name || ""}`.trim();
      el.tgUserUsername.textContent = user.username ? `@${user.username}` : "Tanpa Username";
      el.tgUserPhone.textContent = user.phone || "-";
      appendLog(`Akun Telegram @${user.username || user.phone} terhubung & siap digunakan.`, "success");
    } else {
      // User logged out
      el.authContainer.className = "auth-pill unauthenticated";
      el.authLabel.textContent = "Belum Login Telegram";
      el.btnAuthToggle.textContent = "Masuk";

      el.sectionAuth.classList.remove("hidden");
      el.bannerConnected.classList.add("hidden");
    }
  }

  // Populate saved inputs
  if (state.apiId) el.inputApiId.value = state.apiId;
  if (state.apiHash) el.inputApiHash.value = state.apiHash;
  if (state.phone) el.inputPhone.value = state.phone;
  if (state.apiId) el.restoreApiId.value = state.apiId;
  if (state.apiHash) el.restoreApiHash.value = state.apiHash;
  if (state.stringSession) el.restoreString.value = state.stringSession;

  // Tabs for Auth (Login, Restore, Guide)
  function switchAuthTab(target) {
    el.tabLoginBtn?.classList.remove("active");
    el.tabRestoreBtn?.classList.remove("active");
    el.tabGuideBtn?.classList.remove("active");
    el.tabLoginContent?.classList.add("hidden");
    el.tabRestoreContent?.classList.add("hidden");
    el.tabGuideContent?.classList.add("hidden");

    if (target === "login") {
      el.tabLoginBtn?.classList.add("active");
      el.tabLoginContent?.classList.remove("hidden");
    } else if (target === "restore") {
      el.tabRestoreBtn?.classList.add("active");
      el.tabRestoreContent?.classList.remove("hidden");
    } else if (target === "guide") {
      el.tabGuideBtn?.classList.add("active");
      el.tabGuideContent?.classList.remove("hidden");
    }
  }

  el.tabLoginBtn?.addEventListener("click", () => switchAuthTab("login"));
  el.tabRestoreBtn?.addEventListener("click", () => switchAuthTab("restore"));
  el.tabGuideBtn?.addEventListener("click", () => switchAuthTab("guide"));
  el.btnBackToLogin?.addEventListener("click", () => {
    switchAuthTab("login");
    el.sectionAuth.scrollIntoView({ behavior: "smooth" });
  });

  // Toggle Auth Card
  el.btnAuthToggle.addEventListener("click", () => {
    el.sectionAuth.classList.toggle("hidden");
    if (!el.sectionAuth.classList.contains("hidden")) {
      el.sectionAuth.scrollIntoView({ behavior: "smooth" });
    }
  });

  // Step 1: Send OTP
  el.formSendOtp.addEventListener("submit", async (e) => {
    e.preventDefault();
    const apiId = parseInt(el.inputApiId.value.trim(), 10);
    const apiHash = el.inputApiHash.value.trim();
    const phone = el.inputPhone.value.trim();

    if (!apiId || !apiHash || !phone) {
      showToast("Mohon lengkapi seluruh formulir!", "error");
      return;
    }

    // Save for convenience
    localStorage.setItem("shopee_api_id", apiId);
    localStorage.setItem("shopee_api_hash", apiHash);
    localStorage.setItem("shopee_phone", phone);
    state.apiId = apiId;
    state.apiHash = apiHash;
    state.phone = phone;

    setLoading(el.btnSendOtp, true, "Mengirim OTP...");

    try {
      const resp = await fetch("/api/auth/send-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          api_id: apiId,
          api_hash: apiHash,
          phone: phone,
        }),
      });
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Gagal mengirim kode OTP");
      }

      showToast("Kode login berhasil dikirim ke Telegram Anda!", "success");
      el.otpMessageInfo.textContent = `Kode telah dikirim ke nomor ${phone}. Masukkan di bawah ini:`;
      el.otpContainer.classList.remove("hidden");
      el.inputOtp.focus();
      appendLog(`Kode login Telegram dikirim ke ${phone}. Menunggu verifikasi...`, "info");
    } catch (err) {
      showToast(err.message, "error");
      appendLog(`Error kirim OTP: ${err.message}`, "error");
    } finally {
      setLoading(el.btnSendOtp, false, "Kirim Kode OTP");
    }
  });

  // Step 2: Verify OTP
  el.formVerifyOtp.addEventListener("submit", async (e) => {
    e.preventDefault();
    const code = el.inputOtp.value.trim();
    const password = el.input2fa.value.trim();

    if (!code) {
      showToast("Masukkan kode OTP dari Telegram!", "error");
      return;
    }

    setLoading(el.btnVerifyOtp, true, "Memverifikasi...");

    try {
      const resp = await fetch("/api/auth/verify-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          code: code,
          password: password || null,
        }),
      });
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Gagal verifikasi kode OTP");
      }

      if (data.need_2fa) {
        showToast("Akun memiliki verifikasi 2 langkah (2FA). Silakan masukkan password 2FA Anda.", "warning");
        el.input2fa.focus();
        appendLog("Akun memerlukan Password 2FA.", "warning");
        return;
      }

      showToast("Login Telegram Berhasil!", "success");
      setAuthState(data.user, data.string_session);
    } catch (err) {
      showToast(err.message, "error");
      appendLog(`Gagal verifikasi OTP: ${err.message}`, "error");
    } finally {
      setLoading(el.btnVerifyOtp, false, "Verifikasi & Masuk ke Dashboard");
    }
  });

  // Restore via StringSession
  el.formRestoreSession.addEventListener("submit", async (e) => {
    e.preventDefault();
    const apiId = parseInt(el.restoreApiId.value.trim(), 10);
    const apiHash = el.restoreApiHash.value.trim();
    const stringSession = el.restoreString.value.trim();

    if (!apiId || !apiHash || !stringSession) {
      showToast("Mohon isi seluruh bidang StringSession!", "error");
      return;
    }

    setLoading(el.btnRestoreSession, true, "Memulihkan...");

    try {
      const resp = await fetch("/api/auth/restore-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          api_id: apiId,
          api_hash: apiHash,
          string_session: stringSession,
        }),
      });
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Gagal memulihkan sesi");
      }

      localStorage.setItem("shopee_api_id", apiId);
      localStorage.setItem("shopee_api_hash", apiHash);
      showToast("Sesi berhasil dipulihkan!", "success");
      setAuthState(data.user, stringSession);
    } catch (err) {
      showToast(err.message, "error");
      appendLog(`Gagal restore session: ${err.message}`, "error");
    } finally {
      setLoading(el.btnRestoreSession, false, "Pulihkan Sesi & Masuk");
    }
  });

  // Auto-restore on load if saved
  async function attemptAutoRestore() {
    if (state.stringSession && state.apiId && state.apiHash) {
      try {
        appendLog("Mencoba memulihkan sesi Telegram tersimpan...", "info");
        const resp = await fetch("/api/auth/restore-session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: state.sessionId,
            api_id: parseInt(state.apiId, 10),
            api_hash: state.apiHash,
            string_session: state.stringSession,
          }),
        });
        if (resp.ok) {
          const data = await resp.json();
          setAuthState(data.user, state.stringSession);
          showToast(`Sesi otomatis aktif: @${data.user.username || data.user.phone}`, "success");
        }
      } catch (e) {
        console.warn("Auto-restore session failed:", e);
      }
    }
  }

  // Logout
  el.btnLogout.addEventListener("click", async () => {
    if (!confirm("Apakah Anda yakin ingin keluar dari akun Telegram ini?")) return;
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId }),
      });
    } catch (e) {}
    localStorage.removeItem("shopee_string_session");
    state.stringSession = "";
    setAuthState(null);
    showToast("Berhasil logout dari akun Telegram.", "info");
    appendLog("Logout berhasil.", "info");
  });

  // Backup String Session Modal
  el.btnCopySession.addEventListener("click", () => {
    el.modalSessionText.value = state.stringSession || "Tidak ada sesi aktif.";
    el.modalSession.classList.remove("hidden");
  });
  el.modalSessionClose.addEventListener("click", () => el.modalSession.classList.add("hidden"));
  el.btnCopyModalSession.addEventListener("click", () => {
    navigator.clipboard.writeText(el.modalSessionText.value).then(() => {
      showToast("StringSession berhasil disalin ke clipboard!", "success");
    });
  });

  function setLoading(btn, loading, defaultText) {
    const textSpan = btn.querySelector(".btn-text");
    const spinner = btn.querySelector(".spinner");
    if (loading) {
      btn.disabled = true;
      if (textSpan) textSpan.textContent = defaultText;
      if (spinner) spinner.classList.remove("hidden");
    } else {
      btn.disabled = false;
      if (textSpan) textSpan.textContent = defaultText;
      if (spinner) spinner.classList.add("hidden");
    }
  }

  // ===================================================================
  // WEBSOCKET CONTROLLER
  // ===================================================================
  function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${state.sessionId}`;

    el.wsStatus.className = "status-pill status-offline";
    el.wsStatusText.textContent = "Menghubungkan...";

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      state.wsConnected = true;
      el.wsStatus.className = "status-pill status-online";
      el.wsStatusText.textContent = "Online";
      appendLog("Koneksi WebSocket terhubung ke server.", "info");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWsMessage(msg);
      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };

    ws.onclose = () => {
      state.wsConnected = false;
      el.wsStatus.className = "status-pill status-offline";
      el.wsStatusText.textContent = "Terputus";
      // Auto-reconnect after 3s
      setTimeout(initWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.warn("WebSocket error:", err);
    };

    state.ws = ws;
  }

  function handleWsMessage(msg) {
    switch (msg.type) {
      case "start":
        state.isChecking = true;
        setCheckingUi(true);
        state.results = [];
        renderTable();
        appendLog(msg.message, "info");
        break;

      case "progress":
        updateProgressBar(msg.current, msg.total, msg.percent, msg.username);
        break;

      case "log":
        appendLog(msg.message, msg.level || "info");
        break;

      case "result":
        addResultItem(msg.data, msg.stats);
        break;

      case "stopped":
        state.isChecking = false;
        setCheckingUi(false);
        showToast(msg.message, "warning");
        appendLog(msg.message, "warning");
        break;

      case "completed":
        state.isChecking = false;
        setCheckingUi(false);
        updateProgressBar(msg.total, msg.total, 100, "Selesai");
        showToast(msg.message, "success");
        appendLog(msg.message, "success");
        break;

      case "error":
        showToast(msg.message, "error");
        appendLog(msg.message, "error");
        state.isChecking = false;
        setCheckingUi(false);
        break;
    }
  }

  function setCheckingUi(checking) {
    if (checking) {
      el.btnStartCheck.classList.add("hidden");
      el.btnStopCheck.classList.remove("hidden");
      el.textareaUsernames.disabled = true;
    } else {
      el.btnStartCheck.classList.remove("hidden");
      el.btnStopCheck.classList.add("hidden");
      el.textareaUsernames.disabled = false;
    }
  }

  function updateProgressBar(current, total, percent, user) {
    el.progressBarFill.style.width = `${percent}%`;
    el.progressPercentText.textContent = `${percent}%`;
    el.progressStatusText.textContent = user 
      ? `Memeriksa (${current}/${total}): ${user}`
      : `Proses: ${current}/${total}`;
  }

  // ===================================================================
  // INPUT & CONTROLS
  // ===================================================================
  el.textareaUsernames.addEventListener("input", updateAccountCount);

  // File Upload
  el.fileUploadInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target.result;
      el.textareaUsernames.value = text;
      updateAccountCount();
      showToast(`Berhasil memuat file '${file.name}'`, "success");
      appendLog(`File '${file.name}' berhasil dimuat ke daftar akun.`, "info");
    };
    reader.readAsText(file);
    e.target.value = "";
  });

  // Sample data
  el.btnSampleData.addEventListener("click", () => {
    const samples = [
      "user_shopee_demo1",
      "user_shopee_demo2",
      "user_shopee_demo3",
      "user_shopee_demo4",
      "user_shopee_demo5",
    ];
    el.textareaUsernames.value = samples.join("\n");
    updateAccountCount();
    showToast("Data contoh berhasil dimasukkan.", "info");
  });

  // Clear accounts
  el.btnClearAccounts.addEventListener("click", () => {
    if (state.isChecking) return;
    el.textareaUsernames.value = "";
    updateAccountCount();
    state.results = [];
    renderTable();
    el.progressBarFill.style.width = "0%";
    el.progressPercentText.textContent = "0%";
    el.progressStatusText.textContent = "Siap memulai pengecekan";
    showToast("Daftar akun & hasil dibersihkan.", "info");
  });

  // Delay slider
  el.inputDelay.addEventListener("input", () => {
    el.delayValueLabel.textContent = `${parseFloat(el.inputDelay.value).toFixed(1)} detik`;
  });

  // Start Checking
  el.btnStartCheck.addEventListener("click", () => {
    if (!state.telegramUser) {
      showToast("Harap login Telegram terlebih dahulu!", "warning");
      el.sectionAuth.classList.remove("hidden");
      el.sectionAuth.scrollIntoView({ behavior: "smooth" });
      return;
    }

    const usernames = parseUsernamesFromText(el.textareaUsernames.value);
    if (!usernames.length) {
      showToast("Daftar akun Shopee masih kosong!", "warning");
      el.textareaUsernames.focus();
      return;
    }

    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
      showToast("Koneksi WebSocket belum siap, coba lagi sesaat lagi...", "error");
      return;
    }

    const selectedMode = document.querySelector('input[name="check-mode"]:checked').value;
    const delay = parseFloat(el.inputDelay.value);

    // Reset stats
    el.statTotal.textContent = usernames.length;
    el.statProcessed.textContent = "0";
    el.statValid.textContent = "0";
    el.statInvalid.textContent = "0";
    state.results = [];
    renderTable();

    state.ws.send(JSON.stringify({
      action: "start",
      usernames: usernames,
      mode: selectedMode,
      delay: delay,
    }));
  });

  // Stop Checking
  el.btnStopCheck.addEventListener("click", () => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ action: "stop" }));
      appendLog("Mengirim sinyal penghentian pengecekan...", "warning");
    }
  });

  // Console Log Controls
  el.checkAutoscroll.addEventListener("change", () => {
    state.autoScrollLog = el.checkAutoscroll.checked;
  });
  el.btnClearLog.addEventListener("click", () => {
    el.logBox.innerHTML = `
      <div class="log-entry log-system">
        <span class="log-time">[System]</span>
        <span class="log-msg">Log dibersihkan.</span>
      </div>`;
  });

  // ===================================================================
  // TABLE & RESULTS RENDERING
  // ===================================================================
  function addResultItem(item, stats) {
    state.results.push(item);
    if (stats) {
      el.statProcessed.textContent = stats.processed;
      el.statValid.textContent = stats.valid;
      el.statInvalid.textContent = stats.invalid;
    }
    updateFilterCounts();
    renderTable();
  }

  function updateFilterCounts() {
    el.countAll.textContent = state.results.length;
    el.countValid.textContent = state.results.filter(r => r.is_valid).length;
    el.countQris.textContent = state.results.filter(r => r.qris && r.qris.status === "SELESAI").length;
    el.countFood.textContent = state.results.filter(r => r.food && r.food.is_valid).length;
    el.countFailed.textContent = state.results.filter(r => !r.is_valid).length;
  }

  function renderTable() {
    el.tableBody.innerHTML = "";

    const filtered = state.results.filter(item => {
      // Search filter
      if (state.searchQuery && !item.username.toLowerCase().includes(state.searchQuery)) {
        return false;
      }
      // Pill filter
      if (state.filter === "valid") return item.is_valid;
      if (state.filter === "qris-done") return item.qris && item.qris.status === "SELESAI";
      if (state.filter === "food-ok") return item.food && item.food.is_valid;
      if (state.filter === "failed") return !item.is_valid;
      return true;
    });

    if (filtered.length === 0) {
      const emptyRow = document.createElement("tr");
      emptyRow.className = "empty-row";
      emptyRow.innerHTML = `<td colspan="5" class="text-center py-6 text-muted">
        ${state.results.length ? "Tidak ada akun yang cocok dengan filter." : "Belum ada hasil pengecekan."}
      </td>`;
      el.tableBody.appendChild(emptyRow);
      return;
    }

    filtered.forEach((r, idx) => {
      const tr = document.createElement("tr");

      // QRIS status text
      let qrisText = "-";
      if (r.qris) {
        if (r.qris.coins !== null && r.qris.coins !== undefined) {
          qrisText = `<strong>${r.qris.coins}</strong> Koin<br><span style="font-size:0.675rem; color:#4A4A4A;">${r.qris.status}</span>`;
        } else {
          qrisText = `<span style="font-size:0.75rem;">${r.qris.status}</span>`;
        }
      }

      // Food status text
      let foodText = "-";
      if (r.food) {
        if (r.food.has_25k && r.food.has_12k) {
          foodText = `<span class="badge-status badge-valid">25K+12K</span>`;
        } else if (r.food.has_25k) {
          foodText = `<span class="badge-status badge-partial">25K Saja</span>`;
        } else if (r.food.has_12k) {
          foodText = `<span class="badge-status badge-partial">12K Saja</span>`;
        } else {
          foodText = `<span style="font-size:0.75rem;">${r.food.status}</span>`;
        }
      }

      // Overall badge
      let badgeHtml = "";
      if (r.is_valid) {
        badgeHtml = `<span class="badge-status badge-valid">VALID</span>`;
      } else if (r.food?.status === "PARSIAL") {
        badgeHtml = `<span class="badge-status badge-partial">PARSIAL</span>`;
      } else if (r.qris?.status === "ERROR" || r.food?.status === "ERROR") {
        badgeHtml = `<span class="badge-status badge-error">ERROR</span>`;
      } else {
        badgeHtml = `<span class="badge-status badge-invalid">TIDAK</span>`;
      }

      const timeStr = r.timestamp.split(" ")[1] || r.timestamp;

      tr.innerHTML = `
        <td class="font-mono text-center">${idx + 1}</td>
        <td>
          <div style="font-weight: 800; color: #121212;">${escapeHtml(r.username)}</div>
          <div style="font-size: 0.675rem; color: #71717A;">${timeStr}</div>
        </td>
        <td style="font-size: 0.75rem;">${qrisText}</td>
        <td style="font-size: 0.75rem;">${foodText}</td>
        <td>${badgeHtml}</td>
      `;
      el.tableBody.appendChild(tr);
    });
  }

  // Filter Pill clicks
  el.filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      el.filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      state.filter = pill.getAttribute("data-filter");
      renderTable();
    });
  });

  // Table Search
  el.inputSearchTable.addEventListener("input", (e) => {
    state.searchQuery = e.target.value.trim().toLowerCase();
    renderTable();
  });

  // ===================================================================
  // EXPORT TOOLS (CSV & TXT)
  // ===================================================================
  // Export CSV
  el.btnExportCsv.addEventListener("click", () => {
    if (!state.results.length) {
      showToast("Belum ada data untuk di-export!", "warning");
      return;
    }

    const headers = [
      "Waktu",
      "Username",
      "Mode",
      "Koin QRIS",
      "Status Misi QRIS",
      "Status Voucher Food",
      "Diskon 25RB",
      "Ongkir 12RB",
      "Status Akhir",
      "Keterangan",
    ];

    const rows = state.results.map(r => [
      `"${r.timestamp}"`,
      `"${r.username}"`,
      `"${r.mode}"`,
      `"${r.qris?.coins !== null && r.qris?.coins !== undefined ? r.qris.coins : '-'}"`,
      `"${r.qris?.status || '-'}"`,
      `"${r.food?.status || '-'}"`,
      `"${r.food?.has_25k ? 'ADA' : 'TIDAK'}"`,
      `"${r.food?.has_12k ? 'ADA' : 'TIDAK'}"`,
      `"${r.is_valid ? 'VALID' : 'TIDAK VALID'}"`,
      `"${(r.food?.detail || r.qris?.detail || '-').replace(/"/g, '""')}"`,
    ]);

    const csvContent = "\uFEFF" + [headers.join(","), ...rows.map(e => e.join(","))].join("\r\n");
    downloadBlob(csvContent, `hasil_shopee_${Date.now()}.csv`, "text/csv;charset=utf-8;");
    showToast("File CSV berhasil diunduh!", "success");
  });

  // Export TXT of valid usernames
  el.btnExportValidTxt.addEventListener("click", () => {
    const validUsers = state.results.filter(r => r.is_valid).map(r => r.username);
    if (!validUsers.length) {
      showToast("Tidak ada akun valid yang ditemukan untuk di-export!", "warning");
      return;
    }
    const txtContent = validUsers.join("\r\n");
    downloadBlob(txtContent, `valid_shopee_${Date.now()}.txt`, "text/plain;charset=utf-8;");
    showToast(`Berhasil mengunduh ${validUsers.length} akun valid!`, "success");
  });

  // Copy valid to clipboard
  el.btnCopyValid.addEventListener("click", () => {
    const validUsers = state.results.filter(r => r.is_valid).map(r => r.username);
    if (!validUsers.length) {
      showToast("Belum ada akun valid yang ditemukan!", "warning");
      return;
    }
    navigator.clipboard.writeText(validUsers.join("\n")).then(() => {
      showToast(`${validUsers.length} akun valid berhasil disalin ke clipboard!`, "success");
    });
  });

  function downloadBlob(content, filename, contentType) {
    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  // ===================================================================
  // INITIALIZATION
  // ===================================================================
  updateAccountCount();
  initWebSocket();
  attemptAutoRestore();
});
