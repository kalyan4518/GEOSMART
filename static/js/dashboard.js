function badgeClassForSeverity(label) {
  if (label === 'Critical' || label === 'High') return 'badge-destructive';
  if (label === 'Moderate') return 'badge-secondary';
  return 'badge-outline';
}

function formatDate(iso) {
  return new Date(iso).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

function buildStatusTimeline(status) {
  var steps = ['Pending', 'Assigned', 'In Progress', 'Resolved'];
  var currentIndex = steps.indexOf(status);
  var html = '<div class="mt-3 grid grid-cols-4 gap-2">';

  steps.forEach(function(step, index) {
    var isDone = currentIndex >= index;
    var isCurrent = currentIndex === index;
    var badgeClass = isDone ? 'badge-default' : 'badge-outline';
    if (isCurrent && step !== 'Resolved') {
      badgeClass = 'badge-secondary';
    }
    html += '<span class="badge ' + badgeClass + ' justify-center">' + step + '</span>';
  });

  html += '</div>';
  return html;
}

function renderDashboardHotspots(hotspots) {
  var html = '';
  if (!hotspots.length) {
    html = '<p class="text-sm text-muted-foreground">No hotspot activity yet.</p>';
  } else {
    hotspots.slice(0, 4).forEach(function(hotspot) {
      var badgeClass = hotspot.severity === 'Critical' || hotspot.severity === 'High' ? 'badge-destructive' : hotspot.severity === 'Moderate' ? 'badge-secondary' : 'badge-outline';
      html += '<div class="rounded-xl border border-border/70 bg-background/70 p-4">' +
        '<div class="flex items-center justify-between gap-3">' +
          '<div><p class="text-sm font-semibold">' + hotspot.ward + '</p><p class="text-xs text-muted-foreground">' + hotspot.complaintCount + ' reports · ' + hotspot.leadIssue + '</p></div>' +
          '<span class="badge ' + badgeClass + '">' + hotspot.severity + '</span>' +
        '</div>' +
        '<p class="mt-2 text-xs text-muted-foreground">Depot: ' + hotspot.recommendedDepot + ' · ETA ' + (hotspot.etaMinutes || '--') + ' min</p>' +
      '</div>';
    });
  }
  document.getElementById('dashboardHotspots').innerHTML = html;
}

function renderMyComplaints(complaints) {
  var html = '';
  if (!complaints.length) {
    html = '<div class="rounded-lg border border-border/70 bg-background/70 p-4 text-sm text-muted-foreground">No complaints submitted yet. Use the complaint form to create your first report.</div>';
  } else {
    complaints.forEach(function(c) {
      var statusBadge = c.status === 'Resolved' ? 'badge-outline' : c.status === 'In Progress' ? 'badge-secondary' : c.status === 'Assigned' ? 'badge-default' : 'badge-outline';
      html += '<div class="rounded-lg border border-border/70 bg-background/70 p-4">' +
        '<div class="flex flex-wrap items-center justify-between gap-2">' +
          '<div><p class="text-sm font-semibold">' + c.id + '</p><p class="text-xs text-muted-foreground">' + formatDate(c.createdAt) + '</p></div>' +
          '<div class="flex flex-wrap gap-2">' +
            '<span class="badge ' + badgeClassForSeverity(c.severityLabel) + '">' + c.severityLabel + '</span>' +
            '<span class="badge ' + statusBadge + '">' + c.status + '</span>' +
          '</div>' +
        '</div>' +
        '<p class="mt-2 text-sm text-muted-foreground">' + c.ward + ' · ' + c.location + '</p>' +
        '<p class="mt-1 text-sm">' + c.description + '</p>' +
        (c.status === 'Resolved' && c.resolvedAt ? '<p class="mt-2 text-xs text-muted-foreground">Resolved on ' + formatDate(c.resolvedAt) + ' by ' + (c.resolvedBy || 'Admin Team') + '</p>' : '') +
        buildStatusTimeline(c.status) +
      '</div>';
    });
  }
  document.getElementById('myComplaintList').innerHTML = html;
}

function loadMyComplaints() {
  return fetch('/api/complaints')
    .then(function(r) {
      if (!r.ok) throw new Error('Failed to load your complaints');
      return r.json();
    })
    .then(function(complaints) {
      var openCount = complaints.filter(function(c) { return c.status !== 'Resolved'; }).length;
      var resolvedCount = complaints.filter(function(c) { return c.status === 'Resolved'; }).length;

      document.getElementById('metricMyTotal').textContent = String(complaints.length);
      document.getElementById('metricMyOpen').textContent = String(openCount);
      document.getElementById('metricMyResolved').textContent = String(resolvedCount);
      renderMyComplaints(complaints);
    });
}

function loadDashboardSummary() {
  fetch('/api/dashboard-summary')
    .then(function(r) {
      if (!r.ok) throw new Error('Failed to load dashboard summary');
      return r.json();
    })
    .then(function(summary) {
      if (summary.topHotspot) {
        document.getElementById('topHotspotTitle').textContent = summary.topHotspot.title;
        document.getElementById('topHotspotMeta').textContent = summary.topHotspot.complaintCount + ' reports · lead issue: ' + summary.topHotspot.leadIssue;
        document.getElementById('topHotspotSeverity').textContent = summary.topHotspot.severity;
        document.getElementById('topHotspotSeverity').className = 'badge ' + (summary.topHotspot.severity === 'Critical' || summary.topHotspot.severity === 'High' ? 'badge-destructive' : summary.topHotspot.severity === 'Moderate' ? 'badge-secondary' : 'badge-outline');
        document.getElementById('topHotspotDepot').textContent = summary.recommendedRoute ? summary.recommendedRoute.startDepot : '--';
        document.getElementById('topHotspotEta').textContent = summary.recommendedRoute ? summary.recommendedRoute.etaMinutes + ' min' : '--';
      }

      fetch('/api/hotspots')
        .then(function(r) {
          if (!r.ok) throw new Error('Failed to load hotspot queue');
          return r.json();
        })
        .then(function(data) {
          renderDashboardHotspots(data.hotspots || []);
        });
    })
    .catch(function(err) {
      showToast('Dashboard load failed', err.message || 'Please refresh the page.');
    });
}

document.addEventListener('DOMContentLoaded', function() {
  var myComplaintsCard = document.getElementById('myComplaintsCard');
  var trackingSection = document.getElementById('myComplaintTrackingSection');
  if (myComplaintsCard && trackingSection) {
    myComplaintsCard.addEventListener('click', function() {
      trackingSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  loadMyComplaints().catch(function(err) {
    showToast('Could not load your complaints', err.message || 'Please refresh the page.');
  });
  loadDashboardSummary();
  setInterval(function() {
    loadMyComplaints().catch(function() {
      // Keep silent during periodic refresh.
    });
  }, 10000);
  setInterval(loadDashboardSummary, 10000);
});