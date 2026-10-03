// ==========================================================================
// APEX FAMILY DIAGNOSTIC LAB - VOICE AI PIPELINE FRONTEND
// Implements the End-to-End Voice Architecture:
// [User] ➔ [Audio Input Engine] ➔ [Streaming STT] ➔ [Conversation Engine]
// ➔ [LLM/Agent] ➔ [Question (RAG) vs Action (Agent Tools)] ➔ [Response Gen]
// ➔ [Streaming TTS] ➔ [Audio Output]
// Dedicated Indian Male Lab Assistant: Vinod (+91 80 4388 8802)
// Features Instant Barge-In Interruption & Real-Time Pipeline Visualizer
// ==========================================================================

let callSocket = null;
let isCallActive = false;
let callDuration = 0;
let callTimerInterval = null;
let isVoiceOutputEnabled = true;
let isRecording = false;
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
const modalAudioState = document.getElementById('modal-audio-state');
const modalWaveformCanvas = document.getElementById('modal-waveform-canvas');
const modalTranscriptFeed = document.getElementById('modal-transcript-feed');
const modalActionBar = document.getElementById('modal-action-bar');
const modalActionText = document.getElementById('modal-action-text');
const btnModalMic = document.getElementById('btn-modal-mic');
const modalUserText = document.getElementById('modal-user-text');
const btnModalSend = document.getElementById('btn-modal-send');
const btnModalInterrupt = document.getElementById('btn-modal-interrupt');
const btnModalVoiceToggle = document.getElementById('btn-modal-voice-toggle');
const bargeInBadge = document.getElementById('barge-in-badge');
const packagesContainer = document.getElementById('packages-container');

// Floating Live Chat Widget Elements
const floatingChatLauncher = document.getElementById('floating-chat-launcher');
const floatingChatWidget = document.getElementById('floating-chat-widget');
const btnChatClose = document.getElementById('btn-chat-close');
const headerChatTrigger = document.getElementById('header-chat-trigger');
const btnHeroChat = document.getElementById('btn-hero-chat');
const chatMessagesContainer = document.getElementById('chat-messages-container');
const chatTextInput = document.getElementById('chat-text-input');
const chatBtnSend = document.getElementById('chat-btn-send');
const btnChatVoiceToggle = document.getElementById('btn-chat-voice-toggle');
const chatVoiceIcon = document.getElementById('chat-voice-icon');
const btnChatOpenCall = document.getElementById('btn-chat-open-call');

// Visualizer nodes
const pipelineStatusBadge = document.getElementById('pipeline-status-badge');
const pipeUser = document.getElementById('pipe-user');
const pipeAudioEngine = document.getElementById('pipe-audio-engine');
const pipeSTT = document.getElementById('pipe-stt');
const pipeConvEngine = document.getElementById('pipe-conv-engine');
const pipeLLMAgent = document.getElementById('pipe-llm-agent');
const pipeBranch = document.getElementById('pipe-branch');
const pipeBranchTitle = document.getElementById('pipe-branch-title');
const pipeBranchDesc = document.getElementById('pipe-branch-desc');
const pipeRespGen = document.getElementById('pipe-resp-gen');
const pipeTTS = document.getElementById('pipe-tts');
const pipeOutput = document.getElementById('pipe-output');

// --- Toast System ---
function showToast(message) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ==========================================================================
// ARCHITECTURE COMPONENT: PIPELINE VISUALIZER
// ==========================================================================
class PipelineVisualizer {
  static resetAll() {
    [pipeUser, pipeAudioEngine, pipeSTT, pipeConvEngine, pipeLLMAgent, pipeBranch, pipeRespGen, pipeTTS, pipeOutput].forEach(el => {
      if (el) {
        el.className = 'pipeline-step';
      }
    });
    if (pipeBranchTitle) pipeBranchTitle.textContent = 'Question / Action';
    if (pipeBranchDesc) pipeBranchDesc.textContent = 'RAG or Tools';
    if (pipelineStatusBadge) {
      pipelineStatusBadge.textContent = 'Idle • Listening';
      pipelineStatusBadge.style.color = '#38bdf8';
    }
  }

  static showUserSpeaking() {
    this.resetAll();
    if (pipeUser) pipeUser.classList.add('active');
    if (pipeAudioEngine) pipeAudioEngine.classList.add('active');
    if (pipeSTT) pipeSTT.classList.add('active');
    if (pipelineStatusBadge) {
      pipelineStatusBadge.textContent = '🎤 User Speaking • VAD Active';
      pipelineStatusBadge.style.color = '#34d399';
    }
  }

