/* ============================================================
   HealthCare — Video Consultation (real Jitsi Meet call)
   Shared logic for frontend/video-call.html.
   This is the ONLY place that computes Jitsi room names,
   joins a call, or reads/writes "[VIDEO-CALL ...]" history
   records. No other file may compute room names.
   ============================================================ */

/* ── Room name ──────────────────────────────────────────────
   Deterministic: patient and doctor compute the IDENTICAL
   room from the assignment id + appointment date (FNV-1a
   32-bit hash of "id|date"). No backend call is needed, and
   the room cannot be guessed without the exact date. */
function roomName(assignmentId, appointmentDate) {
  var seed = String(assignmentId) + '|' + String(appointmentDate || '');
  var hash = 0x811c9dc5; /* FNV-1a offset basis */
  for (var i = 0; i < seed.length; i++) {
    hash ^= seed.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193); /* FNV-1a prime */
  }
  var hex = (hash >>> 0).toString(16).padStart(8, '0');
  var safeId = String(assignmentId).replace(/[^a-z0-9]/gi, '').toLowerCase();
  return 'healthcare-appt-' + safeId + '-' + hex;
}

/* ── Duration formatting (seconds -> "MM:SS") ── */
function formatCallDuration(totalSeconds) {
  var s = Math.max(0, Math.floor(totalSeconds || 0));
  var m = Math.floor(s / 60);
  var r = s % 60;
  return (m < 10 ? '0' + m : '' + m) + ':' + (r < 10 ? '0' + r : '' + r);
}

/* ── Parse "[VIDEO-CALL date | N min | doctor]" records ────
   out of an assignment notes string. Returns an array of
   { date, minutes, doctor }. Used by consultation-history. */
function parseVideoCallRecords(notes) {
  var out = [];
  if (!notes) return out;
  var re = /\[VIDEO-CALL\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\s*\|\s*(\d+)\s*min\s*\|\s*([^\]]+)\]/g;
  var m;
  while ((m = re.exec(String(notes))) !== null) {
    out.push({ date: m[1], minutes: parseInt(m[2], 10), doctor: (m[3] || '').trim() });
  }
  return out;
}

/* ── Record a consultation in the assignment notes ──────────
   Appends ONE "[VIDEO-CALL ...]" record to the assignment
   notes. Existing notes (payment info etc.) are NEVER
   overwritten — the record is appended to them. Best-effort:
   returns false if the save fails; the caller still shows
   the summary. */
async function recordConsultation(assignmentId, doctorName, durationMinutes) {
  try {
    var res = await DoctorsAPI.assignment(assignmentId);
    var asg = res && res.assignment;
    if (!asg) return false;
    var dateIso = new Date().toISOString().slice(0, 10);
    var record = '[VIDEO-CALL ' + dateIso + ' | ' + Math.max(1, Math.round(durationMinutes || 0)) + ' min | ' + (doctorName || 'Doctor') + ']';
    var notes = (asg.notes || '').trim();
    var merged = notes ? notes + ' ' + record : record;
    var saved = await DoctorsAPI.updateAssign(assignmentId, { notes: merged });
    return saved !== null && saved !== undefined;
  } catch (e) {
    return false;
  }
}

/* ── Patient-waiting flag ─────────────────────────────────────
   When the PATIENT joins the room, mark the assignment "patient
   is waiting" (an ISO timestamp) so the doctor's bell shows a
   red "Patient is waiting — join now" item. When the DOCTOR
   joins, or the call ends, or the patient leaves, clear it
   (null removes the attribute in DynamoDB). Best-effort: a
   failed save never breaks the call. */
async function setPatientWaiting(assignmentId, waiting) {
  try {
    if (!assignmentId || typeof DoctorsAPI === 'undefined' || !DoctorsAPI.setWaiting) return false;
    var ts = waiting ? new Date().toISOString() : null;
    var res = await DoctorsAPI.setWaiting(assignmentId, ts);
    return res !== null && res !== undefined;
  } catch (e) {
    return false;
  }
}

