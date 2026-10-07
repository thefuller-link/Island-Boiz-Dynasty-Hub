"""Read cache/sleeper.json + cache/ktc.json + cache/picks.json and write site/trades.html.

The page embeds league-wide roster/KTC data and runs the evaluator and suggestion
search in the browser, so no server is needed.
"""

import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
import suggest_trades as st
from analyze_trade import MODE_WEIGHTS
from html_utils import page_shell, stale_banner, missing_section, _atomic_write

OUTPUT_FILE = os.path.join(st.REPO_ROOT, "site", "trades.html")


def _load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def build_payload(sleeper, ktc, picks_cache, cfg):
    teams = st.build_teams(sleeper, ktc, picks_cache)
    profiles = st.classify_needs(teams)
    cfg_owners = [str(o) for o in cfg.get("owners") or []]
    cfg_mode = {str(k): str(v).lower() for k, v in (cfg.get("team_mode") or {}).items()}
    ours = st.find_team(teams, None, cfg_owners, sleeper.get("user_map", {}))

    modes = {}
    if ours:
        mode = next((cfg_mode[o] for o in cfg_owners if o in cfg_mode), "")
        if mode in MODE_WEIGHTS:
            modes[ours["name"]] = MODE_WEIGHTS[mode]

    out_teams = []
    for rid, t in sorted(teams.items(), key=lambda kv: kv[1]["name"].lower()):
        prof = profiles[rid]
        out_teams.append({
            "name": t["name"],
            "ours": bool(ours and rid == ours["roster_id"]),
            "players": t["players"],
            "picks": t["picks"],
            "ratio": {p: round(prof["ratio"][p], 2) for p in st.POSITIONS},
            "needs": prof["needs"],
            "surplus": prof["surplus"],
            "pool": [a["name"] for a in st.tradable_pool(t, prof)],
        })

    return {
        "teams": out_teams,
        "ktcPlayers": [{"type": "player", "name": p["player_name"], "position": p["position"], "value": p["value"]}
                       for p in ktc.get("players", []) if p.get("value")],
        "ktcPicks": [{"type": "pick", "name": p["pick_label"], "value": p["value"]}
                     for p in ktc.get("picks", []) if p.get("value")],
        "modes": modes,
        "positions": list(st.POSITIONS),
        "cfg": {
            "pieceWeights": list(st.PIECE_WEIGHTS), "fairLow": st.FAIR_LOW, "fairHigh": st.FAIR_HIGH,
            "minTarget": st.MIN_TARGET_VALUE, "candidatePool": st.CANDIDATE_POOL,
            "maxPieces": st.MAX_OFFER_PIECES, "maxPartners": st.MAX_PARTNERS,
        },
    }


