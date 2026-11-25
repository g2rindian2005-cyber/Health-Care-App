/* ============================================================
   HealthCare — Shared UI Utilities
   Sidebar injection, Toast, Confirm Dialog, Helpers
   ============================================================ */

/* ── Path prefix: '../' only when the page lives in a module subfolder.
      Segment-count detection breaks on subpath hosting (e.g. GitHub Pages
      project sites under /<repo>/), so detect the module folder by name. ── */
function _prefix() {
  const parts = window.location.pathname.split('/').filter(Boolean);
  const MODULE_DIRS = ['patients', 'billing', 'diseases', 'doctors', 'laboratory', 'pharmacy', 'patient', 'doctor'];
  return parts.some(p => MODULE_DIRS.includes(p)) ? '../' : '';
}

/* ── Theme (dark mode): apply the saved choice as early as possible ── */
try {
  if (localStorage.getItem('hms_theme') === 'dark') {
    document.documentElement.dataset.theme = 'dark';
  }
} catch (e) { /* storage unavailable — stay on light theme */ }

function toggleTheme() {
  const dark = document.documentElement.dataset.theme !== 'dark';
  if (dark) document.documentElement.dataset.theme = 'dark';
  else delete document.documentElement.dataset.theme;
  try { localStorage.setItem('hms_theme', dark ? 'dark' : 'light'); } catch (e) {}
}

/* ── Build sidebar HTML with correct relative paths ──────── */
function buildSidebarHTML() {
  const p = _prefix();
  return `
<div class="sidebar-header">
  <div class="sidebar-logo-icon">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
    </svg>
  </div>
  <span class="sidebar-brand-name">Health<span>Care</span></span>
  <button class="sidebar-collapse-btn" id="sidebarCollapseBtn" title="Collapse sidebar" aria-label="Collapse sidebar">
    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>
  </button>
</div>

<nav class="sidebar-nav">
  <div class="nav-group">
    <span class="nav-group-label">Overview</span>
    <a href="${p}dashboard.html" class="nav-item" data-page="dashboard">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/>
          <rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>
        </svg>
      </span>
      Dashboard
    </a>
  </div>

  <div class="nav-group">
    <span class="nav-group-label">Patients</span>
    <a href="${p}patients/view-patient.html" class="nav-item" data-page="view-patient">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
          <path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </span>
      All Patients
    </a>
    <a href="${p}patients/add-patient.html" class="nav-item" data-page="add-patient">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
          <line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>
        </svg>
      </span>
      Register Patient
    </a>
    <a href="${p}patients/patient-history.html" class="nav-item" data-page="patient-history">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/>
          <line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>
        </svg>
      </span>
      Patient History
    </a>
  </div>

  <div class="nav-group">
    <span class="nav-group-label">Billing</span>
    <a href="${p}billing/create-bill.html" class="nav-item" data-page="create-bill">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/>
        </svg>
      </span>
      Create Bill
    </a>
    <a href="${p}billing/payment.html" class="nav-item" data-page="payment">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" x2="12" y1="1" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
        </svg>
      </span>
      Payments
    </a>
    <a href="${p}billing/pending-dues.html" class="nav-item" data-page="pending-dues">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
          <path d="M12 9v4"/><path d="M12 17h.01"/>
        </svg>
      </span>
      Pending Dues
    </a>
  </div>

  <div class="nav-group">
    <span class="nav-group-label">Clinical</span>
    <a href="${p}diseases/disease-history.html" class="nav-item" data-page="disease-history">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/>
          <path d="M3 10h18"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/>
          <path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/>
        </svg>
      </span>
      Diseases
    </a>
    <a href="${p}diseases/add-disease.html" class="nav-item" data-page="add-disease">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M8 12h8"/><path d="M12 8v8"/>
        </svg>
      </span>
      Add Disease
    </a>
  </div>

  <div class="nav-group">
    <span class="nav-group-label">Doctors</span>
    <a href="${p}doctors/add-doctor.html" class="nav-item" data-page="add-doctor">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 9h18v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9Z"/>
          <path d="m3 9 2.45-4.9A2 2 0 0 1 7.24 3h9.52a2 2 0 0 1 1.8 1.1L21 9"/>
          <path d="M12 3v6"/><path d="M9 12h6"/><path d="M12 12v6"/>
        </svg>
      </span>
      Add Doctor
    </a>
    <a href="${p}doctors/assign-doctor.html" class="nav-item" data-page="assign-doctor">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </span>
      Assign Doctor
    </a>
    <a href="${p}doctors/appointments.html" class="nav-item" data-page="appointments">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/>
          <path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>
        </svg>
      </span>
      Appointments
    </a>
  </div>
  <div class="nav-group">
    <span class="nav-group-label">Laboratory</span>
    <a href="${p}laboratory/lab-orders.html" class="nav-item" data-page="lab-orders">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 2v6L4.5 18a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 8V2"/><path d="M8.5 2h7"/><path d="M7 16h10"/>
        </svg>
      </span>
      Lab Orders
    </a>
    <a href="${p}laboratory/order-test.html" class="nav-item" data-page="order-test">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M8 12h8"/><path d="M12 8v8"/>
        </svg>
      </span>
      Order Test
    </a>
    <a href="${p}laboratory/test-catalog.html" class="nav-item" data-page="test-catalog">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
        </svg>
      </span>
      Test Catalog
    </a>
  </div>

  <div class="nav-group">
    <span class="nav-group-label">Pharmacy</span>
    <a href="${p}pharmacy/prescriptions.html" class="nav-item" data-page="prescriptions">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>
        </svg>
      </span>
      Prescriptions
    </a>
    <a href="${p}pharmacy/add-prescription.html" class="nav-item" data-page="add-prescription">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M8 12h8"/><path d="M12 8v8"/>
        </svg>
      </span>
      New Prescription
    </a>
    <a href="${p}pharmacy/medicine-catalog.html" class="nav-item" data-page="medicine-catalog">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
        </svg>
      </span>
      Medicine Catalog
    </a>
  </div>

  <div class="nav-group">
    <span class="nav-group-label">System</span>
    <a href="${p}reports.html" class="nav-item" data-page="reports">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/>
          <line x1="10" x2="10" y1="18" y2="6"/><line x1="14" x2="14" y1="18" y2="10"/>
          <line x1="18" x2="18" y1="18" y2="3"/>
        </svg>
      </span>
      Reports
    </a>
    <a href="${p}settings.html" class="nav-item" data-page="settings">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      </span>
      Settings
    </a>
  </div>
</nav>

<div class="sidebar-footer">
  <div class="sidebar-user">
    <div class="sidebar-user-avatar" id="sidebarUserAvatar">A</div>
    <div class="sidebar-user-info">
      <div class="sidebar-user-name" id="sidebarUserName">Administrator</div>
      <div class="sidebar-user-role">Hospital Admin</div>
    </div>
  </div>
  <div style="padding:10px 16px 0; font-size:11px; letter-spacing:.02em; color:rgba(226,238,255,.45);">HealthCare · by Gokul Rathod</div>
  <a href="${p}login.html" class="nav-item" id="logoutBtn" style="color:var(--red-600); margin-top:4px;">
    <span class="nav-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
           fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
        <polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>
      </svg>
    </span>
    Logout
  </a>
</div>`;
}

