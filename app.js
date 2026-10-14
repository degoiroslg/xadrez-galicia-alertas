const DATA_URL = "data/tournaments.json";
const SEEN_KEY = "xadrez-galicia-seen-v1";
let tournaments = [];
let seen = new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]"));

const $ = (id) => document.getElementById(id);
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[ch]));
const dateText = (start, end) => {
  if (!start) return "Data por confirmar";
  const fmt = (s) => new Intl.DateTimeFormat("gl-ES",{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"}).format(new Date(`${s}T12:00:00Z`));
  return end && end !== start ? `${fmt(start)} – ${fmt(end)}` : fmt(start);
};
const months = [
  ["01","Xaneiro"],["02","Febreiro"],["03","Marzo"],["04","Abril"],
  ["05","Maio"],["06","Xuño"],["07","Xullo"],["08","Agosto"],
  ["09","Setembro"],["10","Outubro"],["11","Novembro"],["12","Decembro"]
];
months.forEach(([v,n]) => $("month").add(new Option(n,v)));

function render() {
  const q = $("search").value.trim().toLocaleLowerCase("gl");
  const province = $("province").value;
  const month = $("month").value;
  const format = $("format").value;
  const onlyNew = $("only-new").checked;
  const filtered = tournaments.filter(t => {
    const text = [t.title,t.location,t.province,t.format,t.description,t.source_name].join(" ").toLocaleLowerCase("gl");
    const date = t.start_date || "";
    return (!q || text.includes(q)) &&
      (!province || (t.province || "Sen determinar") === province) &&
      (!month || date.slice(5,7) === month) &&
      (!format || (t.format || "Sen determinar") === format) &&
      (!onlyNew || !seen.has(t.id));
  }).sort((a,b) => (a.start_date || "9999").localeCompare(b.start_date || "9999") || a.title.localeCompare(b.title,"gl"));
  $("result-count").textContent = `${filtered.length} ${filtered.length === 1 ? "torneo" : "torneos"}`;
  $("status").hidden = filtered.length > 0;
  $("tournaments").innerHTML = filtered.map(t => {
    const isNew = !seen.has(t.id);
    const loc = [t.location,t.province].filter(Boolean).join(" · ");
    return `<article class="card">
      <div class="card-top">${isNew ? '<span class="tag new">Novo</span>' : ""}<span class="tag">${safe(t.format || "Sen determinar")}</span></div>
      <h2>${safe(t.title)}</h2>
      <div class="date">${safe(dateText(t.start_date,t.end_date))}</div>
      <div class="details">${loc ? `<span>📍 ${safe(loc)}</span>` : ""}${t.category ? `<span>♟ ${safe(t.category)}</span>` : ""}</div>
      ${t.description ? `<p>${safe(t.description)}</p>` : ""}
      <p class="details">Fonte: ${safe(t.source_name || "Fonte externa")}${t.last_seen ? ` · comprobado ${safe(t.last_seen)}` : ""}</p>
      ${t.url ? `<a href="${safe(t.url)}" target="_blank" rel="noopener noreferrer">Ver información orixinal ↗</a>` : ""}
    </article>`;
  }).join("");
}
function markSeen() {
  tournaments.forEach(t => seen.add(t.id));
  localStorage.setItem(SEEN_KEY, JSON.stringify([...seen]));
  $("new-count").hidden = true;
  render();
}
async function init() {
  try {
    const response = await fetch(DATA_URL, {cache:"no-store"});
    if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);
    const data = await response.json();
    tournaments = Array.isArray(data.tournaments) ? data.tournaments : [];
    const fresh = tournaments.filter(t => !seen.has(t.id)).length;
    $("updated").textContent = data.updated_at ? `Última actualización: ${new Intl.DateTimeFormat("gl-ES",{dateStyle:"medium",timeStyle:"short"}).format(new Date(data.updated_at))}` : "Aínda non hai data de actualización";
    if (fresh) {
      $("new-count").textContent = `${fresh} ${fresh === 1 ? "novidade" : "novidades"}`;
      $("new-count").hidden = false;
    }
    if (!tournaments.length) {
      $("status").textContent = "Aínda non hai torneos extraídos automaticamente. Executa o workflow de actualización e revisa os rexistros en GitHub Actions.";
      $("status").hidden = false;
    } else {
      $("status").textContent = "";
      $("status").hidden = true;
    }
    render();
  } catch (err) {
    $("status").textContent = "Non foi posible cargar o calendario. Comproba a conexión ou tenta máis tarde.";
    $("status").classList.add("error");
    $("status").hidden = false;
    console.error(err);
  }
}
["search","province","month","format","only-new"].forEach(id => $(id).addEventListener("input",render));
$("reset").addEventListener("click",() => {
  $("search").value = ""; $("province").value = ""; $("month").value = ""; $("format").value = ""; $("only-new").checked = false; render();
});
$("new-count").addEventListener("click",markSeen);
$("new-count").title = "Preme para marcar as novidades como vistas";
init();
