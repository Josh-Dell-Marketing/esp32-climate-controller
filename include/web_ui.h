#pragma once
#include <Arduino.h>

// Control page served at "/". Polls /api/state every second.
const char INDEX_HTML[] PROGMEM = R"rawliteral(<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Climate Controller</title>
<style>
:root{--bg:#f3f4f6;--card:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--accent:#2563eb;
--on:#16a34a;--heat:#ea580c;--cool:#0284c7;--wet:#7c3aed;--bad:#dc2626;--chip:#eef2f7}
@media (prefers-color-scheme:dark){:root{--bg:#0d1014;--card:#171b21;--text:#e5e7eb;--muted:#9ca3af;
--line:#2a3039;--accent:#60a5fa;--chip:#222831}}
*{box-sizing:border-box}
body{margin:0;font:15px/1.4 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
main{max-width:560px;margin:0 auto;padding:16px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:12px}
h1{font-size:1.2rem;margin:0}
h2{font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 10px}
.muted{color:var(--muted);font-size:.8rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:12px}
.readings{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.big{font-size:2.4rem;font-weight:650;line-height:1.1;font-variant-numeric:tabular-nums}
.big small{font-size:1rem;font-weight:500;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{background:var(--chip);border-radius:999px;padding:3px 10px;font-size:.8rem;font-weight:600}
.chip.cool{color:var(--cool)}.chip.heat{color:var(--heat)}.chip.wet{color:var(--wet)}.chip.bad{color:#fff;background:var(--bad)}
.badge{font-size:.7rem;font-weight:700;letter-spacing:.05em;color:var(--wet)}
.seg{display:grid;grid-template-columns:repeat(3,1fr);background:var(--chip);border-radius:10px;padding:3px;gap:3px}
.seg button{border:0;border-radius:8px;padding:9px;background:transparent;color:var(--text);font:inherit;font-weight:600;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--card);box-shadow:0 1px 3px rgba(0,0,0,.15);color:var(--accent)}
.row{display:flex;align-items:center;gap:12px;padding:10px 0;border-top:1px solid var(--line)}
.row:first-of-type{border-top:0}
.dot{width:12px;height:12px;border-radius:50%;background:var(--line);flex:none}
.row.on .dot{background:var(--on);box-shadow:0 0 0 4px color-mix(in srgb,var(--on) 25%,transparent)}
.row .what{flex:1;min-width:0}
.row .name{font-weight:600}
.row .reason{font-size:.8rem;color:var(--muted)}
.pill{font-size:.75rem;font-weight:700;color:var(--muted)}
.row.on .pill{color:var(--on)}
.switch{position:relative;flex:none;width:50px;height:28px;border:0;border-radius:14px;background:var(--line);cursor:pointer}
.switch::after{content:"";position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;background:#fff;transition:left .15s}
.switch[aria-pressed=true]{background:var(--accent)}
.switch[aria-pressed=true]::after{left:25px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:4px}
.stepper{display:flex}
.stepper input{width:100%;min-width:0;text-align:center;border-left:0;border-right:0;border-radius:0}
.stepper button{width:38px;flex:none;border:1px solid var(--line);background:var(--chip);color:var(--text);font-size:1.1rem;cursor:pointer}
.stepper button:first-child{border-radius:8px 0 0 8px}.stepper button:last-child{border-radius:0 8px 8px 0}
input,select{font:inherit;color:var(--text);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:7px 8px;width:100%}
input[data-dirty]{border-color:var(--accent)}
.actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}
.btn{border:0;border-radius:8px;padding:9px 16px;background:var(--accent);color:#fff;font:inherit;font-weight:600;cursor:pointer}
.check{display:flex;align-items:center;gap:8px;font-size:.9rem;color:var(--text);margin:10px 0 0}
.check input{width:auto}
details{margin-top:12px}
summary{cursor:pointer;color:var(--muted);font-size:.85rem}
details .grid2{margin-top:10px}
#msg{min-height:1.2em;font-size:.85rem;color:var(--bad);margin:0 0 8px}
</style>
</head>
<body>
<main>
<header><h1>Climate controller</h1><span id="net" class="muted">connecting&hellip;</span></header>
<p id="msg"></p>

<section class="card">
  <div class="readings">
    <div><h2>Temperature</h2><div class="big"><span id="t">--</span><small> &deg;C</small></div><div id="tset" class="muted"></div></div>
    <div><h2>Humidity</h2><div class="big"><span id="h">--</span><small> %RH</small></div><div id="hset" class="muted"></div></div>
  </div>
  <div class="chips" id="chips"></div>
</section>

<section class="card">
  <h2>Mode</h2>
  <div class="seg" id="mode">
    <button data-mode="off">Off</button><button data-mode="auto">Auto</button><button data-mode="manual">Manual</button>
  </div>
</section>

<section class="card">
  <h2>Equipment</h2>
  <div id="relays"></div>
</section>

<section class="card">
  <h2>Set points</h2>
  <div class="grid2">
    <div><label for="tempSet">Temperature (&deg;C)</label>
      <div class="stepper"><button data-for="tempSet" data-step="-0.5">&minus;</button><input id="tempSet" type="number" step="0.1" min="5" max="40"><button data-for="tempSet" data-step="0.5">+</button></div></div>
    <div><label for="humSet">Humidity (%RH)</label>
      <div class="stepper"><button data-for="humSet" data-step="-1">&minus;</button><input id="humSet" type="number" step="1" min="20" max="90"><button data-for="humSet" data-step="1">+</button></div></div>
  </div>
  <details>
    <summary>Advanced</summary>
    <div class="grid2">
      <div><label for="tempBand">Temperature band (&deg;C)</label><input id="tempBand" type="number" step="0.1" min="0.2" max="5"></div>
      <div><label for="humBand">Humidity band (%RH)</label><input id="humBand" type="number" step="0.5" min="1" max="15"></div>
      <div><label for="compMinOff">Compressor rest (s)</label><input id="compMinOff" type="number" step="1" min="0" max="900"></div>
      <div><label for="compMinOn">Compressor min run (s)</label><input id="compMinOn" type="number" step="1" min="0" max="900"></div>
      <div><label for="fanRunOn">Fan run-on (s)</label><input id="fanRunOn" type="number" step="1" min="0" max="600"></div>
      <div><label for="fanMode">Fan in Auto</label><select id="fanMode"><option value="auto">With equipment</option><option value="on">Always on</option></select></div>
    </div>
    <p class="muted">The band stops relays chattering: each demand starts at set point &plusmn; band and stops at the set point.</p>
  </details>
  <div class="actions"><button class="btn" id="save">Save</button></div>
</section>

<section class="card">
  <h2>Simulated sensor <span class="badge">NO SENSOR FITTED</span></h2>
  <div class="grid2">
    <div><label for="simT">Temperature (&deg;C)</label>
      <div class="stepper"><button data-for="simT" data-step="-0.5" data-live>&minus;</button><input id="simT" type="number" step="0.1"><button data-for="simT" data-step="0.5" data-live>+</button></div></div>
    <div><label for="simH">Humidity (%RH)</label>
      <div class="stepper"><button data-for="simH" data-step="-2" data-live>&minus;</button><input id="simH" type="number" step="1" min="0" max="100"><button data-for="simH" data-step="2" data-live>+</button></div></div>
  </div>
  <label class="check"><input type="checkbox" id="react"> Room reacts to the relays (fast simulation)</label>
  <label class="check"><input type="checkbox" id="fault"> Sensor fault</label>
  <div class="actions"><button class="btn" id="simSet">Apply</button></div>
</section>
</main>

<script>
const $ = id => document.getElementById(id);
let last = null, built = false;

async function api(path, data) {
  const opt = data ? { method: 'POST', body: new URLSearchParams(data) } : {};
  const r = await fetch(path, opt);
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r.json();
}

async function call(path, data) {
  try { render(await api(path, data)); $('msg').textContent = ''; }
  catch (e) { $('msg').textContent = e.message; }
}

// Don't overwrite a field the user is editing.
function fill(id, v) {
  const el = $(id);
  if (document.activeElement === el || el.dataset.dirty) return;
  el.value = v;
}
function clean(ids) { ids.forEach(id => delete $(id).dataset.dirty); }
document.querySelectorAll('input[type=number]').forEach(el =>
  el.addEventListener('input', () => el.dataset.dirty = '1'));

const fmt = s => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');

function chip(text, cls) { return '<span class="chip ' + cls + '">' + text + '</span>'; }

function buildRelays(relays) {
  $('relays').innerHTML = relays.map(r =>
    '<div class="row" id="r' + r.id + '"><span class="dot"></span>' +
    '<div class="what"><div class="name">' + r.name + '</div><div class="reason"></div></div>' +
    '<span class="pill"></span><button class="switch" aria-label="Switch ' + r.name + '" hidden></button></div>').join('');
  relays.forEach(r => {
    $('r' + r.id).querySelector('.switch').onclick = () => call('/api/manual', { ch: r.id, state: 'toggle' });
  });
  built = true;
}

function render(s) {
  last = s;
  const rd = s.reading, st = s.settings, d = s.demand;
  $('t').textContent = rd.valid ? rd.temp.toFixed(1) : '--';
  $('h').textContent = rd.valid ? rd.hum.toFixed(1) : '--';
  $('tset').textContent = 'Set ' + st.tempSet.toFixed(1) + ' ± ' + st.tempBand;
  $('hset').textContent = 'Set ' + st.humSet.toFixed(0) + ' ± ' + st.humBand;

  let c = '';
  if (s.mode === 'off') c += chip('Off', '');
  if (s.mode === 'manual') c += chip('Manual control', '');
  if (d.sensorFault) c += chip('Sensor fault', 'bad');
  if (d.cool) c += chip('Cooling', 'cool');
  if (d.heat) c += chip('Heating', 'heat');
  if (d.dehumidify) c += chip('Dehumidifying', 'wet');
  if (d.reheat) c += chip('Reheat', 'heat');
  if (d.humidify) c += chip('Humidifying', 'wet');
  if (s.mode === 'auto' && !c) c = chip('Holding at set points', '');
  $('chips').innerHTML = c;

  document.querySelectorAll('#mode button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.mode === s.mode));

  if (!built) buildRelays(s.relays);
  const manual = s.mode === 'manual';
  s.relays.forEach(r => {
    const row = $('r' + r.id);
    row.classList.toggle('on', r.on);
    let why = r.reason;
    if (r.name === 'Compressor' && !r.on && s.compRestLeft > 0) {
      why = (why || 'Resting') + ' · ' + fmt(s.compRestLeft) + ' left';
    }
    row.querySelector('.reason').textContent = why || (r.on ? '' : 'Off');
    row.querySelector('.pill').textContent = r.on ? 'ON' : 'OFF';
    const sw = row.querySelector('.switch');
    sw.hidden = !manual;
    sw.setAttribute('aria-pressed', r.manual);
  });

  fill('tempSet', st.tempSet); fill('humSet', st.humSet);
  fill('tempBand', st.tempBand); fill('humBand', st.humBand);
  fill('compMinOff', st.compMinOff); fill('compMinOn', st.compMinOn); fill('fanRunOn', st.fanRunOn);
  if (document.activeElement !== $('fanMode')) $('fanMode').value = s.fanMode;
  fill('simT', rd.temp.toFixed(1)); fill('simH', rd.hum.toFixed(1));
  $('react').checked = s.sim.react;
  $('fault').checked = s.sim.fault;

  $('net').textContent = s.net.ip + ' · ' + (s.net.mode === 'ap' ? 'setup AP' : s.net.rssi + ' dBm');
}

document.querySelectorAll('#mode button').forEach(b =>
  b.onclick = () => call('/api/settings', { mode: b.dataset.mode }));

document.querySelectorAll('.stepper button').forEach(b => b.onclick = () => {
  const el = $(b.dataset.for);
  const step = parseFloat(b.dataset.step);
  el.value = Math.round(((parseFloat(el.value) || 0) + step) * 10) / 10;
  el.dataset.dirty = '1';
  if (b.hasAttribute('data-live')) applySim();
});

$('save').onclick = async () => {
  const ids = ['tempSet', 'humSet', 'tempBand', 'humBand', 'compMinOff', 'compMinOn', 'fanRunOn'];
  const data = { fanMode: $('fanMode').value };
  ids.forEach(id => data[id] = $(id).value);
  clean(ids);
  await call('/api/settings', data);
};

function applySim() {
  const data = { temp: $('simT').value, hum: $('simH').value };
  clean(['simT', 'simH']);
  call('/api/sim', data);
}
$('simSet').onclick = applySim;
['simT', 'simH'].forEach(id => $(id).addEventListener('keydown', e => { if (e.key === 'Enter') applySim(); }));
$('react').onchange = () => call('/api/sim', { react: $('react').checked ? 1 : 0 });
$('fault').onchange = () => call('/api/sim', { fault: $('fault').checked ? 1 : 0 });

async function poll() {
  try { render(await api('/api/state')); if ($('msg').textContent === 'Offline') $('msg').textContent = ''; }
  catch (e) { $('msg').textContent = 'Offline'; }
}
poll();
setInterval(poll, 1000);
</script>
</body>
</html>
)rawliteral";