  static showProcessing() {
    if (pipeConvEngine) pipeConvEngine.classList.add('active');
    if (pipeLLMAgent) pipeLLMAgent.classList.add('active');
    if (pipelineStatusBadge) {
      pipelineStatusBadge.textContent = '⚡ Conversation Engine & Agent Routing';
      pipelineStatusBadge.style.color = '#f59e0b';
    }
  }

  static showTrace(trace) {
    if (!trace) return;
    this.resetAll();

    if (pipeConvEngine) pipeConvEngine.classList.add('active');
    if (pipeLLMAgent) pipeLLMAgent.classList.add('active');
    if (pipeRespGen) pipeRespGen.classList.add('active');
    if (pipeTTS) pipeTTS.classList.add('active');
    if (pipeOutput) pipeOutput.classList.add('active');

    const category = trace.category || 'Action required';
    const component = trace.component || 'Tools';

    if (category === 'Question' || trace.route === 'RAG') {
      if (pipeBranch) {
        pipeBranch.className = 'pipeline-step highlight-rag';
      }
      if (pipeBranchTitle) pipeBranchTitle.textContent = 'RAG (Question)';
      if (pipeBranchDesc) pipeBranchDesc.textContent = component || 'Prep / SOPs';
      if (pipelineStatusBadge) {
        pipelineStatusBadge.textContent = `📚 RAG Router: ${component}`;
        pipelineStatusBadge.style.color = '#c084fc';
      }
    } else {
      if (pipeBranch) {
        pipeBranch.className = 'pipeline-step highlight-tools';
      }
      if (pipeBranchTitle) pipeBranchTitle.textContent = 'Agent Tools';
      if (pipeBranchDesc) pipeBranchDesc.textContent = component || 'Availability / Price';
      if (pipelineStatusBadge) {
        pipelineStatusBadge.textContent = `🛠️ Agent Tool: ${component}`;
        pipelineStatusBadge.style.color = '#34d399';
      }
    }
  }

  static showTTSPlaying() {
    if (pipeTTS) pipeTTS.classList.add('active');
    if (pipeOutput) pipeOutput.classList.add('active');
    if (pipelineStatusBadge) {
      pipelineStatusBadge.textContent = '🔊 Streaming TTS (Indian Male: Vinod)';
      pipelineStatusBadge.style.color = '#38bdf8';
    }
  }
}

