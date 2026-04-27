function badgeClassForSeverity(label) {
  if (label === 'Critical' || label === 'High') return 'badge-destructive';
  if (label === 'Moderate') return 'badge-secondary';
  return 'badge-outline';
}

function statusBadgeClass(status) {
  if (status === 'Resolved') return 'badge-outline';
  if (status === 'In Progress') return 'badge-secondary';
  if (status === 'Assigned') return 'badge-default';
  return 'badge-outline';
}

function formatDate(iso) {
  return new Date(iso).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

function renderDashboardHotspots(hotspots) {
  var html = '';
  if (!hotspots.length) {
    html = '<p class="text-sm text-muted-foreground">No hotspot activity yet.</p>';
  } else {
    hotspots.slice(0, 4).forEach(function(hotspot) {
      html += '<div class="rounded-xl border border-border/70 bg-background/70 p-4">' +
        '<div class="flex items-center justify-between gap-3">' +
          '<div><p class="text-sm font-semibold">' + hotspot.ward + '</p><p class="text-xs text-muted-foreground">' + hotspot.complaintCount + ' reports · ' + hotspot.leadIssue + '</p></div>' +
          '<span class="badge ' + badgeClassForSeverity(hotspot.severity) + '">' + hotspot.severity + '</span>' +
        '</div>' +
        '<p class="mt-2 text-xs text-muted-foreground">Depot: ' + hotspot.recommendedDepot + ' · ETA ' + (hotspot.etaMinutes || '--') + ' min</p>' +
      '</div>';
    });
  }
  document.getElementById('dashboardHotspots').innerHTML = html;
}

function renderAdminComplaints(complaints) {
  var unresolved = complaints.filter(function(c) { return c.status !== 'Resolved'; });
  var html = '';

  if (!unresolved.length) {
    html = '<p class="text-sm text-muted-foreground">All complaints are resolved. Great work.</p>';
  } else {
    unresolved.forEach(function(c) {
      html += '<div class="rounded-lg border border-border/70 bg-background/70 p-4">' +
        '<div class="flex flex-wrap items-center justify-between gap-2">' +
          '<div><p class="text-sm font-semibold">' + c.id + '</p><p class="text-xs text-muted-foreground">Logged ' + formatDate(c.createdAt) + '</p></div>' +
          '<div class="flex flex-wrap gap-2">' +
            '<span class="badge ' + badgeClassForSeverity(c.severityLabel) + '">' + c.severityLabel + '</span>' +
            '<span class="badge ' + statusBadgeClass(c.status) + '">' + c.status + '</span>' +
          '</div>' +
        '</div>' +
        '<p class="mt-3 text-sm text-muted-foreground">' + c.ward + ' · ' + c.location + '</p>' +
        '<p class="text-sm mt-1">' + c.description + '</p>' +
        '<div class="mt-3 flex flex-wrap gap-2">';

      if (c.status === 'Pending') {
        html += '<button class="btn btn-secondary btn-sm" onclick="updateComplaintStatus(\'' + c.id + '\', \'Assigned\')">Assign</button>';
      }
      if (c.status === 'Assigned') {
        html += '<button class="btn btn-secondary btn-sm" onclick="updateComplaintStatus(\'' + c.id + '\', \'In Progress\')">Start work</button>';
      }
      html += '<button class="btn btn-ghost btn-sm" onclick="updateComplaintStatus(\'' + c.id + '\', \'Resolved\')">Mark resolved</button>';
      html += '</div></div>';
    });
  }

  document.getElementById('adminComplaintList').innerHTML = html;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function loadAdminData() {
  return Promise.all([
    fetch('/api/dashboard-summary').then(function(r) {
      if (!r.ok) throw new Error('Failed to load summary');
      return r.json();
    }),
    fetch('/api/hotspots').then(function(r) {
      if (!r.ok) throw new Error('Failed to load hotspots');
      return r.json();
    }),
    fetch('/api/complaints').then(function(r) {
      if (!r.ok) throw new Error('Failed to load complaints');
      return r.json();
    })
  ]).then(function(results) {
    var summary = results[0];
    var hotspotData = results[1];
    var complaints = results[2];

    var openCount = complaints.filter(function(c) { return c.status !== 'Resolved'; }).length;
    var resolvedCount = complaints.filter(function(c) { return c.status === 'Resolved'; }).length;

    document.getElementById('metricAdminOpen').textContent = String(openCount);
    document.getElementById('metricAdminResolved').textContent = String(resolvedCount);
    document.getElementById('metricActiveHotspots').textContent = String(summary.activeHotspots);
    document.getElementById('metricEta').textContent = summary.averageDispatchEta ? summary.averageDispatchEta + ' min' : '--';

    renderDashboardHotspots(hotspotData.hotspots || []);
    renderAdminComplaints(complaints);
  });
}

function updateComplaintStatus(complaintId, status) {
  fetch('/api/complaints/' + encodeURIComponent(complaintId) + '/status', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: status })
  })
    .then(function(r) {
      return r.json().then(function(payload) {
        if (!r.ok) {
          throw new Error(payload.error || 'Status update failed');
        }
        return payload;
      });
    })
    .then(function() {
      showToast('Status updated', 'Complaint moved to ' + status + '.');
      return loadAdminData();
    })
    .catch(function(err) {
      showToast('Update failed', err.message || 'Could not update status.');
    });
}

document.addEventListener('DOMContentLoaded', function() {
  loadAdminData().catch(function(err) {
    showToast('Dashboard load failed', err.message || 'Please refresh the page.');
  });
  setInterval(function() {
    loadAdminData().catch(function() {
      // Keep silent during periodic refresh.
    });
  }, 12000);
});
