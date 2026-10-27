/**
 * Venture Fund Mode - frontend
 * Talks to /api/venture; every number shown comes from the server.
 */

const API = '/api/venture';

let fundId = null;
let lastState = null;
let mechanics = {};
let jCurveChart = null;

// ============================================================================
// API
// ============================================================================

async function api(endpoint, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);
    const response = await fetch(`${API}${endpoint}`, options);
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        const detail = Array.isArray(error.detail) ? error.detail.map(d => d.msg).join('; ') : error.detail;
        throw new Error(detail || `Request failed: ${response.status}`);
    }
    return response.json();
}

// ============================================================================
// Formatting
// ============================================================================

function esc(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function money(value) {
    const sign = value < 0 ? '-' : '';
    const v = Math.abs(value);
    if (v >= 1e6) return `${sign}$${(v / 1e6).toFixed(2)}M`;
    if (v >= 1e3) return `${sign}$${Math.round(v / 1e3).toLocaleString()}k`;
    return `${sign}$${Math.round(v)}`;
}

function pct(value, digits = 1) {
    return `${(value * 100).toFixed(digits)}%`;
}

function multiple(value) {
    return `${value.toFixed(2)}x`;
}

function stars(score) {
    return '★'.repeat(score) + '☆'.repeat(5 - score);
}

function mechanicLabel(key, text) {
    return `<span class="vc-mechanic-link" data-mechanic="${key}" title="What is this?">${text}</span>`;
}

function showMessage(text, isError = false) {
    const el = document.getElementById('action-message');
    el.textContent = text;
    el.className = `vc-message ${isError ? 'negative' : 'positive'}`;
}

// ============================================================================
// Rendering
// ============================================================================

function renderHeader(state) {
    const fund = state.fund;
    const shownPeriod = Math.min(fund.period, fund.max_periods);
    document.getElementById('period-label').textContent = fund.phase === 'over' ? 'Fund closed' : fund.period_label;
    document.getElementById('period-num').textContent = shownPeriod;
    document.getElementById('max-periods').textContent = fund.max_periods;
    document.getElementById('period-progress').style.width =
        `${Math.min(100, (fund.period - 1) / fund.max_periods * 100)}%`;
    const badge = document.getElementById('phase-badge');
    badge.textContent = fund.phase.toUpperCase();
    badge.className = `vc-phase ${fund.phase}`;
    badge.dataset.mechanic = 'investment_period';
    document.getElementById('seed-display').textContent = `seed ${state.seed}`;
}

function renderFund(state) {
    const f = state.fund;
    const futureFees = f.lifetime_fees - f.fees_paid;
    const segments = [
        { key: 'fees', label: 'Fees paid', value: f.fees_paid, cls: 'seg-fees' },
        { key: 'fees', label: 'Future fees', value: futureFees, cls: 'seg-future-fees' },
        { key: 'power_law', label: 'Invested', value: f.invested, cls: 'seg-invested' },
        { key: 'reserves', label: 'Reserved', value: f.reserved, cls: 'seg-reserved' },
        { key: 'reserves', label: 'Promised this half', value: f.pending, cls: 'seg-pending' },
        { key: 'reserves', label: 'Free for new deals', value: Math.max(0, f.available), cls: 'seg-free' },
    ];
    document.getElementById('capital-bar').innerHTML = segments
        .filter(s => s.value > 0)
        .map(s => `<div class="vc-seg ${s.cls}" style="width:${s.value / f.fund_size * 100}%" title="${s.label}: ${money(s.value)}"></div>`)
        .join('');
    document.getElementById('capital-legend').innerHTML = segments
        .map(s => `<span class="vc-legend-item"><i class="${s.cls}"></i>${mechanicLabel(s.key, s.label)} <b>${money(s.value)}</b></span>`)
        .join('');

    const irr = f.net_irr === null ? 'n/a' : `${f.net_irr >= 0 ? '+' : ''}${pct(f.net_irr)}`;
    const metrics = [
        ['tvpi_dpi', 'Net TVPI', multiple(f.tvpi), f.tvpi >= 1 ? 'positive' : 'negative'],
        ['tvpi_dpi', 'Net DPI', multiple(f.dpi), ''],
        ['carry', 'Gross MOIC', multiple(f.gross_moic), ''],
        ['j_curve', 'Net IRR', irr, f.net_irr !== null && f.net_irr >= 0 ? 'positive' : 'negative'],
        ['tvpi_dpi', 'NAV (marks)', money(f.nav), ''],
        ['fees', 'Paid in by LPs', money(f.paid_in), ''],
        ['tvpi_dpi', 'Distributed', money(f.distributions), ''],
        ['carry', 'Carry accrued', money(f.carry_accrued), ''],
    ];
    document.getElementById('fund-metrics').innerHTML = metrics
        .map(([key, label, value, cls]) =>
            `<div class="vc-metric"><div class="vc-metric-label">${mechanicLabel(key, label)}</div><div class="vc-metric-value ${cls}">${value}</div></div>`)
        .join('') +
        `<div class="vc-terms">${money(f.fund_size)} fund &middot; ${mechanicLabel('fees', `${pct(f.management_fee_rate, 0)}/yr fee`)} &middot; ${mechanicLabel('carry', `${pct(f.carry_rate, 0)} carry`)} &middot; ${mechanicLabel('concentration', `max ${money(f.max_company_amount)} per company`)}</div>`;
}

function renderDeals(state) {
    const container = document.getElementById('deal-cards');
    const f = state.fund;
    if (state.deals.length === 0) {
        container.innerHTML = `<p class="empty-message">${f.phase === 'over'
            ? 'The fund has closed.'
            : `The ${mechanicLabel('investment_period', 'investment period')} is over: no new deals. Support your winners and wait for exits.`}</p>`;
        return;
    }
    container.innerHTML = state.deals.map(deal => {
        const committed = deal.committed_check !== null;
        const check = committed ? deal.committed_check : Math.min(250000, deal.raise_amount);
        const reserve = committed ? deal.committed_reserve : check * f.default_reserve_ratio;
        return `
        <div class="vc-deal ${committed ? 'committed' : ''}" data-deal="${deal.id}">
            <div class="vc-deal-head">
                <span class="vc-deal-name">${esc(deal.name)}</span>
                <span class="vc-tag">${esc(deal.stage)}</span>
                <span class="vc-tag vc-tag-dim">${esc(deal.sector)}</span>
            </div>
            <p class="vc-pitch">${esc(deal.pitch)}</p>
            <div class="vc-signals">
                <span>Team <b>${stars(deal.signals.team)}</b></span>
                <span>Market <b>${stars(deal.signals.market)}</b></span>
                <span>Traction <b>${stars(deal.signals.traction)}</b></span>
            </div>
            <div class="vc-terms-row">Raising <b>${money(deal.raise_amount)}</b> at <b>${money(deal.pre_money)}</b> pre / <b>${money(deal.post_money)}</b> post</div>
            <div class="vc-inputs">
                <label><span>Cheque $k</span><input type="number" class="in-check" min="0" step="25" value="${Math.round(check / 1000)}"></label>
                <label><span>${mechanicLabel('reserves', 'Reserve')} $k</span><input type="number" class="in-reserve" min="0" step="25" value="${Math.round(reserve / 1000)}"></label>
            </div>
            <div class="vc-preview"></div>
            <div class="vc-deal-actions">
                <button class="action-btn btn-commit">${committed ? 'UPDATE' : 'BACK IT'}</button>
                ${committed ? '<button class="action-btn vc-secondary btn-withdraw">WITHDRAW</button>' : ''}
            </div>
        </div>`;
    }).join('');

    container.querySelectorAll('.vc-deal').forEach(card => {
        const deal = state.deals.find(d => d.id === Number(card.dataset.deal));
        const checkInput = card.querySelector('.in-check');
        const reserveInput = card.querySelector('.in-reserve');
        const preview = card.querySelector('.vc-preview');
        const updatePreview = () => {
            const check = Number(checkInput.value) * 1000;
            preview.textContent = check > 0
                ? `Buys ${pct(check / deal.post_money, 2)} today. Total commitment ${money(check + Number(reserveInput.value) * 1000)}.`
                : '';
        };
        checkInput.addEventListener('input', () => {
            if (deal.committed_check === null) {
                reserveInput.value = Math.round(Number(checkInput.value) * f.default_reserve_ratio);
            }
            updatePreview();
        });
        reserveInput.addEventListener('input', updatePreview);
        updatePreview();
        card.querySelector('.btn-commit').addEventListener('click', () =>
            commit(deal.id, Number(checkInput.value) * 1000, Number(reserveInput.value) * 1000));
        const withdraw = card.querySelector('.btn-withdraw');
        if (withdraw) withdraw.addEventListener('click', () => commit(deal.id, 0, 0));
    });
}

function renderFollowOns(state) {
    const container = document.getElementById('follow-ons');
    if (state.follow_ons.length === 0) {
        container.innerHTML = '<p class="empty-message">No portfolio company is raising this half-year.</p>';
        return;
    }
    container.innerHTML = `
        <table class="vc-table">
            <thead><tr>
                <th>COMPANY</th><th>ROUND</th><th>PRE-MONEY</th><th>VS LAST POST</th>
                <th>YOU OWN</th><th>${mechanicLabel('pro_rata', 'PRO-RATA')}</th><th>${mechanicLabel('reserves', 'RESERVE')}</th>
                <th>DECISION</th><th>AMOUNT $k</th><th></th>
            </tr></thead>
            <tbody>
            ${state.follow_ons.map(o => `
                <tr data-startup="${o.startup_id}">
                    <td class="company-name">${esc(o.name)}</td>
                    <td>${esc(o.round_name)}</td>
                    <td>${money(o.pre_money)}</td>
                    <td class="${o.down_round ? 'negative' : 'positive'}">${o.step_up.toFixed(2)}x${o.down_round ? ` ${mechanicLabel('dilution', 'DOWN')}` : ''}</td>
                    <td>${pct(o.ownership, 2)}</td>
                    <td>${money(o.pro_rata)}</td>
                    <td>${money(o.reserve)}</td>
                    <td>${o.decision === null ? '<span class="vc-dim">pass (default)</span>' : (o.decision === 0 ? 'pass' : money(o.decision))}</td>
                    <td><input type="number" class="in-amount" min="0" step="5" value="${Math.round(o.pro_rata / 1000)}"></td>
                    <td class="vc-row-actions">
                        <button class="action-btn btn-full">FULL</button>
                        <button class="action-btn vc-secondary btn-set">SET</button>
                        <button class="action-btn vc-secondary btn-pass">PASS</button>
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>`;

    container.querySelectorAll('tr[data-startup]').forEach(row => {
        const offer = state.follow_ons.find(o => o.startup_id === Number(row.dataset.startup));
        row.querySelector('.btn-full').addEventListener('click', () => followOn(offer.startup_id, offer.pro_rata));
        row.querySelector('.btn-pass').addEventListener('click', () => followOn(offer.startup_id, 0));
        row.querySelector('.btn-set').addEventListener('click', () =>
            followOn(offer.startup_id, Math.min(offer.pro_rata, Number(row.querySelector('.in-amount').value) * 1000)));
    });
}

function renderPortfolio(state) {
    const container = document.getElementById('portfolio');
    if (state.portfolio.length === 0) {
        container.innerHTML = '<p class="empty-message">No investments yet. Back a startup from the deal flow.</p>';
        return;
    }
    container.innerHTML = `
        <table class="vc-table">
            <thead><tr>
                <th>COMPANY</th><th>ENTRY</th><th>STATUS</th><th>INVESTED</th><th>${mechanicLabel('dilution', 'OWN')}</th>
                <th>${mechanicLabel('tvpi_dpi', 'MARK')}</th><th>RETURNED</th><th>MULTIPLE</th><th>ROUNDS</th>
            </tr></thead>
            <tbody>
            ${state.portfolio.map(p => `
                <tr>
                    <td class="company-name">${esc(p.name)} <span class="vc-dim">${esc(p.sector)}</span></td>
                    <td>${esc(p.stage)} ${esc(p.entry_label)}</td>
                    <td class="vc-status-${p.status.replace(' ', '-')}">${esc(p.status)}</td>
                    <td>${money(p.invested)}</td>
                    <td>${p.status === 'private' ? pct(p.ownership, 2) : '-'}</td>
                    <td>${money(p.mark)}</td>
                    <td>${money(p.proceeds)}</td>
                    <td class="${p.multiple >= 1 ? 'positive' : 'negative'}">${multiple(p.multiple)}</td>
                    <td class="vc-rounds">${p.rounds.map(r => `${esc(r.name)} ${money(r.post_money)}`).join(' &rarr; ')}</td>
                </tr>`).join('')}
            </tbody>
        </table>`;
}

function waterfallHtml(exit) {
    const w = exit.waterfall;
    const title = exit.kind === 'shutdown' ? 'shut down; assets sold for' : 'exited for';
    const rows = [...w.rows].reverse().map(r => `
        <tr>
            <td>${esc(r.name)}</td>
            <td>${money(r.preference)}</td>
            <td>${r.converted ? 'converted' : 'preference'}</td>
            <td>${money(r.payout)}</td>
            <td class="highlight">${r.yours ? money(r.yours) : '-'}</td>
        </tr>`).join('');
    return `
        <div class="vc-waterfall">
            <div class="vc-waterfall-title">${mechanicLabel('liquidation_preference', 'Waterfall')}: ${esc(exit.name)} ${title} ${money(exit.exit_value)} (${esc(exit.period_label)})</div>
            <table class="vc-table">
                <thead><tr><th>CLASS</th><th>1X PREF</th><th>TOOK</th><th>PAID</th><th>YOURS</th></tr></thead>
                <tbody>${rows}
                    <tr><td>Common (founders, staff)</td><td>-</td><td>-</td><td>${money(w.common_payout)}</td><td>-</td></tr>
                </tbody>
            </table>
            <div class="vc-dim">You put in ${money(exit.fund_invested)} and got back ${money(exit.fund_proceeds)}.</div>
        </div>`;
}

function renderLog(state) {
    const latest = state.exits.find(e => e.waterfall);
    document.getElementById('latest-waterfall').innerHTML = latest ? waterfallHtml(latest) : '';
    document.getElementById('event-log').innerHTML = state.log.length
        ? state.log.map(e => `<li><span class="vc-dim">${esc(e.period_label)}</span> ${esc(e.text)}</li>`).join('')
        : '<li class="vc-dim">Nothing yet. Back some startups and advance the clock.</li>';
}

function renderChart(state) {
    const labels = state.history.map(h => h.label);
    const cash = state.history.map(h => h.cumulative_net_cash_flow / 1e6);
    const nav = state.history.map(h => h.nav / 1e6);
    if (jCurveChart) {
        jCurveChart.data.labels = labels;
        jCurveChart.data.datasets[0].data = cash;
        jCurveChart.data.datasets[1].data = nav;
        jCurveChart.update();
        return;
    }
    if (typeof Chart === 'undefined') return;
    jCurveChart = new Chart(document.getElementById('jcurve-chart'), {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: 'LP cumulative net cash ($M)', data: cash, borderColor: '#ff9900',
                  backgroundColor: 'rgba(255,153,0,0.15)', fill: 'origin', tension: 0.2, pointRadius: 2 },
                { label: 'NAV at marks ($M)', data: nav, borderColor: '#00aaff', borderDash: [5, 4],
                  tension: 0.2, pointRadius: 0 },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { labels: { color: '#cccccc', font: { family: 'monospace' } } } },
            scales: {
                x: { ticks: { color: '#888888' }, grid: { color: '#222222' } },
                y: { ticks: { color: '#888888', callback: v => `$${v}M` }, grid: { color: '#333333' } },
            },
        },
    });
}

function renderReport(state) {
    const r = state.report;
    if (!r) return;
    const irr = r.net_irr === null ? 'n/a' : `${r.net_irr >= 0 ? '+' : ''}${pct(r.net_irr)}`;
    const bars = r.deals.map(d => `
        <div class="vc-bar-row ${d.returned_fund ? 'returner' : ''}">
            <span class="vc-bar-name">${esc(d.name)}${d.returned_fund ? ' 🏆' : ''}</span>
            <span class="vc-bar"><i style="width:${Math.max(0.5, d.share_of_value * 100)}%"></i></span>
            <span class="vc-bar-value">${pct(d.share_of_value, 0)} &middot; ${d.multiple.toFixed(1)}x</span>
        </div>`).join('');
    document.getElementById('report-body').innerHTML = `
        <p class="vc-headline">${esc(r.headline)}</p>
        <div class="vc-report-grid">
            <div><span>Deals made</span><b>${r.deal_count} (${r.losers} lost money)</b></div>
            <div><span>Paid in by LPs</span><b>${money(r.paid_in)}</b></div>
            <div><span>of which fees</span><b>${money(r.fees_paid)}</b></div>
            <div><span>Gross proceeds</span><b>${money(r.gross_proceeds)}</b></div>
            <div><span>GP carry</span><b>${money(r.carry_paid)}</b></div>
            <div><span>Net to LPs</span><b>${money(r.net_to_lps)}</b></div>
            <div><span>${mechanicLabel('carry', 'Gross MOIC')}</span><b>${multiple(r.gross_moic)}</b></div>
            <div><span>${mechanicLabel('tvpi_dpi', 'Net TVPI')}</span><b class="${r.tvpi >= 1 ? 'positive' : 'negative'}">${multiple(r.tvpi)}</b></div>
            <div><span>Net IRR</span><b>${irr}</b></div>
        </div>
        <h3>${mechanicLabel('power_law', 'Where the returns came from')}</h3>
        <div class="vc-bars">${bars}</div>
        <div class="rating-display"><div class="rating">${esc(r.rating)}</div></div>`;
    document.getElementById('report-modal').classList.remove('hidden');
}

function render(state, { showReport = true } = {}) {
    lastState = state;
    renderHeader(state);
    renderFund(state);
    renderDeals(state);
    renderFollowOns(state);
    renderPortfolio(state);
    renderLog(state);
    renderChart(state);
    const over = state.fund.phase === 'over';
    const next = document.getElementById('btn-next');
    next.disabled = over;
    next.innerHTML = over ? 'FUND CLOSED'
        : (state.fund.period === state.fund.max_periods ? 'CLOSE THE FUND &rarr;' : 'NEXT HALF-YEAR &rarr;');
    if (over && showReport) renderReport(state);
}

// ============================================================================
// Actions
// ============================================================================

async function openFund(seed = null) {
    try {
        const response = await api('/new', 'POST', { seed });
        fundId = response.game_id;
        try { localStorage.setItem('vc-fund-id', fundId); } catch (e) { /* storage unavailable */ }
        if (jCurveChart) { jCurveChart.destroy(); jCurveChart = null; }
        document.getElementById('report-modal').classList.add('hidden');
        document.getElementById('start-screen').classList.add('hidden');
        document.getElementById('game-container').classList.remove('hidden');
        render(response.state);
        showMessage('Fund open. Back a few startups, then advance the clock.');
    } catch (error) {
        showMessage(`Could not open a fund: ${error.message}`, true);
    }
}

async function commit(dealId, check, reserve) {
    try {
        const response = await api('/commit', 'POST', { game_id: fundId, deal_id: dealId, check, reserve });
        render(response.state);
        showMessage(response.message, !response.success);
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function followOn(startupId, amount) {
    try {
        const response = await api('/follow-on', 'POST', { game_id: fundId, startup_id: startupId, amount });
        render(response.state);
        showMessage(response.message, !response.success);
    } catch (error) {
        showMessage(error.message, true);
    }
}

async function advance() {
    const button = document.getElementById('btn-next');
    button.disabled = true;
    try {
        const response = await api('/advance', 'POST', { game_id: fundId });
        render(response.state);
        showMessage(response.events.length ? `${response.events.length} things happened - see the log.` : 'A quiet half-year.');
    } catch (error) {
        showMessage(error.message, true);
        button.disabled = false;
    }
}

async function resumeFund(id) {
    try {
        const response = await api(`/state?game_id=${encodeURIComponent(id)}`);
        fundId = id;
        document.getElementById('start-screen').classList.add('hidden');
        document.getElementById('game-container').classList.remove('hidden');
        render(response.state, { showReport: false });
        showMessage('Welcome back to your fund.');
    } catch (error) {
        try { localStorage.removeItem('vc-fund-id'); } catch (e) { /* storage unavailable */ }
    }
}

function showMechanic(key) {
    const m = mechanics[key];
    if (!m) return;
    document.getElementById('mechanic-title').textContent = m.title;
    document.getElementById('mechanic-body').textContent = m.body;
    document.getElementById('mechanic-modal').classList.remove('hidden');
}

async function loadMechanics() {
    try {
        const response = await api('/mechanics');
        response.mechanics.forEach(m => { mechanics[m.key] = m; });
        document.getElementById('mechanics-list').innerHTML = response.mechanics
            .map(m => `<div class="vc-mechanic"><h3>${esc(m.title)}</h3><p>${esc(m.body)}</p></div>`).join('');
    } catch (error) {
        document.getElementById('mechanics-list').textContent = 'Could not load explanations.';
    }
}

// ============================================================================
// Setup
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    loadMechanics();

    document.getElementById('btn-open-fund').addEventListener('click', () => {
        const raw = document.getElementById('seed-input').value.trim();
        openFund(raw === '' ? null : Number(raw));
    });
    document.getElementById('btn-next').addEventListener('click', advance);
    document.getElementById('btn-help').addEventListener('click', () =>
        document.getElementById('help-modal').classList.remove('hidden'));
    document.getElementById('btn-help-close').addEventListener('click', () =>
        document.getElementById('help-modal').classList.add('hidden'));
    document.getElementById('btn-mechanic-close').addEventListener('click', () =>
        document.getElementById('mechanic-modal').classList.add('hidden'));
    document.getElementById('btn-report-close').addEventListener('click', () =>
        document.getElementById('report-modal').classList.add('hidden'));
    document.getElementById('btn-new-fund').addEventListener('click', () => openFund(null));
    document.getElementById('btn-same-seed').addEventListener('click', () => openFund(lastState ? lastState.seed : null));

    // Any element tagged with a mechanic opens its explanation
    document.body.addEventListener('click', (e) => {
        const target = e.target.closest('[data-mechanic]');
        if (target) showMechanic(target.dataset.mechanic);
    });

    let saved = null;
    try { saved = localStorage.getItem('vc-fund-id'); } catch (e) { /* storage unavailable */ }
    if (saved) resumeFund(saved);
});