// ==========================================================================
// ARCHITECTURE COMPONENT: STREAMING TTS ENGINE (SENTENCE-STREAMED AUDIO)
// Plays chunks on sentence boundaries with 0 latency and instant barge-in cancel
// ==========================================================================
class StreamingTTSEngine {
  constructor() {
    this.isSpeaking = false;
    this.sentenceQueue = [];
    this.activeUtterance = null;
    this.cachedVoice = null;
    this.generationId = 0;
    this.lastSpeakStartTime = 0;

    if ('speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = () => {
        this.cachedVoice = this.pickVoice();
      };
    }
  }

  pickVoice() {
    if (!('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    // 1. Explicit Indian English Male Voice
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

    // 3. Natural English male
    const maleEn = voices.find(v => v.lang.startsWith('en') && 
      (v.name.toLowerCase().includes('male') || v.name.toLowerCase().includes('david') || 
       v.name.toLowerCase().includes('george') || v.name.toLowerCase().includes('guy') || 
       v.name.toLowerCase().includes('natural') || v.name.toLowerCase().includes('google uk english male'))
    );
    if (maleEn) return maleEn;

    return voices.find(v => v.lang.startsWith('en')) || voices[0];
  }

  speak(text) {
    if (!isVoiceOutputEnabled || !('speechSynthesis' in window)) return;
    this.cancel();

    // Clean text and split into streaming sentence chunks
    const clean = text.replace(/[*#_\[\]\(\)]/g, '').replace(/https?:\/\/\S+/g, '').trim();
    if (!clean) return;

    // Split on sentence terminators (. ! ? or newline)
    const sentences = clean.match(/[^.!?\n]+[.!?\n]*/g) || [clean];
    this.sentenceQueue = sentences.map(s => s.trim()).filter(s => s.length > 0);

    this.playNextChunk();
  }

  playNextChunk() {
    const currentGen = this.generationId;
    if (this.sentenceQueue.length === 0 || this.generationId !== currentGen) {
      this.isSpeaking = false;
      if (modalAudioState && isCallActive) {
        modalAudioState.textContent = 'Voice Audio Active (Listening to you)';
        modalAudioState.style.color = '#34d399';
      }
      PipelineVisualizer.resetAll();
      return;
    }

    const chunk = this.sentenceQueue.shift();
    const utterance = new SpeechSynthesisUtterance(chunk);
    this.activeUtterance = utterance;

    // Calibrated Indian Male tone (warm, reassuring, clinical)
    utterance.rate = 0.98;
    utterance.pitch = 0.92;

    const voice = this.cachedVoice || this.pickVoice();
    if (voice) {
      utterance.voice = voice;
    }

    utterance.onstart = () => {
      if (this.generationId !== currentGen) {
        window.speechSynthesis.cancel();
        return;
      }
      this.isSpeaking = true;
      this.lastSpeakStartTime = Date.now();
      if (modalAudioState) {
        modalAudioState.textContent = 'Vinod is Speaking • Speak or type to interrupt';
        modalAudioState.style.color = '#38bdf8';
      }
      PipelineVisualizer.showTTSPlaying();
    };

    utterance.onend = () => {
      if (this.generationId === currentGen) {
        this.playNextChunk();
      }
    };

    utterance.onerror = (e) => {
      this.isSpeaking = false;
      if (this.generationId === currentGen) {
        this.playNextChunk();
      }
    };

    window.speechSynthesis.speak(utterance);
  }

  cancel() {
    this.generationId++;
    this.sentenceQueue = [];
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    this.isSpeaking = false;
    this.activeUtterance = null;
  }
}

const streamingTTS = new StreamingTTSEngine();

// Helper bridge
function speakAudio(text) {
  streamingTTS.speak(text);
}

// ==========================================================================
// ARCHITECTURE COMPONENT: AUDIO INPUT ENGINE
// Noise suppression • Echo cancellation • Hardware VAD • Turn detection
// ==========================================================================
class AudioInputEngine {
  constructor() {
    this.audioContext = null;
    this.analyser = null;
    this.micStream = null;
    this.vadThreshold = 0.035;
    this.animFrameId = null;
    this.isMonitoring = false;
  }

  async start() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
      if (!this.audioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.audioContext = new AudioCtx();
      }
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      // Enforce Echo Cancellation and Noise Suppression on Hardware Stream
      this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;
      const source = this.audioContext.createMediaStreamSource(this.micStream);
      source.connect(this.analyser);

      this.isMonitoring = true;
      const dataArray = new Uint8Array(this.analyser.frequencyBinCount);

      const checkEnergy = () => {
        if (!this.isMonitoring || !isCallActive) return;

        this.analyser.getByteTimeDomainData(dataArray);
        let sumSquares = 0.0;
        for (let i = 0; i < dataArray.length; i++) {
          const norm = (dataArray[i] - 128) / 128;
          sumSquares += norm * norm;
        }
        const rms = Math.sqrt(sumSquares / dataArray.length);

        // Hardware VAD: RMS energy drives waveform visualizer only.
        // It does NOT stop TTS to prevent acoustic feedback loops from laptop speakers.

        this.animFrameId = requestAnimationFrame(checkEnergy);
      };
      this.animFrameId = requestAnimationFrame(checkEnergy);
    } catch (err) {
      console.log('AudioInputEngine Notice:', err);
    }
  }

  stop() {
    this.isMonitoring = false;
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.micStream) {
      this.micStream.getTracks().forEach(t => t.stop());
      this.micStream = null;
    }
  }
}

const audioInputEngine = new AudioInputEngine();

// ==========================================================================
// ARCHITECTURE COMPONENT: STREAMING STT ENGINE (Speech → Text)
// Real-time continuous recognition with turn completion debouncing
// ==========================================================================
class STTEngine {
  constructor() {
    this.recognition = null;
    this.speechDebounceTimer = null;
    this.accumulatedSpeech = '';
    this.init();
  }

  init() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (btnModalMic) btnModalMic.style.display = 'none';
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = 'en-IN'; // Indian English acoustic profile

    this.recognition.onstart = () => {
      isRecording = true;
      if (btnModalMic) btnModalMic.classList.add('recording');
    };