/* ── Patient sidebar: only the patient panel pages ──────────
   Shown when the signed-in account has role "patient". The admin
   modules (Patients / Billing / Doctors / Lab / Pharmacy) are not
   listed here at all. */
function buildPatientSidebarHTML() {
  const p = _prefix();
  return `
<div class="sidebar-header">
  <div class="sidebar-logo-icon">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
    </svg>
  </div>
  <span class="sidebar-brand-name">Health<span>Care</span></span>
  <button class="sidebar-collapse-btn" id="sidebarCollapseBtn" title="Collapse sidebar" aria-label="Collapse sidebar">
    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>
  </button>
</div>

<nav class="sidebar-nav">
  <div class="nav-group">
    <span class="nav-group-label">My Care</span>
    <a href="${p}patient/my-appointments.html" class="nav-item" data-page="my-appointments">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>
        </svg>
      </span>
      My Appointments
    </a>
    <a href="${p}patient/book-appointment.html" class="nav-item" data-page="book-appointment">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 9h18v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9Z"/><path d="m3 9 2.45-4.9A2 2 0 0 1 7.24 3h9.52a2 2 0 0 1 1.8 1.1L21 9"/><path d="M12 3v6"/><path d="M9 12h6"/><path d="M12 12v6"/>
        </svg>
      </span>
      Book Appointment
    </a>
    <a href="${p}patient/find-doctor.html" class="nav-item" data-page="find-doctor">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
      </span>
      Find a Doctor
    </a>
    <a href="${p}patient/messages.html" class="nav-item" data-page="messages">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </span>
      Messages
    </a>
    <a href="${p}patient/my-profile.html" class="nav-item" data-page="my-profile">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
        </svg>
      </span>
      My Profile
    </a>
    <a href="${p}patient/consultation-history.html" class="nav-item" data-page="consultation-history">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>
        </svg>
      </span>
      Consultation History
    </a>
    <a href="${p}patient/video-visit.html" class="nav-item" data-page="video-visit">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2"/>
        </svg>
      </span>
      Video Visit
    </a>
    <a href="${p}patient/my-reports.html" class="nav-item" data-page="my-reports">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
        </svg>
      </span>
      My Reports
    </a>
  </div>
</nav>

<div class="sidebar-footer">
  <div class="sidebar-user">
    <div class="sidebar-user-avatar" id="sidebarUserAvatar">P</div>
    <div class="sidebar-user-info">
      <div class="sidebar-user-name" id="sidebarUserName">Patient</div>
      <div class="sidebar-user-role">Patient</div>
    </div>
  </div>
  <div style="padding:10px 16px 0; font-size:11px; letter-spacing:.02em; color:rgba(226,238,255,.45);">HealthCare · by Gokul Rathod</div>
  <a href="${p}login.html" class="nav-item" id="logoutBtn" style="color:var(--red-600); margin-top:4px;">
    <span class="nav-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
           fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>
      </svg>
    </span>
    Logout
  </a>
</div>`;
}

/* ── Doctor sidebar: only the doctor panel pages ──────────
   Shown when the signed-in account has role "doctor". The admin
   modules (Patients / Billing / Doctors / Lab / Pharmacy) and the
   patient panel are not listed here at all — a doctor sees only
   their own appointments, patients and consultations. */
function buildDoctorSidebarHTML() {
  const p = _prefix();
  return `
<div class="sidebar-header">
  <div class="sidebar-logo-icon">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
    </svg>
  </div>
  <span class="sidebar-brand-name">Health<span>Care</span></span>
  <button class="sidebar-collapse-btn" id="sidebarCollapseBtn" title="Collapse sidebar" aria-label="Collapse sidebar">
    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>
  </button>
</div>

<nav class="sidebar-nav">
  <div class="nav-group">
    <span class="nav-group-label">My Practice</span>
    <a href="${p}doctor/my-appointments.html" class="nav-item" data-page="my-appointments">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>
        </svg>
      </span>
      My Appointments
    </a>
    <a href="${p}doctor/my-patients.html" class="nav-item" data-page="my-patients">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </span>
      My Patients
    </a>
    <a href="${p}doctor/messages.html" class="nav-item" data-page="messages">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </span>
      Messages
    </a>
    <a href="${p}doctor/consultation-history.html" class="nav-item" data-page="consultation-history">
      <span class="nav-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>
        </svg>
      </span>
      Consultation History
    </a>
  </div>
</nav>

<div class="sidebar-footer">
  <div class="sidebar-user">
    <div class="sidebar-user-avatar" id="sidebarUserAvatar">D</div>
    <div class="sidebar-user-info">
      <div class="sidebar-user-name" id="sidebarUserName">Doctor</div>
      <div class="sidebar-user-role">Doctor</div>
    </div>
  </div>
  <div style="padding:10px 16px 0; font-size:11px; letter-spacing:.02em; color:rgba(226,238,255,.45);">HealthCare · by Gokul Rathod</div>
  <a href="${p}login.html" class="nav-item" id="logoutBtn" style="color:var(--red-600); margin-top:4px;">
    <span class="nav-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>
      </svg>
    </span>
    Logout
  </a>
</div>`;
}

