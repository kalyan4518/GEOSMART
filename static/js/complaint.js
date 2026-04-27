var ISSUE_LABELS = {
  collection_delay: 'Delayed collection',
  overflow: 'Overflowing bin',
  illegal_dumping: 'Illegal dumping',
  hazardous_waste: 'Hazardous waste leak',
  no_segregation: 'Segregation breach',
  other: 'Other'
};

var complaints = [];
var hotspots = [];
var complaintMap = null;
var evidenceLayer = null;
var hotspotLayer = null;
var reporterMarker = null;
var canUpdateStatus = window.CAN_UPDATE_STATUS === true;

function formatDate(iso) {
  return new Date(iso).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

function badgeClassForSeverity(label) {
  if (label === 'Critical' || label === 'High') return 'badge-destructive';
  if (label === 'Moderate') return 'badge-secondary';
  return 'badge-outline';
}

function initComplaintMap() {
  if (typeof L === 'undefined' || complaintMap) return;
  complaintMap = L.map('complaintMap').setView([12.9355, 77.6180], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(complaintMap);
  evidenceLayer = L.layerGroup().addTo(complaintMap);
  hotspotLayer = L.layerGroup().addTo(complaintMap);
}

function refreshMap() {
  if (!complaintMap || !evidenceLayer || !hotspotLayer) return;
  evidenceLayer.clearLayers();
  hotspotLayer.clearLayers();

  complaints.forEach(function(complaint) {
    var marker = L.circleMarker([complaint.latitude, complaint.longitude], {
      radius: complaint.priority === 'critical' ? 10 : 7,
      color: complaint.status === 'Resolved' ? '#10b981' : complaint.priority === 'critical' ? '#ef4444' : '#f97316',
      fillOpacity: 0.85
    });
    marker.bindPopup(
      '<strong>' + complaint.id + '</strong><br>' +
      complaint.ward + ' · ' + complaint.location + '<br>' +
      (complaint.verification ? 'Verification: ' + Math.round(complaint.verification.confidence * 100) + '%' : '')
    );
    marker.addTo(evidenceLayer);
  });

  hotspots.forEach(function(hotspot) {
    var circle = L.circle([hotspot.latitude, hotspot.longitude], {
      radius: 120 + hotspot.complaintCount * 35,
      color: hotspot.severity === 'Critical' ? '#ef4444' : hotspot.severity === 'High' ? '#f97316' : '#facc15',
      fillColor: hotspot.severity === 'Critical' ? '#ef4444' : hotspot.severity === 'High' ? '#f97316' : '#facc15',
      fillOpacity: 0.12
    });
    circle.bindPopup(
      '<strong>' + hotspot.title + '</strong><br>' +
      'Open tickets: ' + hotspot.openCount + '<br>' +
      'Recommended depot: ' + hotspot.recommendedDepot
    );
    circle.addTo(hotspotLayer);
  });
}

function loadComplaints() {
  return fetch('/api/complaints')
    .then(function(r) {
      if (!r.ok) throw new Error('Could not load complaints');
      return r.json();
    })
    .then(function(data) {
      complaints = data;
      renderAll();
    });
}

function loadHotspots() {
  return fetch('/api/hotspots')
    .then(function(r) {
      if (!r.ok) throw new Error('Could not load hotspots');
      return r.json();
    })
    .then(function(data) {
      hotspots = data.hotspots || [];
      renderHotspots();
      refreshMap();
    });
}

function renderAll() {
  updateMetrics();
  renderList();
  refreshMap();
}

function updateMetrics() {
  var total = complaints.length;
  var open = complaints.filter(function(c) { return c.status !== 'Resolved'; }).length;
  var critical = complaints.filter(function(c) { return c.priority === 'critical'; }).length;
  var resolved = complaints.filter(function(c) { return c.status === 'Resolved'; }).length;
  var verified = complaints.filter(function(c) { return c.verification && c.verification.status === 'Verified'; }).length;

  document.getElementById('metricTotal').textContent = total;
  document.getElementById('metricOpen').textContent = open;
  document.getElementById('metricCritical').textContent = critical;
  document.getElementById('metricResolved').textContent = resolved;
  document.getElementById('metricVerified').textContent = verified + ' / ' + total;
  document.getElementById('metricHotspots').textContent = (hotspots.length || 0) + ' hotspot zones';

  document.getElementById('badgeOpen').textContent = 'Open tickets: ' + open;
  document.getElementById('badgeResolved').textContent = 'Resolved: ' + resolved;
  var badgeCrit = document.getElementById('badgeCritical');
  badgeCrit.textContent = 'Critical: ' + critical;
  badgeCrit.className = 'badge ' + (critical > 0 ? 'badge-destructive' : 'badge-secondary');
}

function renderHotspots() {
  var html = '';
  if (!hotspots.length) {
    html = '<p class="text-sm text-muted-foreground">Hotspot intelligence will appear once reports are available.</p>';
  } else {
    hotspots.forEach(function(hotspot) {
      html += '<div class="rounded-xl border border-border/70 bg-background/70 p-4">' +
        '<div class="flex items-center justify-between gap-3">' +
          '<div><p class="text-sm font-semibold">' + hotspot.ward + '</p>' +
          '<p class="text-xs text-muted-foreground">' + hotspot.complaintCount + ' reports · lead issue: ' + hotspot.leadIssue + '</p></div>' +
          '<span class="badge ' + badgeClassForSeverity(hotspot.severity) + '">' + hotspot.severity + '</span>' +
        '</div>' +
        '<div class="mt-3 grid gap-2 text-xs text-muted-foreground">' +
          '<span>Priority score: ' + hotspot.priorityScore.toFixed(1) + '</span>' +
          '<span>Recommended depot: ' + hotspot.recommendedDepot + '</span>' +
          '<span>ETA: ' + (hotspot.etaMinutes ? hotspot.etaMinutes + ' min' : 'Pending') + '</span>' +
        '</div>' +
        '<button class="btn btn-outline btn-sm mt-3 w-full" onclick="openMunicipalRoute(\'' + hotspot.id + '\')">View route plan</button>' +
      '</div>';
    });
  }
  document.getElementById('hotspotList').innerHTML = html;
  updateMetrics();
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderVerification(record) {
  var verification = record.verification || {};
  var confidence = verification.confidence ? Math.round(verification.confidence * 100) : 0;
  var html = '<div class="grid gap-4">' +
    '<div class="rounded-xl border border-primary/20 bg-primary/5 p-4">' +
      '<div class="flex items-center justify-between gap-3">' +
        '<div><p class="text-sm text-muted-foreground">Verification result</p><p class="text-lg font-semibold">' + (verification.predictedWaste || 'Awaiting evidence') + '</p></div>' +
        '<span class="badge ' + (verification.status === 'Verified' ? 'badge-default' : 'badge-secondary') + '">' + (verification.status || 'Pending') + '</span>' +
      '</div>' +
      '<p class="mt-3 text-sm text-muted-foreground">Confidence score: ' + confidence + '%</p>' +
      '<p class="mt-2 text-sm text-muted-foreground">Nearest depot: ' + (record.routeHint ? record.routeHint.depot : 'Pending') + ' · ETA ' + (record.routeHint && record.routeHint.etaMinutes ? record.routeHint.etaMinutes + ' min' : 'Pending') + '</p>' +
    '</div>' +
    '<div class="space-y-2">';

  (verification.flags || []).forEach(function(flag) {
    html += '<div class="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-sm text-muted-foreground">' + flag + '</div>';
  });
  if (record.imageUrl) {
    html += '<a class="btn btn-outline w-full" href="' + record.imageUrl + '" target="_blank" rel="noreferrer">Open uploaded evidence</a>';
  }
  html += '</div></div>';
  document.getElementById('verificationPanel').innerHTML = html;
}

function renderList() {
  var html = '';
  complaints.forEach(function(c) {
    var statusBadge = c.status === 'Resolved' ? 'badge-outline' : c.status === 'In Progress' ? 'badge-secondary' : c.status === 'Assigned' ? 'badge-default' : 'badge-outline';
    html += '<div class="rounded-lg border border-border/70 bg-background/70 p-4">' +
      '<div class="flex flex-wrap items-center justify-between gap-2">' +
        '<div>' +
          '<p class="text-sm font-semibold">' + c.id + '</p>' +
          '<p class="text-xs text-muted-foreground">Logged ' + formatDate(c.createdAt) + '</p>' +
        '</div>' +
        '<div class="flex flex-wrap gap-2">' +
          '<span class="badge ' + badgeClassForSeverity(c.severityLabel) + '">' + c.severityLabel + '</span>' +
          '<span class="badge ' + statusBadge + '">' + c.status + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="separator my-3"></div>' +
      '<div class="grid gap-2 text-sm text-muted-foreground">' +
        '<span class="flex items-center gap-2"><i data-lucide="alert-triangle" class="h-4 w-4"></i> ' + (ISSUE_LABELS[c.issueType] || c.issueType) + '</span>' +
        '<span class="flex items-center gap-2"><i data-lucide="scan-search" class="h-4 w-4"></i> ' + c.verification.status + ' · ' + Math.round(c.verification.confidence * 100) + '% confidence</span>' +
        '<span class="flex items-center gap-2"><i data-lucide="map-pin" class="h-4 w-4"></i> ' + c.ward + ' · ' + c.location + '</span>' +
        '<span class="flex items-center gap-2"><i data-lucide="route" class="h-4 w-4"></i> ' + c.routeHint.depot + ' · ' + (c.routeHint.etaMinutes ? c.routeHint.etaMinutes + ' min ETA' : 'ETA pending') + '</span>' +
        '<p>' + c.description + '</p>' +
        (c.contact ? '<p>Reporter: ' + c.contact + '</p>' : '') +
        (c.imageUrl ? '<a class="text-primary hover:underline" href="' + c.imageUrl + '" target="_blank" rel="noreferrer">View attached evidence</a>' : '') +
      '</div>';

    if (canUpdateStatus && c.status !== 'Resolved') {
      html += '<div class="mt-3 flex flex-wrap gap-2">';
      if (c.status === 'Pending') {
        html += '<button class="btn btn-secondary btn-sm" onclick="updateStatus(\'' + c.id + '\', \'Assigned\')">Assign ticket</button>';
      }
      if (c.status === 'Assigned') {
        html += '<button class="btn btn-secondary btn-sm" onclick="updateStatus(\'' + c.id + '\', \'In Progress\')">Start work</button>';
      }
      html += '<button class="btn btn-ghost btn-sm" onclick="updateStatus(\'' + c.id + '\', \'Resolved\')">Mark resolved</button>';
      html += '</div>';
    }

    html += '</div>';
  });

  document.getElementById('complaintList').innerHTML = html;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function captureLocation() {
  if (!navigator.geolocation) {
    showToast('Geolocation unavailable', 'Your browser does not support location capture.');
    return;
  }

  var button = document.getElementById('captureLocationBtn');
  button.disabled = true;
  button.textContent = 'Capturing location...';

  navigator.geolocation.getCurrentPosition(function(position) {
    var lat = position.coords.latitude.toFixed(6);
    var lng = position.coords.longitude.toFixed(6);
    document.getElementById('latitude').value = lat;
    document.getElementById('longitude').value = lng;
    showToast('Location captured', 'GPS coordinates attached to this report.');

    if (complaintMap) {
      if (reporterMarker) reporterMarker.remove();
      reporterMarker = L.marker([parseFloat(lat), parseFloat(lng)]).addTo(complaintMap).bindPopup('Current reporter location');
      complaintMap.setView([parseFloat(lat), parseFloat(lng)], 14);
    }

    button.disabled = false;
    button.innerHTML = '<i data-lucide="locate-fixed" class="h-4 w-4"></i> Capture my location';
    if (typeof lucide !== 'undefined') lucide.createIcons();
  }, function() {
    button.disabled = false;
    button.innerHTML = '<i data-lucide="locate-fixed" class="h-4 w-4"></i> Capture my location';
    showToast('Location failed', 'Enable browser location access to attach GPS coordinates.');
    if (typeof lucide !== 'undefined') lucide.createIcons();
  });
}

function previewEvidenceName() {
  var input = document.getElementById('evidenceImage');
  var label = document.getElementById('imageMeta');
  if (!input.files || !input.files.length) {
    label.textContent = 'Attach a clear image so the verification engine can score the report.';
    return;
  }
  var file = input.files[0];
  label.textContent = file.name + ' · ' + Math.round(file.size / 1024) + ' KB selected';
}

function handleComplaintSubmit(e) {
  e.preventDefault();
  var ward = document.getElementById('ward').value.trim();
  var location = document.getElementById('complaintLocation').value.trim();
  var description = document.getElementById('description').value.trim();

  if (!ward || !location || !description) {
    showToast('Missing information', 'Ward, location, and description help us route your complaint quickly.');
    return false;
  }

  var formData = new FormData();
  formData.append('issueType', document.getElementById('issueType').value);
  formData.append('priority', document.getElementById('priority').value);
  formData.append('ward', ward);
  formData.append('location', location);
  formData.append('description', description);
  formData.append('contact', document.getElementById('contact').value.trim());
  formData.append('latitude', document.getElementById('latitude').value.trim());
  formData.append('longitude', document.getElementById('longitude').value.trim());

  var imageInput = document.getElementById('evidenceImage');
  if (imageInput.files && imageInput.files[0]) {
    formData.append('image', imageInput.files[0]);
  }

  fetch('/api/complaints', {
    method: 'POST',
    body: formData
  })
  .then(function(r) { return r.json(); })
  .then(function(record) {
    showToast('Complaint submitted', 'Tracking ID: ' + record.id + '. Hotspot intelligence has been refreshed.');
    renderVerification(record);
    document.getElementById('complaintForm').reset();
    document.getElementById('imageMeta').textContent = 'Attach a clear image so the verification engine can score the report.';
    document.getElementById('latitude').value = '';
    document.getElementById('longitude').value = '';
    if (reporterMarker) {
      reporterMarker.remove();
      reporterMarker = null;
    }
    Promise.all([loadComplaints(), loadHotspots()]);
  });

  return false;
}

function updateStatus(id, status) {
  fetch('/api/complaints/' + encodeURIComponent(id) + '/status', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: status })
  })
  .then(function(r) {
    if (!r.ok) {
      throw new Error('Only admin users can update complaint status.');
    }
    return r.json();
  })
  .then(function() {
    return Promise.all([loadComplaints(), loadHotspots()]);
  })
  .catch(function(err) {
    showToast('Status update failed', err.message || 'Could not update complaint status.');
  });
}

function openMunicipalRoute(hotspotId) {
  window.location.href = '/municipal?hotspot=' + encodeURIComponent(hotspotId);
}

document.addEventListener('DOMContentLoaded', function() {
  initComplaintMap();
  document.getElementById('evidenceImage').addEventListener('change', previewEvidenceName);
  Promise.all([loadComplaints(), loadHotspots()]).catch(function(err) {
    showToast('Unable to load complaint desk', err.message || 'Please refresh and try again.');
  });
  setInterval(function() {
    Promise.all([loadComplaints(), loadHotspots()]).catch(function() {
      // Keep silent during background polling.
    });
  }, 15000);
});