    // Instant speech start detection -> with Echo Guard
    this.recognition.onspeechstart = () => {
      const isAgentActive = streamingTTS.isSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking);
      // Echo Guard: If the agent is speaking or started speaking recently (<1.5s), don't trigger false barge-in
      if (isAgentActive && (Date.now() - streamingTTS.lastSpeakStartTime < 1500)) {
        return; // Ignore speaker output echo
      }
      PipelineVisualizer.showUserSpeaking();
      if (modalAudioState) {
        modalAudioState.textContent = '🎤 Voice detected — Listening to you...';
        modalAudioState.style.color = '#34d399';
      }
    };

    this.recognition.onsoundstart = () => {
      // Do NOT interrupt on raw sound detection (room noise, fan, or speaker bleed triggers soundstart)
    };

    this.recognition.onresult = (event) => {
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
        this.accumulatedSpeech = (this.accumulatedSpeech + ' ' + finalChunk).trim();
      }

      const display = (this.accumulatedSpeech + ' ' + interimTranscript).trim();

      // Intentional speech barge-in: Only interrupt when user speaks actual words with sufficient length
      const isAgentActive = streamingTTS.isSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking);
      if (isAgentActive && display.length >= 3 && (Date.now() - streamingTTS.lastSpeakStartTime > 800)) {
        stopAgentSpeaking('stt_user_words');
      }

      PipelineVisualizer.showUserSpeaking();

      if (display && modalUserText) {
        modalUserText.value = display;
        if (modalActionText) {
          modalActionText.textContent = `🎤 Listening to your complete query...`;
          modalActionText.style.color = '#34d399';
        }
      }

      // Intelligent Turn Detection: Gather complete speech until user finishes (950ms silence)
      clearTimeout(this.speechDebounceTimer);
      this.speechDebounceTimer = setTimeout(() => {
        const complete = (this.accumulatedSpeech || (modalUserText ? modalUserText.value : '')).trim();
        if (complete && complete.length > 1) {
          this.accumulatedSpeech = '';
          if (modalUserText) modalUserText.value = complete;
          PipelineVisualizer.showProcessing();
          if (modalAudioState) {
            modalAudioState.textContent = 'Processing speech with AI...';
            modalAudioState.style.color = '#38bdf8';
          }
          sendUserSpeechTurn();
        }
      }, 950);
    };

    this.recognition.onerror = (e) => {
      if (e.error !== 'no-speech') {
        console.log('STT notice:', e.error);
      }
    };

    this.recognition.onend = () => {
      isRecording = false;
      if (btnModalMic) btnModalMic.classList.remove('recording');
      if (isCallActive) {
        try {
          this.recognition.start();
        } catch (e) {}
      }
    };
  }

  start() {
    if (this.recognition) {
      try {
        this.recognition.start();
      } catch (e) {}
    }
  }

  stop() {
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {}
    }
  }
}

const sttEngine = new STTEngine();

// ==========================================================================
// USER SPEECH DETECTOR (ZERO-LATENCY BARGE-IN INTERRUPTION ENGINE)
// Architecture Diagram:
//          USER SPEECH DETECTOR
//                   │
//                   ▼
//        User starts speaking?
//                   │
//                  YES
//                   │
//                   ▼
//        IMMEDIATELY STOP TTS
//                   │
//                   ▼
//         CANCEL AI AUDIO
//                   │
//                   ▼
//          LISTEN TO USER
// ==========================================================================
class UserSpeechDetector {
  constructor() {
    this.isUserSpeaking = false;
    this.interruptionCount = 0;
    this.lastInterruptTimestamp = 0;
  }

  // Triggered when: User starts speaking? -> YES
  onUserStartsSpeaking(source = 'vad_mic_energy') {
    // Guard against false positive interruptions from ambient noise or speaker bleed
    if (source === 'mic_voice_energy_vad' || source === 'stt_sound_start') {
      return;
    }
    // Echo guard: if agent started speaking < 1200ms ago, ignore speech start echo from speakers
    if (source === 'stt_speech_start' && (Date.now() - streamingTTS.lastSpeakStartTime < 1200)) {
      return;
    }

    const isAiSpeaking = streamingTTS.isSpeaking || 
                         (window.speechSynthesis && window.speechSynthesis.speaking) ||
                         this.isAnyAudioPlaying();

    this.isUserSpeaking = true;
    this.interruptionCount++;
    this.lastInterruptTimestamp = Date.now();

    console.log(`[USER SPEECH DETECTOR] User speech detected (${source}). AI Active: ${isAiSpeaking}`);

    // STEP 1: IMMEDIATELY STOP TTS
    this.immediatelyStopTTS();

    // STEP 2: CANCEL AI AUDIO
    this.cancelAiAudio(source);

    // STEP 3: LISTEN TO USER
    this.listenToUser(source);
  }

  // 1. IMMEDIATELY STOP TTS
  immediatelyStopTTS() {
    streamingTTS.cancel();
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }

  // 2. CANCEL AI AUDIO
  cancelAiAudio(source) {
    // Pause & reset any active HTML5 audio or media playback on the page
    document.querySelectorAll('audio, video').forEach(media => {
      try {
        media.pause();
        media.currentTime = 0;
      } catch (e) {}
    });

    // Notify server via WebSocket to halt server-side generation
    if (!useRestFallback && callSocket && callSocket.readyState === WebSocket.OPEN) {
      callSocket.send(JSON.stringify({
        type: 'user_interrupt',
        reason: source,
        timestamp: Date.now()
      }));
    }
  }

