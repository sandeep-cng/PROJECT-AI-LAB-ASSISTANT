// ==========================================================================
// APEX FAMILY DIAGNOSTIC LAB - FRONTEND APPLICATION
// Clean Clinic Experience with Dedicated Customer Support AI Agent
// Features Instant Barge-In (Agent stops speaking the instant user speaks)
// ==========================================================================

let callSocket = null;
let isCallActive = false;
let callDuration = 0;
let callTimerInterval = null;
let isVoiceOutputEnabled = true;
let isRecording = false;
let recognition = null;
let canvasAnimId = null;

// Barge-In & Audio State Tracking
let isAgentSpeaking = false;
let audioContext = null;
let analyser = null;
let micStream = null;
let vadThreshold = 0.035; // Voice activity detection threshold

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
const modalAudioState = document.getElementById('modal-audio-state');
const modalWaveformCanvas = document.getElementById('modal-waveform-canvas');
const modalTranscriptFeed = document.getElementById('modal-transcript-feed');
const modalActionBar = document.getElementById('modal-action-bar');
const modalActionText = document.getElementById('modal-action-text');
const btnModalMic = document.getElementById('btn-modal-mic');
const modalUserText = document.getElementById('modal-user-text');
const btnModalSend = document.getElementById('btn-modal-send');
const btnModalInterrupt = document.getElementById('btn-modal-interrupt');
const bargeInBadge = document.getElementById('barge-in-badge');
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

// ==========================================================================
// BARGE-IN INTERRUPTION ENGINE
// Immediately halts agent speech playback the instant human voice or input is detected!
// ==========================================================================
function stopAgentSpeaking(reason = 'user_speaking') {
  const wasSpeaking = isAgentSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking);
  if (!wasSpeaking) return;

  // 1. Immediately cancel Web Speech API TTS
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  isAgentSpeaking = false;

  // 2. Update UI Indicators
  if (modalAudioState) {
    modalAudioState.textContent = 'Vinod Paused (Barge-In Active) • Listening to you...';
    modalAudioState.style.color = '#f59e0b';
  }
  if (modalActionText) {
    modalActionText.textContent = `⚡ Vinod stopped speaking (${reason}) — Listening to your complete query...`;
    modalActionText.style.color = '#f59e0b';
  }

  // 3. Mark the interrupted agent speech bubble in transcript
  const agentBubbles = modalTranscriptFeed.querySelectorAll('.speech-bubble.agent');
  if (agentBubbles.length > 0) {
    const lastBubble = agentBubbles[agentBubbles.length - 1];
    if (!lastBubble.querySelector('.bubble-interrupted-tag')) {
      const tag = document.createElement('span');
      tag.className = 'bubble-interrupted-tag';
      tag.textContent = ' [Interrupted by you]';
      tag.style.color = '#f59e0b';
      tag.style.fontSize = '0.74rem';
      tag.style.fontWeight = '600';
      tag.style.marginLeft = '6px';
      lastBubble.querySelector('.bubble-speaker').appendChild(tag);
    }
  }

  // 4. Send cancellation signal to server WebSocket
  if (!useRestFallback && callSocket && callSocket.readyState === WebSocket.OPEN) {
    callSocket.send(JSON.stringify({
      type: 'user_interrupt',
      reason: reason,
      timestamp: Date.now()
    }));
  }

  console.log(`[Barge-In Active] Agent speech halted: ${reason}`);
}

// Hardware-level Voice Activity Detection (VAD) via Web Audio API Analyser
async function startVoiceActivityDetection() {
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
    if (!audioContext) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioCtx();
    }
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    const source = audioContext.createMediaStreamSource(micStream);
    source.connect(analyser);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    function monitorVoiceEnergy() {
      if (!isCallActive) return;

      analyser.getByteTimeDomainData(dataArray);
      let sumSquares = 0.0;
      for (let i = 0; i < dataArray.length; i++) {
        const norm = (dataArray[i] - 128) / 128;
        sumSquares += norm * norm;
      }
      const rms = Math.sqrt(sumSquares / dataArray.length);

      // If user voice energy exceeds threshold while agent is speaking -> INSTANT BARGE IN!
      if (rms > vadThreshold && (isAgentSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking))) {
        stopAgentSpeaking('mic_voice_energy_vad');
      }

      requestAnimationFrame(monitorVoiceEnergy);
    }
    requestAnimationFrame(monitorVoiceEnergy);
  } catch (err) {
    console.log('Voice Activity Detection note:', err);
  }
}

