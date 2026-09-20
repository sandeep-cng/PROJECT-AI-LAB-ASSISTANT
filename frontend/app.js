// ==========================================================================
// APEX FAMILY DIAGNOSTIC LAB - FRONTEND APPLICATION
// Clean Clinic Experience with Dedicated Customer Support AI Agent
// ==========================================================================

let callSocket = null;
let isCallActive = false;
let callDuration = 0;
let callTimerInterval = null;
let isVoiceOutputEnabled = true;
let isRecording = false;
let recognition = null;
let canvasAnimId = null;

// DOM Elements
const callModal = document.getElementById('call-modal');
const headerCallTrigger = document.getElementById('header-call-trigger');
const heroCallTrigger = document.getElementById('btn-hero-call');
const btnModalClose = document.getElementById('btn-modal-close');
const btnModalHangup = document.getElementById('btn-modal-hangup');
const modalCallStatus = document.getElementById('modal-call-status');
const modalCallerDesc = document.getElementById('modal-caller-desc');
const modalPhoneInput = document.getElementById('modal-phone-input');
const modalAvatar = document.getElementById('modal-avatar');
const modalTimer = document.getElementById('modal-timer');
const modalWaveformCanvas = document.getElementById('modal-waveform-canvas');
const modalTranscriptFeed = document.getElementById('modal-transcript-feed');
const modalActionBar = document.getElementById('modal-action-bar');
const modalActionText = document.getElementById('modal-action-text');
const btnModalMic = document.getElementById('btn-modal-mic');
const modalUserText = document.getElementById('modal-user-text');
const btnModalSend = document.getElementById('btn-modal-send');
const packagesContainer = document.getElementById('packages-container');

document.addEventListener('DOMContentLoaded', () => {
  initCallTriggers();
  initFAQAccordion();
  initSpeechRecognition();
  initModalVisualizer();
  loadHealthPackages();
});

// --- Toast System ---
function showToast(message) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// --- Direct Customer Support Call Triggers ---
function initCallTriggers() {
  headerCallTrigger.addEventListener('click', () => openCallModal());
  headerCallTrigger.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') openCallModal();
  });

  if (heroCallTrigger) {
    heroCallTrigger.addEventListener('click', () => openCallModal());
  }

  btnModalClose.addEventListener('click', closeCallModal);
  btnModalHangup.addEventListener('click', closeCallModal);

  modalPhoneInput.addEventListener('change', () => {
    checkCallerId(modalPhoneInput.value);
  });

  btnModalSend.addEventListener('click', sendUserSpeechTurn);
  modalUserText.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendUserSpeechTurn();
  });

  // Quick chips
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      modalUserText.value = chip.dataset.speak;
      sendUserSpeechTurn();
    });
  });
}

function openCallModal(preferredTest = null) {
  callModal.style.display = 'flex';
  startCallSession(preferredTest);
}

function closeCallModal() {
  if (isCallActive) {
    endCallSession();
  }
  callModal.style.display = 'none';
}

// --- Caller ID Lookup ---
async function checkCallerId(phone) {
  try {
    const res = await fetch(`/api/patients/${encodeURIComponent(phone)}/lookup`);
    if (res.ok) {
      const patient = await res.json();
      modalCallerDesc.textContent = `Recognized: ${patient.full_name} • Verified Returning Patient Profile`;
      modalAvatar.textContent = patient.full_name.split(' ').map(n => n[0]).join('').substring(0, 2);
    } else {
      modalCallerDesc.textContent = 'New / Unregistered Number • Guest Profile will be created';
      modalAvatar.textContent = '??';
    }
  } catch (err) {
    console.log('Lookup fallback');
  }
}

// --- Active Call Engine ---
let currentCallSid = null;
let useRestFallback = false;