  // 3. LISTEN TO USER
  listenToUser(source) {
    // Update live Audio State in UI
    if (modalAudioState) {
      modalAudioState.textContent = '⚡ Vinod Paused (Barge-In Active) • Listening to you...';
      modalAudioState.style.color = '#f59e0b';
    }
    if (modalActionText) {
      modalActionText.textContent = `⚡ AI Audio Cancelled (${source}) — Listening to your complete query...`;
      modalActionText.style.color = '#f59e0b';
    }

    // Trigger visualizer state
    PipelineVisualizer.showUserSpeaking();

    // Animate the 4 steps of the User Speech Detector Circuit
    const detUser = document.getElementById('det-user-starts');
    const detStop = document.getElementById('det-stop-tts');
    const detCancel = document.getElementById('det-cancel-audio');
    const detListen = document.getElementById('det-listen-user');

    if (detUser && detStop && detCancel && detListen) {
      detUser.classList.add('flashing');
      setTimeout(() => detStop.classList.add('flashing'), 80);
      setTimeout(() => detCancel.classList.add('flashing'), 160);
      setTimeout(() => detListen.classList.add('flashing'), 240);
      setTimeout(() => {
        [detUser, detStop, detCancel, detListen].forEach(el => el && el.classList.remove('flashing'));
      }, 2000);
    }

    // Mark interrupted agent bubble in transcript feed
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
        const speakerEl = lastBubble.querySelector('.bubble-speaker');
        if (speakerEl) speakerEl.appendChild(tag);
      }
    }
  }

  isAnyAudioPlaying() {
    const audioElements = document.querySelectorAll('audio');
    for (const a of audioElements) {
      if (!a.paused && a.currentTime > 0) return true;
    }
    return false;
  }
}

const userSpeechDetector = new UserSpeechDetector();

function stopAgentSpeaking(reason = 'user_speaking') {
  userSpeechDetector.onUserStartsSpeaking(reason);
}

// ==========================================================================
// CALL SESSION ENGINE (WEBSOCKET WITH REST FALLBACK)
// ==========================================================================
let currentCallSid = null;
let useRestFallback = false;