/* ── Topbar HTML ──────────────────────────────────────────── */
function buildTopbar(title, subtitle) {
  const p = _prefix();
  return `
  <button class="mobile-menu-btn" id="mobileMenuBtn">
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/>
      <line x1="4" x2="20" y1="18" y2="18"/>
    </svg>
  </button>
  <div class="topbar-left">
    <div>
      <div class="topbar-title">${title}</div>
      ${subtitle ? `<div class="topbar-breadcrumb"><a href="${p}dashboard.html">Dashboard</a><span>›</span><span>${subtitle}</span></div>` : ''}
    </div>
  </div>
  <div class="topbar-right">
    <div class="topbar-date" id="topbarDate"></div>
    <button class="topbar-btn" id="themeToggleBtn" title="Toggle dark mode">
      <svg class="theme-icon-moon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
           fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
      </svg>
      <svg class="theme-icon-sun" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
           fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>
        <path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>
      </svg>
    </button>
    <div class="topbar-notif-wrap">
      <button class="topbar-btn" id="topbarNotifBtn" title="Notifications" aria-label="Notifications" aria-haspopup="true" aria-expanded="false">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>
        </svg>
        <span class="dot"></span>
      </button>
    </div>
    <button class="topbar-btn" id="topbarSettingsBtn" title="Settings">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
           fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
    </button>
  </div>`;
}

/* ── App init ─────────────────────────────────────────────── */
function initApp(opts = {}) {
  const { page = '', title = 'Dashboard', subtitle = '' } = opts;

  /* Auth guard */
  if (!localStorage.getItem('hms_token') && !sessionStorage.getItem('hms_token')) {
    window.location.href = resolveRoot('login.html');
    return;
  }

  /* Role guard: each role stays in its own area — patients in the
     patient panel, doctors in the doctor panel, admins in the admin
     app. No role stored yet (e.g. an old session) means patient —
     the safe default is patient, never admin. Note: '/doctor/' does
     not match the admin '/doctors/' module folder (the "s" breaks
     the match), so the two areas stay distinct. */
  const _role = localStorage.getItem('hms_role') || sessionStorage.getItem('hms_role') || 'patient';
  const _inPatientArea = window.location.pathname.includes('/patient/');
  const _inDoctorArea = window.location.pathname.includes('/doctor/');
  const _homeFor = { patient: 'patient/my-appointments.html', doctor: 'doctor/my-appointments.html', admin: 'dashboard.html' };
  const _home = _homeFor[_role] || _homeFor.patient;
  const _inOwnArea = (_role === 'patient' && _inPatientArea)
    || (_role === 'doctor' && _inDoctorArea)
    || (_role === 'admin' && !_inPatientArea && !_inDoctorArea);
  if (!_inOwnArea) {
    window.location.href = resolveRoot(_home);
    return;
  }

  /* Inject sidebar overlay */
  const overlay = document.createElement('div');
  overlay.className = 'sidebar-overlay';
  overlay.id = 'sidebarOverlay';
  document.body.prepend(overlay);

  /* Inject sidebar */
  let sidebar = document.querySelector('.sidebar');
  if (!sidebar) {
    sidebar = document.createElement('aside');
    sidebar.className = 'sidebar';
    document.body.prepend(sidebar);
  }
  sidebar.innerHTML = _role === 'patient' ? buildPatientSidebarHTML()
    : _role === 'doctor' ? buildDoctorSidebarHTML() : buildSidebarHTML();

  /* Inject topbar */
  let topbar = document.querySelector('.topbar');
  if (!topbar) {
    topbar = document.createElement('header');
    topbar.className = 'topbar';
    document.body.prepend(topbar);
  }
  topbar.innerHTML = buildTopbar(title, subtitle);

  /* Inject toast container */
  if (!document.getElementById('toast-container')) {
    const tc = document.createElement('div');
    tc.id = 'toast-container';
    document.body.appendChild(tc);
  }

  /* Active nav item — resolve paths to filename */
  const filename = window.location.pathname.split('/').pop().replace('.html','');
  const active = sidebar.querySelector(`[data-page="${filename}"]`)
               || sidebar.querySelector(`[data-page="${page}"]`);
  if (active) active.classList.add('active');

  /* User display */
  const u = localStorage.getItem('hms_user') || sessionStorage.getItem('hms_user') || 'Admin';
  const el = document.getElementById('sidebarUserName');
  if (el) el.textContent = u;
  const av = document.getElementById('sidebarUserAvatar');
  if (av) av.textContent = u[0].toUpperCase();

  /* Logout: end the Cognito session too, then drop the local copy. */
  document.getElementById('logoutBtn')?.addEventListener('click', () => {
    if (typeof AuthAPI !== 'undefined' && AuthAPI.signOut) {
      try { AuthAPI.signOut(); } catch (e) {}
    }
    localStorage.removeItem('hms_token');
    localStorage.removeItem('hms_user');
    localStorage.removeItem('hms_role');
    sessionStorage.removeItem('hms_token');
    sessionStorage.removeItem('hms_user');
    sessionStorage.removeItem('hms_role');
  });

  /* Mobile toggle */
  document.getElementById('mobileMenuBtn')?.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
  });
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
  });

  /* Desktop sidebar collapse (persisted) */
  const applyCollapsed = (c) => {
    document.body.classList.toggle('sidebar-collapsed', c);
    sidebar.classList.toggle('collapsed', c);
  };
  let collapsed = false;
  try { collapsed = localStorage.getItem('hms_sidebar_collapsed') === '1'; } catch (e) {}
  applyCollapsed(collapsed);
  document.getElementById('sidebarCollapseBtn')?.addEventListener('click', () => {
    collapsed = !collapsed;
    applyCollapsed(collapsed);
    try { localStorage.setItem('hms_sidebar_collapsed', collapsed ? '1' : '0'); } catch (e) {}
  });

  /* Topbar settings shortcut */
  document.getElementById('topbarSettingsBtn')?.addEventListener('click', () => {
    window.location.href = resolveRoot('settings.html');
  });

  /* Dark mode toggle */
  document.getElementById('themeToggleBtn')?.addEventListener('click', toggleTheme);

  /* Notification bell + dropdown (live data, best-effort) */
  _initNotifBell();

  /* Date */
  const dateEl = document.getElementById('topbarDate');
  if (dateEl) {
    dateEl.textContent = new Date().toLocaleDateString('en-IN', {
      weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
    });
  }
}

/* ── Notifications (topbar bell) ──────────────────────────────
   The bell opens a dropdown fed by LIVE API data only — no mock or
   hardcoded items. Patient: upcoming Confirmed/Scheduled appointments
   + Pending bills. Doctor: upcoming Confirmed/Scheduled appointments
   with the patient name — a "New" badge for appointments assigned
   since the doctor last opened the bell, and a red "Waiting" item
   (linking straight into the video call) when the patient has
   joined the room; the doctor panel polls every 30 seconds so
   both appear without a page refresh. Admin: pending dues + pending
   lab orders + low-stock medicines. Opening the dropdown marks everything read
   (localStorage 'hms_notif_read_at'); the red dot only shows while
   unread items exist. Every fetch is best-effort: a failed fetch shows
   a short line in the dropdown and never breaks the page.
   NOTE on item dates: the enriched GET /assignments/patient/{pid}
   rows carry no created_at, so an appointment's item date IS its
   appointment_date — the dot returns on the next page load while an
   appointment is still upcoming, and hides once it passes or is no
   longer Confirmed/Scheduled. Bills/dues/orders use their creation
   dates, so marking them read sticks until a new one appears.
   Low-stock items have no date (they are a live condition), so they
   count as new while the stock is low. */