// --- Active Call Engine ---
function startCallSession(preferredTest = null) {
  const phone = modalPhoneInput.value.trim() || '+1 (555) 234-5678';
  isCallActive = true;
  useRestFallback = false;
  currentCallSid = null;
  modalCallStatus.textContent = 'Call Active • Connected to Dedicated Care Specialist';
  modalCallStatus.style.color = '#34d399';
  modalTranscriptFeed.innerHTML = '';
  checkCallerId(phone);

  // Timer
  callDuration = 0;
  if (callTimerInterval) clearInterval(callTimerInterval);
  callTimerInterval = setInterval(() => {
    callDuration++;
    const mins = String(Math.floor(callDuration / 60)).padStart(2, '0');
    const secs = String(callDuration % 60).padStart(2, '0');
    modalTimer.textContent = `${mins}:${secs}`;
  }, 1000);

  // Attempt WebSocket first; seamlessly fall back to REST on serverless platforms (Vercel)
  try {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    callSocket = new WebSocket(`${protocol}//${window.location.host}/ws/phone-call`);

    callSocket.onopen = () => {
      callSocket.send(JSON.stringify({
        type: 'initiate_call',
        caller_phone: phone
      }));

      if (preferredTest) {
        setTimeout(() => {
          modalUserText.value = `I would like to book the ${preferredTest}`;
          sendUserSpeechTurn();
        }, 1800);
      }
    };

    callSocket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'call_connected') {
        currentCallSid = msg.call_sid;
        appendSpeechBubble('Maya (Care Specialist)', msg.speech, 'agent');
        speakAudio(msg.speech);
      } else if (msg.type === 'agent_response') {
        appendSpeechBubble('Maya (Care Specialist)', msg.speech, 'agent');
        speakAudio(msg.speech);

        if (msg.actions_taken && msg.actions_taken.length > 0) {
          modalActionText.textContent = msg.actions_taken[msg.actions_taken.length - 1];
        }
      }
    };

    callSocket.onerror = () => {
      console.log('WebSocket not supported by environment, switching to HTTP REST API');
      startRestCallSession(phone, preferredTest);
    };

    callSocket.onclose = () => {
      if (isCallActive && !useRestFallback) {
        // If closed prematurely without user hangup, transition to REST
        useRestFallback = true;
      }
    };
  } catch (err) {
    startRestCallSession(phone, preferredTest);
  }
}

async function startRestCallSession(phone, preferredTest = null) {
  useRestFallback = true;
  try {
    const res = await fetch('/api/telephony/chat-initiate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caller_phone: phone })
    });
    if (res.ok) {
      const data = await res.json();
      currentCallSid = data.call_sid;
      appendSpeechBubble('Maya (Care Specialist)', data.speech, 'agent');
      speakAudio(data.speech);

      if (preferredTest) {
        setTimeout(() => {
          modalUserText.value = `I would like to book the ${preferredTest}`;
          sendUserSpeechTurn();
        }, 1800);
      }
    }
  } catch (err) {
    console.error('REST call failed:', err);
  }
}

function endCallSession() {
  isCallActive = false;
  clearInterval(callTimerInterval);
  if (callSocket && callSocket.readyState === WebSocket.OPEN) {
    callSocket.send(JSON.stringify({ type: 'hangup' }));
    callSocket.close();
  }
  modalCallStatus.textContent = 'Call Disconnected';
  modalCallStatus.style.color = '#ef4444';
  showToast('Call ended. Your appointment & call summary have been saved.');
}

async function sendUserSpeechTurn() {
  const text = modalUserText.value.trim();
  if (!text) return;

  appendSpeechBubble('You', text, 'user');
  modalUserText.value = '';

  if (!useRestFallback && callSocket && callSocket.readyState === WebSocket.OPEN) {
    callSocket.send(JSON.stringify({
      type: 'user_speech',
      text: text
    }));
  } else {
    // REST turn fallback
    const phone = modalPhoneInput.value.trim() || '+1 (555) 234-5678';
    try {
      const res = await fetch('/api/telephony/chat-turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          call_sid: currentCallSid || '',
          caller_phone: phone,
          text: text
        })
      });
      if (res.ok) {
        const data = await res.json();
        appendSpeechBubble('Maya (Care Specialist)', data.speech, 'agent');
        speakAudio(data.speech);

        if (data.actions_taken && data.actions_taken.length > 0) {
          modalActionText.textContent = data.actions_taken[data.actions_taken.length - 1];
        }
      }
    } catch (err) {
      console.error('Failed to send turn over REST:', err);
    }
  }
}

function appendSpeechBubble(speaker, text, type) {
  const bubble = document.createElement('div');
  bubble.className = `speech-bubble ${type}`;
  bubble.innerHTML = `
    <div class="bubble-speaker">${speaker}</div>
    <div class="bubble-text">${text.replace(/\n/g, '<br>')}</div>
  `;
  modalTranscriptFeed.appendChild(bubble);
  modalTranscriptFeed.scrollTop = modalTranscriptFeed.scrollHeight;
}