function startCallSession(preferredTest = null) {
  const phone = modalPhoneInput.value.trim() || '+91 98200 23456';
  isCallActive = true;
  useRestFallback = false;
  currentCallSid = null;
  modalCallStatus.textContent = 'Call Active • Connected to Vinod (+91 80 4388 8802)';
  modalCallStatus.style.color = '#34d399';
  modalTranscriptFeed.innerHTML = '';
  checkCallerId(phone);

  audioInputEngine.start();
  sttEngine.start();
  PipelineVisualizer.resetAll();

  callDuration = 0;
  if (callTimerInterval) clearInterval(callTimerInterval);
  callTimerInterval = setInterval(() => {
    callDuration++;
    const mins = String(Math.floor(callDuration / 60)).padStart(2, '0');
    const secs = String(callDuration % 60).padStart(2, '0');
    modalTimer.textContent = `${mins}:${secs}`;
  }, 1000);

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

        // Update Architecture Visualizer with real-time pipeline trace!
        const trace = (msg.extra && msg.extra.pipeline_trace) ? msg.extra.pipeline_trace : msg.pipeline_trace;
        if (trace) {
          PipelineVisualizer.showTrace(trace);
        }

        if (msg.intent === 'human_handover_ambiguity') {
          appendTransferCard('Senior Duty Medical Officer & Human Clinical Desk', 'Clinical Ambiguity / Nuance Detected', '+91 80 4388 8802');
        } else if (msg.intent === 'emergency_transfer') {
          appendTransferCard('Emergency Clinical Response Desk', 'Emergency Red-Flag Symptoms', '112 / +91 80 4388 8802');
        } else if (msg.intent === 'human_handover' || msg.intent === 'out_of_scope_transfer') {
          appendTransferCard('Senior Human Clinical Desk', 'Specialist Consultation Required', '+91 80 4388 8802');
        } else if (msg.intent === 'check_availability_slots' || (msg.extra && msg.extra.slots)) {
          appendSlotSelectionCards(msg.extra.slots || [], msg.extra.test_name);
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
      console.log('WebSocket notice, using HTTP REST API');
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
  audioInputEngine.stop();
  sttEngine.stop();
  PipelineVisualizer.resetAll();

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

  stopAgentSpeaking('user_sent_speech');
  appendSpeechBubble('You', text, 'user');
  modalUserText.value = '';
  modalUserText.focus();
  PipelineVisualizer.showProcessing();

  if (!useRestFallback && callSocket && callSocket.readyState === WebSocket.OPEN) {
    callSocket.send(JSON.stringify({
      type: 'user_speech',
      text: text
    }));
  } else {
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

        const trace = (data.extra && data.extra.pipeline_trace) ? data.extra.pipeline_trace : data.pipeline_trace;
        if (trace) {
          PipelineVisualizer.showTrace(trace);
        }

        if (data.intent === 'human_handover_ambiguity') {
          appendTransferCard('Senior Duty Medical Officer & Human Clinical Desk', 'Clinical Ambiguity / Nuance Detected', '+91 80 4388 8802');
        } else if (data.intent === 'check_availability_slots' || (data.extra && data.extra.slots)) {
          appendSlotSelectionCards(data.extra.slots || [], data.extra.test_name);
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

function appendSlotSelectionCards(slots, testName) {
  if (!slots || slots.length === 0) return;
  const card = document.createElement('div');
  card.className = 'speech-slot-selection-box';
  card.style.margin = '10px 0';
  card.style.background = '#ffffff';
  card.style.border = '1px solid #bae6fd';
  card.style.borderRadius = '10px';
  card.style.padding = '12px';
  card.style.boxShadow = '0 2px 8px rgba(2, 132, 199, 0.08)';

  card.innerHTML = `
    <div style="font-size: 0.85rem; font-weight: 700; color: #0369a1; margin-bottom: 8px;">
      📅 Available Slots in Database (Tap to Choose or Speak):
    </div>
    <div style="display: flex; gap: 10px;">
      ${slots.map(s => `
        <button type="button" onclick="selectSlot('${s.slot_label}')" style="flex: 1; padding: 10px 8px; border-radius: 8px; border: 1.5px solid #0284c7; background: #f0f9ff; cursor: pointer; text-align: center; font-family: inherit;">
          <div style="font-weight: 700; font-size: 0.95rem; color: #0369a1;">${s.slot_label}</div>
          <div style="font-size: 0.75rem; color: #64748b; margin: 2px 0;">${s.time_slot}</div>
          <div style="font-size: 1.05rem; font-weight: 800; color: #059669;">${s.price_formatted}</div>
        </button>
      `).join('')}
    </div>
  `;
  modalTranscriptFeed.appendChild(card);
  modalTranscriptFeed.scrollTop = modalTranscriptFeed.scrollHeight;
}

window.selectSlot = function(slotLabel) {
  stopAgentSpeaking('slot_selected_click');
  modalUserText.value = `${slotLabel} please`;
  sendUserSpeechTurn();
};

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

  modalUserText.addEventListener('input', () => {
    if (streamingTTS.isSpeaking || (window.speechSynthesis && window.speechSynthesis.speaking)) {
      stopAgentSpeaking('user_typing');
    }
  });

  if (btnModalInterrupt) {
    btnModalInterrupt.addEventListener('click', () => {
      stopAgentSpeaking('manual_interrupt_button');
      modalUserText.focus();
    });
  }

  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      stopAgentSpeaking('quick_chip_selected');
      modalUserText.value = chip.dataset.speak;
      sendUserSpeechTurn();
    });
  });

  if (btnModalMic) {
    btnModalMic.addEventListener('click', () => {
      stopAgentSpeaking('mic_button_clicked');
      if (!isRecording) {
        sttEngine.start();
      } else {
        sttEngine.stop();
      }
    });
  }
}

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
        if (streamingTTS.isSpeaking) {
          barHeight = Math.sin(t + i * 0.35) * 18 + Math.cos(t * 0.9 + i * 0.2) * 12 + 24;
        } else {
          barHeight = Math.sin(t * 0.6 + i * 0.2) * 6 + 10;
        }
      } else {
        barHeight = 4;
      }

      const x = i * (barWidth + 2);
      const y = (height - barHeight) / 2;

      ctx.fillStyle = isCallActive && streamingTTS.isSpeaking ? '#38bdf8' : '#334155';
      ctx.fillRect(x, y, barWidth, barHeight);
    }
    canvasAnimId = requestAnimationFrame(renderWaveform);
  }
  renderWaveform();
}

function initFAQAccordion() {
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    question.addEventListener('click', () => {
      const isOpen = item.classList.contains('open');
      faqItems.forEach(i => i.classList.remove('open'));
      if (!isOpen) {
        item.classList.add('open');
      }
    });
  });
}