const NOTIF_READ_KEY = 'hms_notif_read_at';
const NOTIF_MAX_ITEMS = 6;
/* Doctor "new appointment" tracking: assignment ids the doctor has
   already seen (localStorage 'hms_notif_seen_assignments'). An
   assignment whose id is not in the list is "New" and shows a badge
   + the red dot. Opening the bell marks every current assignment
   seen. On the very first run the list is seeded with the current
   ids, so existing appointments don't all flood in as "New". */
const NOTIF_SEEN_ASSIGNMENTS_KEY = 'hms_notif_seen_assignments';
const NOTIF_WAITING_MAX_AGE_MS = 60 * 60 * 1000; /* a waiting patient counts for 60 minutes */
const NOTIF_POLL_MS = 10000; /* doctor panel only: re-check every 10 seconds, so a waiting patient pops up fast */

function _notifSeenAssignments() {
  try {
    const v = JSON.parse(localStorage.getItem(NOTIF_SEEN_ASSIGNMENTS_KEY) || '[]');
    return Array.isArray(v) ? v.map(Number).filter(n => !isNaN(n)) : [];
  } catch (e) { return []; }
}
function _notifHasSeenList() {
  try { return localStorage.getItem(NOTIF_SEEN_ASSIGNMENTS_KEY) !== null; } catch (e) { return false; }
}
function _notifMarkAssignmentsSeen(ids) {
  try {
    const seen = new Set(_notifSeenAssignments());
    (ids || []).forEach(id => seen.add(Number(id)));
    localStorage.setItem(NOTIF_SEEN_ASSIGNMENTS_KEY, JSON.stringify(Array.from(seen).slice(-200)));
  } catch (e) {}
}

/* Doctor "confirmed" tracking: the last status the doctor saw for
   each assignment (localStorage 'hms_notif_seen_status', an object
   {id: status}). The id-only list above cannot tell a confirm apart
   from an already-seen appointment — so when an assignment the
   doctor already saw changes TO "Confirmed" (the patient confirmed
   it), the bell shows a "Confirmed" badge + red dot. On the very
   first run the map is seeded with the current statuses, so
   already-confirmed appointments don't all flood in as new. */
const NOTIF_SEEN_STATUS_KEY = 'hms_notif_seen_status';

function _notifSeenStatus() {
  try {
    const v = JSON.parse(localStorage.getItem(NOTIF_SEEN_STATUS_KEY) || '{}');
    return (v && typeof v === 'object' && !Array.isArray(v)) ? v : {};
  } catch (e) { return {}; }
}
function _notifHasSeenStatus() {
  try { return localStorage.getItem(NOTIF_SEEN_STATUS_KEY) !== null; } catch (e) { return false; }
}
function _notifMarkStatusSeen(rows) {
  try {
    const map = _notifSeenStatus();
    (rows || []).forEach(a => { map[String(a.assignment_id)] = a.status || ''; });
    const pruned = {};
    Object.keys(map).slice(-200).forEach(k => { pruned[k] = map[k]; });
    localStorage.setItem(NOTIF_SEEN_STATUS_KEY, JSON.stringify(pruned));
  } catch (e) {}
}

