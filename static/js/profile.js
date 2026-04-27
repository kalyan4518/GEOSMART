/* ── Profile page – edit & save via Flask API ─────────────────────── */

var isDirty = false;

function markDirty() {
  isDirty = true;
  document.getElementById('saveBtn').disabled = false;
  updateDisplay();
}

function updateDisplay() {
  var name = document.getElementById('profileName').value;
  var org = document.getElementById('profileOrg').value;
  document.getElementById('displayName').textContent = name;
  document.getElementById('displayOrg').textContent = org;

  var initials = name.split(' ').map(function(p) { return p[0] || ''; }).join('').slice(0, 2).toUpperCase();
  document.getElementById('avatarInitials').textContent = initials;
}

function saveProfile() {
  var payload = {
    name: document.getElementById('profileName').value,
    email: document.getElementById('profileEmail').value,
    location: document.getElementById('profileLocation').value,
    organisation: document.getElementById('profileOrg').value
  };

  fetch('/api/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    isDirty = false;
    document.getElementById('saveBtn').disabled = true;
    document.getElementById('roleBadge').textContent = 'Role: ' + (data.role || 'Community Sustainability Officer');
    showToast('Profile saved', 'Your contact details are now synced with the ward dashboard.');
  });
}

function loadProfile() {
  fetch('/api/profile')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      document.getElementById('profileName').value = data.name;
      document.getElementById('profileEmail').value = data.email;
      document.getElementById('profileLocation').value = data.location;
      document.getElementById('profileOrg').value = data.organisation;
      document.getElementById('roleBadge').textContent = 'Role: ' + (data.role || 'Community Sustainability Officer');
      updateDisplay();
    });
}

document.addEventListener('DOMContentLoaded', function() {
  loadProfile();
});