function stopVoiceActivityDetection() {
  if (micStream) {
    micStream.getTracks().forEach(track => track.stop());
    micStream = null;
  }
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

  btnModalSend.addEventListener('click', () => {
    stopAgentSpeaking('send_button_pressed');
    sendUserSpeechTurn();
  });

  modalUserText.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      stopAgentSpeaking('enter_key_pressed');
      sendUserSpeechTurn();
    }
  });

  // Typing immediately stops agent speaking (instant responsive barge-in)
  modalUserText.addEventListener('input', () => {
    if (isAgentSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking)) {
      stopAgentSpeaking('user_typing');
    }
  });

  // Dedicated manual interrupt button
  if (btnModalInterrupt) {
    btnModalInterrupt.addEventListener('click', () => {
      stopAgentSpeaking('manual_interrupt_button');
      modalUserText.focus();
    });
  }

  // Quick chips: clicking any chip halts agent speech immediately
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      stopAgentSpeaking('quick_chip_selected');
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

function startCallSession(preferredTest = null) {
  const phone = modalPhoneInput.value.trim() || '+91 98200 23456';
  isCallActive = true;
  useRestFallback = false;
  currentCallSid = null;
  modalCallStatus.textContent = 'Call Active • Connected to Dedicated Care Specialist';
  modalCallStatus.style.color = '#34d399';
  modalTranscriptFeed.innerHTML = '';
  checkCallerId(phone);

  // Initialize VAD & Speech Recognition
  startVoiceActivityDetection();
  if (recognition) {
    try {
      recognition.start();
    } catch (e) {
      // already active
    }
  }

  // Timer
  callDuration = 0;
  if (callTimerInterval) clearInterval(callTimerInterval);
  callTimerInterval = setInterval(() => {
    callDuration++;
    const mins = String(Math.floor(callDuration / 60)).padStart(2, '0');
    const secs = String(callDuration % 60).padStart(2, '0');
    modalTimer.textContent = `${mins}:${secs}`;
  }, 1000);

  // Attempt WebSocket first; seamlessly fall back to REST on serverless platforms
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
        appendSpeechBubble('Vinod (Virtual Lab Assistant)', msg.speech, 'agent');
        speakAudio(msg.speech);
      } else if (msg.type === 'agent_response') {
        appendSpeechBubble('Vinod (Virtual Lab Assistant)', msg.speech, 'agent');
        speakAudio(msg.speech);

        if (msg.intent === 'human_handover_ambiguity') {
          appendTransferCard('Senior Duty Medical Officer & Human Clinical Desk', 'Clinical Ambiguity / Nuance Detected', '+91 80 4388 8802');
        } else if (msg.intent === 'emergency_transfer') {
          appendTransferCard('Emergency Clinical Response Desk', 'Emergency Red-Flag Symptoms', '112 / +91 80 4388 8802');
        } else if (msg.intent === 'human_handover' || msg.intent === 'out_of_scope_transfer') {
          appendTransferCard('Senior Human Clinical Desk', 'Specialist Consultation Required', '+91 80 4388 8802');
        } else if (msg.intent === 'book_appointment_success') {
          appendConfirmationBadges(msg.extra || {});
        }

        if (msg.actions_taken && msg.actions_taken.length > 0) {
          modalActionText.textContent = msg.actions_taken[msg.actions_taken.length - 1];
          modalActionText.style.color = 'var(--text-muted)';
        }
      } else if (msg.type === 'agent_interrupted') {
        if (modalActionText) {
          modalActionText.textContent = `⚡ Agent speech paused — listening to you...`;
        }
      }
    };

    callSocket.onerror = () => {
      console.log('WebSocket not supported, switching to HTTP REST API');
      startRestCallSession(phone, preferredTest);
    };

    callSocket.onclose = () => {
      if (isCallActive && !useRestFallback) {
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
      appendSpeechBubble('Vinod (Virtual Lab Assistant)', data.speech, 'agent');
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
  stopAgentSpeaking('call_ended');
  stopVoiceActivityDetection();

  if (recognition) {
    try {
      recognition.stop();
    } catch (e) {}
  }

  if (callSocket && callSocket.readyState === WebSocket.OPEN) {
    callSocket.send(JSON.stringify({ type: 'hangup' }));
    callSocket.close();
  }
  modalCallStatus.textContent = 'Call Disconnected';
  modalCallStatus.style.color = '#ef4444';
  if (modalAudioState) {
    modalAudioState.textContent = 'Call Ended';
    modalAudioState.style.color = '#94a3b8';
  }
  showToast('Call ended. Your appointment & call summary have been saved.');
}

async function sendUserSpeechTurn() {
  const text = modalUserText.value.trim();
  if (!text) return;

  // Stop any lingering audio immediately
  stopAgentSpeaking('user_sent_speech');

  appendSpeechBubble('You', text, 'user');
  modalUserText.value = '';

  if (!useRestFallback && callSocket && callSocket.readyState === WebSocket.OPEN) {
    callSocket.send(JSON.stringify({
      type: 'user_speech',
      text: text
    }));
  } else {
    // REST turn fallback
    const phone = modalPhoneInput.value.trim() || '+91 98200 23456';
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
        appendSpeechBubble('Vinod (Virtual Lab Assistant)', data.speech, 'agent');
        speakAudio(data.speech);

        if (data.intent === 'human_handover_ambiguity') {
          appendTransferCard('Senior Duty Medical Officer & Human Clinical Desk', 'Clinical Ambiguity / Nuance Detected', '+91 80 4388 8802');
        } else if (data.intent === 'book_appointment_success') {
          appendConfirmationBadges(data.extra || {});
        }

        if (data.actions_taken && data.actions_taken.length > 0) {
          modalActionText.textContent = data.actions_taken[data.actions_taken.length - 1];
          modalActionText.style.color = 'var(--text-muted)';
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

function appendTransferCard(department, reason, phone) {
  const card = document.createElement('div');
  card.className = 'speech-transfer-card';
  card.innerHTML = `
    <div class="transfer-card-header">
      <span class="transfer-icon">📞</span>
      <strong>DIRECT CLINICAL TRANSFER INITIATED</strong>
    </div>
    <div class="transfer-card-body">
      <p><strong>Department:</strong> ${department}</p>
      <p><strong>Reason:</strong> ${reason}</p>
      <p><strong>Direct Line:</strong> <a href="tel:${phone}" style="color: #0284c7; font-weight: 700;">${phone}</a></p>
      <div class="transfer-pulse-bar"><span class="transfer-dot"></span> Connecting caller directly to Senior Human Medical Officer...</div>
    </div>
  `;
  modalTranscriptFeed.appendChild(card);
  modalTranscriptFeed.scrollTop = modalTranscriptFeed.scrollHeight;
}

function appendConfirmationBadges(extra) {
  const badgesRow = document.createElement('div');
  badgesRow.className = 'speech-confirmation-badges';
  badgesRow.innerHTML = `
    <span class="badge-notif-whatsapp">💬 WhatsApp Dispatched (${extra.whatsapp_dispatched || 'Active'})</span>
    <span class="badge-notif-gmail">✉️ Gmail Dispatched (${extra.gmail_dispatched || 'Active'})</span>
  `;
  modalTranscriptFeed.appendChild(badgesRow);
  modalTranscriptFeed.scrollTop = modalTranscriptFeed.scrollHeight;
}

// --- Text-to-Speech (Indian Male Virtual Lab Assistant: Vinod) ---
function pickIndianMaleVoice() {
  if (!('speechSynthesis' in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  // 1. Priority: Explicit Indian English Male Voice
  const inMale = voices.find(v => 
    (v.lang === 'en-IN' || v.lang.startsWith('en-IN') || v.name.includes('India')) &&
    (v.name.toLowerCase().includes('male') || v.name.toLowerCase().includes('ravi') || 
     v.name.toLowerCase().includes('prabhat') || v.name.toLowerCase().includes('madhav') || 
     v.name.toLowerCase().includes('mohan') || v.name.toLowerCase().includes('hemant'))
  );
  if (inMale) return inMale;

  // 2. Any Indian English voice
  const inAny = voices.find(v => v.lang === 'en-IN' || v.lang.startsWith('en-IN') || v.name.includes('India'));
  if (inAny) return inAny;

  // 3. High quality natural male English voice
  const maleEn = voices.find(v => v.lang.startsWith('en') && 
    (v.name.toLowerCase().includes('male') || v.name.toLowerCase().includes('david') || 
     v.name.toLowerCase().includes('george') || v.name.toLowerCase().includes('guy') || 
     v.name.toLowerCase().includes('natural') || v.name.toLowerCase().includes('google uk english male'))
  );
  if (maleEn) return maleEn;

  // 4. General English voice fallback
  return voices.find(v => v.lang.startsWith('en')) || voices[0];
}

// Ensure voices are loaded
if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    pickIndianMaleVoice();
  };
}

function speakAudio(text) {
  if (!isVoiceOutputEnabled || !('speechSynthesis' in window)) return;

  // Immediately cancel any previous audio
  window.speechSynthesis.cancel();

  const cleanSpeech = text.replace(/[*#_\[\]\(\)]/g, '').replace(/https?:\/\/\S+/g, '');
  const utterance = new SpeechSynthesisUtterance(cleanSpeech);

  // Calibrate acoustic parameters for Indian Male lab assistant (steady, warm, reassuring)
  utterance.rate = 0.98;
  utterance.pitch = 0.92;

  const chosenVoice = pickIndianMaleVoice();
  if (chosenVoice) {
    utterance.voice = chosenVoice;
  }

  utterance.onstart = () => {
    isAgentSpeaking = true;
    if (modalAudioState) {
      modalAudioState.textContent = 'Vinod is Speaking • Speak anytime to interrupt';
      modalAudioState.style.color = '#38bdf8';
    }
  };

  utterance.onend = () => {
    isAgentSpeaking = false;
    if (modalAudioState && isCallActive) {
      modalAudioState.textContent = 'Voice Audio Active (Listening to you)';
      modalAudioState.style.color = '#34d399';
    }
  };

  utterance.onerror = (e) => {
    isAgentSpeaking = false;
  };

  window.speechSynthesis.speak(utterance);
}

// --- Speech-to-Text (Microphone with Continuous Barge-In & Complete Speech Capture) ---
let speechDebounceTimer = null;
let accumulatedUserSpeech = '';

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    btnModalMic.style.display = 'none';
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = true;       // Keep listening during entire call
  recognition.interimResults = true;    // Instant phoneme / speech detection
  recognition.lang = 'en-IN';          // Indian English acoustic model

  recognition.onstart = () => {
    isRecording = true;
    btnModalMic.classList.add('recording');
  };

  // VAD: Instant speech start detected -> IMMEDIATELY STOP TTS!
  recognition.onspeechstart = () => {
    stopAgentSpeaking('speech_start_vad');
    if (modalAudioState) {
      modalAudioState.textContent = '🎤 Voice detected — Listening to you...';
      modalAudioState.style.color = '#34d399';
    }
  };

  recognition.onsoundstart = () => {
    stopAgentSpeaking('sound_start_vad');
  };

  recognition.onresult = (event) => {
    // 1. If agent is speaking, IMMEDIATELY STOP TTS with 0 latency
    stopAgentSpeaking('speech_in_progress');

    let interimTranscript = '';
    let finalChunk = '';

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalChunk += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }

    if (finalChunk.trim()) {
      accumulatedUserSpeech = (accumulatedUserSpeech + ' ' + finalChunk).trim();
    }

    const currentDisplay = (accumulatedUserSpeech + ' ' + interimTranscript).trim();
    if (currentDisplay) {
      modalUserText.value = currentDisplay;
      if (modalActionText) {
        modalActionText.textContent = `🎤 Listening to your complete query...`;
        modalActionText.style.color = '#34d399';
      }
    }

    // 2. Capture user's complete speech using intelligent silence debouncer (950ms)
    clearTimeout(speechDebounceTimer);
    speechDebounceTimer = setTimeout(() => {
      const completeQuery = (accumulatedUserSpeech || modalUserText.value || '').trim();
      if (completeQuery && completeQuery.length > 1) {
        accumulatedUserSpeech = '';
        modalUserText.value = completeQuery;
        if (modalAudioState) {
          modalAudioState.textContent = 'Processing speech with AI...';
          modalAudioState.style.color = '#38bdf8';
        }
        sendUserSpeechTurn();
      }
    }, 950);
  };

  recognition.onerror = (event) => {
    if (event.error !== 'no-speech') {
      console.log('Speech recognition notice:', event.error);
    }
  };

  recognition.onend = () => {
    isRecording = false;
    btnModalMic.classList.remove('recording');

    // If call is still active, automatically restart recognition so user never misses a turn
    if (isCallActive) {
      try {
        recognition.start();
      } catch (e) {}
    }
  };

  btnModalMic.addEventListener('click', () => {
    stopAgentSpeaking('mic_button_clicked');
    if (!isRecording) {
      try {
        recognition.start();
      } catch (e) {}
    } else {
      try {
        recognition.stop();
      } catch (e) {}
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
        if (isAgentSpeaking) {
          // Dynamic tall waves when agent is talking
          barHeight = Math.sin(t + i * 0.35) * 18 + Math.cos(t * 0.9 + i * 0.2) * 12 + 24;
        } else {
          // Gentle ambient listening ripples when listening to user
          barHeight = Math.sin(t * 0.6 + i * 0.2) * 6 + 10;
        }
      } else {
        barHeight = 4;
      }

      const x = i * (barWidth + 2);
      const y = (height - barHeight) / 2;

      const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
      if (isAgentSpeaking) {
        gradient.addColorStop(0, '#0170B9');
        gradient.addColorStop(1, '#38bdf8');
      } else {
        gradient.addColorStop(0, '#10b981');
        gradient.addColorStop(1, '#34d399');
      }

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