function _notifReadAt() {
  try {
    const v = parseInt(localStorage.getItem(NOTIF_READ_KEY) || '0', 10);
    return isNaN(v) ? 0 : v;
  } catch (e) { return 0; }
}
function _notifMarkRead() {
  try { localStorage.setItem(NOTIF_READ_KEY, String(Date.now())); } catch (e) {}
}
function _notifEscape(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function _notifFmtDate(d) {
  if (!d) return '';
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return String(d);
  return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
function _notifFmtDateTime(d) {
  if (!d) return '';
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return String(d);
  return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
    + ', ' + dt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
}
function _notifTs(d) {
  const t = new Date(d).getTime();
  return isNaN(t) ? 0 : t;
}
function _notifRole() {
  return localStorage.getItem('hms_role') || sessionStorage.getItem('hms_role') || 'patient';
}

/* Patient items: upcoming Confirmed/Scheduled appointments + Pending
   bills. PID is resolved exactly like patient/my-appointments.html:
   cached sessionStorage 'hms_pid', else PatientsAPI.byEmail(getMyEmail()). */
async function _notifPatientItems() {
  if (typeof PatientsAPI === 'undefined' || typeof DoctorsAPI === 'undefined' || typeof BillingAPI === 'undefined')
    return { items: [], failed: true };
  let pid = null;
  try { const c = sessionStorage.getItem('hms_pid'); if (c) pid = parseInt(c, 10); } catch (e) {}
  if (!pid) {
    const email = (typeof getMyEmail === 'function') ? getMyEmail() : '';
    if (!email) return { items: [], failed: false };
    const res = await PatientsAPI.byEmail(email);
    if (res && res.patient) {
      pid = res.patient.patient_id;
      try { sessionStorage.setItem('hms_pid', String(pid)); } catch (e) {}
    }
  }
  if (!pid) return { items: [], failed: false }; /* no patient profile yet */
  const [aRes, bRes] = await Promise.all([DoctorsAPI.forPatient(pid), BillingAPI.billsFor(pid)]);
  if (!aRes && !bRes) return { items: [], failed: true };
  const items = [];
  ((aRes && aRes.assignments) || [])
    .filter(a => a.status === 'Confirmed' || a.status === 'Scheduled')
    .forEach(a => {
      const when = _notifFmtDateTime(a.appointment_date);
      items.push({
        color: a.status === 'Confirmed' ? 'var(--green-500)' : 'var(--blue-500)',
        text: `Appointment #${a.assignment_id} with ${a.doctor_name || 'Doctor'}${when ? ' — ' + when : ''}`,
        time: a.room_number ? `${a.status} · Room ${a.room_number}` : (a.status || ''),
        ts: _notifTs(a.appointment_date),
        href: resolveRoot('patient/my-appointments.html'),
      });
    });
  ((bRes && bRes.bills) || [])
    .filter(b => b.status === 'Pending')
    .forEach(b => {
      const amt = b.net_amount != null ? b.net_amount : b.amount;
      items.push({
        color: 'var(--amber-500)',
        text: `Bill #${b.bill_id} — ₹${Number(amt || 0).toLocaleString('en-IN')} pending`,
        time: _notifFmtDate(b.bill_date),
        ts: _notifTs(b.bill_date),
        href: resolveRoot('patient/my-appointments.html'),
      });
    });
  return { items, failed: false };
}

/* Doctor items — THREE live notification types:
   (1) NEW APPOINTMENT ASSIGNED: an assignment whose id is not in
   the seen list shows with a "New" badge (the first run seeds the
   list, so old appointments don't flood in as new).
   (2) APPOINTMENT CONFIRMED: an assignment the doctor already saw
   whose status changed TO "Confirmed" (the patient confirmed it)
   shows with a green "Confirmed" badge. The id-only seen list
   cannot tell this apart from an already-seen appointment, so the
   last-seen status per assignment is tracked separately
   (localStorage 'hms_notif_seen_status'); the first run seeds it
   with the current statuses.
   (3) PATIENT WAITING FOR VIDEO CALL: a Confirmed appointment
   whose patient_waiting_at is set and less than 60 minutes old
   shows first, in red, with a "Waiting" badge and a one-click
   link straight into the video call. The flag is set by the
   patient's video-call page on join and cleared when the doctor
   joins or the call ends (see video-call.js).
   DID + doctor name are resolved exactly like the doctor panel:
   cached sessionStorage 'hms_did', else DoctorsAPI.byEmail(getMyEmail()).
   Returns { items, failed, unread, assignmentIds, assignmentRows } —
   unread drives the red dot (any New, Confirmed or Waiting item);
   assignmentIds/assignmentRows let the bell mark everything seen
   (ids + statuses) when the doctor opens it. */
async function _notifDoctorItems() {
  if (typeof DoctorsAPI === 'undefined')
    return { items: [], failed: true };
  let did = null;
  let doctorName = '';
  try { const c = sessionStorage.getItem('hms_did'); if (c) did = parseInt(c, 10); } catch (e) {}
  try { doctorName = sessionStorage.getItem('hms_doctor_name') || ''; } catch (e) {}
  if (!did) {
    const email = (typeof getMyEmail === 'function') ? getMyEmail() : '';
    if (!email) return { items: [], failed: false };
    const res = await DoctorsAPI.byEmail(email);
    if (res && res.doctor) {
      did = res.doctor.doctor_id;
      doctorName = [res.doctor.first_name, res.doctor.last_name].filter(Boolean).join(' ');
      try { sessionStorage.setItem('hms_did', String(did)); } catch (e) {}
      try { sessionStorage.setItem('hms_doctor_name', doctorName); } catch (e) {}
    }
  }
  if (!did) return { items: [], failed: false }; /* no doctor profile yet */
  const aRes = await DoctorsAPI.forDoctor(did);
  if (!aRes) return { items: [], failed: true };
  const rows = (aRes && aRes.assignments) || [];
  const assignmentIds = rows.map(a => a.assignment_id);
  /* First run: seed the seen list with what already exists, so
     only appointments assigned AFTER this count as "New". The seed
     must happen BEFORE the set is built, or the first run floods
     every existing appointment in as "New". */
  if (!_notifHasSeenList()) _notifMarkAssignmentsSeen(assignmentIds);
  if (!_notifHasSeenStatus()) _notifMarkStatusSeen(rows);
  const seen = new Set(_notifSeenAssignments());
  const seenStatus = _notifSeenStatus();
  const items = [];
  rows
    .filter(a => a.status === 'Confirmed' || a.status === 'Scheduled')
    .forEach(a => {
      const when = _notifFmtDateTime(a.appointment_date);
      const waitingTs = _notifTs(a.patient_waiting_at);
      const isWaiting = a.status === 'Confirmed' && waitingTs > 0
        && (Date.now() - waitingTs) <= NOTIF_WAITING_MAX_AGE_MS;
      if (isWaiting) {
        const callUrl = resolveRoot('video-call.html')
          + '?assignment_id=' + a.assignment_id
          + '&role=doctor&doctor_name=' + encodeURIComponent(doctorName || '')
          + '&appointment_date=' + encodeURIComponent(a.appointment_date || '');
        items.push({
          color: 'var(--red-500)',
          badge: 'Waiting',
          badgeKind: 'waiting',
          isNew: true,
          assignmentId: a.assignment_id,
          patientName: a.patient_name || 'Patient',
          text: `Patient ${a.patient_name || 'Patient'} is waiting for the video call — Appointment #${a.assignment_id}`,
          time: `Waiting since ${_notifFmtDateTime(a.patient_waiting_at)} · Join now`,
          ts: waitingTs,
          href: callUrl,
        });
        return;
      }
      const isNew = !seen.has(Number(a.assignment_id));
      /* The patient confirmed it after the doctor last looked:
         the doctor saw this assignment before, its last-seen status
         was not Confirmed, and now it is. */
      const prevStatus = seenStatus[String(a.assignment_id)];
      const justConfirmed = !isNew && prevStatus && prevStatus !== 'Confirmed' && a.status === 'Confirmed';
      items.push({
        color: a.status === 'Confirmed' ? 'var(--green-500)' : 'var(--blue-500)',
        badge: justConfirmed ? 'Confirmed' : (isNew ? 'New' : ''),
        badgeKind: justConfirmed ? 'confirmed' : (isNew ? 'new' : ''),
        isNew: justConfirmed || isNew,
        text: justConfirmed
          ? `Patient ${a.patient_name || 'Patient'} confirmed Appointment #${a.assignment_id}${when ? ' — ' + when : ''}`
          : `Appointment #${a.assignment_id} with ${a.patient_name || 'Patient'}${when ? ' — ' + when : ''}`,
        time: a.status || '',
        ts: _notifTs(a.appointment_date),
        href: resolveRoot('doctor/my-appointments.html'),
      });
    });
  return { items, failed: false, unread: items.some(it => it.isNew), assignmentIds, assignmentRows: rows };
}

/* Admin items: pending dues + pending lab orders + low-stock medicines.
   Only endpoints that exist in js/api.js are used. */
async function _notifAdminItems() {
  if (typeof BillingAPI === 'undefined' || typeof LabAPI === 'undefined' || typeof PharmacyAPI === 'undefined')
    return { items: [], failed: true };
  const [duesRes, labRes, stockRes] = await Promise.all([
    BillingAPI.dues(), LabAPI.pending(), PharmacyAPI.lowStock(),
  ]);
  if (!duesRes && !labRes && !stockRes) return { items: [], failed: true };
  const items = [];
  ((duesRes && duesRes.dues) || []).forEach(d => {
    const amt = d.due_amount != null ? d.due_amount : d.net_amount;
    items.push({
      color: 'var(--red-500)',
      text: `₹${Number(amt || 0).toLocaleString('en-IN')} due — ${d.patient_name || 'Patient'} (Bill #${d.bill_id})`,
      time: _notifFmtDate(d.bill_date),
      ts: _notifTs(d.bill_date),
      href: resolveRoot('billing/pending-dues.html'),
    });
  });
  ((labRes && labRes.orders) || []).forEach(o => {
    items.push({
      color: 'var(--purple-500)',
      text: `Lab order #${o.order_id} — ${o.test_name || 'Test'} (${o.patient_name || 'Patient'})`,
      time: _notifFmtDate(o.order_date),
      ts: _notifTs(o.order_date),
      href: resolveRoot('laboratory/lab-orders.html'),
    });
  });
  ((stockRes && stockRes.medicines) || []).forEach(m => {
    items.push({
      color: 'var(--amber-500)',
      text: `Low stock — ${m.medicine_name} (${m.stock_quantity} left)`,
      time: (m.reorder_level != null) ? `Reorder level: ${m.reorder_level}` : '',
      ts: Date.now(),
      href: resolveRoot('pharmacy/medicine-catalog.html'),
    });
  });
  return { items, failed: false };
}

async function _notifFetchItems() {
  try {
    const role = _notifRole();
    if (role === 'patient') return await _notifPatientItems();
    if (role === 'doctor') return await _notifDoctorItems();
    return await _notifAdminItems();
  } catch (e) {
    return { items: [], failed: true };
  }
}

function _notifRenderList(dd, result) {
  const list = dd.querySelector('.notif-list');
  if (!list) return;
  if (result.failed) {
    list.innerHTML = `<div class="notif-empty">Couldn't load notifications</div>`;
    return;
  }
  const items = (result.items || []).slice()
    .sort((a, b) => b.ts - a.ts)
    .slice(0, NOTIF_MAX_ITEMS);
  if (!items.length) {
    list.innerHTML = `<div class="notif-empty">No new notifications</div>`;
    return;
  }
  list.innerHTML = items.map(it => `
    <a class="notification-item" href="${_notifEscape(it.href)}">
      <div class="notif-dot-wrap"><div class="notif-dot" style="background:${it.color}"></div></div>
      <div class="notif-body">
        <div class="notif-text">${_notifEscape(it.text)}${it.badge ? ` <span class="notif-badge notif-badge-${it.badgeKind || 'new'}">${_notifEscape(it.badge)}</span>` : ''}</div>
        ${it.time ? `<div class="notif-time">${_notifEscape(it.time)}</div>` : ''}
      </div>
    </a>`).join('');
}

function _notifSetDot(show) {
  const btn = document.getElementById('topbarNotifBtn');
  const dot = btn && btn.querySelector('.dot');
  if (dot) dot.style.display = show ? '' : 'none';
}
function _notifSetBellExpanded(open) {
  const btn = document.getElementById('topbarNotifBtn');
  if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}
function _notifClose() {
  const dd = document.getElementById('notifDropdown');
  if (dd) dd.hidden = true;
  _notifSetBellExpanded(false);
}
async function _notifToggle() {
  const dd = document.getElementById('notifDropdown');
  if (!dd) return;
  if (!dd.hidden) { _notifClose(); return; }
  dd.hidden = false;
  _notifSetBellExpanded(true);
  const list = dd.querySelector('.notif-list');
  if (list) list.innerHTML = `<div class="notif-empty">Loading…</div>`;
  const result = await _notifFetchItems();
  if (dd.hidden) return; /* closed while loading — don't reopen it */
  _notifRenderList(dd, result);
  if (!result.failed) {
    _notifMarkRead(); _notifSetDot(false);
    /* Doctor: opening the bell marks every current appointment
       seen (ids + statuses), so "New" and "Confirmed" badges clear
       until the next new one arrives or another confirm happens. */
    if (result.assignmentIds) _notifMarkAssignmentsSeen(result.assignmentIds);
    if (result.assignmentRows) _notifMarkStatusSeen(result.assignmentRows);
  }
}

/* Background dot state — never blocks the page. A failed fetch leaves
   the dot as-is (visible by default, so the user can still open it). */
function _notifRefreshDot() {
  return _notifFetchItems().then(result => {
    if (result.failed) return;
    const items = result.items || [];
    const readAt = _notifReadAt();
    /* The doctor branch reports unread directly (any New or
       Waiting item); patient/admin keep the read-timestamp rule. */
    const unread = (typeof result.unread === 'boolean')
      ? result.unread
      : (items.length > 0 && (readAt <= 0 || items.some(it => it.ts > readAt)));
    _notifSetDot(unread);
    _notifShowIncomingCall(result);
  }).catch(() => {});
}

/* Doctor "incoming call" popup: a waiting patient is easy to miss
   as a small red dot on the bell. When the load-time check or the
   30-second poll finds a patient waiting for the video call, show a
   prominent modal — "Incoming Video Call" with the patient, the
   appointment and a Join button — so the doctor cannot miss that a
   call is coming. Shown once per waiting appointment per browser
   session (a dismissed call does not pop up again); a different
   waiting patient pops up again. Never shows while the doctor is
   already on the video-call page. */
const NOTIF_INCOMING_KEY = 'hms_incoming_shown';
const NOTIF_RINGTONE_KEY = 'hms_ringtone_muted';

/* ── Incoming-call ringtone (Web Audio API, no audio file) ────
   A soft two-tone ring that repeats while the incoming-call popup
   is on screen, so the doctor hears the call coming — not just a
   red dot. Best-effort: if the browser blocks audio (autoplay
   policy) it fails silently and the popup still works visually.
   The doctor can mute it; the choice persists in localStorage. */
let _ringCtx = null, _ringTimer = null, _ringMuted = false;
try { _ringMuted = localStorage.getItem(NOTIF_RINGTONE_KEY) === '1'; } catch (e) {}
function _ringtoneMuted() { return _ringMuted; }
function _setRingtoneMuted(m) {
  _ringMuted = !!m;
  try { localStorage.setItem(NOTIF_RINGTONE_KEY, _ringMuted ? '1' : '0'); } catch (e) {}
  if (_ringMuted) _stopRingtone(); else _startRingtone();
}
function _ringBeep(freq, when, dur) {
  try {
    const o = _ringCtx.createOscillator(), g = _ringCtx.createGain();
    o.type = 'sine'; o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, when);
    g.gain.exponentialRampToValueAtTime(0.18, when + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    o.connect(g); g.connect(_ringCtx.destination);
    o.start(when); o.stop(when + dur + 0.05);
  } catch (e) {}
}
function _startRingtone() {
  if (_ringMuted || _ringTimer) return;
  try {
    if (!_ringCtx) _ringCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (_ringCtx.state === 'suspended') _ringCtx.resume();
    const ringOnce = function () {
      if (!_ringCtx) return;
      const t = _ringCtx.currentTime + 0.05;
      _ringBeep(880, t, 0.28); _ringBeep(880, t + 0.35, 0.28);
      _ringBeep(1174, t + 0.9, 0.28); _ringBeep(1174, t + 1.25, 0.28);
    };
    ringOnce();
    _ringTimer = setInterval(ringOnce, 2200);
  } catch (e) { /* audio blocked — popup still works */ }
}
function _stopRingtone() {
  if (_ringTimer) { clearInterval(_ringTimer); _ringTimer = null; }
}

/* Live "Waiting since" timer for the incoming-call popup: counts
   up from the moment the patient started waiting. Cleared when
   the popup is hidden. */
let _incomingTimer = null;
function _stopIncomingTimer() {
  if (_incomingTimer) { clearInterval(_incomingTimer); _incomingTimer = null; }
}
function _fmtElapsed(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60), r = s % 60;
  return (m < 10 ? '0' + m : '' + m) + ':' + (r < 10 ? '0' + r : '' + r);
}
function _initials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function _notifIncomingShown() {
  try {
    const v = JSON.parse(sessionStorage.getItem(NOTIF_INCOMING_KEY) || '[]');
    return new Set(Array.isArray(v) ? v.map(Number).filter(n => !isNaN(n)) : []);
  } catch (e) { return new Set(); }
}
function _notifMarkIncomingShown(id) {
  try {
    const s = _notifIncomingShown();
    s.add(Number(id));
    sessionStorage.setItem(NOTIF_INCOMING_KEY, JSON.stringify(Array.from(s).slice(-20)));
  } catch (e) {}
}
function _notifHideIncomingCall() {
  _stopRingtone();
  _stopIncomingTimer();
  const m = document.getElementById('incomingCallModal');
  if (m) m.hidden = true;
}
function _notifShowIncomingCall(result) {
  if (_notifRole() !== 'doctor') return;
  if (typeof location !== 'undefined' && String(location.pathname || '').indexOf('video-call') !== -1) return;
  const items = (result && result.items) || [];
  /* First waiting patient not shown yet — if several patients wait
     at once, a dismissed one must not hide the next one. */
  const shown = _notifIncomingShown();
  const waiting = items.find(it => it.badgeKind === 'waiting' && it.assignmentId && !shown.has(Number(it.assignmentId)));
  if (!waiting) return;
  _notifMarkIncomingShown(waiting.assignmentId);
  let modal = document.getElementById('incomingCallModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'incomingCallModal';
    modal.className = 'incoming-call-modal';
    modal.hidden = true;
    document.body.appendChild(modal);
  }
  const patientName = waiting.patientName || 'Patient';
  const waitingTs = waiting.ts || Date.now();
  const sinceText = waiting.time ? waiting.time.replace(/ · Join now$/, '') : '';
  modal.innerHTML = `
    <div class="incoming-call-card">
      <button type="button" class="incoming-call-mute" id="incomingCallMute" title="Ringtone on/off">${_ringtoneMuted() ? '🔇' : '🔔'}</button>
      <div class="incoming-call-avatar">${_notifEscape(_initials(patientName))}</div>
      <div class="incoming-call-title">Incoming Video Call</div>
      <div class="incoming-call-name">${_notifEscape(patientName)}</div>
      <div class="incoming-call-text">Appointment #${_notifEscape(waiting.assignmentId)} — is waiting for the video call</div>
      <div class="incoming-call-time">${_notifEscape(sinceText)} · <span id="incomingCallElapsed">00:00</span></div>
      <div class="incoming-call-actions">
        <a class="btn btn-primary" href="${_notifEscape(waiting.href)}" id="incomingCallJoin">Join Video Call</a>
        <button type="button" class="btn" id="incomingCallDismiss">Dismiss</button>
      </div>
    </div>`;
  const dismiss = modal.querySelector('#incomingCallDismiss');
  if (dismiss) dismiss.addEventListener('click', _notifHideIncomingCall);
  const join = modal.querySelector('#incomingCallJoin');
  if (join) join.addEventListener('click', function () { _stopRingtone(); _stopIncomingTimer(); });
  const mute = modal.querySelector('#incomingCallMute');
  if (mute) mute.addEventListener('click', function () {
    _setRingtoneMuted(!_ringtoneMuted());
    mute.textContent = _ringtoneMuted() ? '🔇' : '🔔';
  });
  /* Live "Waiting since" timer — counts up from when the patient
     started waiting. */
  _stopIncomingTimer();
  const tick = function () {
    const el = document.getElementById('incomingCallElapsed');
    if (el) el.textContent = _fmtElapsed(Date.now() - waitingTs);
  };
  tick();
  _incomingTimer = setInterval(tick, 1000);
  _startRingtone();
  modal.hidden = false;
}

function _initNotifBell() {
  const btn = document.getElementById('topbarNotifBtn');
  if (!btn) return;
  /* Inject the dropdown panel once, anchored under the bell. */
  let dd = document.getElementById('notifDropdown');
  if (!dd) {
    dd = document.createElement('div');
    dd.id = 'notifDropdown';
    dd.className = 'notif-dropdown';
    dd.hidden = true;
    dd.innerHTML = `<div class="notif-dropdown-header">Notifications</div><div class="notif-list"></div>`;
    const wrap = btn.closest('.topbar-notif-wrap') || btn.parentElement;
    (wrap || document.body).appendChild(dd);
  }
  /* Doctor panel only: poll every 30 seconds so a new appointment
     or a waiting patient shows up without a page refresh (the red
     dot and the open dropdown both refresh). Patient/admin
     behaviour is unchanged — one fetch on load. Guarded so a
     topbar re-render never starts a second interval. */
  if (_notifRole() === 'doctor' && !window._notifPollId) {
    window._notifPollId = setInterval(function () {
      _notifRefreshDot();
      const openDd = document.getElementById('notifDropdown');
      if (openDd && !openDd.hidden) {
        _notifFetchItems().then(function (result) {
          const panel = document.getElementById('notifDropdown');
          if (!panel || panel.hidden || result.failed) return;
          _notifRenderList(panel, result);
        }).catch(function () {});
      }
    }, NOTIF_POLL_MS);
  }
  btn.addEventListener('click', (e) => { e.stopPropagation(); _notifToggle(); });
  /* Close when clicking anywhere outside the panel (or pressing Escape).
     Attached once — initApp may run again after a topbar re-render. */
  if (!window._notifDocWired) {
    window._notifDocWired = true;
    document.addEventListener('click', (e) => {
      const panel = document.getElementById('notifDropdown');
      if (!panel || panel.hidden) return;
      if (e.target.closest('#notifDropdown') || e.target.closest('#topbarNotifBtn')) return;
      _notifClose();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') _notifClose();
    });
  }
  _notifRefreshDot();
}

/* ── Resolve root path (works from sub-dirs) ──────────────── */
function resolveRoot(path) {
  return _prefix() + path;
}

/* ── Toast notification ───────────────────────────────────── */
function showToast(msg, type = 'info', title = null) {
  const icons = {
    success: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
    error:   `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" x2="6" y1="6" y2="18"/><line x1="6" x2="18" y1="6" y2="18"/></svg>`,
    warning: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
    info:    `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
  };
  const titles = { success: 'Success', error: 'Error', warning: 'Warning', info: 'Info' };

  let tc = document.getElementById('toast-container');
  if (!tc) {
    tc = document.createElement('div');
    tc.id = 'toast-container';
    document.body.appendChild(tc);
  }

  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `
    <div class="toast-icon">${icons[type] || icons.info}</div>
    <div class="toast-body">
      <div class="toast-title">${title || titles[type]}</div>
      <div class="toast-msg">${msg}</div>
    </div>`;
  tc.appendChild(t);

  setTimeout(() => {
    t.classList.add('removing');
    setTimeout(() => t.remove(), 350);
  }, 3800);
}

/* ── Confirm dialog ───────────────────────────────────────── */
function confirmDialog(opts = {}) {
  const {
    title   = 'Are you sure?',
    message = 'This action cannot be undone.',
    confirmText = 'Confirm',
    cancelText  = 'Cancel',
    type = 'danger'
  } = opts;

  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay show';
    overlay.innerHTML = `
      <div class="modal modal-sm fade-in">
        <div class="modal-body" style="padding-top:32px;">
          <div class="confirm-modal-icon ${type}">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
                 fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
              <path d="M12 9v4"/><path d="M12 17h.01"/>
            </svg>
          </div>
          <div class="confirm-modal-title">${title}</div>
          <div class="confirm-modal-text">${message}</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline btn-sm" id="confirmCancel">${cancelText}</button>
          <button class="btn btn-danger btn-sm" id="confirmOk">${confirmText}</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    overlay.querySelector('#confirmCancel').addEventListener('click', () => {
      overlay.remove(); resolve(false);
    });
    overlay.querySelector('#confirmOk').addEventListener('click', () => {
      overlay.remove(); resolve(true);
    });
  });
}