// --- Text-to-Speech (Human-Like Spoken Feedback) ---
function speakAudio(text) {
  if (!isVoiceOutputEnabled || !('speechSynthesis' in window)) return;

  window.speechSynthesis.cancel();
  const cleanSpeech = text.replace(/[*#_\[\]\(\)]/g, '').replace(/https?:\/\/\S+/g, '');
  const utterance = new SpeechSynthesisUtterance(cleanSpeech);
  utterance.rate = 1.0;
  utterance.pitch = 1.04;

  const voices = window.speechSynthesis.getVoices();
  const naturalVoice = voices.find(v => v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('Jenny') || v.lang.startsWith('en'));
  if (naturalVoice) utterance.voice = naturalVoice;

  window.speechSynthesis.speak(utterance);
}

// --- Speech-to-Text (Microphone) ---
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    btnModalMic.style.display = 'none';
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isRecording = true;
    btnModalMic.classList.add('recording');
  };

  recognition.onresult = (event) => {
    const spoken = event.results[0][0].transcript;
    modalUserText.value = spoken;
    sendUserSpeechTurn();
  };

  recognition.onerror = () => {
    isRecording = false;
    btnModalMic.classList.remove('recording');
  };

  recognition.onend = () => {
    isRecording = false;
    btnModalMic.classList.remove('recording');
  };

  btnModalMic.addEventListener('click', () => {
    if (!isRecording) {
      recognition.start();
    } else {
      recognition.stop();
    }
  });
}

// --- Audio Waveform Visualizer ---
function initModalVisualizer() {
  const ctx = modalWaveformCanvas.getContext('2d');
  const barCount = 38;

  function renderWaveform() {
    ctx.clearRect(0, 0, modalWaveformCanvas.width, modalWaveformCanvas.height);
    const width = modalWaveformCanvas.width;
    const height = modalWaveformCanvas.height;
    const barWidth = width / barCount - 2;

    for (let i = 0; i < barCount; i++) {
      let barHeight;
      if (isCallActive) {
        const t = Date.now() * 0.005;
        barHeight = Math.sin(t + i * 0.35) * 16 + Math.cos(t * 0.9 + i * 0.2) * 10 + 22;
      } else {
        barHeight = 4;
      }

      const x = i * (barWidth + 2);
      const y = (height - barHeight) / 2;

      const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
      gradient.addColorStop(0, '#0170B9');
      gradient.addColorStop(1, '#38bdf8');

      ctx.fillStyle = gradient;
      ctx.fillRect(x, y, barWidth, barHeight);
    }
    canvasAnimId = requestAnimationFrame(renderWaveform);
  }
  renderWaveform();
}

// --- Health Packages ---
async function loadHealthPackages() {
  try {
    const res = await fetch('/api/packages');
    const packages = await res.json();
    packagesContainer.innerHTML = '';

    packages.forEach(pkg => {
      const card = document.createElement('div');
      card.className = `pkg-card ${pkg.is_popular ? 'popular' : ''}`;
      card.innerHTML = `
        ${pkg.is_popular ? '<span class="badge-pop">POPULAR CHOICE</span>' : ''}
        <div>
          <h3>${pkg.package_name}</h3>
          <p>${pkg.description}</p>
          <div class="pkg-tests-list">Included: ${pkg.test_codes.join(' • ')}</div>
        </div>
        <div>
          <div class="pkg-price-row">
            <span class="pkg-discount">$${pkg.discounted_price.toFixed(2)}</span>
            <span class="pkg-original">$${pkg.price.toFixed(2)}</span>
          </div>
          <button class="btn-pkg-call" onclick="openCallModal('${pkg.package_name}')">
            📞 Call Support to Book ($${pkg.discounted_price.toFixed(0)})
          </button>
        </div>
      `;
      packagesContainer.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading packages:', err);
  }
}

// --- FAQ Accordion ---
function initFAQAccordion() {
  document.querySelectorAll('.faq-question').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.parentElement;
      const isOpen = item.classList.contains('open');
      document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
      if (!isOpen) {
        item.classList.add('open');
      }
    });
  });
}