/* ── Jitsi call controller ────────────────────────────────── */
var VideoCall = (function () {
  var api = null;
  var opts = null;
  var timerId = null;
  var consultStart = null; /* when the other side joined */
  var peerPresent = false;
  var ended = false;
  var audioMuted = false;
  var videoMuted = false;

  function consultSeconds() {
    if (!consultStart) return 0;
    return Math.floor((Date.now() - consultStart) / 1000);
  }

  function markPeerJoined() {
    if (!peerPresent) {
      peerPresent = true;
      if (!consultStart) consultStart = Date.now();
      if (opts && opts.onPeerJoined) opts.onPeerJoined();
      startTimer();
    }
  }

  function startTimer() {
    if (timerId || !opts) return;
    timerId = setInterval(function () {
      if (opts.onTick) opts.onTick(consultSeconds());
    }, 1000);
  }

  function stopTimer() {
    if (timerId) { clearInterval(timerId); timerId = null; }
  }

  /* Ends the call exactly once — from the page's End Call
     button OR from Jitsi's own hangup (readyToClose). */
  function finish() {
    if (ended) return null;
    ended = true;
    stopTimer();
    var seconds = consultSeconds();
    var result = {
      durationSeconds: seconds,
      durationMinutes: Math.max(1, Math.round(seconds / 60)),
      peerJoined: peerPresent
    };
    if (api) { try { api.dispose(); } catch (e) { /* already closed */ } api = null; }
    if (opts && opts.onEnded) opts.onEnded(result);
    return result;
  }

  function join(o) {
    opts = o || {};
    var container = document.getElementById(opts.containerId);
    if (!container) {
      if (opts.onError) opts.onError('Call screen is missing. Please refresh the page.');
      return null;
    }
    if (typeof JitsiMeetExternalAPI === 'undefined') {
      if (opts.onError) opts.onError('Jitsi could not load — check your internet connection and refresh.');
      return null;
    }
    try {
      api = new JitsiMeetExternalAPI('meet.ffmuc.net', {
        roomName: opts.room,
        width: '100%',
        height: '100%',
        parentNode: container,
        userInfo: { displayName: opts.displayName || 'HealthCare' },
        configOverwrite: {
          startWithAudioMuted: false,
          startWithVideoMuted: false,
          prejoinPageEnabled: false,
          prejoinConfig: { enabled: false },
          disableDeepLinking: true,
          toolbarButtons: ['microphone', 'camera', 'tileview', 'fullscreen', 'hangup']
        },
        interfaceConfigOverwrite: {
          TOOLBAR_BUTTONS: ['microphone', 'camera', 'tileview', 'fullscreen', 'hangup']
        }
      });
    } catch (e) {
      if (opts.onError) opts.onError('Could not start the video call. Please refresh and try again.');
      return null;
    }

    api.addEventListener('videoConferenceJoined', function () {
      if (opts.onStatus) opts.onStatus('joined');
      /* The other side may ALREADY be in the room — check the
         participant count too, not just future join events. */
      try {
        if (api && typeof api.getNumberOfParticipants === 'function') {
          api.getNumberOfParticipants().then(function (n) {
            if (n && n > 1) markPeerJoined();
          }).catch(function () { /* join events alone will catch it */ });
        }
      } catch (e) { /* join events alone will catch it */ }
    });
    api.addEventListener('participantJoined', function () { markPeerJoined(); });
    api.addEventListener('participantLeft', function () {
      peerPresent = false;
      if (opts.onPeerLeft) opts.onPeerLeft();
    });
    api.addEventListener('audioMuteStatusChanged', function (ev) {
      audioMuted = !!(ev && ev.muted);
      if (opts.onMuteChange) opts.onMuteChange({ audio: audioMuted, video: videoMuted });
    });
    api.addEventListener('videoMuteStatusChanged', function (ev) {
      videoMuted = !!(ev && ev.muted);
      if (opts.onMuteChange) opts.onMuteChange({ audio: audioMuted, video: videoMuted });
    });
    /* Fires when the user presses Jitsi's own hangup button. */
    api.addEventListener('readyToClose', function () { finish(); });
    return api;
  }

  function toggleAudio() { if (api) { try { api.executeCommand('toggleAudio'); } catch (e) {} } }
  function toggleVideo() { if (api) { try { api.executeCommand('toggleVideo'); } catch (e) {} } }

  function endCall() { return finish(); }
  function isPeerPresent() { return peerPresent; }
  function getDurationSeconds() { return consultSeconds(); }

  return {
    join: join,
    toggleAudio: toggleAudio,
    toggleVideo: toggleVideo,
    endCall: endCall,
    isPeerPresent: isPeerPresent,
    getDurationSeconds: getDurationSeconds
  };
})();