async function loadHealthPackages() {
  if (!packagesContainer) return;
  try {
    const res = await fetch('/api/packages');
    if (res.ok) {
      const packages = await res.json();
      packagesContainer.innerHTML = packages.map(pkg => `
        <div class="package-card">
          <div class="pkg-header">
            <h4>${pkg.package_name}</h4>
            <span class="pkg-category">${pkg.category || 'Comprehensive'}</span>
          </div>
          <p class="pkg-desc">${pkg.description}</p>
          <div class="pkg-pricing">
            <span class="price-discounted">₹${intOrVal(pkg.discounted_price)}</span>
            <span class="price-original">₹${intOrVal(pkg.price)}</span>
          </div>
          <div class="pkg-meta">
            <span>✓ ${pkg.test_codes.length} Parameters</span>
            <span>✓ ${pkg.fasting_required ? 'Fasting Required' : 'No Fasting'}</span>
          </div>
          <button class="btn-book-pkg" onclick="openCallModal('${pkg.package_name}')">
            Book via Vinod (+91 80 4388 8802)
          </button>
        </div>
      `).join('');
    }
  } catch (err) {
    console.log('Failed to load packages:', err);
  }
}

function intOrVal(v) {
  return typeof v === 'number' ? Math.round(v) : v;
}

// ==========================================================================
// FLOATING LIVE CHAT & TYPING CONVERSATION ENGINE
// ==========================================================================
let chatSessionSid = null;
let currentChatPhone = '+91 98200 23456';

function toggleChatWidget(show) {
  if (show) {
    if (floatingChatWidget) floatingChatWidget.style.display = 'flex';
    if (floatingChatLauncher) floatingChatLauncher.style.display = 'none';
    if (chatTextInput) {
      setTimeout(() => chatTextInput.focus(), 120);
    }
  } else {
    if (floatingChatWidget) floatingChatWidget.style.display = 'none';
    if (floatingChatLauncher) floatingChatLauncher.style.display = 'flex';
  }
}

function toggleVoiceOutput() {
  isVoiceOutputEnabled = !isVoiceOutputEnabled;
  if (!isVoiceOutputEnabled) {
    streamingTTS.cancel();
    if (btnChatVoiceToggle) btnChatVoiceToggle.innerHTML = '🔇 Voice Off';
    if (btnModalVoiceToggle) {
      btnModalVoiceToggle.innerHTML = '🔇 Voice Off';
      btnModalVoiceToggle.classList.add('muted');
    }
    showToast('Voice output muted. You can type and converse silently.');
  } else {
    if (btnChatVoiceToggle) btnChatVoiceToggle.innerHTML = '🔊 Voice On';
    if (btnModalVoiceToggle) {
      btnModalVoiceToggle.innerHTML = '🔊 Voice On';
      btnModalVoiceToggle.classList.remove('muted');
    }
    showToast('Voice output enabled.');
  }
}