PAGE_JS = r"""
const D = JSON.parse(document.getElementById('trade-data').textContent);
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const teamByName = n => D.teams.find(t => t.name === n);
const weightFor = n => D.modes[n] || 1;
const adjFor = (receiver, assets) => assets
  .map(a => a.value * (a.type === 'pick' ? weightFor(receiver) : 1))
  .sort((x, y) => y - x)
  .reduce((s, v, i) => s + v * D.cfg.pieceWeights[Math.min(i, D.cfg.pieceWeights.length - 1)], 0);
const label = a => a.type === 'player' ? `${a.name} (${a.position})` : a.name;

function compare(nameA, giveA, nameB, giveB) {
  const adjA = adjFor(nameA, giveB), adjB = adjFor(nameB, giveA);
  const hi = Math.max(adjA, adjB), diff = Math.abs(adjA - adjB), pct = hi ? diff / hi * 100 : 0;
  let text = 'approximately even';
  if (pct > 1) text = `favors ${adjA > adjB ? nameA : nameB} by ${Math.round(diff)} (${pct.toFixed(1)}%)`;
  return {adjA, adjB, text, pct};
}

// ---- Team needs table ----
(function () {
  const rows = D.teams.map(t => `<tr${t.ours ? ' class="ours"' : ''}><td>${esc(t.name)}${t.ours ? ' (us)' : ''}</td>` +
    D.positions.map(p => `<td class="${t.needs.includes(p) ? 'need' : t.surplus.includes(p) ? 'surplus' : ''}">${t.ratio[p].toFixed(2)}</td>`).join('') +
    `<td>${esc(t.needs.join(', ') || '-')}</td><td>${esc(t.surplus.join(', ') || '-')}</td></tr>`);
  $('needs-table').innerHTML = `<table class="trade-table"><thead><tr><th>Team</th>${D.positions.map(p => `<th>${p}</th>`).join('')}<th>Needs</th><th>Surplus</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
})();

// ---- Suggestions ----
const teamOpts = (sel, blank) => (blank ? `<option value="">${blank}</option>` : '') +
  D.teams.map(t => `<option value="${esc(t.name)}"${!blank && t.ours ? ' selected' : ''}>${esc(t.name)}${t.ours ? ' (us)' : ''}</option>`).join('');

function syncNeeds() {
  const t = teamByName($('sg-team').value);
  $('sg-needs').innerHTML = D.positions.map(p =>
    `<label><input type="checkbox" value="${p}"${t.needs.includes(p) ? ' checked' : ''}> ${p}</label>`).join(' ');
}

function* offers(target, pool) {
  const c = D.cfg;
  const cands = [...pool].sort((a, b) => Math.abs(a.value - target.value) - Math.abs(b.value - target.value)).slice(0, c.candidatePool);
  const perceived = combo => combo.map(a => a.value).sort((x, y) => y - x).reduce((s, v, i) => s + v * c.pieceWeights[i], 0);
  const walk = function* (start, combo) {
    if (combo.length) {
      const pv = perceived(combo);
      if (pv >= target.value * c.fairLow && pv <= target.value * c.fairHigh) yield [combo.slice(), pv];
    }
    if (combo.length >= c.maxPieces) return;
    for (let i = start; i < cands.length; i++) { combo.push(cands[i]); yield* walk(i + 1, combo); combo.pop(); }
  };
  yield* walk(0, []);
}

function runSuggest() {
  const me = teamByName($('sg-team').value);
  const needs = [...$('sg-needs').querySelectorAll('input:checked')].map(i => i.value);
  const picked = ['sg-p1', 'sg-p2'].map(id => $(id).value).filter(Boolean);
  const out = $('sg-out');
  if (new Set(picked).size !== picked.length || picked.includes(me.name)) { out.innerHTML = '<p class="banner-warn">Pick two different partners, other than your own team.</p>'; return; }
  let partners = picked.slice();
  const nRandom = Math.min(+$('sg-random').value, D.cfg.maxPartners - partners.length);
  const rest = D.teams.map(t => t.name).filter(n => n !== me.name && !partners.includes(n));
  for (let i = 0; i < nRandom && rest.length; i++) partners.push(rest.splice(Math.floor(Math.random() * rest.length), 1)[0]);
  if (!partners.length) partners = D.teams.map(t => t.name).filter(n => n !== me.name);
  if (!needs.length) { out.innerHTML = '<p class="banner-missing">Select at least one position of need.</p>'; return; }

  const all = $('sg-pool').value === 'all';
  const pool = all ? me.players.concat(me.picks) : (() => { const names = new Set(me.pool); return me.players.concat(me.picks).filter(a => names.has(a.name)); })();
  const results = [];
  for (const pn of partners) {
    const other = teamByName(pn), oPool = new Set(other.pool);
    for (const target of other.players.filter(p => needs.includes(p.position) && p.value >= D.cfg.minTarget)) {
      const offerPool = pool.filter(a => a.name !== target.name);
      for (const [give, pv] of offers(target, offerPool)) {
        if (give.some(a => a.type === 'player' && a.position === target.position)) continue;
        let fit = give.filter(a => a.type === 'player' && other.needs.includes(a.position)).length;
        if (give.some(a => a.type === 'pick')) fit += 0.5;
        const score = (1 - Math.abs(pv - target.value) / target.value) + 0.25 * fit + (oPool.has(target.name) ? 0.3 : 0) - 0.05 * (give.length - 1);
        results.push({partner: pn, give, target, score, verdict: compare(me.name, give, pn, [target]).text, pn: other});
      }
    }
  }
  results.sort((a, b) => b.score - a.score);
  const seen = new Set(), top = [], counts = {};
  for (const r of results) {
    const key = r.partner + '|' + r.give.map(a => a.name).sort().join(',') + '|' + r.target.name;
    if (seen.has(key) || (counts[r.partner] || 0) >= 3) continue;
    seen.add(key); counts[r.partner] = (counts[r.partner] || 0) + 1; top.push(r);
    if (top.length >= +$('sg-top').value) break;
  }
  out.innerHTML = `<p class="section-meta">Partners: ${esc(partners.join(', '))} &middot; targeting ${esc(needs.join(', '))}</p>` +
    (top.length ? top.map((r, i) => `<div class="decision-item"><div class="desc"><strong>${i + 1}. ${esc(r.partner)}</strong> <span class="meta">(needs: ${esc(r.pn.needs.join(', ') || 'none')})</span></div>
      <div>You send: ${esc(r.give.map(a => `${label(a)} - ${a.value}`).join(', '))}</div>
      <div>You receive: ${esc(label(r.target))} - ${r.target.value}</div>
      <div class="meta">Verdict: ${esc(r.verdict)}</div></div>`).join('')
      : '<p class="banner-missing">No balanced trades found. Try other positions, "all assets", or different partners.</p>');
}

$('sg-team').innerHTML = teamOpts(null);
['sg-p1', 'sg-p2'].forEach(id => $(id).innerHTML = teamOpts(null, 'Any / none'));
$('sg-team').addEventListener('change', syncNeeds);
$('sg-go').addEventListener('click', runSuggest);
syncNeeds();

// ---- Evaluator ----
const sides = {a: [], b: []};
function sideAssets(key) {
  const t = teamByName($(`ev-team-${key}`).value);
  return t ? t.players.map(p => ({type: 'player', ...p})).concat(t.picks) : D.ktcPlayers.concat(D.ktcPicks);
}
function refreshSide(key) {
  const assets = sideAssets(key);
  $(`ev-list-${key}`).innerHTML = assets.map(a => `<option value="${esc(label(a))}"></option>`).join('');
  sides[key] = [];
  renderSide(key);
}
function renderSide(key) {
  $(`ev-chips-${key}`).innerHTML = sides[key].map((a, i) =>
    `<li>${esc(label(a))} - ${a.value} <button type="button" data-k="${key}" data-i="${i}">&times;</button></li>`).join('');
  evaluate();
}
function addAsset(key) {
  const input = $(`ev-in-${key}`), v = input.value.trim().toLowerCase();
  const a = sideAssets(key).find(x => label(x).toLowerCase() === v);
  if (a && !sides[key].some(x => x.name === a.name)) { sides[key].push(a); renderSide(key); }
  input.value = '';
}
function evaluate() {
  const nameA = $('ev-team-a').value || 'Side A', nameB = $('ev-team-b').value || 'Side B';
  const out = $('ev-out');
  if (!sides.a.length || !sides.b.length) { out.innerHTML = '<p class="banner-missing">Add at least one asset to each side.</p>'; return; }
  const r = compare(nameA, sides.a, nameB, sides.b);
  const rawA = sides.a.reduce((s, a) => s + a.value, 0), rawB = sides.b.reduce((s, a) => s + a.value, 0);
  out.innerHTML = `<div class="decision-item"><div class="desc"><strong>Verdict: ${esc(r.text)}</strong></div>
    <div>${esc(nameA)} sends ${rawA} raw, receives ${Math.round(r.adjA)} adjusted</div>
    <div>${esc(nameB)} sends ${rawB} raw, receives ${Math.round(r.adjB)} adjusted</div>
    <div class="meta">Values are KTC with a consolidation discount (extra pieces count less)${Object.keys(D.modes).length ? '; picks weighted by team mode for configured teams' : ''}.</div></div>`;
}
['a', 'b'].forEach(k => {
  $(`ev-team-${k}`).innerHTML = teamOpts(null, 'Any (all KTC values)');
  $(`ev-team-${k}`).addEventListener('change', () => refreshSide(k));
  $(`ev-add-${k}`).addEventListener('click', () => addAsset(k));
  $(`ev-in-${k}`).addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); addAsset(k); } });
  $(`ev-chips-${k}`).addEventListener('click', e => { const b = e.target.closest('button'); if (b) { sides[k].splice(+b.dataset.i, 1); renderSide(k); } });
  refreshSide(k);
});
"""

