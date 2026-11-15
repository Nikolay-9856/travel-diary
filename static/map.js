// Карты на Leaflet + OpenStreetMap. Если библиотека не загрузилась
// (нет интернета), страница продолжает работать без карты.
const TILE = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTR = '&copy; участники OpenStreetMap';

function baseMap(id, center, zoom) {
  const el = document.getElementById(id);
  if (!el || typeof L === 'undefined') { if (el) el.classList.add('nomap'); return null; }
  const map = L.map(el).setView(center, zoom);
  L.tileLayer(TILE, { attribution: ATTR, maxZoom: 18 }).addTo(map);
  return map;
}

function initOverviewMap(id) {
  const el = document.getElementById(id);
  const map = baseMap(id, [55.75, 37.62], 3);
  if (!map) return;
  fetch(el.dataset.src).then(r => r.json()).then(points => {
    const bounds = [];
    points.forEach(p => {
      L.marker([p.lat, p.lon]).addTo(map)
        .bindPopup(`<b>${escapeHtml(p.title)}</b><br>${escapeHtml(p.place)}<br><i>${escapeHtml(p.author)}</i><br><a href="${p.url}">Открыть</a>`);
      bounds.push([p.lat, p.lon]);
    });
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [50, 50] });
    else if (bounds.length === 1) map.setView(bounds[0], 8);
  });
}

function initPointMap(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const pos = [parseFloat(el.dataset.lat), parseFloat(el.dataset.lon)];
  const map = baseMap(id, pos, 10);
  if (map) L.marker(pos).addTo(map).bindPopup(escapeHtml(el.dataset.title)).openPopup();
}

let pickMarker = null, pickMap = null;
function initPickerMap(id, latId, lonId) {
  const lat = document.getElementById(latId), lon = document.getElementById(lonId);
  const has = lat.value && lon.value;
  pickMap = baseMap(id, has ? [+lat.value, +lon.value] : [55.75, 37.62], has ? 9 : 4);
  if (!pickMap) return;
  const place = (la, lo) => {
    lat.value = la.toFixed(6); lon.value = lo.toFixed(6);
    if (pickMarker) pickMarker.setLatLng([la, lo]); else pickMarker = L.marker([la, lo]).addTo(pickMap);
  };
  if (has) place(+lat.value, +lon.value);
  pickMap.on('click', e => place(e.latlng.lat, e.latlng.lng));
  window._placeMarker = place;
}

function useMyLocation() {
  if (!navigator.geolocation) { alert('Браузер не поддерживает геолокацию'); return; }
  navigator.geolocation.getCurrentPosition(p => {
    const la = p.coords.latitude, lo = p.coords.longitude;
    if (window._placeMarker) { window._placeMarker(la, lo); pickMap.setView([la, lo], 12); }
    else { document.getElementById('lat').value = la.toFixed(6); document.getElementById('lon').value = lo.toFixed(6); }
  }, err => alert('Не удалось определить местоположение: ' + err.message), { enableHighAccuracy: true, timeout: 10000 });
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
