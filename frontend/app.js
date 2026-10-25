document.addEventListener("DOMContentLoaded", () => {
    // --- Elements: Connection ---
    const ipInput = document.getElementById("ip-address");
    const rackInput = document.getElementById("rack");
    const slotInput = document.getElementById("slot");
    const portInput = document.getElementById("port");
    
    const btnPing = document.getElementById("btn-ping");
    const btnTestS7 = document.getElementById("btn-test-s7");
    const btnConnect = document.getElementById("btn-connect");
    const btnDisconnect = document.getElementById("btn-disconnect");
    const btnReconnect = document.getElementById("btn-reconnect");
    
    const indicator = document.getElementById("connection-indicator");
    const s7StateEl = document.getElementById("s7-state");
    const cpuStateEl = document.getElementById("cpu-state");
    const pingStateEl = document.getElementById("ping-state");
    const s7TestStateEl = document.getElementById("s7-test-state");
    const logList = document.getElementById("log-list");

    // --- Elements: Navigation ---
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    const appContainer = document.getElementById("app-container");
    const pageNames = { 'tab-connection': 'Connection', 'tab-tags': 'Tag Tables', 'tab-groups': 'Live Groups' };
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('page-title').textContent = pageNames[btn.dataset.target];
        });
        btn.addEventListener('keydown', event => {
            const directions = {ArrowDown:1, ArrowRight:1, ArrowUp:-1, ArrowLeft:-1};
            if (!(event.key in directions) && event.key !== 'Home' && event.key !== 'End') return;
            event.preventDefault();
            const tabs = Array.from(tabBtns);
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : (tabs.indexOf(btn)+directions[event.key]+tabs.length)%tabs.length;
            tabs[next].focus(); tabs[next].click();
        });
    });


    // --- Elements: Tag Tables ---
    const tableSelect = document.getElementById("tag-table-select");
    const tableListUl = document.getElementById("table-list");
    const btnNewTableSidebar = document.getElementById("btn-new-table-sidebar");
    const btnNewTable = document.getElementById("btn-new-table");
    const btnDeleteTable = document.getElementById("btn-delete-table");
    const btnTogglePoll = document.getElementById("btn-toggle-poll");
    const btnAddTag = document.getElementById("btn-add-tag");
    const tagsTbody = document.getElementById("tags-tbody");
    const readDiagnosticsBar = document.getElementById("read-diagnostics");

    // --- Modals ---
    const modalTable = document.getElementById("modal-table");
    const btnSaveTable = document.getElementById("btn-save-table");
    const tableNameInput = document.getElementById("modal-table-name");
    const tableDescInput = document.getElementById("modal-table-desc");
    const tableNameError = document.getElementById("modal-table-name-error");

    const modalTag = document.getElementById("modal-tag");
    const modalTagTitle = document.getElementById("modal-tag-title");
    const tagIdInput = document.getElementById("modal-tag-id");
    const tagNameInput = document.getElementById("modal-tag-name");
    const tagAreaSelect = document.getElementById("modal-tag-area");
    const groupDbNumber = document.getElementById("group-db-number");
    const tagDbNumberInput = document.getElementById("modal-tag-db-number");
    const tagTypeSelect = document.getElementById("modal-tag-type");
    const tagAddressInput = document.getElementById("modal-tag-address");
    const tagAccessSelect = document.getElementById("modal-tag-access");
    const tagAddressHelp = document.getElementById("tag-address-help");
    const tagAddressPreview = document.getElementById("tag-address-preview");
    const tagNameError = document.getElementById("modal-tag-name-error");
    const tagAddressError = document.getElementById("modal-tag-address-error");
    const btnSaveTag = document.getElementById("btn-save-tag");

    const modalWrite = document.getElementById("modal-write");
    const writeTagId = document.getElementById("write-tag-id");
    const writeMetaName = document.getElementById("write-meta-name");
    const writeMetaDest = document.getElementById("write-meta-dest");
    const writeMetaAddr = document.getElementById("write-meta-addr");
    const writeMetaType = document.getElementById("write-meta-type");
    const writeMetaCurrentStatus = document.getElementById("write-meta-current-status");
    const writeWarningQ = document.getElementById("write-warning-q");
    const writeInputBoolGroup = document.getElementById("write-input-bool-group");
    const writeBoolSelect = document.getElementById("write-bool-select");
    const writeInputNumericGroup = document.getElementById("write-input-numeric-group");
    const writeNumericInput = document.getElementById("write-numeric-input");
    const writeNumericHint = document.getElementById("write-numeric-hint");
    const writeInputError = document.getElementById("write-input-error");
    const compareCurrentVal = document.getElementById("compare-current-val");
    const compareProposedVal = document.getElementById("compare-proposed-val");
    const writeStatusMsg = document.getElementById("write-status-msg");
    const btnExecuteWrite = document.getElementById("btn-execute-write");

    // --- State ---
    let isConnected = false;
    let activeTableId = null;
    let isPollingTags = false;
    let tagPollInterval = null;
    let pollInterval = null;
    let activeModal = null;
    let lastActiveElement = null;
    let isWriteInFlight = false;
    
    // In-memory tag dictionary (tag_id -> tag object)
    const tagDataMap = new Map();

    // Never substitute simulated operations for the desktop bridge.
    let bridgeReady = null;
    const waitForApi = () => {
        if (window.pywebview && window.pywebview.api) return Promise.resolve(window.pywebview.api);
        if (bridgeReady) return bridgeReady;
        bridgeReady = new Promise((resolve) => {
        if (window.pywebview && window.pywebview.api) {
            resolve(window.pywebview.api);
            return;
        }
        indicator.textContent = "BACKEND UNAVAILABLE â€” waiting for application";
        document.querySelectorAll("button").forEach(button => {
            button.dataset.bridgeDisabled = String(button.disabled);
            button.disabled = true;
        });
        window.addEventListener("pywebviewready", () => {
            document.querySelectorAll("button[data-bridge-disabled]").forEach(button => {
                button.disabled = button.dataset.bridgeDisabled === "true";
                delete button.dataset.bridgeDisabled;
            });
            resolve(window.pywebview.api);
        }, { once: true });
    });
        return bridgeReady;
    };

    // --- Modal Management with Accessible Focus & Escape Trapping ---
    const openModal = (modal, triggerEl = null) => {
        lastActiveElement = triggerEl || document.activeElement;
        activeModal = modal;
        modal.classList.add("active");
        appContainer.setAttribute("inert", "");
        
        // Trap focus inside modal
        const focusable = modal.querySelectorAll('input:not([type=hidden]), select, textarea, button:not([disabled])');
        if (focusable.length > 0) {
            focusable[0].focus();
        }
    };

    const closeModal = (modal) => {
        if (!modal) return;
        modal.classList.remove("active");
        activeModal = null;
        appContainer.removeAttribute("inert");
        if (lastActiveElement && typeof lastActiveElement.focus === "function") {
            lastActiveElement.focus();
        }
    };

    // Global Key Listener for Modal Keyboard Navigation
    document.addEventListener("keydown", (e) => {
        if (!activeModal) return;

        // Escape closes idle dialog
        if (e.key === "Escape") {
            if (isWriteInFlight) {
                // Do not close while write is in flight
                return;
            }
            closeModal(activeModal);
            return;
        }

        // Tab focus trap
        if (e.key === "Tab") {
            const focusable = Array.from(activeModal.querySelectorAll('input:not([type=hidden]), select, textarea, button:not([disabled])')).filter(el => el.getClientRects().length > 0);
            if (focusable.length === 0) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];

            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    });

    document.querySelectorAll(".btn-close-modal").forEach(btn => {
        btn.addEventListener("click", () => {
            if (isWriteInFlight) return;
            const modal = btn.closest(".modal-overlay");
            closeModal(modal);
        });
    });

    // Close on clicking backdrop
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay && !isWriteInFlight) {
                closeModal(overlay);
            }
        });
    });

    // --- Tab Navigation ---
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => {
                b.classList.remove("active");
                b.setAttribute("aria-selected", "false");
            });
            tabContents.forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            btn.setAttribute("aria-selected", "true");
            const target = document.getElementById(btn.dataset.target);
            if (target) target.classList.add("active");
        });
    });

    // --- Connection Logic ---
    const getConfig = () => {
        if (!document.getElementById('connection-form').reportValidity()) return null;
        return {ip: ipInput.value.trim(), rack: Number(rackInput.value), slot: Number(slotInput.value), port: Number(portInput.value)};
    };

    const updateUIState = (status) => {
        if (!status) return;

        const state = status.state || "DISCONNECTED";
        indicator.textContent = state;
        indicator.className = `status-badge ${state.toLowerCase().replace(/\s+/g, '-')}`;
        
        let stateText = state;
        if (status.last_s7_success_time && state === "CONNECTED") {
            stateText += ` (Success: ${status.last_s7_success_time})`;
        }
        s7StateEl.textContent = stateText;
        s7StateEl.className = `value ${state.toLowerCase().replace(/\s+/g, '-')}`;
        
        if (status.cpu_state_error) {
            cpuStateEl.textContent = `${status.cpu_state} (Unavailable)`;
            cpuStateEl.className = `value unknown`;
        } else {
            cpuStateEl.textContent = status.cpu_state || "UNKNOWN";
            const cpuLower = (status.cpu_state || "").toLowerCase();
            cpuStateEl.className = `value ${cpuLower.includes('run') ? 'run' : (cpuLower.includes('stop') ? 'stop' : 'unknown')}`;
        }
        
        isConnected = (state === "CONNECTED");
        const guidance = document.getElementById("connection-guidance");
        if (guidance) guidance.textContent = isConnected
            ? "Connected. Open Tag Tables to monitor your values."
            : state === "DISCONNECTED" ? "Connect to read CPU status and live values."
            : "Check the activity log below for connection details.";
        btnConnect.disabled = isConnected;
        btnDisconnect.disabled = !isConnected;
        btnReconnect.disabled = (state === "DISCONNECTED");

        renderLogs(status.diagnostics || []);
    };

    const renderLogs = (diagnostics) => {
        logList.innerHTML = '';
        if (!diagnostics || diagnostics.length === 0) {
            logList.innerHTML = '<li class="log-empty">No connection activity yet.</li>';
            return;
        }
        
        diagnostics.forEach(log => {
            const li = document.createElement('li');
            
            const timeSpan = document.createElement('span');
            timeSpan.className = 'log-time';
            timeSpan.textContent = log.time || '';
            
            const opSpan = document.createElement('span');
            opSpan.className = 'log-op';
            opSpan.textContent = log.operation || '';
            
            const stSpan = document.createElement('span');
            stSpan.className = `log-status ${log.status || ''}`;
            stSpan.textContent = log.status || '';
            
            const dtSpan = document.createElement('span');
            dtSpan.className = 'log-details';
            dtSpan.textContent = log.details || '';
            
            li.appendChild(timeSpan);
            li.appendChild(opSpan);
            li.appendChild(stSpan);
            li.appendChild(dtSpan);
            logList.appendChild(li);
        });
        
        const container = document.querySelector('.log-container');
        if (container) container.scrollTop = container.scrollHeight;
    };

    btnPing.addEventListener("click", async () => {
        const api = await waitForApi();
        const conf = getConfig();
        if (!conf) return;
        pingStateEl.textContent = "TESTING...";
        pingStateEl.className = "value";
        const res = await api.ping(conf.ip, conf.rack, conf.slot, conf.port);
        if (res.success) {
            pingStateEl.textContent = `PASS (${res.latency}ms)`;
            pingStateEl.className = "value pass";
        } else {
            pingStateEl.textContent = `FAIL (${res.message || 'Error'})`;
            pingStateEl.className = "value fail";
        }
        pollStatus();
    });

    btnTestS7.addEventListener("click", async () => {
        const api = await waitForApi();
        const conf = getConfig();
        if (!conf) return;
        s7TestStateEl.textContent = "TESTING...";
        s7TestStateEl.className = "value";
        const res = await api.test_s7_communication(conf.ip, conf.rack, conf.slot, conf.port);
        if (res.success) {
            s7TestStateEl.textContent = `PASS (${res.latency}ms)`;
            s7TestStateEl.className = "value pass";
            if (res.cpu_state) {
                cpuStateEl.textContent = res.cpu_state;
            }
        } else {
            s7TestStateEl.textContent = `FAIL`;
            s7TestStateEl.className = "value fail";
        }
        pollStatus();
    });

    btnConnect.addEventListener("click", async () => {
        const api = await waitForApi();
        const conf = getConfig();
        if (!conf) return;
        btnConnect.disabled = true;
        indicator.textContent = "CONNECTING...";
        indicator.className = "status-badge connecting";
        await api.connect(conf.ip, conf.rack, conf.slot, conf.port);
        pollStatus();
    });

    btnDisconnect.addEventListener("click", async () => {
        const api = await waitForApi();
        btnDisconnect.disabled = true;
        await api.disconnect();
        pollStatus();
    });

    btnReconnect.addEventListener("click", async () => {
        const api = await waitForApi();
        const conf = getConfig();
        if (!conf) return;
        btnReconnect.disabled = true;
        indicator.textContent = "RECONNECTING...";
        indicator.className = "status-badge connecting";
        await api.reconnect(conf.ip, conf.rack, conf.slot, conf.port);
        pollStatus();
    });

    let isStatusPolling = false;
    const pollStatus = async () => {
        if (isStatusPolling) return;
        isStatusPolling = true;
        try {
            const api = await waitForApi();
            const status = await api.get_status();
            updateUIState(status);
        } catch (err) {
            console.error("Status poll error:", err);
        } finally {
            isStatusPolling = false;
        }
    };

    pollInterval = setInterval(pollStatus, 200);

    // --- Tag Tables Navigation & Loading ---
    const loadTables = async () => {
        const api = await waitForApi();
        const tables = await api.get_all_tables();
        
        tableSelect.innerHTML = '<option value="">Select a Table...</option>';
        tableListUl.innerHTML = '';
        
        tables.forEach(t => {
            // Dropdown option (for narrow layout)
            const opt = document.createElement("option");
            opt.value = t.id;
            opt.textContent = t.name;
            tableSelect.appendChild(opt);
            
            // Sidebar item (for wide layout)
            const li = document.createElement("li");
            li.textContent = t.name;
            li.dataset.id = t.id;
            li.setAttribute("role", "option");
            if (t.id === activeTableId) {
                li.classList.add("active");
                li.setAttribute("aria-selected", "true");
            }
            
            li.addEventListener("click", () => switchTable(t.id));
            tableListUl.appendChild(li);
        });
        
        if (tables.length > 0) {
            let targetId = activeTableId;
            if (!targetId || !tables.find(t => t.id === targetId)) {
                targetId = tables[0].id;
            }
            await switchTable(targetId);
        } else {
            activeTableId = null;
            btnAddTag.disabled = true;
            btnDeleteTable.disabled = true;
            btnTogglePoll.disabled = true;
            tagsTbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">
                        No tag tables yet. Click <strong>+ New</strong> to create your first table.
                    </td>
                </tr>
            `;
        }
    };

    const switchTable = async (tableId) => {
        activeTableId = parseInt(tableId, 10);
        tableSelect.value = activeTableId;
        
        document.querySelectorAll("#table-list li").forEach(li => {
            const isMatch = (parseInt(li.dataset.id, 10) === activeTableId);
            li.classList.toggle("active", isMatch);
            li.setAttribute("aria-selected", isMatch ? "true" : "false");
        });
        
        btnAddTag.disabled = false;
        btnDeleteTable.disabled = false;
        btnTogglePoll.disabled = false;
        
        const api = await waitForApi();
        await api.set_active_table(activeTableId);
        await loadTags();
    };

    tableSelect.addEventListener("change", (e) => {
        if (e.target.value) {
            switchTable(e.target.value);
        }
    });

    const loadTags = async () => {
        if (!activeTableId) return;
        const api = await waitForApi();
        const tags = await api.get_tags_for_table(activeTableId);
        
        tagDataMap.clear();
        tagsTbody.innerHTML = '';
        
        if (tags.length === 0) {
            tagsTbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">
                        No tags defined in this table. Click <strong>+ Add Tag</strong> to define one.
                    </td>
                </tr>
            `;
            return;
        }
        
        tags.forEach(t => {
            tagDataMap.set(t.id, t);
            
            const tr = document.createElement("tr");
            tr.id = `tag-row-${t.id}`;
            
            // Name cell (safe textContent prevents HTML injection / apostrophe issues)
            const tdName = document.createElement("td");
            const pick = document.createElement("input");
            pick.type = "checkbox"; pick.className = "tag-pick";
            pick.dataset.tagId = t.id; pick.setAttribute("aria-label", `Select ${t.name} for a group`);
            tdName.appendChild(pick);
            tdName.appendChild(document.createTextNode(t.name));
            tdName.style.fontWeight = "600";
            tr.appendChild(tdName);
            
            // Address cell
            const tdAddr = document.createElement("td");
            tdAddr.className = "tag-addr-cell";
            tdAddr.textContent = formatDisplayAddress(t);
            tr.appendChild(tdAddr);
            
            
            // Value cell
            const tdVal = document.createElement("td");
            tdVal.className = "tag-val";
            tdVal.textContent = isPollingTags ? "Reading..." : "Not monitored";
            tr.appendChild(tdVal);
            
            // Quality cell
            const tdQual = document.createElement("td");
            tdQual.className = "tag-qual";
            tdQual.textContent = "---";
            tr.appendChild(tdQual);
            
            
            // Actions cell
            const tdActions = document.createElement("td");
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "tag-actions-cell";
            
            const btnEdit = document.createElement("button");
            btnEdit.type = "button";
            btnEdit.className = "btn btn-small secondary";
            btnEdit.textContent = "Edit";
            btnEdit.addEventListener("click", () => openEditTagModal(t.id));
            actionsDiv.appendChild(btnEdit);
            
            if (t.access_mode === "Read/Write") {
                const btnWrite = document.createElement("button");
                btnWrite.type = "button";
                btnWrite.className = "btn btn-small primary";
                btnWrite.textContent = "Write";
                btnWrite.addEventListener("click", () => openWriteModal(t.id));
                actionsDiv.appendChild(btnWrite);
            }
            
            const btnDel = document.createElement("button");
            btnDel.type = "button";
            btnDel.className = "btn btn-small danger";
            btnDel.textContent = "Delete tag";
            btnDel.addEventListener("click", () => deleteTag(t.id, t.name));
            const details = document.createElement("details");
            details.className = "tag-details";
            const summary = document.createElement("summary");
            summary.textContent = "Details";
            summary.setAttribute("aria-label", `Details for ${t.name}`);
            details.appendChild(summary);
            const metadata = document.createElement("div");
            metadata.className = "tag-metadata";
            const description = document.createElement("span");
            description.textContent = `${t.data_type} · ${t.access_mode}`;
            metadata.appendChild(description);
            const latency = document.createElement("span");
            latency.textContent = "Latency: ";
            const latencyValue = document.createElement("span");
            latencyValue.className = "tag-lat";
            latencyValue.textContent = "—";
            latency.appendChild(latencyValue);
            metadata.appendChild(latency);
            metadata.appendChild(btnDel);
            details.appendChild(metadata);
            tdName.appendChild(details);
            
            tdActions.appendChild(actionsDiv);
            tr.appendChild(tdActions);
            
            tagsTbody.appendChild(tr);
        });
    };

    const formatDisplayAddress = (t) => {
        const area = (t.area || "M").toUpperCase();
        const dt = (t.data_type || "BOOL").toUpperCase();
        const addr = (t.address || "0").trim();
        
        if (area === "DB") {
            const dbNum = t.db_number || 1;
            let prefix = "DBD";
            if (dt === "BOOL") prefix = "DBX";
            else if (["BYTE", "SINT", "USINT"].includes(dt)) prefix = "DBB";
            else if (["INT", "UINT", "WORD"].includes(dt)) prefix = "DBW";
            
            // Strip any user-typed prefix in address
            const clean = addr.replace(/^DB\d+\./i, '').replace(/^(DBX|DBB|DBW|DBD)/i, '');
            return `DB${dbNum}.${prefix}${clean}`;
        } else {
            const areaChar = area === "M" ? "M" : (area === "I" ? "I" : "Q");
            if (dt === "BOOL") {
                const clean = addr.replace(/^[MIQ]/i, '');
                return `${areaChar}${clean}`;
            } else if (["BYTE", "SINT", "USINT"].includes(dt)) {
                const clean = addr.replace(/^[MIQ]B?/i, '').split('.')[0];
                return `${areaChar}B${clean}`;
            } else if (["INT", "UINT", "WORD"].includes(dt)) {
                const clean = addr.replace(/^[MIQ]W?/i, '').split('.')[0];
                return `${areaChar}W${clean}`;
            } else {
                const clean = addr.replace(/^[MIQ]D?/i, '').split('.')[0];
                return `${areaChar}D${clean}`;
            }
        }
    };

    const deleteTag = async (tagId, tagName) => {
        if (confirm(`Are you sure you want to delete tag "${tagName}"?`)) {
            const api = await waitForApi();
            await api.delete_tag(tagId);
            await loadTags();
        }
    };

    // --- Table Creation & Deletion ---
    const handleNewTableClick = () => {
        tableNameInput.value = "";
        tableDescInput.value = "";
        tableNameError.style.display = "none";
        tableNameError.textContent = "";
        openModal(modalTable);
    };

    btnNewTableSidebar.addEventListener("click", handleNewTableClick);
    btnNewTable.addEventListener("click", handleNewTableClick);

    btnSaveTable.addEventListener("click", async () => {
        const name = tableNameInput.value.trim();
        if (!name) {
            tableNameError.textContent = "Table name is required.";
            tableNameError.style.display = "block";
            tableNameInput.focus();
            return;
        }
        tableNameError.style.display = "none";
        
        const api = await waitForApi();
        const res = await api.create_table(name, tableDescInput.value.trim());
        if (res.success) {
            closeModal(modalTable);
            activeTableId = res.id;
            await loadTables();
        } else {
            tableNameError.textContent = res.message || "Failed to create table.";
            tableNameError.style.display = "block";
        }
    });

    btnDeleteTable.addEventListener("click", async () => {
        if (!activeTableId) return;
        const currentOpt = tableSelect.querySelector(`option[value="${activeTableId}"]`);
        const tableName = currentOpt ? currentOpt.textContent : "this table";
        
        if (confirm(`Are you sure you want to permanently delete table "${tableName}" and all its tags?`)) {
            const api = await waitForApi();
            await api.delete_table(activeTableId);
            activeTableId = null;
            await loadTables();
        }
    });

    // --- Add & Edit Tag Dialog with Dynamic Guidance ---
    const updateAddressGuidanceAndPreview = () => {
        const area = tagAreaSelect.value;
        const dt = tagTypeSelect.value;
        const dbNum = tagDbNumberInput.value || "1";
        const addr = tagAddressInput.value.trim();

        // 1. Update help text with clear examples
        if (dt === "BOOL") {
            tagAddressHelp.textContent = area === "DB" 
                ? "Byte.bit offset inside DB, for example 0.0 or 4.7" 
                : "Byte.bit offset, for example 0.0 or 10.3";
        } else if (["BYTE", "SINT", "USINT"].includes(dt)) {
            tagAddressHelp.textContent = area === "DB" 
                ? "Byte offset (1 byte), for example 0 or 2" 
                : "Byte offset (1 byte), for example 0 or 10";
        } else if (["INT", "UINT", "WORD"].includes(dt)) {
            tagAddressHelp.textContent = area === "DB" 
                ? "Word byte offset (2 bytes, even byte recommended), for example 0 or 2" 
                : "Word byte offset (2 bytes), for example 0 or 10";
        } else {
            tagAddressHelp.textContent = area === "DB" 
                ? "DWord byte offset (4 bytes, even byte recommended), for example 0 or 4" 
                : "DWord byte offset (4 bytes), for example 0 or 4";
        }

        // 2. Generate live resolved address preview
        if (!addr) {
            tagAddressPreview.textContent = "Preview: (enter offset)";
            return;
        }

        try {
            const dummyTag = { area, db_number: parseInt(dbNum, 10), address: addr, data_type: dt };
            const resolved = formatDisplayAddress(dummyTag);
            tagAddressPreview.textContent = `Preview: ${resolved}`;
        } catch {
            tagAddressPreview.textContent = `Preview: ${addr}`;
        }
    };

    tagAreaSelect.addEventListener("change", () => {
        groupDbNumber.style.display = (tagAreaSelect.value === "DB") ? "block" : "none";
        updateAddressGuidanceAndPreview();
    });
    tagTypeSelect.addEventListener("change", updateAddressGuidanceAndPreview);
    tagDbNumberInput.addEventListener("input", updateAddressGuidanceAndPreview);
    tagAddressInput.addEventListener("input", updateAddressGuidanceAndPreview);

    btnAddTag.addEventListener("click", () => {
        modalTagTitle.textContent = "Add Tag";
        tagIdInput.value = "";
        tagNameInput.value = "";
        tagAreaSelect.value = "M";
        groupDbNumber.style.display = "none";
        tagDbNumberInput.value = "1";
        tagTypeSelect.value = "BOOL";
        tagAddressInput.value = "0.0";
        tagAccessSelect.value = "Read/Write";
        
        tagNameError.style.display = "none";
        tagAddressError.style.display = "none";
        updateAddressGuidanceAndPreview();
        openModal(modalTag);
    });

    const openEditTagModal = (tagId) => {
        const t = tagDataMap.get(tagId);
        if (!t) return;
        
        modalTagTitle.textContent = "Edit Tag";
        tagIdInput.value = t.id;
        tagNameInput.value = t.name;
        tagAreaSelect.value = t.area;
        groupDbNumber.style.display = (t.area === "DB") ? "block" : "none";
        tagDbNumberInput.value = t.db_number || 1;
        tagTypeSelect.value = t.data_type;
        tagAddressInput.value = t.address;
        tagAccessSelect.value = t.access_mode;
        
        tagNameError.style.display = "none";
        tagAddressError.style.display = "none";
        updateAddressGuidanceAndPreview();
        openModal(modalTag);
    };

    btnSaveTag.addEventListener("click", async () => {
        const id = tagIdInput.value;
        const name = tagNameInput.value.trim();
        const area = tagAreaSelect.value;
        const dbNumber = (area === "DB") ? parseInt(tagDbNumberInput.value, 10) : null;
        const dataType = tagTypeSelect.value;
        const address = tagAddressInput.value.trim();
        const accessMode = tagAccessSelect.value;

        // Validation
        let valid = true;
        if (!name) {
            tagNameError.textContent = "Tag name is required.";
            tagNameError.style.display = "block";
            valid = false;
        } else {
            tagNameError.style.display = "none";
        }

        if (!address) {
            tagAddressError.textContent = "Address is required.";
            tagAddressError.style.display = "block";
            valid = false;
        } else {
            tagAddressError.style.display = "none";
        }

        if (!valid) return;

        const api = await waitForApi();
        let res;
        if (id) {
            res = await api.update_tag(parseInt(id, 10), name, area, dbNumber, address, dataType, accessMode, "");
        } else {
            res = await api.create_tag(activeTableId, name, area, dbNumber, address, dataType, accessMode, "");
        }

        if (res.success) {
            closeModal(modalTag);
            await loadTags();
        } else {
            tagAddressError.textContent = res.message || "Validation failed.";
            tagAddressError.style.display = "block";
            tagAddressInput.focus();
        }
    });

    // --- Redesigned Write Value Dialog ---
    const openWriteModal = async (tagId) => {
        const api = await waitForApi();
        const info = await api.get_tag_details_for_write(tagId);
        
        if (!info || !info.success) {
            alert(info ? info.message : "Failed to load tag details.");
            return;
        }

        const t = info.tag;
        writeTagId.value = t.id;
        writeMetaName.textContent = t.name;
        writeMetaDest.textContent = `${info.plc_ip || '---'}:${info.plc_port || 102}`;
        writeMetaAddr.textContent = info.resolved_address;
        writeMetaType.textContent = t.data_type;
        
        // Current status
        if (info.current_value !== null && info.current_value !== undefined) {
            const qual = info.quality || "UNKNOWN";
            const ts = info.timestamp ? ` at ${info.timestamp}` : "";
            writeMetaCurrentStatus.textContent = `${info.current_value} (${qual}${ts})`;
            compareCurrentVal.textContent = String(info.current_value);
        } else {
            writeMetaCurrentStatus.textContent = "Unavailable";
            compareCurrentVal.textContent = "Unavailable";
        }

        // Q Output Warning
        writeWarningQ.style.display = (t.area === "Q") ? "block" : "none";

        // Input Setup based on Data Type
        const dtUpper = t.data_type.toUpperCase();
        writeInputError.style.display = "none";
        writeInputError.textContent = "";
        writeStatusMsg.className = "write-status-msg";
        writeStatusMsg.textContent = "";
        writeStatusMsg.style.display = "none";
        compareProposedVal.textContent = "None";

        if (dtUpper === "BOOL") {
            writeInputBoolGroup.style.display = "block";
            writeInputNumericGroup.style.display = "none";
            writeBoolSelect.value = "";
        } else {
            writeInputBoolGroup.style.display = "none";
            writeInputNumericGroup.style.display = "block";
            writeNumericInput.value = "";
            
            if (["BYTE", "USINT"].includes(dtUpper)) {
                writeNumericHint.textContent = "Valid range: 0 to 255 (unsigned 8-bit integer)";
            } else if (dtUpper === "SINT") {
                writeNumericHint.textContent = "Valid range: -128 to 127 (signed 8-bit integer)";
            } else if (dtUpper === "INT") {
                writeNumericHint.textContent = "Valid range: -32,768 to 32,767 (signed 16-bit integer)";
            } else if (["UINT", "WORD"].includes(dtUpper)) {
                writeNumericHint.textContent = "Valid range: 0 to 65,535 (unsigned 16-bit integer)";
            } else if (dtUpper === "DINT") {
                writeNumericHint.textContent = "Valid range: -2,147,483,648 to 2,147,483,647 (signed 32-bit integer)";
            } else if (["UDINT", "DWORD"].includes(dtUpper)) {
                writeNumericHint.textContent = "Valid range: 0 to 4,294,967,295 (unsigned 32-bit integer)";
            } else if (dtUpper === "REAL") {
                writeNumericHint.textContent = "Valid range: IEEE 754 32-bit floating point (finite decimal number)";
            }
        }

        // Connection Check
        if (!info.plc_connected) {
            btnExecuteWrite.disabled = true;
            writeStatusMsg.className = "write-status-msg warning";
            writeStatusMsg.textContent = "Connect to a PLC before writing.";
            writeStatusMsg.style.display = "block";
        } else {
            btnExecuteWrite.disabled = true; // Enabled when user selects/types valid value
        }

        openModal(modalWrite);
    };

    const validateWriteInput = () => {
        const tagId = parseInt(writeTagId.value, 10);
        const t = tagDataMap.get(tagId);
        if (!t) return { valid: false };

        const dtUpper = t.data_type.toUpperCase();
        let proposed = null;

        if (dtUpper === "BOOL") {
            const val = writeBoolSelect.value;
            if (val === "true" || val === "false") {
                proposed = (val === "true");
                writeInputError.style.display = "none";
                compareProposedVal.textContent = proposed ? "True (1)" : "False (0)";
                return { valid: true, value: proposed };
            } else {
                compareProposedVal.textContent = "None";
                return { valid: false };
            }
        } else {
            const val = writeNumericInput.value.trim();
            if (!val) {
                compareProposedVal.textContent = "None";
                writeInputError.style.display = "none";
                return { valid: false };
            }

            if (dtUpper === "REAL") {
                const f = Number(val);
                if (isNaN(f) || !isFinite(f)) {
                    writeInputError.textContent = "Please enter a valid finite decimal number.";
                    writeInputError.style.display = "block";
                    compareProposedVal.textContent = "Invalid";
                    return { valid: false };
                }
                writeInputError.style.display = "none";
                compareProposedVal.textContent = String(f);
                return { valid: true, value: f };
            } else {
                // Integer types
                if (!/^-?\d+$/.test(val)) {
                    writeInputError.textContent = "Please enter an integer number without decimal points.";
                    writeInputError.style.display = "block";
                    compareProposedVal.textContent = "Invalid";
                    return { valid: false };
                }
                const n = Number(val);
                let min = 0, max = 0;
                if (["BYTE", "USINT"].includes(dtUpper)) { min = 0; max = 255; }
                else if (dtUpper === "SINT") { min = -128; max = 127; }
                else if (dtUpper === "INT") { min = -32768; max = 32767; }
                else if (["UINT", "WORD"].includes(dtUpper)) { min = 0; max = 65535; }
                else if (dtUpper === "DINT") { min = -2147483648; max = 2147483647; }
                else if (["UDINT", "DWORD"].includes(dtUpper)) { min = 0; max = 4294967295; }

                if (n < min || n > max) {
                    writeInputError.textContent = `Value ${n} is out of bounds for ${dtUpper} (${min} to ${max}).`;
                    writeInputError.style.display = "block";
                    compareProposedVal.textContent = "Out of bounds";
                    return { valid: false };
                }

                writeInputError.style.display = "none";
                compareProposedVal.textContent = String(n);
                return { valid: true, value: n };
            }
        }
    };

    writeBoolSelect.addEventListener("change", () => {
        const check = validateWriteInput();
        if (!isWriteInFlight && isConnected && check.valid) {
            btnExecuteWrite.disabled = isWriteInFlight || !isConnected;
        } else {
            btnExecuteWrite.disabled = true;
        }
    });

    writeNumericInput.addEventListener("input", () => {
        const check = validateWriteInput();
        if (!isWriteInFlight && isConnected && check.valid) {
            btnExecuteWrite.disabled = isWriteInFlight || !isConnected;
        } else {
            btnExecuteWrite.disabled = true;
        }
    });

    btnExecuteWrite.addEventListener("click", async () => {
        if (isWriteInFlight || !isConnected) return;
        const check = validateWriteInput();
        if (!check.valid) return;

        const tagId = parseInt(writeTagId.value, 10);
        isWriteInFlight = true;
        const api = await waitForApi();
        btnExecuteWrite.disabled = true;
        btnExecuteWrite.textContent = "Writing...";
        writeStatusMsg.className = "write-status-msg";
        writeStatusMsg.textContent = "Sending write command and verifying readback...";
        writeStatusMsg.style.display = "block";

        try {
            const res = await api.write_tag(tagId, check.value);
            isWriteInFlight = false;
            btnExecuteWrite.textContent = "Write Value";

            if (res.success) {
                writeStatusMsg.className = "write-status-msg success";
                writeStatusMsg.textContent = res.message || "Write verified.";
                // Refresh tag table live values
                if (isPollingTags) {
                    setTimeout(() => closeModal(modalWrite), 1200);
                }
            } else {
                btnExecuteWrite.disabled = isWriteInFlight || !isConnected;
                if ((res.message || "").toLowerCase().includes("verification failed")) {
                    writeStatusMsg.className = "write-status-msg warning";
                } else {
                    writeStatusMsg.className = "write-status-msg error";
                }
                writeStatusMsg.textContent = res.message || "Write failed.";
            }
        } catch (e) {
            isWriteInFlight = false;
            btnExecuteWrite.disabled = isWriteInFlight || !isConnected;
            btnExecuteWrite.textContent = "Write Value";
            writeStatusMsg.className = "write-status-msg error";
            writeStatusMsg.textContent = `Error: ${e.message || String(e)}`;
        }
    });

    // --- Tag Monitoring Polling Loop ---
    btnTogglePoll.addEventListener("click", async () => {
        const api = await waitForApi();
        if (!activeTableId && tableSelect.value) {
            activeTableId = parseInt(tableSelect.value, 10);
        }
        
        isPollingTags = !isPollingTags;
        await api.set_polling(isPollingTags, activeTableId);
        
        if (isPollingTags) {
            btnTogglePoll.textContent = "Stop Monitoring";
            btnTogglePoll.classList.remove("primary");
            btnTogglePoll.classList.add("danger");
            
            let isTagPolling = false;
            tagPollInterval = setInterval(async () => {
                if (isTagPolling) return;
                isTagPolling = true;
                let response = null;
                try {
                    response = await api.get_live_tags();
                } catch (err) {
                    console.error("Live tag poll error:", err);
                } finally {
                    isTagPolling = false;
                }
                if (!response || !response.tags) return;
                
                const live = response.tags;
                const diag = response.diagnostics;
                
                // Update diagnostic bar
                if (readDiagnosticsBar && diag) {
                    readDiagnosticsBar.innerHTML = `
                        <span><strong>Status:</strong> Active</span>
                        <span><strong>Last Poll:</strong> ${diag.last_cycle}</span>
                        <span><strong>Attempted:</strong> ${diag.attempted}</span>
                        <span><strong>Success:</strong> <span style="color: var(--success-light);">${diag.success}</span></span>
                        <span><strong>Failed:</strong> <span style="color: var(--danger-hover);">${diag.failed}</span></span>
                        ${diag.last_error && diag.last_error !== "None" ? `<span><strong>Error:</strong> ${diag.last_error}</span>` : ''}
                    `;
                }
                
                Object.keys(live).forEach(tId => {
                    const row = document.getElementById(`tag-row-${tId}`);
                    if (!row) return;
                    
                    const d = live[tId];
                    const valEl = row.querySelector('.tag-val');
                    const qualEl = row.querySelector('.tag-qual');
                    const latEl = row.querySelector('.tag-lat');
                    
                    if (d.quality === "GOOD") {
                        valEl.textContent = (d.value !== null) ? d.value : '---';
                        valEl.style.color = 'var(--text-main)';
                        qualEl.textContent = "GOOD";
                        qualEl.className = "tag-qual value pass";
                        latEl.textContent = `${d.latency}ms`;
                    } else if (d.quality === "STALE") {
                        valEl.innerHTML = `${d.value} <span class="stale-note">Stale: ${d.timestamp || ''}</span>`;
                        valEl.style.color = 'var(--warning)';
                        qualEl.textContent = "STALE";
                        qualEl.className = "tag-qual value stop";
                        latEl.textContent = `${d.latency}ms`;
                    } else {
                        // BAD / UNKNOWN
                        if (!isConnected) {
                            valEl.textContent = "Disconnected";
                        } else {
                            valEl.textContent = "Read failed";
                        }
                        valEl.style.color = 'var(--danger-hover)';
                        qualEl.textContent = "BAD";
                        qualEl.className = "tag-qual value fail";
                        latEl.textContent = `${d.latency}ms`;
                    }
                });
            }, 500);
            
        } else {
            btnTogglePoll.textContent = "Start Monitoring";
            btnTogglePoll.classList.add("primary");
            btnTogglePoll.classList.remove("danger");
            clearInterval(tagPollInterval);
            
            if (readDiagnosticsBar) {
                readDiagnosticsBar.innerHTML = `
                    <span><strong>Status:</strong> Not monitoring</span>
                    <span><strong>Last Poll:</strong> Never</span>
                    <span><strong>Attempted:</strong> 0</span>
                    <span><strong>Success:</strong> 0</span>
                    <span><strong>Failed:</strong> 0</span>
                `;
            }
            
            document.querySelectorAll('.tag-val').forEach(el => {
                el.textContent = 'Not monitored';
                el.style.color = 'var(--text-muted)';
            });
            document.querySelectorAll('.tag-qual').forEach(el => {
                el.textContent = '---';
                el.className = 'tag-qual';
            });
            document.querySelectorAll('.tag-lat').forEach(el => {
                el.textContent = '---';
            });
        }
    });

    window.initGroups({waitForApi, openModal, closeModal});

    // Initialize
    waitForApi().then(() => {
        loadTables().then(() => {
            // Check hash navigation for tests/screenshots
            const hash = window.location.hash.toLowerCase();
            if (hash.includes("tags") || hash.includes("add-tag") || hash.includes("write")) {
                const btnTags = document.getElementById("tab-btn-tags");
                if (btnTags) btnTags.click();
            }
            if (hash.includes("add-tag")) {
                setTimeout(() => { btnAddTag.click(); }, 150);
            } else if (hash.includes("write")) {
                setTimeout(() => { openWriteModal(1); }, 150);
            }
        });
    });
});