PAGE_CSS = """
<style>
.trade-table{width:100%;border-collapse:collapse;font-size:.9rem}
.trade-table th,.trade-table td{padding:.3rem .5rem;border-bottom:1px solid #ddd;text-align:left}
.trade-table td.need{color:#b00020;font-weight:600}
.trade-table td.surplus{color:#1b7f3b;font-weight:600}
.trade-table tr.ours{background:rgba(0,0,0,.05)}
.trade-form{display:flex;flex-wrap:wrap;gap:.75rem;align-items:flex-end;margin-bottom:1rem}
.trade-form label{display:flex;flex-direction:column;font-size:.85rem;gap:.2rem}
.trade-form .inline{flex-direction:row;gap:.25rem;align-items:center}
.ev-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem}
.ev-chips{list-style:none;padding:0;margin:.5rem 0}
.ev-chips li{display:flex;justify-content:space-between;padding:.2rem 0;border-bottom:1px solid #eee}
</style>
"""


def main():
    sleeper = _load(st.SLEEPER_CACHE)
    ktc = _load(st.KTC_CACHE)
    picks_cache = _load(st.PICKS_CACHE) or {}

    if not sleeper or not ktc:
        body = '<h1 class="page-title">Trades</h1>\n' + missing_section("Sleeper/KTC")
        _atomic_write(OUTPUT_FILE, page_shell("Trades", "trades", body))
        print("site/trades.html written (placeholder: caches missing).")
        return

    with open(st.CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    payload = build_payload(sleeper, ktc, picks_cache, cfg)
    data_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    banner = stale_banner("KTC", ktc.get("last_updated"), 48) + stale_banner("Sleeper", sleeper.get("last_updated"), 24)

    body = f"""{PAGE_CSS}<h1 class="page-title">Trades</h1>
{banner}
<div class="section-card">
  <h2>Team Needs</h2>
  <p class="section-meta">Starter-level value by position relative to the league average (below 0.90 = need, above 1.10 = surplus).</p>
  <div id="needs-table"></div>
</div>

<div class="section-card">
  <h2>Trade Suggestions</h2>
  <div class="trade-form">
    <label>Team <select id="sg-team"></select></label>
    <label>Positions to target <span id="sg-needs"></span></label>
    <label>Partner 1 <select id="sg-p1"></select></label>
    <label>Partner 2 <select id="sg-p2"></select></label>
    <label>Random partners
      <select id="sg-random"><option value="0">0</option><option value="1">1</option><option value="2">2</option></select></label>
    <label>Offer from <select id="sg-pool"><option value="depth">Depth, surplus &amp; picks</option><option value="all">All assets</option></select></label>
    <label>Results <select id="sg-top"><option>5</option><option selected>10</option><option>15</option></select></label>
    <button type="button" id="sg-go">Suggest trades</button>
  </div>
  <p class="section-meta">Up to two partners in total (chosen + random). With none selected, every team is searched.</p>
  <div id="sg-out"></div>
</div>

<div class="section-card">
  <h2>Trade Evaluator</h2>
  <div class="ev-grid">
    <div><h3>Side A sends</h3>
      <select id="ev-team-a"></select>
      <input id="ev-in-a" list="ev-list-a" placeholder="Player or pick"><button type="button" id="ev-add-a">Add</button>
      <datalist id="ev-list-a"></datalist><ul class="ev-chips" id="ev-chips-a"></ul></div>
    <div><h3>Side B sends</h3>
      <select id="ev-team-b"></select>
      <input id="ev-in-b" list="ev-list-b" placeholder="Player or pick"><button type="button" id="ev-add-b">Add</button>
      <datalist id="ev-list-b"></datalist><ul class="ev-chips" id="ev-chips-b"></ul></div>
  </div>
  <div id="ev-out"></div>
</div>

<script type="application/json" id="trade-data">{data_json}</script>
<script>{PAGE_JS}</script>"""

    _atomic_write(OUTPUT_FILE, page_shell("Trades", "trades", body))
    print("site/trades.html written.")


if __name__ == "__main__":
    main()
