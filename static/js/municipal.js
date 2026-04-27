var CONTACTS = [
  {
    id: 'BBMP-01', name: 'Kavya Narayan', designation: 'Assistant Executive Engineer',
    phone: '+91 98457 43120', email: 'kavya.n@bbmp.gov.in', zone: 'South Zone',
    shift: 'Day', sla: 'Responds within 4 hrs'
  },
  {
    id: 'BBMP-02', name: 'Arun Kumar', designation: 'Health Inspector',
    phone: '+91 97311 22841', email: 'arun.kumar@bbmp.gov.in', zone: 'Koramangala Ward',
    shift: 'Night', sla: 'On-call rapid response'
  },
  {
    id: 'BBMP-03', name: 'Meera Singh', designation: 'Material Recovery Facility Lead',
    phone: '+91 96201 84150', email: 'meera.singh@bbmp.gov.in', zone: 'Ward Cluster 14-16',
    shift: 'Day', sla: 'Schedules pickups within 24 hrs'
  }
];

var hotspots = [];
var routeMap = null;
var routeLayer = null;
var routeMarkerLayer = null;

function badgeClassForSeverity(label) {
  if (label === 'Critical' || label === 'High') return 'badge-destructive';
  if (label === 'Moderate') return 'badge-secondary';
  return 'badge-outline';
}