/* ── Avatar initials helper ───────────────────────────────── */
function initials(name) {
  return (name || '?').split(' ').slice(0,2).map(w => w[0]).join('').toUpperCase();
}

/* ── Format currency ──────────────────────────────────────── */
function formatCurrency(n) {
  return '₹' + Number(n || 0).toLocaleString('en-IN');
}

/* ── Format date ──────────────────────────────────────────── */
function formatDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' });
}

/* ── Skeleton rows ────────────────────────────────────────── */
function skeletonRows(cols, count = 5) {
  return Array.from({ length: count }, () =>
    `<tr>${Array.from({ length: cols }, () =>
      `<td><div class="skeleton skeleton-text" style="width:${60+Math.random()*30}%"></div></td>`
    ).join('')}</tr>`
  ).join('');
}

/* ── Status badge helper ──────────────────────────────────── */
function statusBadge(status) {
  const map = {
    'Paid':             'badge-success',
    'Confirmed':         'badge-success',
    'Active':           'badge-success',
    'Available':        'badge-success',
    'Recovered':        'badge-success',
    'Partial':          'badge-warning',
    'Scheduled':        'badge-info',
    'Under Treatment':  'badge-info',
    'Pending':          'badge-danger',
    'Busy':             'badge-warning',
    'On Leave':         'badge-gray',
    'Chronic':          'badge-purple',
    'Mild':             'badge-teal',
    'Moderate':         'badge-warning',
    'Severe':           'badge-danger',
    'Ordered':          'badge-info',
    'Sample Collected': 'badge-warning',
    'Processing':       'badge-purple',
    'Completed':        'badge-success',
    'Cancelled':        'badge-danger',
    'Routine':          'badge-gray',
    'Urgent':           'badge-warning',
    'STAT':             'badge-danger',
    'Inactive':         'badge-gray',
    'Hematology':       'badge-info',
    'Biochemistry':     'badge-teal',
    'Microbiology':     'badge-purple',
    'Serology':         'badge-warning',
    'Pathology':        'badge-gray',
    'Radiology':        'badge-info',
    'Hormones':         'badge-purple',
  };
  const cls = map[status] || 'badge-gray';
  return `<span class="badge ${cls}"><span class="badge-dot"></span>${status}</span>`;
}

/* ── Pagination helper ────────────────────────────────────── */
const _paginationCbs = {};
function buildPagination(container, total, page, perPage, onPage) {
  const pages = Math.ceil(total / perPage);
  if (pages <= 1) { container.innerHTML = ''; return; }
  const start = (page - 1) * perPage + 1;
  const end   = Math.min(page * perPage, total);

  /* Store callback in registry so it's accessible from onclick */
  const cbKey = '_pagCb_' + container.id;
  window[cbKey] = onPage;

  let html = `<span class="pagination-info">Showing ${start}–${end} of ${total}</span><div class="pagination-controls">`;
  html += `<button class="page-btn" ${page===1?'disabled':''} onclick="${cbKey}(${page-1})">‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i===1 || i===pages || Math.abs(i-page)<=1)
      html += `<button class="page-btn${i===page?' active':''}" onclick="${cbKey}(${i})">${i}</button>`;
    else if (Math.abs(i-page)===2)
      html += `<span class="page-btn" style="pointer-events:none">…</span>`;
  }
  html += `<button class="page-btn" ${page===pages?'disabled':''} onclick="${cbKey}(${page+1})">›</button>`;
  html += '</div>';
  container.innerHTML = html;
}
