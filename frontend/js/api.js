/* ============================================================
   API layer — talks to AWS API Gateway which proxies to Lambdas
   Update API_BASE_URL with your deployed API Gateway URL.
   ============================================================ */

const API_BASE_URL = window.HMS_CONFIG?.apiBase ||
  (() => { try { return localStorage.getItem("hms_api_base"); } catch (e) { return null; } })() ||
  "https://cbtlt9vvfi.execute-api.us-east-1.amazonaws.com/prod";

/** Simple JWT-like token stored in localStorage after login.
    Since the Cognito migration the token is the Cognito ID token
    (RS256, issued by the user pool); getToken/setToken/clearToken
    are unchanged, so every page keeps working as before. */
function getToken() {
  return localStorage.getItem("hms_token") || sessionStorage.getItem("hms_token") || "";
}
function setToken(t, remember = true) {
  const store = remember ? localStorage : sessionStorage;
  const other = remember ? sessionStorage : localStorage;
  other.removeItem("hms_token");
  store.setItem("hms_token", t);
}
function clearToken() {
  localStorage.removeItem("hms_token");
  sessionStorage.removeItem("hms_token");
}

/** Read a claim out of the session JWT (client-side only, for
    routing/display — the server re-verifies the signature). */
function _tokenPayloadFrom(token) {
  try {
    const parts = (token || "").split(".");
    if (parts.length !== 3) return {};
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4)));
  } catch (e) { return {}; }
}
function _tokenPayload() {
  return _tokenPayloadFrom(getToken());
}
/** Role from a Cognito token payload: "admin" when the
    cognito:groups claim contains "Admins" or the custom:role claim
    (set by the migration Lambda) is "admin"; "doctor" when the
    groups contain "Doctors" or custom:role is "doctor" (the
    migration Lambda sets it for an email found in
    hospital-doctors). Anything else — including a token with no
    groups and no role claim — is a patient. The safe default is
    patient, never admin. */
function _roleFromPayload(p) {
  const groups = p["cognito:groups"] || [];
  if (groups.indexOf("Admins") !== -1) return "admin";
  if (groups.indexOf("Doctors") !== -1) return "doctor";
  if ((p["custom:role"] || "").toLowerCase() === "admin") return "admin";
  if ((p["custom:role"] || "").toLowerCase() === "doctor") return "doctor";
  return "patient";
}
function getMyEmail() { return _tokenPayload().email || ""; }
function getMyRole() { return _roleFromPayload(_tokenPayload()); }

/* ---------------- Cognito (amazon-cognito-identity-js, CDN) -------
   The SDK is loaded from the CDN on login.html / register.html
   before this file. The user pool id + client id come from
   js/config.js (written by Terraform on every apply). Sign-in uses
   the SDK's default SRP flow — the password is never sent in a
   form the server could replay. */
function _cognitoPool() {
  if (typeof AmazonCognitoIdentity === "undefined") return null;
  const poolId = window.HMS_CONFIG?.cognitoUserPoolId;
  const clientId = window.HMS_CONFIG?.cognitoClientId;
  if (!poolId || !clientId) return null;
  return new AmazonCognitoIdentity.CognitoUserPool({ UserPoolId: poolId, ClientId: clientId });
}
function _cognitoUser(email) {
  const pool = _cognitoPool();
  return pool ? new AmazonCognitoIdentity.CognitoUser({ Username: email, Pool: pool }) : null;
}
/** Refresh the Cognito session when the stored ID token is expired
    (or about to expire). No network call when the token is still
    fresh. Returns a Promise of the usable ID token, or "" when
    there is no session (the caller then sends no token). */
function _refreshTokenIfNeeded() {
  const current = getToken();
  if (!current) return Promise.resolve("");
  const payload = _tokenPayloadFrom(current);
  if (payload.exp && payload.exp * 1000 > Date.now() + 300000) return Promise.resolve(current);
  const pool = _cognitoPool();
  const user = pool && pool.getCurrentUser();
  if (!user) return Promise.resolve(current);
  return new Promise((resolve) => {
    user.getSession((err, session) => {
      if (err || !session || !session.isValid()) { clearToken(); resolve(""); return; }
      const fresh = session.getIdToken().getJwtToken();
      setToken(fresh, !!localStorage.getItem("hms_token"));
      resolve(fresh);
    });
  });
}