function initRouteMap() {
  if (typeof L === 'undefined' || routeMap) return;
  routeMap = L.map('routeMap').setView([12.9370, 77.6180], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(routeMap);
  routeLayer = L.layerGroup().addTo(routeMap);
  routeMarkerLayer = L.layerGroup().addTo(routeMap);
}

function renderContacts(filtered) {
  var html = '';
  if (filtered.length === 0) {
    html = '<p class="text-sm text-muted-foreground">No officers found. Try another keyword.</p>';
  } else {
    filtered.forEach(function(c) {
      var shiftBadge = c.shift === 'Night' ? 'badge-secondary' : 'badge-outline';
      html += '<div class="rounded-xl border border-border/70 bg-background/70 p-4">' +
        '<div class="flex flex-wrap items-center justify-between gap-2">' +
          '<div><p class="text-sm font-semibold">' + c.name + '</p>' +
          '<p class="text-xs text-muted-foreground">' + c.designation + '</p></div>' +
          '<span class="badge ' + shiftBadge + '">' + c.shift + ' shift</span>' +
        '</div>' +
        '<div class="mt-3 space-y-2 text-xs text-muted-foreground">' +
          '<span class="flex items-center gap-2"><i data-lucide="map-pin" class="h-4 w-4"></i> ' + c.zone + '</span>' +
          '<span class="flex items-center gap-2"><i data-lucide="phone" class="h-4 w-4"></i> ' + c.phone + '</span>' +
          '<span class="flex items-center gap-2"><i data-lucide="mail" class="h-4 w-4"></i> ' + c.email + '</span>' +
        '</div>' +
        '<p class="mt-2 text-xs font-medium text-foreground">' + c.sla + '</p>' +
      '</div>';
    });
  }
  document.getElementById('contactsList').innerHTML = html;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderHotspotQueue(selectedId) {
  var html = '';
  if (!hotspots.length) {
    html = '<p class="text-sm text-muted-foreground">No hotspot queue available yet.</p>';
  } else {
    hotspots.forEach(function(hotspot) {
      html += '<button class="w-full rounded-xl border border-border/70 bg-background/70 p-4 text-left transition hover:border-primary/40 ' +
        (selectedId === hotspot.id ? 'ring-2 ring-primary/50' : '') + '" onclick="optimizeRoute(\'' + hotspot.id + '\')">' +
        '<div class="flex items-center justify-between gap-2">' +
          '<div><p class="text-sm font-semibold">' + hotspot.ward + '</p>' +
          '<p class="text-xs text-muted-foreground">' + hotspot.complaintCount + ' reports · ' + hotspot.leadIssue + '</p></div>' +
          '<span class="badge ' + badgeClassForSeverity(hotspot.severity) + '">' + hotspot.severity + '</span>' +
        '</div>' +
        '<div class="mt-3 grid gap-1 text-xs text-muted-foreground">' +
          '<span>Priority score: ' + hotspot.priorityScore.toFixed(1) + '</span>' +
          '<span>Open incidents: ' + hotspot.openCount + '</span>' +
          '<span>Recommended depot: ' + hotspot.recommendedDepot + '</span>' +
        '</div>' +
      '</button>';
    });
  }
  document.getElementById('hotspotQueue').innerHTML = html;
}

function drawRoute(route, hotspot) {
  if (!routeMap || !routeLayer || !routeMarkerLayer) return;

  routeLayer.clearLayers();
  routeMarkerLayer.clearLayers();

  var latLngs = route.path.map(function(point) {
    return [point.latitude, point.longitude];
  });

  if (latLngs.length) {
    L.polyline(latLngs, { color: '#f97316', weight: 5, opacity: 0.9 }).addTo(routeLayer);
    route.path.forEach(function(point, index) {
      L.marker([point.latitude, point.longitude]).addTo(routeMarkerLayer)
        .bindPopup((index + 1) + '. ' + point.name);
    });
    routeMap.fitBounds(latLngs, { padding: [20, 20] });
  }

  hotspots.forEach(function(item) {
    L.circle([item.latitude, item.longitude], {
      radius: 120 + item.complaintCount * 35,
      color: item.id === hotspot.id ? '#f97316' : '#64748b',
      fillOpacity: item.id === hotspot.id ? 0.2 : 0.08
    }).addTo(routeMarkerLayer);
  });
}

function renderRoutePlan(route, hotspot) {
  document.getElementById('routeTitle').textContent = hotspot.title;
  document.getElementById('routeSeverity').textContent = hotspot.severity;
  document.getElementById('routeSeverity').className = 'badge ' + badgeClassForSeverity(hotspot.severity);
  document.getElementById('routeDepot').textContent = route.startDepot;
  document.getElementById('routeDistance').textContent = route.distanceKm.toFixed(2) + ' km';
  document.getElementById('routeEta').textContent = route.etaMinutes + ' min';

  var stopsHtml = '';
  route.stops.forEach(function(stop, index) {
    stopsHtml += '<div class="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-sm">' +
      '<span class="text-muted-foreground">Stop ' + (index + 1) + '</span><br><span class="font-medium">' + stop + '</span></div>';
  });
  document.getElementById('routeStops').innerHTML = stopsHtml;

  drawRoute(route, hotspot);
}

function optimizeRoute(hotspotId) {
  fetch('/api/routes/optimize?hotspotId=' + encodeURIComponent(hotspotId))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      renderHotspotQueue(data.hotspot.id);
      renderRoutePlan(data.route, data.hotspot);
      if (typeof lucide !== 'undefined') lucide.createIcons();
    });
}

function loadHotspots() {
  return fetch('/api/hotspots')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      hotspots = data.hotspots || [];
      var params = new URLSearchParams(window.location.search);
      var initialHotspot = params.get('hotspot') || (hotspots[0] && hotspots[0].id);
      renderHotspotQueue(initialHotspot);
      if (initialHotspot) optimizeRoute(initialHotspot);
    });
}

function filterContacts() {
  var term = document.getElementById('search').value.toLowerCase().trim();
  if (!term) {
    renderContacts(CONTACTS);
    return;
  }
  var filtered = CONTACTS.filter(function(c) {
    return c.name.toLowerCase().indexOf(term) !== -1 ||
           c.zone.toLowerCase().indexOf(term) !== -1 ||
           c.designation.toLowerCase().indexOf(term) !== -1;
  });
  renderContacts(filtered);
}

document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('updateBadge').textContent = 'Updated ' + new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
  initRouteMap();
  renderContacts(CONTACTS);
  loadHotspots();
  setInterval(function() {
    loadHotspots().then(function() {
      document.getElementById('updateBadge').textContent = 'Updated ' + new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
    }).catch(function() {
      // Keep silent during background polling.
    });
  }, 15000);
});