function appendChatMessageBubble(sender, text, type, extra = {}) {
  if (!chatMessagesContainer) return;

  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-msg ${type}`;

  const avatar = type === 'user' ? 'ME' : 'VN';

  let slotsHtml = '';
  const slots = (extra.extra && extra.extra.slots) ? extra.extra.slots : (extra.slots || []);
  if (slots.length > 0) {
    slotsHtml = `
      <div style="margin-top: 10px; padding: 10px; background: #ffffff; border: 1.5px solid #bae6fd; border-radius: 8px;">
        <div style="font-size: 0.76rem; font-weight: 700; color: #0369a1; margin-bottom: 6px;">📅 Choose a Slot:</div>
        <div style="display: flex; gap: 8px;">
          ${slots.map(s => `
            <button type="button" onclick="selectChatSlot('${s.slot_label}')" style="flex: 1; padding: 8px 6px; border: 1.5px solid #0284c7; background: #f0f9ff; border-radius: 6px; cursor: pointer; text-align: center; font-family: inherit;">
              <div style="font-weight: 700; font-size: 0.88rem; color: #0369a1;">${s.slot_label}</div>
              <div style="font-size: 0.7rem; color: #64748b;">${s.time_slot}</div>
              <div style="font-size: 0.95rem; font-weight: 800; color: #059669;">${s.price_formatted}</div>
            </button>
          `).join('')}
        </div>
      </div>
    `;
  }

  let bookingHtml = '';
  const intentName = extra.intent || (extra.extra && extra.extra.intent);
  if (intentName === 'book_appointment_success' || (extra.extra && extra.extra.appointment_id)) {
    const ex = extra.extra || extra;
    bookingHtml = `
      <div style="margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap;">
        <span class="badge-notif-whatsapp">💬 WhatsApp Dispatched (${ex.whatsapp_dispatched || 'Active'})</span>
        <span class="badge-notif-gmail">✉️ Gmail Dispatched (${ex.gmail_dispatched || 'Active'})</span>
      </div>
    `;
  }

  let handoverHtml = '';
  if (intentName === 'human_handover_ambiguity' || intentName === 'human_handover' || (extra.extra && extra.extra.ambiguity_detected)) {
    handoverHtml = `
      <div style="margin-top: 8px; padding: 8px 10px; background: #fffbeb; border-left: 3px solid #f59e0b; border-radius: 4px; font-size: 0.76rem; color: #78350f;">
        <strong>Clinical Specialist Desk:</strong> Direct transfer to Senior Duty Medical Officer at <a href="tel:+918043888802" style="font-weight: 700; color: #0284c7;">+91 80 4388 8802</a>.
      </div>
    `;
  }

  msgDiv.innerHTML = `
    <div class="chat-msg-avatar">${avatar}</div>
    <div class="chat-msg-content">
      <div class="chat-msg-sender">${sender}</div>
      <div class="chat-msg-text">${text.replace(/\n/g, '<br>')}</div>
      ${slotsHtml}
      ${bookingHtml}
      ${handoverHtml}
    </div>
  `;

  chatMessagesContainer.appendChild(msgDiv);
  chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

window.selectChatSlot = function(slotLabel) {
  sendChatMessage(`${slotLabel} please`);
};

async function sendChatMessage(customText) {
  const text = (customText !== undefined ? customText : (chatTextInput ? chatTextInput.value : '')).trim();
  if (!text) return;

  stopAgentSpeaking('user_typing_chat');
  appendChatMessageBubble('You', text, 'user');
  if (chatTextInput) chatTextInput.value = '';

  if (!chatSessionSid) {
    chatSessionSid = 'CHAT-' + Date.now();
  }

  // Show typing indicator in chat
  const typingIndicator = document.createElement('div');
  typingIndicator.className = 'chat-msg agent typing-indicator-msg';
  typingIndicator.innerHTML = `
    <div class="chat-msg-avatar">VN</div>
    <div class="chat-msg-content" style="font-style: italic; color: #64748b;">
      Vinod is typing...
    </div>
  `;
  if (chatMessagesContainer) {
    chatMessagesContainer.appendChild(typingIndicator);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
  }

  try {
    const res = await fetch('/api/telephony/chat-turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        call_sid: chatSessionSid,
        caller_phone: currentChatPhone,
        text: text
      })
    });

    if (typingIndicator) typingIndicator.remove();

    if (res.ok) {
      const data = await res.json();
      appendChatMessageBubble('Vinod (Lab Assistant)', data.speech, 'agent', data);
      
      // If voice is enabled, speak Vinod's response
      if (isVoiceOutputEnabled) {
        speakAudio(data.speech);
      }
    }
  } catch (err) {
    if (typingIndicator) typingIndicator.remove();
    console.error('Chat turn failed:', err);
    appendChatMessageBubble('Vinod (Lab Assistant)', 'I apologize, but I had trouble processing that. Please try again or call me directly at +91 80 4388 8802.', 'agent');
  }
}

function initChatWidgetListeners() {
  if (floatingChatLauncher) {
    floatingChatLauncher.addEventListener('click', () => toggleChatWidget(true));
  }
  if (btnChatClose) {
    btnChatClose.addEventListener('click', () => toggleChatWidget(false));
  }
  if (headerChatTrigger) {
    headerChatTrigger.addEventListener('click', () => toggleChatWidget(true));
  }
  if (btnHeroChat) {
    btnHeroChat.addEventListener('click', () => toggleChatWidget(true));
  }

  if (chatBtnSend && chatTextInput) {
    chatBtnSend.addEventListener('click', () => sendChatMessage());
    chatTextInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  if (btnChatVoiceToggle) {
    btnChatVoiceToggle.addEventListener('click', toggleVoiceOutput);
  }
  if (btnModalVoiceToggle) {
    btnModalVoiceToggle.addEventListener('click', toggleVoiceOutput);
  }

  if (btnChatOpenCall) {
    btnChatOpenCall.addEventListener('click', () => {
      toggleChatWidget(false);
      openCallModal();
    });
  }

  document.querySelectorAll('.chat-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const msg = chip.dataset.msg;
      sendChatMessage(msg);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initCallTriggers();
  initChatWidgetListeners();
  initFAQAccordion();
  initModalVisualizer();
  loadHealthPackages();
});