/** Central request wrapper with auth + error handling.
    options.quiet: true suppresses the error toasts — for best-effort
    background calls (e.g. the patient-waiting flag) that must never
    pop an error in front of the user. */
async function request(path, options = {}) {
  const { quiet, ...fetchOptions } = options;
  const url = `${API_BASE_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const token = await _refreshTokenIfNeeded();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const res = await fetch(url, { ...fetchOptions, headers });
    const data = await res.json();
    if (!res.ok) {
      const msg = data?.error || data?.message || `HTTP ${res.status}`;
      if (!quiet) showToast(msg, "error");
      return null;
    }
    return data;
  } catch (err) {
    // Mock data is strictly opt-in for local development (HMS_CONFIG.devMock).
    // In production a network failure is a real error: tell the user, return null.
    if (window.HMS_CONFIG?.devMock === true) {
      console.warn(`[API] ${path} failed, using mock data (devMock):`, err.message);
      return mockFallback(path, options);
    }
    console.warn(`[API] ${path} failed:`, err.message);
    if (!quiet && typeof showToast === "function") {
      try { showToast("Unable to reach the server. Please check your connection and try again.", "error"); } catch (e) {}
    }
    return null;
  }
}

/* ---------------- PATIENTS ---------------- */
const PatientsAPI = {
  list:   ()        => request("/patients"),
  get:    (id)      => request(`/patients/${id}`),
  byEmail: (email)  => request(`/patients/by-email/${encodeURIComponent(email)}`),
  create: (body)    => request("/patients",        { method: "POST",   body: JSON.stringify(body) }),
  update: (id, b)   => request(`/patients/${id}`, { method: "PUT",    body: JSON.stringify(b) }),
  remove: (id)      => request(`/patients/${id}`, { method: "DELETE" }),
};

/* ---------------- BILLING ---------------- */
const BillingAPI = {
  listBills:    ()        => request("/bills"),
  getBill:      (id)      => request(`/bills/${id}`),
  billsFor:     (pid)     => request(`/bills/patient/${pid}`),
  createBill:   (body)    => request("/bills",        { method: "POST", body: JSON.stringify(body) }),
  updateBill:   (id, b)   => request(`/bills/${id}`, { method: "PUT",  body: JSON.stringify(b) }),
  removeBill:   (id)      => request(`/bills/${id}`, { method: "DELETE" }),

  listPayments: ()        => request("/payments"),
  paymentsFor:  (pid)     => request(`/payments/patient/${pid}`),
  recordPayment:(body)    => request("/payments",     { method: "POST", body: JSON.stringify(body) }),

  dues:         ()        => request("/dues"),
};

/* ---------------- DISEASES ---------------- */
const DiseasesAPI = {
  list:    ()        => request("/diseases"),
  get:     (id)      => request(`/diseases/${id}`),
  create:  (body)    => request("/diseases",         { method: "POST",   body: JSON.stringify(body) }),
  update:  (id, b)   => request(`/diseases/${id}`,   { method: "PUT",    body: JSON.stringify(b) }),
  remove:  (id)      => request(`/diseases/${id}`,   { method: "DELETE" }),
  forPatient: (pid)  => request(`/diseases/patient/${pid}`),
  active:  ()        => request("/diseases/active"),
};

/* ---------------- DOCTORS ---------------- */
const DoctorsAPI = {
  list:           ()        => request("/doctors"),
  get:            (id)      => request(`/doctors/${id}`),
  byEmail:        (email)   => request(`/doctors/by-email/${encodeURIComponent(email)}`),
  create:         (body)    => request("/doctors",            { method: "POST",   body: JSON.stringify(body) }),
  update:         (id, b)   => request(`/doctors/${id}`,       { method: "PUT",    body: JSON.stringify(b) }),
  remove:         (id)      => request(`/doctors/${id}`,       { method: "DELETE" }),

  listAssignments:()        => request("/assignments"),
  assignment:     (id)      => request(`/assignments/${id}`),
  forDoctor:      (did)     => request(`/assignments/doctor/${did}`),
  forPatient:      (pid)     => request(`/assignments/patient/${pid}`),
  assign:         (body)    => request("/assignments",         { method: "POST",   body: JSON.stringify(body) }),
  updateAssign:   (id, b)   => request(`/assignments/${id}`,   { method: "PUT",    body: JSON.stringify(b) }),
  /* Patient-waiting flag (video call): set to an ISO timestamp when
     the patient joins the room, null to clear it. Quiet + keepalive
     so a best-effort save never toasts and still goes out when the
     tab closes. The doctor may only clear this one field on their
     own appointment; the patient may only touch their own. */
  setWaiting:     (id, ts)  => request(`/assignments/${id}`,   { method: "PUT",    body: JSON.stringify({ patient_waiting_at: ts }), quiet: true, keepalive: true }),
  removeAssign:   (id)      => request(`/assignments/${id}`,   { method: "DELETE" }),
};

/* ---------------- LABORATORY ---------------- */
const LabAPI = {
  listTests:  ()        => request("/lab/tests"),
  getTest:    (id)      => request(`/lab/tests/${id}`),
  createTest: (body)    => request("/lab/tests",        { method: "POST",   body: JSON.stringify(body) }),
  updateTest: (id, b)   => request(`/lab/tests/${id}`,  { method: "PUT",    body: JSON.stringify(b) }),
  removeTest: (id)      => request(`/lab/tests/${id}`,  { method: "DELETE" }),

  listOrders: ()        => request("/lab/orders"),
  getOrder:   (id)      => request(`/lab/orders/${id}`),
  createOrder:(body)    => request("/lab/orders",         { method: "POST",   body: JSON.stringify(body) }),
  updateOrder:(id, b)   => request(`/lab/orders/${id}`,   { method: "PUT",    body: JSON.stringify(b) }),
  removeOrder:(id)      => request(`/lab/orders/${id}`,   { method: "DELETE" }),
  ordersForPatient: (pid) => request(`/lab/orders/patient/${pid}`),
  sendReport: (id)   => request(`/lab/orders/${id}/send-report`, { method: "POST" }),
  pending:    ()        => request("/lab/pending"),
};

/* ---------------- PHARMACY ---------------- */
const PharmacyAPI = {
  listMedicines:  ()        => request("/pharmacy/medicines"),
  getMedicine:    (id)      => request(`/pharmacy/medicines/${id}`),
  createMedicine: (body)    => request("/pharmacy/medicines",        { method: "POST",   body: JSON.stringify(body) }),
  updateMedicine: (id, b)   => request(`/pharmacy/medicines/${id}`,  { method: "PUT",    body: JSON.stringify(b) }),
  removeMedicine: (id)      => request(`/pharmacy/medicines/${id}`,  { method: "DELETE" }),

  listPrescriptions: ()     => request("/pharmacy/prescriptions"),
  getPrescription:   (id)   => request(`/pharmacy/prescriptions/${id}`),
  createPrescription:(body) => request("/pharmacy/prescriptions",        { method: "POST",   body: JSON.stringify(body) }),
  updatePrescription:(id, b)=> request(`/pharmacy/prescriptions/${id}`,  { method: "PUT",    body: JSON.stringify(b) }),
  removePrescription:(id)   => request(`/pharmacy/prescriptions/${id}`,  { method: "DELETE" }),
  prescriptionsForPatient: (pid) => request(`/pharmacy/prescriptions/patient/${pid}`),
  sendPrescription: (id) => request(`/pharmacy/prescriptions/${id}/send-report`, { method: "POST" }),
  lowStock:       ()        => request("/pharmacy/low-stock"),
};

/* ---------------- AUTH (AWS Cognito User Pool) ----------------
   The old /auth/login, /auth/verify-otp and /auth/register routes
   are retired (the auth Lambda is removed). Sign-up, email
   verification and sign-in all happen against Cognito directly:
   the password never touches our own backend. Old users keep
   working: on their first Cognito sign-in the User Migration
   trigger checks their existing password in hospital-users and
   Cognito creates the account for them. */
const AuthAPI = {
  // Cognito sign-up: creates the user in the pool; Cognito emails
  // the verification code. Resolves { userConfirmed, user }.
  // Rejects with the Cognito error (UsernameExistsException,
  // InvalidPasswordException, ...).
  register: (name, email, password) => new Promise((resolve, reject) => {
    const pool = _cognitoPool();
    if (!pool) return reject(new Error("Sign-up is not configured yet"));
    const attrs = [
      new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "email", Value: email }),
      new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "name", Value: name }),
    ];
    pool.signUp(email, password, attrs, null, (err, result) => {
      if (err) return reject(err);
      resolve({ userConfirmed: result.userConfirmed, user: { name, email, role: "patient" } });
    });
  }),
  // Confirm the emailed verification code after sign-up (or for an
  // unconfirmed user at sign-in). Resolves {} on success.
  confirmSignUp: (email, code) => new Promise((resolve, reject) => {
    const user = _cognitoUser(email);
    if (!user) return reject(new Error("Sign-in is not configured yet"));
    user.confirmRegistration(code, true, (err) => err ? reject(err) : resolve({}));
  }),
  // Ask Cognito to send a fresh verification code.
  resendCode: (email) => new Promise((resolve, reject) => {
    const user = _cognitoUser(email);
    if (!user) return reject(new Error("Sign-in is not configured yet"));
    user.resendConfirmationCode((err) => err ? reject(err) : resolve({}));
  }),
  // Cognito sign-in. Resolves { token, user } with the ID token and
  // the name/role from its claims. Rejects with the Cognito error —
  // err.code is UserNotConfirmedException (account needs the emailed
  // code first), NotAuthorizedException (wrong password),
  // UserNotFoundException, or TooManyRequestsException.
  login: (email, password) => new Promise((resolve, reject) => {
    const user = _cognitoUser(email);
    if (!user) return reject(new Error("Sign-in is not configured yet"));
    user.authenticateUser(
      new AmazonCognitoIdentity.AuthenticationDetails({ Username: email, Password: password }),
      {
        onSuccess: (session) => {
          const token = session.getIdToken().getJwtToken();
          const payload = _tokenPayloadFrom(token);
          resolve({ token, user: { name: payload.name || email, email: payload.email || email, role: _roleFromPayload(payload) } });
        },
        onFailure: (err) => reject(err),
        newPasswordRequired: () => reject(new Error("Password change required — contact the hospital administrator.")),
      }
    );
  }),
  // Forgot password: ask Cognito to email a reset code. Resolves
  // { destination } with the masked email the code went to. The page
  // then asks for the code + new password and calls confirmPassword.
  // Rejects with the Cognito error (UserNotFoundException,
  // LimitExceededException, ...).
  forgotPassword: (email) => new Promise((resolve, reject) => {
    const user = _cognitoUser(email);
    if (!user) return reject(new Error("Sign-in is not configured yet"));
    let done = false;
    const finish = (data) => {
      if (done) return; done = true;
      const dest = (data && data.CodeDeliveryDetails && data.CodeDeliveryDetails.Destination) || email;
      resolve({ destination: dest });
    };
    user.forgotPassword({
      onSuccess: finish,
      onFailure: (err) => { if (!done) { done = true; reject(err); } },
      inputVerificationCode: finish,
    });
  }),
  // Confirm the emailed reset code and set the new password.
  // Resolves {} on success. Rejects with CodeMismatchException
  // (wrong code), ExpiredCodeException, or InvalidPasswordException.
  confirmPassword: (email, code, newPassword) => new Promise((resolve, reject) => {
    const user = _cognitoUser(email);
    if (!user) return reject(new Error("Sign-in is not configured yet"));
    user.confirmPassword(code, newPassword, {
      onSuccess: () => resolve({}),
      onFailure: (err) => reject(err),
    });
  }),
  // End the Cognito session and drop the stored token.
  signOut: () => {
    const pool = _cognitoPool();
    const user = pool && pool.getCurrentUser();
    if (user) { try { user.signOut(); } catch (e) {} }
    clearToken();
  },
};

/* ---------------- Toast helper ----------------
   ui.js (loaded before this file on every app page) provides the rich
   toast with icon + title inside #toast-container. This minimal fallback
   is installed ONLY when ui.js is absent, so the whole project uses one
   consistent toast and success/error messages never get lost. */
if (typeof window.showToast !== "function") {
  window.showToast = function (msg, type = "info") {
    let toast = document.getElementById("toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "toast";
      toast.className = "toast";
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.className = `toast toast-${type} show`;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => toast.classList.remove("show"), 3500);
  };
}

/* ---------------- Mock fallback (for local preview) ---------------- */
function mockFallback(path) {
  // Returns a sample payload so the UI works offline during development
  const m = {
    "/patients":              { count: 5, patients: MOCK_DATA.patients },
    "/bills":                 { count: 5, bills: MOCK_DATA.bills },
    "/dues":                  { count: 3, dues: MOCK_DATA.dues },
    "/payments":              { count: 3, payments: MOCK_DATA.payments },
    "/diseases":              { count: 5, diseases: MOCK_DATA.diseases },
    "/diseases/active":       { count: 4, active_diseases: MOCK_DATA.diseases.filter(d => d.status !== "Recovered") },
    "/doctors":               { count: 5, doctors: MOCK_DATA.doctors },
    "/assignments":          { count: 5, assignments: MOCK_DATA.assignments },
    "/lab/tests":             { count: 12, tests: MOCK_DATA.labTests },
    "/lab/orders":            { count: 6, orders: MOCK_DATA.labOrders },
    "/lab/pending":           { count: 3, orders: MOCK_DATA.labOrders.filter(o => o.status !== "Completed") },
    "/pharmacy/medicines":    { count: 12, medicines: MOCK_DATA.medicines },
    "/pharmacy/prescriptions": { count: 6, prescriptions: MOCK_DATA.prescriptions },
    "/pharmacy/low-stock":    { count: 1, medicines: MOCK_DATA.medicines.filter(m => m.stock_quantity <= m.reorder_level) },
  };
  return Promise.resolve(m[path] || { message: "ok" });
}

const MOCK_DATA = {
  patients: [
    { patient_id:1, first_name:"Rahul",  last_name:"Sharma", date_of_birth:"1990-05-14", gender:"Male",   phone:"9876543210", email:"rahul.sharma@email.com",  blood_group:"O+",  registration_date:"2026-10-01" },
    { patient_id:2, first_name:"Priya",  last_name:"Patel",  date_of_birth:"1988-09-22", gender:"Female", phone:"9876543211", email:"priya.patel@email.com",   blood_group:"A+",  registration_date:"2026-09-20" },
    { patient_id:3, first_name:"Amit",   last_name:"Verma",  date_of_birth:"1995-01-30", gender:"Male",   phone:"9876543212", email:"amit.verma@email.com",     blood_group:"B+",  registration_date:"2026-10-15" },
    { patient_id:4, first_name:"Sneha",  last_name:"Reddy",  date_of_birth:"2000-07-08", gender:"Female", phone:"9876543213", email:"sneha.reddy@email.com",    blood_group:"AB+", registration_date:"2026-08-05" },
    { patient_id:5, first_name:"Karan",  last_name:"Singh",  date_of_birth:"1982-11-19", gender:"Male",   phone:"9876543214", email:"karan.singh@email.com",    blood_group:"O-",  registration_date:"2026-07-10" },
  ],
  bills: [
    { bill_id:1, patient_id:1, patient_name:"Rahul Sharma",  description:"Cardiology consultation + ECG",      category:"Consultation", amount:1500, net_amount:1500, status:"Partial", bill_date:"2026-10-01" },
    { bill_id:2, patient_id:2, patient_name:"Priya Patel",   description:"Neurology consultation + MRI scan",  category:"Lab Test",     amount:5000, net_amount:4500, status:"Pending", bill_date:"2026-09-20" },
    { bill_id:3, patient_id:3, patient_name:"Amit Verma",    description:"Orthopedic consultation + X-Ray",    category:"Consultation", amount:2500, net_amount:2500, status:"Paid",    bill_date:"2026-10-15" },
    { bill_id:4, patient_id:4, patient_name:"Sneha Reddy",   description:"Pulmonology consultation + Spirometry",category:"Consultation",amount:1800, net_amount:1800, status:"Pending", bill_date:"2026-08-05" },
    { bill_id:5, patient_id:5, patient_name:"Karan Singh",   description:"General consult + Blood sugar panel", category:"Lab Test",    amount:1200, net_amount:1100, status:"Partial", bill_date:"2026-07-10" },
  ],
  dues: [
    { bill_id:1, patient_id:1, patient_name:"Rahul Sharma", description:"Cardiology consultation + ECG",     net_amount:1500, due_amount:500,  status:"Partial", bill_date:"2026-10-01" },
    { bill_id:2, patient_id:2, patient_name:"Priya Patel",  description:"Neurology consultation + MRI scan", net_amount:4500, due_amount:4500, status:"Pending", bill_date:"2026-09-20" },
    { bill_id:4, patient_id:4, patient_name:"Sneha Reddy",   description:"Pulmonology consultation + Spirometry",net_amount:1800,due_amount:1800,status:"Pending", bill_date:"2026-08-05" },
  ],
  payments: [
    { payment_id:1, bill_id:1, patient_id:1, patient_name:"Rahul Sharma", amount_paid:1000, payment_method:"UPI",  transaction_id:"TXN-1001", payment_date:"2026-10-01" },
    { payment_id:2, bill_id:3, patient_id:3, patient_name:"Amit Verma",   amount_paid:2500, payment_method:"Card", transaction_id:"TXN-1002", payment_date:"2026-10-15" },
    { payment_id:3, bill_id:5, patient_id:5, patient_name:"Karan Singh",  amount_paid:500,  payment_method:"Cash", transaction_id:"TXN-1003", payment_date:"2026-07-10" },
  ],
  diseases: [
    { disease_id:1, patient_id:1, patient_name:"Rahul Sharma", disease_name:"Hypertension",    severity:"Moderate", status:"Under Treatment", diagnosis_date:"2026-10-01", follow_up_date:"2026-11-15" },
    { disease_id:2, patient_id:2, patient_name:"Priya Patel",  disease_name:"Migraine",        severity:"Mild",     status:"Active",          diagnosis_date:"2026-09-20", follow_up_date:"2026-11-10" },
    { disease_id:3, patient_id:3, patient_name:"Amit Verma",   disease_name:"Fracture - Tibia",severity:"Severe",  status:"Under Treatment", diagnosis_date:"2026-10-15", follow_up_date:"2026-12-01" },
    { disease_id:4, patient_id:4, patient_name:"Sneha Reddy",  disease_name:"Asthma",          severity:"Moderate", status:"Active",          diagnosis_date:"2026-08-05", follow_up_date:"2026-11-20" },
    { disease_id:5, patient_id:5, patient_name:"Karan Singh",  disease_name:"Type 2 Diabetes", severity:"Moderate",status:"Chronic",         diagnosis_date:"2026-07-10", follow_up_date:"2026-11-30" },
  ],
  doctors: [
    { doctor_id:1, first_name:"Dr. Anil",  last_name:"Gupta", specialization:"Cardiologist",     department:"Cardiology", phone:"9000012345", availability:"Available", consultation_fee:800 },
    { doctor_id:2, first_name:"Dr. Meera", last_name:"Nair",  specialization:"Neurologist",      department:"Neurology",  phone:"9000012346", availability:"Available", consultation_fee:1000 },
    { doctor_id:3, first_name:"Dr. Vivek", last_name:"Joshi", specialization:"Orthopedic",        department:"Orthopedics",phone:"9000012347", availability:"Busy",      consultation_fee:600 },
    { doctor_id:4, first_name:"Dr. Sunita",last_name:"Kapoor",specialization:"Pediatrician",     department:"Pediatrics", phone:"9000012348", availability:"Available", consultation_fee:500 },
    { doctor_id:5, first_name:"Dr. Rajesh",last_name:"Mehta", specialization:"General Physician", department:"General",    phone:"9000012349", availability:"On Leave",  consultation_fee:400 },
  ],
  assignments: [
    { assignment_id:1, patient_id:1, patient_name:"Rahul Sharma", doctor_id:1, doctor_name:"Dr. Anil Gupta", specialization:"Cardiologist", disease_name:"Hypertension", appointment_date:"2026-11-15 10:00", status:"Active",    room_number:"C-101" },
    { assignment_id:2, patient_id:2, patient_name:"Priya Patel",  doctor_id:2, doctor_name:"Dr. Meera Nair", specialization:"Neurologist", disease_name:"Migraine",     appointment_date:"2026-11-10 11:00", status:"Scheduled", room_number:"N-203" },
    { assignment_id:3, patient_id:3, patient_name:"Amit Verma",   doctor_id:3, doctor_name:"Dr. Vivek Joshi",specialization:"Orthopedic", disease_name:"Fracture - Tibia",appointment_date:"2026-12-01 09:00", status:"Active",    room_number:"O-305" },
    { assignment_id:4, patient_id:4, patient_name:"Sneha Reddy",  doctor_id:4, doctor_name:"Dr. Sunita Kapoor",specialization:"Pediatrician",disease_name:"Asthma",     appointment_date:"2026-11-20 14:00", status:"Scheduled", room_number:"P-102" },
    { assignment_id:5, patient_id:5, patient_name:"Karan Singh",  doctor_id:1, doctor_name:"Dr. Anil Gupta",  specialization:"Cardiologist", disease_name:"Type 2 Diabetes",appointment_date:"2026-11-30 15:00", status:"Active",   room_number:"G-201" },
  ],
  labTests: [
    { test_id:1, test_name:"Complete Blood Count (CBC)", category:"Hematology", sample_type:"Blood", unit:"g/dL", normal_range:"Hb 12.0 - 15.5", price:300, turnaround_hours:6, is_active:1 },
    { test_id:3, test_name:"HbA1c (Glycated Hb)", category:"Biochemistry", sample_type:"Blood", unit:"%", normal_range:"Below 5.7", price:450, turnaround_hours:24, is_active:1 },
    { test_id:4, test_name:"Lipid Profile", category:"Biochemistry", sample_type:"Blood", unit:"mg/dL", normal_range:"Total Chol. below 200", price:800, turnaround_hours:24, is_active:1 },
  ],
  labOrders: [
    { order_id:1, patient_id:1, patient_name:"Rahul Sharma", test_id:4, test_name:"Lipid Profile", ordered_by:1, doctor_name:"Dr. Anil Gupta", order_date:"2026-10-01", priority:"Routine", status:"Completed", result_value:"182", test_unit:"mg/dL", report_date:"2026-10-02" },
    { order_id:4, patient_id:4, patient_name:"Sneha Reddy", test_id:10, test_name:"Dengue NS1 Antigen", ordered_by:4, doctor_name:"Dr. Sunita Kapoor", order_date:"2026-08-05", priority:"Urgent", status:"Sample Collected", result_value:null, test_unit:"", report_date:null },
    { order_id:5, patient_id:5, patient_name:"Karan Singh", test_id:3, test_name:"HbA1c (Glycated Hb)", ordered_by:1, doctor_name:"Dr. Anil Gupta", order_date:"2026-07-10", priority:"Routine", status:"Processing", result_value:null, test_unit:"%", report_date:null },
  ],
  medicines: [
    { medicine_id:1, medicine_name:"Paracetamol 500mg", generic_name:"Paracetamol", category:"Analgesic", manufacturer:"Cipla", unit:"Tablet", unit_price:2.50, stock_quantity:1200, reorder_level:200, expiry_date:"2027-06-30", requires_prescription:0 },
    { medicine_id:3, medicine_name:"Amlodipine 5mg", generic_name:"Amlodipine", category:"Cardiac", manufacturer:"Dr Reddy's", unit:"Tablet", unit_price:4.20, stock_quantity:600, reorder_level:100, expiry_date:"2027-03-31", requires_prescription:1 },
    { medicine_id:11, medicine_name:"Insulin Glargine", generic_name:"Insulin Glargine", category:"Diabetic", manufacturer:"Sanofi", unit:"Injection", unit_price:540, stock_quantity:42, reorder_level:15, expiry_date:"2026-07-31", requires_prescription:1 },
  ],
  prescriptions: [
    { prescription_id:1, patient_id:1, patient_name:"Rahul Sharma", doctor_id:1, doctor_name:"Dr. Anil Gupta", medicine_id:3, medicine_name:"Amlodipine 5mg", medicine_unit:"Tablet", quantity:30, dosage:"5mg", frequency:"Once a day", duration_days:30, total_amount:126, status:"Dispensed", prescribed_date:"2026-10-01" },
    { prescription_id:4, patient_id:4, patient_name:"Sneha Reddy", doctor_id:4, doctor_name:"Dr. Sunita Kapoor", medicine_id:10, medicine_name:"Salbutamol Inhaler", medicine_unit:"Inhaler", quantity:1, dosage:"2 puffs", frequency:"As needed", duration_days:30, total_amount:165, status:"Pending", prescribed_date:"2026-08-05" },
  ],
};
