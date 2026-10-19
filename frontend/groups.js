window.initGroups = ({waitForApi, openModal, closeModal}) => {
    const $ = id => document.getElementById(id);
    let groups = [], selected = null, editing = null, choices = new Set(), catalog = [], busy = false;
    let snapshotBusy = false, revision = 0;
    const trends = new Map();
    const drawTrend = (card, tag, live, quality) => {
        const key = `${selected}:${tag.id}`;
        const series = trends.get(key) || [];
        trends.set(key, series);
        const value = typeof live.value === 'boolean' ? Number(live.value) : live.value;
        const valid = quality === 'GOOD' && typeof value === 'number' && Number.isFinite(value) && live.sampled_at;
        if (valid && series.at(-1)?.time !== live.sampled_at) series.push({time:live.sampled_at,value});
        else if (!valid && series.length && series.at(-1).value !== null) series.push({time:Date.now()/1000,value:null});
        if (series.length > 120) series.splice(0, series.length - 120);
        const chart = card.querySelector('.card-trend'); chart.replaceChildren();
        const points = series.filter(p => p.value !== null);
        if (points.length < 2) { chart.textContent = 'Trend appears after two live readings.'; return; }
        const min = Math.min(...points.map(p=>p.value)), max = Math.max(...points.map(p=>p.value));
        const start = series[0].time, end = series.at(-1).time;
        const span=max-min, pad=span===0?Math.max(Math.abs(max)*.05,.5):span*.08;
        const low=min-pad, high=max+pad;
        const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
        svg.setAttribute('viewBox','0 0 320 126'); svg.setAttribute('role','img');
        svg.setAttribute('aria-label',`${tag.name} trend. Y axis ${low.toPrecision(4)} to ${high.toPrecision(4)}. X axis ${Math.round(end-start)} seconds ago to now. ${points.length} live readings. Gaps indicate unavailable data.`);
        for(const [y,label] of [[24,String(Number(high.toPrecision(4)))],[88,String(Number(low.toPrecision(4)))]]) {
            const grid=document.createElementNS(svg.namespaceURI,'path'); grid.setAttribute('d',`M42 ${y} H316`);grid.setAttribute('stroke','currentColor');grid.setAttribute('opacity','.2');svg.append(grid);
            const tick=document.createElementNS(svg.namespaceURI,'text');tick.setAttribute('x','0');tick.setAttribute('y',String(y+4));tick.textContent=label;tick.setAttribute('fill','currentColor');tick.setAttribute('font-size','10');svg.append(tick);
        }
        let d = '', connected = false, previousY = 0;
        for (const point of series) {
            if (point.value === null) { connected = false; continue; }
            const x = 42 + (point.time-start)/Math.max(end-start,.001)*274;
            const y = 84-(point.value-low)/(high-low)*64;
            if (!connected) d += ` M${x},${y}`;
            else d += tag.data_type === 'BOOL' ? ` L${x},${previousY} L${x},${y}` : ` L${x},${y}`;
            previousY=y; connected=true;
        }
        const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',d);
        path.setAttribute('fill','none');path.setAttribute('stroke','currentColor');path.setAttribute('stroke-width','2');
        svg.append(path);
        const x0=document.createElementNS(svg.namespaceURI,'text');x0.setAttribute('x','42');x0.setAttribute('y','112');x0.textContent=`${Math.round(end-start)}s ago`;x0.setAttribute('fill','currentColor');x0.setAttribute('font-size','10');
        const x1=document.createElementNS(svg.namespaceURI,'text');x1.setAttribute('x','316');x1.setAttribute('y','112');x1.setAttribute('text-anchor','end');x1.textContent='Now';x1.setAttribute('fill','currentColor');x1.setAttribute('font-size','10');svg.append(x0,x1);
        chart.append(svg,node('small',`Range ${min}–${max} · ${points.length} live readings`),node('small','Gaps show paused or unavailable data'));
    };
    const message = text => { $('group-status').textContent = text; };
    const node = (tag, text, cls) => {
        const el = document.createElement(tag); el.textContent = text;
        if (cls) el.className = cls; return el;
    };
    const guard = fn => async () => {
        try { await fn(); } catch (e) { message(`Unable to complete action: ${e.message || e}`); }
    };
    const refresh = async (id = selected) => {
        const api = await waitForApi(); groups = await api.get_groups();
        selected = groups.some(g => g.id === id) ? id : groups[0]?.id ?? null;
        revision++;
        $('group-select').replaceChildren();
        groups.forEach(g => { const opt = node('option', g.name); opt.value = g.id; $('group-select').append(opt); });
        $('group-select').value = selected ?? '';
        ['edit-group','monitor-group','delete-group','group-select'].forEach(id => $(id).disabled = selected === null);
        $('group-cards').replaceChildren();
        await render();
    };
    const render = async () => {
        if (snapshotBusy) return;
        if (selected === null) { message('No groups yet. Select tags in Tag Tables, or create a group here.'); return; }
        snapshotBusy = true;
        const id = selected, version = revision;
        try {
            const api = await waitForApi(), data = await api.get_group_snapshot(id);
            if (id !== selected || version !== revision) return;
            $('monitor-group').textContent = data.running ? 'Pause live view' : 'Start live view';
            $('monitor-group').dataset.running = String(data.running);
            const status=$('group-status');
            const state=!data.connected?'disconnected':data.running?'live':'paused';
            status.dataset.state=state;
            message(state==='disconnected'?'DISCONNECTED · Cached values are stale. Connect your PLC to resume.' : state==='live'?'LIVE · Values are updating automatically.' : 'PAUSED · Showing last known values.');
            if (!data.tags.length) {
                $('group-cards').replaceChildren(node('p', 'This group is empty. Choose Customize to add tags.', 'group-empty'));
                return;
            }
            const existing = new Map(Array.from($('group-cards').children).map(el => [el.dataset.id, el]));
            const keep = new Set();
            data.tags.forEach(({tag, resolved_address, live}) => {
                const key = String(tag.id); keep.add(key);
                let card = existing.get(key);
                const retainReading = card && (!data.running || !data.connected);
                if (!card) {
                    card = node('article', '', 'live-card'); card.dataset.id = key;
                    card.append(node('h3',''), node('p','','card-address'), node('div','','card-value'), node('p','','card-quality'), node('p','','card-time'), node('div','','card-trend'));
                    $('group-cards').append(card);
                }
                const quality = live.quality || 'UNKNOWN'; card.dataset.quality = quality;
                card.children[0].textContent = tag.name;
                card.children[1].textContent = `${resolved_address || tag.address} · ${tag.data_type}`;
                if (!retainReading) card.children[2].textContent = live.value == null ? '—' : tag.data_type==='BOOL' ? (live.value ? 'ON' : 'OFF') : String(live.value);
                card.children[3].textContent = quality === 'GOOD' ? 'LIVE · Good quality' : quality === 'STALE' ? 'STALE · Last known value' : live.error || 'WAITING FOR DATA';
                if (!retainReading) card.children[4].textContent = live.timestamp ? `Last read ${live.timestamp}` : 'No reading yet';
                drawTrend(card, tag, live, quality);
            });
            Array.from($('group-cards').children).forEach(el => { if (!keep.has(el.dataset.id)) el.remove(); });
        } finally { snapshotBusy = false; }
    };
    const picker = () => {
        const query = $('group-search').value.toLowerCase(); $('group-picker').replaceChildren();
        catalog.filter(t => `${t.name} ${t.tableName}`.toLowerCase().includes(query)).forEach(t => {
            const label = node('label','','group-choice'), check = document.createElement('input');
            check.type = 'checkbox'; check.checked = choices.has(t.id);
            check.addEventListener('change', () => { check.checked ? choices.add(t.id) : choices.delete(t.id); count(); });
            label.append(check, node('span', t.name), node('small', t.tableName)); $('group-picker').append(label);
        });
        if (!$('group-picker').children.length) $('group-picker').append(node('p', 'No matching tags. Create tags in Tag Tables first.'));
        count();
    };
    const count = () => { $('group-count').textContent = `${choices.size} tags selected`; };
    const editor = async (id, initial = []) => {
        const api = await waitForApi(); editing = id;
        choices = new Set(id === null ? initial : (await api.get_group_tags(id)).map(t => t.id));
        catalog = [];
        for (const table of await api.get_all_tables()) {
            for (const tag of await api.get_tags_for_table(table.id)) catalog.push({...tag, tableName:table.name});
        }
        $('group-name').value = groups.find(g => g.id === id)?.name || '';
        $('group-search').value = ''; $('group-error').textContent = '';
        $('group-editor-title').textContent = id === null ? 'Create a group' : 'Customize group';
        picker(); openModal($('modal-group')); $('group-name').focus();
    };
    $('group-search').addEventListener('input', picker);
    $('new-group').onclick = guard(() => editor(null));
    $('group-selected').onclick = guard(() => editor(null, Array.from(document.querySelectorAll('.tag-pick:checked')).map(el => Number(el.dataset.tagId))));
    $('edit-group').onclick = guard(() => editor(selected));
    $('group-select').onchange = guard(async () => {
        const api = await waitForApi(); await api.monitor_group(null);
        selected = Number($('group-select').value); revision++; $('group-cards').replaceChildren(); await render();
    });
    $('save-group').onclick = async () => {
        if (busy) return;
        busy = true; $('save-group').disabled = true;
        try {
            const api = await waitForApi();
            const result = await api.save_group(editing, $('group-name').value, [...choices]);
            if (!result.success) throw new Error(result.message);
            closeModal($('modal-group')); selected = result.id; $('tab-btn-groups').click();
        } catch(e) { $('group-error').textContent = e.message || String(e); }
        finally { busy = false; $('save-group').disabled = false; }
    };
    $('monitor-group').onclick = guard(async () => {
        const api = await waitForApi();
        await api.monitor_group($('monitor-group').dataset.running === 'true' ? null : selected); await render();
    });
    $('delete-group').onclick = guard(async () => {
        if (!confirm('Delete this group? The original tags will stay in their tables.')) return;
        const api = await waitForApi(); await api.delete_group(selected); await refresh(null);
    });
    $('tab-btn-groups').addEventListener('click', guard(() => refresh()));
    const applyTheme = theme => {
        const normalized = theme === 'light' ? 'light' : 'dark';
        document.documentElement.dataset.theme = normalized;
        $('theme-day').setAttribute('aria-pressed', String(normalized === 'light'));
        $('theme-night').setAttribute('aria-pressed', String(normalized === 'dark'));
    };
    let themeBusy = false, themeChanged = false;
    const changeTheme = theme => guard(async () => {
        if (themeBusy) return;
        themeChanged = true;
        themeBusy = true;
        try {
            const api = await waitForApi();
            if (await api.set_theme(theme)) applyTheme(theme);
        } finally { themeBusy = false; }
    });
    $('theme-day').onclick = changeTheme('light');
    $('theme-night').onclick = changeTheme('dark');
    waitForApi().then(async api => { const saved = await api.get_theme(); if (!themeChanged) applyTheme(saved); await refresh(); }).catch(e => message(String(e)));
    setInterval(() => {
        if ($('tab-groups').classList.contains('active')) render().catch(e => message(`Live view unavailable: ${e.message || e}`));
    }, 700);
};
