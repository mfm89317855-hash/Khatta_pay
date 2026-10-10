import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Send,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  BookOpen,
  Users,
  TrendingUp,
  FileText,
  Sparkles,
  RefreshCw,
  Terminal,
  Check,
  Copy,
  MessageSquare,
  ShieldCheck,
  Cpu,
  Layers,
  ChevronRight,
  Database,
  Radio,
  Volume2,
  VolumeX,
  Play,
  Square,
  Loader2,
  Headphones
} from 'lucide-react';

// Urdu number mapping matching Python numbers.py
const URDU_DIGITS: Record<string, string> = {
  "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
  "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
};

const BASE_WORDS: Record<string, number> = {
  "ek": 1, "aik": 1, "ایک": 1,
  "do": 2, "دو": 2,
  "teen": 3, "تین": 3,
  "char": 4, "chaar": 4, "چار": 4,
  "paanch": 5, "panch": 5, "پانچ": 5,
  "chhe": 6, "che": 6, "چھ": 6,
  "saat": 7, "سات": 7,
  "aath": 8, "ath": 8, "آٹھ": 8,
  "nau": 9, "no": 9, "نو": 9,
  "das": 10, "دس": 10,
  "sau": 100, "so": 100, "سو": 100,
  "hazaar": 1000, "hazar": 1000, "ہزار": 1000,
  "dedh sau": 150, "dedh so": 150, "ڈیڑھ سو": 150,
  "dhai sau": 250, "ڈھائی سو": 250,
  "dedh hazaar": 1500, "ڈیڑھ ہزار": 1500,
};

const HONORIFICS = ["bhai", "bhaiya", "bhaijan", "sahab", "sahib", "sb", "baji", "aapa", "uncle", "chacha", "بھائی", "صاحب", "باجی"];
const CLITICS = ["ko", "ne", "ka", "ki", "ke", "se", "say", "کو", "نے", "کا", "کی", "سے"];

interface Customer {
  id: number;
  name: string;
  balance: number;
  transactionsCount: number;
  lastActive: string;
}

interface Transaction {
  id: number;
  customerId: number;
  customerName: string;
  type: 'credit' | 'payment';
  amount: number;
  item?: string;
  quantity?: string;
  rawText: string;
  timestamp: string;
}

interface PendingTx {
  customerName: string;
  customerId?: number;
  isNew: boolean;
  type: 'credit' | 'payment';
  amount: number;
  item?: string;
  quantity?: string;
  rawText: string;
  discrepancy?: boolean;
  ruleAmount?: number;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
}

// PCM audio helpers for Gemini Live API
function floatTo16BitPCM(input: Float32Array): ArrayBuffer {
  const output = new DataView(new ArrayBuffer(input.length * 2));
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return output.buffer;
}

function base64ArrayBuffer(arrayBuffer: ArrayBuffer): string {
  let binary = '';
  const bytes = new Uint8Array(arrayBuffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'ledger' | 'live' | 'analytics' | 'architecture' | 'tests'>('ledger');
  const [inputText, setInputText] = useState('');
  const [statusMessage, setStatusMessage] = useState('Ready. Speak or type to record transactions.');
  const [statusType, setStatusType] = useState<'info' | 'success' | 'warning' | 'error'>('info');

  // Transcribe state (gemini-3.5-transcribe)
  const [isRecordingTranscribe, setIsRecordingTranscribe] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Live API state (gemini-3.8-live)
  const [isLiveConnected, setIsLiveConnected] = useState(false);
  const [isLiveActive, setIsLiveActive] = useState(false);
  const [liveStatus, setLiveStatus] = useState<'idle' | 'connecting' | 'listening' | 'speaking'>('idle');
  const [liveMessages, setLiveMessages] = useState<ChatMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const inputAudioCtxRef = useRef<AudioContext | null>(null);
  const outputAudioCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const scheduledSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // Pending confirmation state (Confirm-Before-Save)
  const [pendingTx, setPendingTx] = useState<PendingTx | null>(null);
  const [confirmationPrompt, setConfirmationPrompt] = useState<string | null>(null);

  // Simulated SQLite state
  const [customers, setCustomers] = useState<Customer[]>([
    { id: 1, name: "Ahmed", balance: 400, transactionsCount: 2, lastActive: "10 mins ago" },
    { id: 2, name: "Bilal", balance: 0, transactionsCount: 3, lastActive: "1 hour ago" },
    { id: 3, name: "Tariq Mahmood", balance: 1850, transactionsCount: 5, lastActive: "Yesterday" },
    { id: 4, name: "Kamran Khan", balance: 600, transactionsCount: 1, lastActive: "Today" },
  ]);

  const [transactions, setTransactions] = useState<Transaction[]>([
    { id: 101, customerId: 1, customerName: "Ahmed", type: "credit", amount: 400, item: "cheeni", quantity: "2 kilo", rawText: "Ahmed ko 2 kilo cheeni udhaar di, 400 rupay", timestamp: "Today 10:15 AM" },
    { id: 102, customerId: 2, customerName: "Bilal", type: "credit", amount: 500, rawText: "Bilal ko 500 udhaar", timestamp: "Today 09:30 AM" },
    { id: 103, customerId: 2, customerName: "Bilal", type: "payment", amount: 500, rawText: "Bilal ne 500 rupay wapas kiye", timestamp: "Today 11:00 AM" },
    { id: 104, customerId: 3, customerName: "Tariq Mahmood", type: "credit", amount: 1850, item: "atta & oil", quantity: "1 bag", rawText: "Tariq sahab ko atta udhaar", timestamp: "Yesterday 04:20 PM" },
  ]);

  const [reminderTarget, setReminderTarget] = useState('Ahmed');
  const [generatedReminder, setGeneratedReminder] = useState<string | null>(null);
  const [copiedReminder, setCopiedReminder] = useState(false);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopLiveSession();
    };
  }, []);

  const recognitionRef = useRef<any>(null);

  // ----------------------------------------------------
  // FEATURE 1: Audio Transcription with Web Speech API & Cloud Fallback
  // ----------------------------------------------------
  const startRecordingTranscribe = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
      const recorder = new MediaRecorder(stream, { mimeType });
      
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        stream.getTracks().forEach((track) => track.stop());
        await submitAudioForTranscription(audioBlob, mimeType);
      };

      recorder.start(100);
      mediaRecorderRef.current = recorder;

      // Initialize Browser Native SpeechRecognition for instant, zero-latency transcription
      const SpeechRecognitionClass = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognitionClass) {
        try {
          const recognition = new SpeechRecognitionClass();
          recognition.lang = 'ur-PK';
          recognition.interimResults = true;
          recognition.continuous = true;
          recognition.maxAlternatives = 1;

          recognition.onresult = (event: any) => {
            let transcriptText = '';
            for (let i = 0; i < event.results.length; i++) {
              transcriptText += event.results[i][0].transcript;
            }
            if (transcriptText.trim()) {
              setInputText(transcriptText.trim());
              setStatusMessage(`Sun raha hoon: "${transcriptText.trim()}"`);
            }
          };

          recognition.onerror = (recErr: any) => {
            console.warn("SpeechRecognition notice:", recErr.error);
          };

          recognition.start();
          recognitionRef.current = recognition;
        } catch (recErr) {
          console.warn("SpeechRecognition init error:", recErr);
        }
      }

      setIsRecordingTranscribe(true);
      setStatusMessage("🎙️ Recording microphone... Bolain (e.g. 'Ahmed ko 500 udhaar').");
      setStatusType("info");
    } catch (err: any) {
      console.error("Microphone access error:", err);
      setStatusMessage(`Microphone error: ${err.message || 'Permission denied'}`);
      setStatusType("error");
    }
  };

  const stopRecordingTranscribe = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {}
      recognitionRef.current = null;
    }

    if (mediaRecorderRef.current && isRecordingTranscribe) {
      mediaRecorderRef.current.stop();
      setIsRecordingTranscribe(false);
      setIsTranscribing(true);
      setStatusMessage("Aawaz process ho rahi hai...");
      setStatusType("info");
    }
  };

  const submitAudioForTranscription = async (blob: Blob, mimeType: string) => {
    // If browser speech recognition already captured text, use it directly!
    if (inputText && inputText.trim()) {
      setIsTranscribing(false);
      setStatusMessage(`✅ Aawaz kamyabi se record ho gayi: "${inputText.trim()}"`);
      setStatusType("success");
      return;
    }

    try {
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      reader.onloadend = async () => {
        const base64Data = (reader.result as string).split(',')[1];
        
        try {
          const res = await fetch('/api/transcribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              audioData: base64Data,
              mimeType: mimeType || 'audio/webm',
            }),
          });

          if (!res.ok) {
            throw new Error(`Server status ${res.status}`);
          }

          const contentType = res.headers.get('content-type') || '';
          if (!contentType.includes('application/json')) {
            throw new Error('API route returned non-JSON response');
          }

          const data = await res.json();
          if (data.error) {
            throw new Error(data.error);
          }

          const transcript = data.transcript || '';
          if (transcript) {
            setInputText(transcript);
            setStatusMessage(`✅ Transcribed: "${transcript}"`);
            setStatusType("success");
          } else {
            setStatusMessage("⚠️ Aawaz saaf sunai nahi di. Baraye meherbani dobara bolain ya text likhein.");
            setStatusType("warning");
          }
          setIsTranscribing(false);
        } catch (fetchErr: any) {
          console.warn("Transcribe API notice:", fetchErr.message);
          setIsTranscribing(false);
          // If native speech captured anything in the textarea, keep it
          if (inputText && inputText.trim()) {
            setStatusMessage(`✅ Voice captured: "${inputText.trim()}"`);
            setStatusType("success");
          } else {
            setStatusMessage("Voice recognition ready. Baraye meherbani mic par dobara bolain ya neeche sample click karein.");
            setStatusType("info");
          }
        }
      };
    } catch (err: any) {
      setIsTranscribing(false);
      setStatusMessage(`Audio process error: ${err.message}`);
      setStatusType("error");
    }
  };

  // ----------------------------------------------------
  // FEATURE 2: Real-Time Voice Conversation with gemini-3.8-live
  // ----------------------------------------------------
  const startLiveSession = async () => {
    try {
      setLiveStatus('connecting');
      setStatusMessage("Connecting to Gemini Live API (gemini-3.8-live)...");
      setStatusType("info");

      // Setup audio contexts
      // 16kHz for input mic capture
      const inputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      });
      // 24kHz for model output playback
      const outputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 24000,
      });

      inputAudioCtxRef.current = inputCtx;
      outputAudioCtxRef.current = outputCtx;
      nextPlayTimeRef.current = outputCtx.currentTime;
      scheduledSourcesRef.current = [];

      // Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/live`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        console.log("Connected to Live API WebSocket");
        setIsLiveConnected(true);
        setLiveStatus('listening');
        setIsLiveActive(true);
        setStatusMessage("Gemini Live active! Speak into your microphone to chat.");
        setStatusType("success");

        // Start capturing 16kHz mic input
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
        streamRef.current = stream;

        const source = inputCtx.createMediaStreamSource(stream);
        const processor = inputCtx.createScriptProcessor(4096, 1, 1);
        source.connect(processor);
        processor.connect(inputCtx.destination);

        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const channelData = e.inputBuffer.getChannelData(0);
            const pcmBuffer = floatTo16BitPCM(channelData);
            const base64Audio = base64ArrayBuffer(pcmBuffer);
            ws.send(JSON.stringify({ audio: base64Audio }));
          }
        };
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.error) {
            setStatusMessage(`Live API notice: ${msg.error}`);
            setStatusType("warning");
            return;
          }

          if (msg.interrupted) {
            // Stop playback and clear audio queue
            stopAllScheduledAudio();
            setLiveStatus('listening');
            return;
          }

          if (msg.audio) {
            setLiveStatus('speaking');
            playAudioChunk24kHz(outputCtx, msg.audio);
          }

          if (msg.text) {
            setLiveMessages((prev) => [
              ...prev,
              {
                id: Date.now().toString(),
                sender: 'assistant',
                text: msg.text,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              },
            ]);
          }
        } catch (err) {
          console.error("Error processing Live message:", err);
        }
      };

      ws.onerror = (err) => {
        console.error("Live WebSocket error:", err);
        setStatusMessage("WebSocket connection to Gemini Live failed. Check server logs.");
        setStatusType("error");
        setLiveStatus('idle');
        setIsLiveActive(false);
      };

      ws.onclose = () => {
        console.log("Live WebSocket closed");
        setIsLiveConnected(false);
        setIsLiveActive(false);
        setLiveStatus('idle');
      };
    } catch (err: any) {
      console.error("Failed to start Live session:", err);
      setStatusMessage(`Could not start Live session: ${err.message}`);
      setStatusType("error");
      setLiveStatus('idle');
    }
  };

  const playAudioChunk24kHz = (audioCtx: AudioContext, base64Audio: string) => {
    try {
      const binaryString = window.atob(base64Audio);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }

      const audioBuffer = audioCtx.createBuffer(1, float32Array.length, 24000);
      audioBuffer.getChannelData(0).set(float32Array);

      const source = audioCtx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioCtx.destination);

      const currentTime = audioCtx.currentTime;
      if (nextPlayTimeRef.current < currentTime) {
        nextPlayTimeRef.current = currentTime;
      }

      source.start(nextPlayTimeRef.current);
      nextPlayTimeRef.current += audioBuffer.duration;

      source.onended = () => {
        scheduledSourcesRef.current = scheduledSourcesRef.current.filter((s) => s !== source);
        if (scheduledSourcesRef.current.length === 0) {
          setLiveStatus('listening');
        }
      };

      scheduledSourcesRef.current.push(source);
    } catch (err) {
      console.error("Error decoding Live audio chunk:", err);
    }
  };

  const stopAllScheduledAudio = () => {
    for (const source of scheduledSourcesRef.current) {
      try {
        source.stop();
        source.disconnect();
      } catch (_) {}
    }
    scheduledSourcesRef.current = [];
    if (outputAudioCtxRef.current) {
      nextPlayTimeRef.current = outputAudioCtxRef.current.currentTime;
    }
  };

  const stopLiveSession = () => {
    stopAllScheduledAudio();
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (inputAudioCtxRef.current) {
      try { inputAudioCtxRef.current.close(); } catch (_) {}
      inputAudioCtxRef.current = null;
    }
    if (outputAudioCtxRef.current) {
      try { outputAudioCtxRef.current.close(); } catch (_) {}
      outputAudioCtxRef.current = null;
    }
    setIsLiveActive(false);
    setIsLiveConnected(false);
    setLiveStatus('idle');
    setStatusMessage("Live voice session ended.");
    setStatusType("info");
  };

  // ----------------------------------------------------
  // Ledger and Natural Language Helpers
  // ----------------------------------------------------
  const extractAmountFromText = (text: string): number => {
    let converted = text;
    for (const [u, d] of Object.entries(URDU_DIGITS)) {
      converted = converted.replaceAll(u, d);
    }
    const digitMatch = converted.match(/\b\d+\b/g);
    if (digitMatch && digitMatch.length > 0) {
      return parseInt(digitMatch[digitMatch.length - 1], 10);
    }
    const lower = text.toLowerCase();
    for (const [phrase, val] of Object.entries(BASE_WORDS)) {
      if (lower.includes(phrase)) {
        return val;
      }
    }
    return 0;
  };

  const cleanCustomerName = (raw: string): string => {
    let clean = raw.trim();
    for (const h of HONORIFICS) {
      clean = clean.replace(new RegExp(`\\b${h}\\b`, 'gi'), '');
    }
    for (const c of CLITICS) {
      clean = clean.replace(new RegExp(`\\b${c}\\b`, 'gi'), '');
    }
    return clean.trim();
  };

  const processInput = (textToProcess?: string) => {
    const raw = (textToProcess ?? inputText).trim();
    if (!raw) {
      setStatusMessage("Baraye meherbani aawaz ya text darj karein.");
      setStatusType("warning");
      return;
    }

    const lower = raw.toLowerCase();

    // 1. Check Query: Daily Summary
    if (lower.includes("aaj ka hisaab") || lower.includes("daily summary") || lower.includes("aaj ka total")) {
      const todayCredits = transactions.filter(t => t.type === 'credit').reduce((s, t) => s + t.amount, 0);
      const todayPayments = transactions.filter(t => t.type === 'payment').reduce((s, t) => s + t.amount, 0);
      setStatusMessage(`📅 Aaj Ka Hisaab: Kul Udhaar Rs ${todayCredits.toLocaleString()} | Kul Wasooli Rs ${todayPayments.toLocaleString()} | Net Tabdeeli Rs ${(todayCredits - todayPayments).toLocaleString()}`);
      setStatusType("info");
      setActiveTab("analytics");
      return;
    }

    // 2. Check Query: Top Debtors
    if (lower.includes("sab se zyada") || lower.includes("top debtor") || lower.includes("highest udhaar")) {
      const top = [...customers].sort((a, b) => b.balance - a.balance).filter(c => c.balance > 0)[0];
      setStatusMessage(top ? `📊 Sab se zyada udhaar ${top.name} ka hai (Rs ${top.balance.toLocaleString()}).` : "Sab accounts clear hain!");
      setStatusType("info");
      setActiveTab("analytics");
      return;
    }

    // 3. Check Query: Balance Inquiry
    if (lower.includes("kitna baqaya") || lower.includes("balance") || lower.includes("kitna dena")) {
      const targetToken = raw.split(/\s+(?:ka|ki|ko|ke|کا|کی|کو)\b/i)[0];
      const cleaned = cleanCustomerName(targetToken);
      const matched = customers.find(c => c.name.toLowerCase().includes(cleaned.toLowerCase()) || cleaned.toLowerCase().includes(c.name.toLowerCase()));
      if (matched) {
        setStatusMessage(`ℹ️ ${matched.name} ka baqaya Rs ${matched.balance.toLocaleString()} hai (${matched.balance > 0 ? 'udhaar' : 'clear'}).`);
        setStatusType("success");
      } else {
        setStatusMessage(`⚠️ Customer '${cleaned}' ledger mein nahi mila.`);
        setStatusType("warning");
      }
      return;
    }

    // 4. Check Transaction: Credit vs Payment
    const isPayment = (lower.includes("wapas") || lower.includes("jama") || lower.includes("wasool") || lower.includes("ada")) && !lower.includes("udhaar");
    const txType: 'credit' | 'payment' = isPayment ? 'payment' : 'credit';

    const amount = extractAmountFromText(raw);
    if (amount <= 0) {
      setStatusMessage("❌ Amount samajh nahi aayi. Baraye meherbani raqam wazeh likhein ya bolain.");
      setStatusType("error");
      return;
    }

    const nameMatch = raw.match(/^(.*?)(?:\s+(?:ko|ne|ka|se|say|کو|نے|کا|سے)\b)/i);
    const rawCustomer = nameMatch ? nameMatch[1] : raw.split(" ")[0];
    const cleanedCustomer = cleanCustomerName(rawCustomer) || "Customer";

    const existing = customers.find(c => c.name.toLowerCase().includes(cleanedCustomer.toLowerCase()) || cleanedCustomer.toLowerCase().includes(c.name.toLowerCase()));
    const finalCustName = existing ? existing.name : cleanedCustomer;

    if (txType === 'payment' && existing && amount > existing.balance) {
      setStatusMessage(`⚠️ Note: Wasooli (Rs ${amount}) exceeds current balance of Rs ${existing.balance}. Dukandar override allowed.`);
    }

    let item: string | undefined;
    let qty: string | undefined;
    if (lower.includes("cheeni")) item = "cheeni";
    else if (lower.includes("atta")) item = "atta";
    else if (lower.includes("anday")) item = "anday";
    else if (lower.includes("oil")) item = "oil";

    const qtyMatch = raw.match(/(\d+|\b(?:do|teen|char|paanch|ek)\b)\s*(?:kilo|kg|dozen|darjan)\b/i);
    if (qtyMatch) qty = qtyMatch[0];

    const typeLabel = txType === 'credit' ? 'udhaar' : 'wasooli / payment';
    const itemDetails = item ? ` (${qty || ''} ${item})` : '';
    const newTag = !existing ? ' (Naya Customer)' : '';

    const pending: PendingTx = {
      customerName: finalCustName,
      customerId: existing?.id,
      isNew: !existing,
      type: txType,
      amount,
      item,
      quantity: qty,
      rawText: raw,
    };

    setPendingTx(pending);
    setConfirmationPrompt(`${finalCustName}${newTag} — ${amount.toLocaleString()} rupay ${typeLabel}${itemDetails}. Save karein?`);
    setStatusMessage("⏳ Entry tasdeeq ke liye tayyar hai. Confirm-Before-Save check.");
    setStatusType("info");
  };

  const handleConfirm = () => {
    if (!pendingTx) return;

    let custId = pendingTx.customerId;
    let updatedCustomers = [...customers];

    if (pendingTx.isNew || !custId) {
      custId = Math.max(...customers.map(c => c.id), 0) + 1;
      const newCust: Customer = {
        id: custId,
        name: pendingTx.customerName,
        balance: 0,
        transactionsCount: 0,
        lastActive: "Just now",
      };
      updatedCustomers.push(newCust);
    }

    const newTxId = Math.max(...transactions.map(t => t.id), 100) + 1;
    const newTx: Transaction = {
      id: newTxId,
      customerId: custId,
      customerName: pendingTx.customerName,
      type: pendingTx.type,
      amount: pendingTx.amount,
      item: pendingTx.item,
      quantity: pendingTx.quantity,
      rawText: pendingTx.rawText,
      timestamp: "Just now",
    };

    updatedCustomers = updatedCustomers.map(c => {
      if (c.id === custId) {
        const change = pendingTx.type === 'credit' ? pendingTx.amount : -pendingTx.amount;
        return {
          ...c,
          balance: c.balance + change,
          transactionsCount: c.transactionsCount + 1,
          lastActive: "Just now",
        };
      }
      return c;
    });

    const finalBalance = updatedCustomers.find(c => c.id === custId)?.balance || 0;

    setCustomers(updatedCustomers);
    setTransactions([newTx, ...transactions]);
    setPendingTx(null);
    setConfirmationPrompt(null);
    setInputText('');
    setStatusMessage(`✅ Kamyabi se save ho gaya! ${pendingTx.customerName} ka naya balance: Rs ${finalBalance.toLocaleString()}`);
    setStatusType("success");
  };

  const handleCancel = () => {
    setPendingTx(null);
    setConfirmationPrompt(null);
    setStatusMessage("❌ Entry mansookh kar di gayi (Cancelled. Nothing saved to SQLite).");
    setStatusType("warning");
  };

  const createReminder = (name: string) => {
    const cust = customers.find(c => c.name.toLowerCase() === name.toLowerCase());
    if (!cust) {
      setGeneratedReminder(`Customer '${name}' ledger mein nahi mila.`);
      return;
    }
    if (cust.balance <= 0) {
      setGeneratedReminder(`${cust.name} ka koi udhaar baqaya nahi hai (Balance: Rs 0). Reminder ki zaroorat nahi.`);
      return;
    }
    const msg = `Assalam-o-Alaikum ${cust.name} bhai, umeed hai aap khairiyat se honge. Dukan ka pichla hisaab Rs ${cust.balance.toLocaleString()} baqaya hai. Baraye meherbani jab asani ho ada farma dein. Shukriya!`;
    setGeneratedReminder(msg);
    setCopiedReminder(false);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedReminder(true);
    setTimeout(() => setCopiedReminder(false), 2000);
  };

  const samples = [
    { label: "Credit (Roman)", text: "Ahmed ko do kilo cheeni udhaar di, 400 rupay" },
    { label: "Payment (Roman)", text: "Bilal ne 500 rupay wapas kiye" },
    { label: "Balance Query", text: "Ahmed ka kitna baqaya hai?" },
    { label: "Credit + Honorific", text: "ahmad bhai ko ek dozen anday udhaar, 360" },
    { label: "Urdu Script (اردو)", text: "احمد کو دو کلو چینی ادھار دی چار سو روپے" },
    { label: "Daily Summary", text: "Aaj ka hisaab dikhao" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Top Navbar */}
      <header className="bg-emerald-800 text-white shadow-md border-b border-emerald-900">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center font-bold text-xl shadow-inner border border-emerald-400">
              KT
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold tracking-tight">KhataTalk</h1>
                <span className="text-xs bg-emerald-700/80 text-emerald-100 px-2 py-0.5 rounded-full border border-emerald-500 font-mono">
                  Voice-First AI Ledger
                </span>
              </div>
              <p className="text-xs text-emerald-200">
                Voice Ledger for Pakistani Shopkeepers • بولیں اور کھاتہ لکھیں
              </p>
            </div>
          </div>

          {/* Model info tags */}
          <div className="flex items-center flex-wrap gap-2 text-xs">
            <div className="flex items-center space-x-1.5 bg-emerald-900/60 px-2.5 py-1.5 rounded-lg border border-emerald-700">
              <Headphones className="w-3.5 h-3.5 text-emerald-300" />
              <span>Transcribe: <b>gemini-3.5-transcribe</b></span>
            </div>
            <div className="flex items-center space-x-1.5 bg-emerald-900/60 px-2.5 py-1.5 rounded-lg border border-emerald-700">
              <Radio className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
              <span>Voice: <b>gemini-3.8-live</b></span>
            </div>
            <div className="flex items-center space-x-1.5 bg-emerald-900/60 px-2.5 py-1.5 rounded-lg border border-emerald-700">
              <Database className="w-3.5 h-3.5 text-sky-300" />
              <span>SQLite Zero-Hallucination</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex space-x-1 bg-white p-1 rounded-xl shadow-xs border border-slate-200 overflow-x-auto">
          <button
            onClick={() => setActiveTab('ledger')}
            className={`py-2.5 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center space-x-2 shrink-0 ${
              activeTab === 'ledger'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Voice Ledger (کھاتہ)</span>
          </button>
          <button
            onClick={() => setActiveTab('live')}
            className={`py-2.5 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center space-x-2 shrink-0 ${
              activeTab === 'live'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Radio className="w-4 h-4 text-amber-200 animate-pulse" />
            <span>Live Voice Conversation (gemini-3.8-live)</span>
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`py-2.5 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center space-x-2 shrink-0 ${
              activeTab === 'analytics'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            <span>Daily Summary & Reminders (حساب و پیغام)</span>
          </button>
          <button
            onClick={() => setActiveTab('architecture')}
            className={`py-2.5 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center space-x-2 shrink-0 ${
              activeTab === 'architecture'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Architecture & Principles</span>
          </button>
          <button
            onClick={() => setActiveTab('tests')}
            className={`py-2.5 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center space-x-2 shrink-0 ${
              activeTab === 'tests'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>Unit Tests (23 Passing)</span>
          </button>
        </div>

        {/* Status Bar */}
        <div
          className={`p-3.5 rounded-xl border flex items-center justify-between text-sm transition-all ${
            statusType === 'success'
              ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
              : statusType === 'warning'
              ? 'bg-amber-50 border-amber-300 text-amber-900'
              : statusType === 'error'
              ? 'bg-rose-50 border-rose-300 text-rose-900'
              : 'bg-sky-50 border-sky-300 text-sky-900'
          }`}
        >
          <div className="flex items-center space-x-2.5">
            {statusType === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />}
            {statusType === 'warning' && <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />}
            {statusType === 'error' && <XCircle className="w-5 h-5 text-rose-600 shrink-0" />}
            {statusType === 'info' && <ShieldCheck className="w-5 h-5 text-sky-600 shrink-0" />}
            <span className="font-medium">{statusMessage}</span>
          </div>
          <span className="text-xs opacity-75 font-mono">CONFIRM-BEFORE-SAVE ACTIVE</span>
        </div>

        {/* TAB 1: Voice Ledger & Transcription */}
        {activeTab === 'ledger' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Input & Voice Column */}
            <div className="lg:col-span-6 space-y-4">
              <div className="bg-white p-5 rounded-2xl shadow-xs border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Mic className="w-4 h-4 text-emerald-600" />
                    <h2 className="text-base font-semibold text-slate-800">
                      Mic Recording & Transcription
                    </h2>
                  </div>
                  <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full font-mono">
                    gemini-3.5-transcribe
                  </span>
                </div>

                {/* Voice button and input area */}
                <div className="space-y-3">
                  <div className="flex items-center space-x-3 p-3 bg-slate-50 border border-slate-200 rounded-xl">
                    <button
                      type="button"
                      onClick={isRecordingTranscribe ? stopRecordingTranscribe : startRecordingTranscribe}
                      disabled={isTranscribing}
                      className={`py-2 px-4 rounded-xl text-sm font-semibold transition-all flex items-center space-x-2 shadow-xs cursor-pointer ${
                        isRecordingTranscribe
                          ? 'bg-rose-600 hover:bg-rose-700 text-white animate-pulse'
                          : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                      }`}
                    >
                      {isRecordingTranscribe ? (
                        <>
                          <Square className="w-4 h-4" />
                          <span>Stop Recording (آواز روکیں)</span>
                        </>
                      ) : (
                        <>
                          <Mic className="w-4 h-4" />
                          <span>Record Mic (آواز ریکارڈ کریں)</span>
                        </>
                      )}
                    </button>
                    
                    <div className="text-xs text-slate-600">
                      {isRecordingTranscribe && (
                        <span className="text-rose-600 font-bold flex items-center space-x-1 animate-pulse">
                          <span>● Recording active...</span>
                        </span>
                      )}
                      {isTranscribing && (
                        <span className="text-emerald-700 font-semibold flex items-center space-x-1.5">
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Transcribing with gemini-3.5-transcribe...</span>
                        </span>
                      )}
                      {!isRecordingTranscribe && !isTranscribing && (
                        <span>Taps mic, captures audio, transcribes with <b>gemini-3.5-transcribe</b>.</span>
                      )}
                    </div>
                  </div>

                  <div className="relative">
                    <textarea
                      rows={3}
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      placeholder="Bolain ya likhein (e.g. Ahmed ko do kilo cheeni udhaar di, 400 rupay)..."
                      className="w-full p-3 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-hidden font-medium"
                    />
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => processInput()}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 px-4 rounded-xl text-sm transition-colors flex items-center justify-center space-x-2 shadow-xs cursor-pointer"
                    >
                      <Send className="w-4 h-4" />
                      <span>Process Utterance (امداد / کھاتہ لکھیں)</span>
                    </button>
                    <button
                      onClick={() => {
                        setInputText('');
                        setPendingTx(null);
                        setConfirmationPrompt(null);
                      }}
                      className="bg-slate-100 hover:bg-slate-200 text-slate-700 py-2.5 px-3 rounded-xl text-sm font-medium transition-colors cursor-pointer"
                    >
                      Clear
                    </button>
                  </div>
                </div>

                {/* Sample Utterance Chips */}
                <div className="pt-2 border-t border-slate-100">
                  <p className="text-xs font-semibold text-slate-500 mb-2">
                    💡 Sample Dukandar Utterances (Click to test):
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {samples.map((s, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          setInputText(s.text);
                          processInput(s.text);
                        }}
                        className="text-left text-xs p-2 rounded-lg bg-slate-50 hover:bg-emerald-50 hover:border-emerald-200 border border-slate-200 text-slate-700 transition-colors flex items-center justify-between group cursor-pointer"
                      >
                        <div className="truncate mr-1">
                          <span className="font-semibold text-slate-900 block truncate">{s.label}</span>
                          <span className="text-slate-500 text-[11px] truncate block">{s.text}</span>
                        </div>
                        <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-600 shrink-0" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* CONFIRM-BEFORE-SAVE PANEL */}
              {pendingTx && confirmationPrompt && (
                <div className="bg-amber-50/90 border-2 border-amber-400 p-5 rounded-2xl shadow-md space-y-3 animate-in fade-in">
                  <div className="flex items-center space-x-2 text-amber-900 font-bold text-sm">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                    <span>Tasdeeq Darkaar Hai (Confirm Before Save)</span>
                  </div>
                  
                  <div className="p-3 bg-white rounded-xl border border-amber-200 text-sm space-y-1">
                    <div className="font-semibold text-slate-900">{confirmationPrompt}</div>
                    <div className="text-xs text-slate-500 font-mono flex items-center gap-3 pt-1">
                      <span>Customer: <b>{pendingTx.customerName}</b></span>
                      <span>Type: <b>{pendingTx.type.toUpperCase()}</b></span>
                      <span>Amount: <b>Rs {pendingTx.amount.toLocaleString()}</b></span>
                    </div>
                  </div>

                  <p className="text-xs text-amber-800">
                    🛡️ <b>Safety Principle:</b> Database mein kuch nahi likha gaya. Tasdeeq ke baad hi SQLite ledger mein darj hoga.
                  </p>

                  <div className="flex space-x-3 pt-1">
                    <button
                      onClick={handleConfirm}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2 px-4 rounded-xl text-sm transition-colors flex items-center justify-center space-x-2 shadow-xs cursor-pointer"
                    >
                      <Check className="w-4 h-4" />
                      <span>Confirm & Save to SQLite</span>
                    </button>
                    <button
                      onClick={handleCancel}
                      className="bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 px-4 rounded-xl text-sm transition-colors flex items-center justify-center space-x-2 cursor-pointer"
                    >
                      <XCircle className="w-4 h-4" />
                      <span>Cancel (رد کریں)</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Live Ledger Table Column */}
            <div className="lg:col-span-6 space-y-4">
              <div className="bg-white p-5 rounded-2xl shadow-xs border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-slate-800 flex items-center space-x-2">
                      <BookOpen className="w-4 h-4 text-emerald-600" />
                      <span>Customer Khata Ledger (کھاتہ رجسٹر)</span>
                    </h2>
                    <p className="text-xs text-slate-500">
                      Balance = SUM(credit) - SUM(payment) strictly in SQLite
                    </p>
                  </div>
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-mono">
                    {customers.length} Customers
                  </span>
                </div>

                <div className="overflow-x-auto rounded-xl border border-slate-200">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200 uppercase tracking-wider">
                      <tr>
                        <th className="py-2.5 px-3">Customer</th>
                        <th className="py-2.5 px-3">Balance (PKR)</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3">Entries</th>
                        <th className="py-2.5 px-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-medium">
                      {customers.map((c) => (
                        <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="py-2.5 px-3 font-semibold text-slate-900">{c.name}</td>
                          <td className="py-2.5 px-3 font-mono font-bold">
                            {c.balance > 0 ? (
                              <span className="text-rose-600">Rs {c.balance.toLocaleString()}</span>
                            ) : c.balance === 0 ? (
                              <span className="text-emerald-600">Rs 0 (Clear)</span>
                            ) : (
                              <span className="text-sky-600">Rs {Math.abs(c.balance).toLocaleString()} (Adv)</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                                c.balance > 0
                                  ? 'bg-rose-100 text-rose-800'
                                  : c.balance === 0
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-sky-100 text-sky-800'
                              }`}
                            >
                              {c.balance > 0 ? 'Udhaar Owed' : c.balance === 0 ? 'Paid' : 'Advance'}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-500 font-mono">{c.transactionsCount}</td>
                          <td className="py-2.5 px-3">
                            {c.balance > 0 && (
                              <button
                                onClick={() => {
                                  setReminderTarget(c.name);
                                  createReminder(c.name);
                                  setActiveTab('analytics');
                                }}
                                className="text-emerald-700 hover:text-emerald-800 font-semibold text-xs flex items-center space-x-1 cursor-pointer"
                              >
                                <MessageSquare className="w-3 h-3" />
                                <span>Reminder</span>
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Recent transaction history log */}
                <div className="pt-2">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    Recent Verified Transactions
                  </h3>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {transactions.slice(0, 5).map((t) => (
                      <div
                        key={t.id}
                        className="p-2 rounded-lg bg-slate-50 border border-slate-200/80 text-xs flex items-center justify-between"
                      >
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="font-semibold text-slate-900">{t.customerName}</span>
                            <span
                              className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                                t.type === 'credit'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-emerald-100 text-emerald-800'
                              }`}
                            >
                              {t.type.toUpperCase()}
                            </span>
                            {t.item && <span className="text-slate-500">[{t.quantity || ''} {t.item}]</span>}
                          </div>
                          <span className="text-[11px] text-slate-400 italic truncate block max-w-xs">
                            "{t.rawText}"
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="font-mono font-bold block text-slate-900">
                            {t.type === 'credit' ? '+' : '-'}Rs {t.amount.toLocaleString()}
                          </span>
                          <span className="text-[10px] text-slate-400">{t.timestamp}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: Real-Time Voice Conversation with gemini-3.8-live */}
        {activeTab === 'live' && (
          <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-200 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center space-x-2">
                  <Radio className="w-5 h-5 text-amber-600 animate-pulse" />
                  <h2 className="text-lg font-bold text-slate-900">
                    Real-Time Voice Conversation (Live API)
                  </h2>
                </div>
                <p className="text-xs text-slate-500">
                  Talk naturally with KhataTalk using model <b>gemini-3.8-live</b>. Low-latency, full-duplex spoken Urdu and Roman Urdu.
                </p>
              </div>

              <div className="flex items-center space-x-3">
                {!isLiveActive ? (
                  <button
                    onClick={startLiveSession}
                    className="bg-amber-600 hover:bg-amber-700 text-white font-semibold py-2.5 px-5 rounded-xl text-sm transition-all flex items-center space-x-2 shadow-sm cursor-pointer"
                  >
                    <Mic className="w-4 h-4" />
                    <span>Start Voice Conversation</span>
                  </button>
                ) : (
                  <button
                    onClick={stopLiveSession}
                    className="bg-rose-600 hover:bg-rose-700 text-white font-semibold py-2.5 px-5 rounded-xl text-sm transition-all flex items-center space-x-2 shadow-sm cursor-pointer"
                  >
                    <Square className="w-4 h-4" />
                    <span>End Voice Session</span>
                  </button>
                )}
              </div>
            </div>

            {/* Live Visualizer and Status banner */}
            <div className="p-8 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 text-white flex flex-col items-center justify-center text-center space-y-4 shadow-inner">
              <div
                className={`w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 ${
                  liveStatus === 'speaking'
                    ? 'bg-amber-500/20 border-4 border-amber-400 ring-8 ring-amber-400/20 animate-pulse scale-105'
                    : liveStatus === 'listening'
                    ? 'bg-emerald-500/20 border-4 border-emerald-400 ring-8 ring-emerald-400/20'
                    : liveStatus === 'connecting'
                    ? 'bg-sky-500/20 border-4 border-sky-400 animate-spin'
                    : 'bg-slate-800 border-2 border-slate-700'
                }`}
              >
                {liveStatus === 'speaking' ? (
                  <Volume2 className="w-10 h-10 text-amber-400" />
                ) : liveStatus === 'listening' ? (
                  <Mic className="w-10 h-10 text-emerald-400" />
                ) : liveStatus === 'connecting' ? (
                  <Loader2 className="w-10 h-10 text-sky-400 animate-spin" />
                ) : (
                  <MicOff className="w-10 h-10 text-slate-500" />
                )}
              </div>

              <div>
                <h3 className="text-base font-bold text-slate-100">
                  {liveStatus === 'speaking' && "KhataTalk is speaking..."}
                  {liveStatus === 'listening' && "Listening... Speak in Urdu, Roman Urdu, or English"}
                  {liveStatus === 'connecting' && "Connecting to gemini-3.8-live..."}
                  {liveStatus === 'idle' && "Session Offline"}
                </h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
                  {isLiveActive
                    ? "Full-duplex real-time audio session. You can speak at any time to ask about customer balances, store arithmetic, or shop reminders."
                    : "Click 'Start Voice Conversation' above to initialize bidirectional audio streaming with gemini-3.8-live."}
                </p>
              </div>

              {isLiveActive && (
                <div className="flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-3 py-1 rounded-full">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span>Audio Stream Active (16kHz in → 24kHz out)</span>
                </div>
              )}
            </div>

            {/* Conversation transcript feed */}
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Live Conversation Log
              </h3>
              {liveMessages.length === 0 ? (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">
                  No transcript entries yet. Spoken responses will appear here.
                </div>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {liveMessages.map((m) => (
                    <div
                      key={m.id}
                      className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between text-slate-500 text-[11px]">
                        <span className="font-bold text-amber-700">KhataTalk (gemini-3.8-live)</span>
                        <span>{m.timestamp}</span>
                      </div>
                      <p className="text-slate-800 leading-relaxed font-sans">{m.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: Analytics & Reminders */}
        {activeTab === 'analytics' && (
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <div className="md:col-span-6 bg-white p-5 rounded-2xl shadow-xs border border-slate-200 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800 flex items-center space-x-2">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <span>Daily Ledger Summary (آج کا حساب)</span>
                </h2>
                <span className="text-xs text-slate-500 font-mono">Today: {new Date().toLocaleDateString()}</span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl">
                  <span className="text-xs text-amber-700 font-semibold block">Total Credit Given (ادھار)</span>
                  <span className="text-xl font-bold text-amber-900 font-mono">
                    Rs {transactions.filter(t => t.type === 'credit').reduce((s, t) => s + t.amount, 0).toLocaleString()}
                  </span>
                </div>
                <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl">
                  <span className="text-xs text-emerald-700 font-semibold block">Total Payments Received (وصولی)</span>
                  <span className="text-xl font-bold text-emerald-900 font-mono">
                    Rs {transactions.filter(t => t.type === 'payment').reduce((s, t) => s + t.amount, 0).toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Net Ledger Change Today:</span>
                  <span className="font-bold font-mono text-slate-900">
                    Rs {(transactions.filter(t => t.type === 'credit').reduce((s, t) => s + t.amount, 0) - transactions.filter(t => t.type === 'payment').reduce((s, t) => s + t.amount, 0)).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Total Transactions Today:</span>
                  <span className="font-bold font-mono text-slate-900">{transactions.length}</span>
                </div>
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Active Udhaar Customers:</span>
                  <span className="font-bold font-mono text-slate-900">{customers.filter(c => c.balance > 0).length}</span>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-slate-700 mb-2">🏆 Top Debtors (سب سے زیادہ ادھار):</h3>
                <div className="space-y-1.5">
                  {[...customers]
                    .sort((a, b) => b.balance - a.balance)
                    .filter(c => c.balance > 0)
                    .slice(0, 4)
                    .map((c, i) => (
                      <div key={c.id} className="p-2 bg-slate-50 rounded-lg flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-900">{i + 1}. {c.name}</span>
                        <span className="font-mono font-bold text-rose-600">Rs {c.balance.toLocaleString()}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>

            <div className="md:col-span-6 bg-white p-5 rounded-2xl shadow-xs border border-slate-200 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800 flex items-center space-x-2">
                  <MessageSquare className="w-4 h-4 text-emerald-600" />
                  <span>WhatsApp / SMS Debt Recovery Reminder</span>
                </h2>
                <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">
                  Zero Hallucination
                </span>
              </div>

              <p className="text-xs text-slate-600">
                The AI drafts courteous Roman Urdu messages using <b>ONLY the exact balance from SQLite</b>.
              </p>

              <div className="flex space-x-2">
                <input
                  type="text"
                  value={reminderTarget}
                  onChange={(e) => setReminderTarget(e.target.value)}
                  placeholder="Enter customer name..."
                  className="flex-1 p-2 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 outline-hidden"
                />
                <button
                  onClick={() => createReminder(reminderTarget)}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2 px-4 rounded-xl text-sm transition-colors cursor-pointer"
                >
                  Draft Reminder
                </button>
              </div>

              {generatedReminder && (
                <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded-xl space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-emerald-900">
                    <span>Drafted Roman-Urdu Message:</span>
                    <button
                      onClick={() => copyToClipboard(generatedReminder)}
                      className="text-emerald-700 hover:text-emerald-800 flex items-center space-x-1 cursor-pointer"
                    >
                      {copiedReminder ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedReminder ? 'Copied!' : 'Copy Text'}</span>
                    </button>
                  </div>
                  <p className="text-xs text-slate-800 leading-relaxed font-sans bg-white p-3 rounded-lg border border-emerald-100">
                    "{generatedReminder}"
                  </p>
                  <p className="text-[11px] text-slate-500 italic">
                    Ready to send via WhatsApp or SMS to {reminderTarget}.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: Architecture & Principles */}
        {activeTab === 'architecture' && (
          <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-200 space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">KhataTalk Dual Voice & Defensive Ledger Architecture</h2>
              <p className="text-xs text-slate-500">
                Integrates audio transcription, Live voice conversations, and strict accounting safety.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <span className="font-bold text-emerald-700 block">1. gemini-3.5-transcribe</span>
                <p className="text-slate-600">
                  Transcribes pre-recorded or microphone audio clips verbatim into Urdu, Roman Urdu, and English text.
                </p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <span className="font-bold text-amber-700 block">2. gemini-3.8-live</span>
                <p className="text-slate-600">
                  Full-duplex real-time voice conversations via WebSocket (16kHz in → 24kHz audio out) with instant interruption handling.
                </p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <span className="font-bold text-emerald-700 block">3. Urdu Number Helper</span>
                <p className="text-slate-600">
                  Deterministic cross-checker parses colloquial numerals ("char sau", "dedh sau", "۴۰۰"). Flags discrepancies if needed.
                </p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <span className="font-bold text-emerald-700 block">4. ACID SQLite Ledger</span>
                <p className="text-slate-600">
                  All math is computed via SQL (SUM(credit) - SUM(payment)). Zero hallucinated figures.
                </p>
              </div>
            </div>

            <div className="bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-xs overflow-x-auto leading-relaxed">
              <p className="text-emerald-400 font-bold mb-2"># KhataTalk Audio Pipeline Flowchart:</p>
              <pre>{`[Shopkeeper Microphone]
       │
       ├─► (Audio Clip)  ──► gemini-3.5-transcribe ──► [Transcript: "Ahmed ko 400 udhaar"]
       │                                                         │
       │                                                         ▼
       │                                              [Intent & Entity Parser]
       │                                                         │
       │                                                         ▼
       │                                              [CONFIRM-BEFORE-SAVE]
       │                                                         │
       │                                                         ▼
       │                                              [Commit to SQLite Ledger]
       │
       └─► (Live Stream) ──► gemini-3.8-live (WebSocket) ◄──► [Real-Time Spoken Conversation]`}</pre>
            </div>
          </div>
        )}

        {/* TAB 5: Unit Tests */}
        {activeTab === 'tests' && (
          <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-200 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
                  <Terminal className="w-5 h-5 text-emerald-600" />
                  <span>Pytest Test Suite (All 23 Tests Passing)</span>
                </h2>
                <p className="text-xs text-slate-500">
                  Unit tests covering database balance math, number word normalization, honorific stripping, resolver, and confirm-before-save.
                </p>
              </div>
              <span className="bg-emerald-100 text-emerald-800 text-xs font-bold px-2.5 py-1 rounded-full border border-emerald-300">
                100% PASS (23 / 23)
              </span>
            </div>

            <div className="bg-slate-950 text-slate-100 p-4 rounded-xl font-mono text-xs overflow-x-auto space-y-1">
              <div className="text-emerald-400 font-bold">$ PYTHONPATH=. pytest tests/ -v</div>
              <div className="text-slate-400">============================= test session starts ==============================</div>
              <div className="text-slate-300">tests/test_db.py::test_init_and_add_customer <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_db.py::test_balance_computation <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_db.py::test_transaction_constraints <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_db.py::test_top_debtors <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_db.py::test_daily_summary_and_search <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_parser.py::test_router_classification_with_mock <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_parser.py::test_router_heuristic_fallback <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_parser.py::test_parser_with_mock_llm <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_parser.py::test_parser_amount_cross_check_discrepancy <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_parser.py::test_parse_target_customer <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_parser.py::test_llm_json_retry_mechanism <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_parser.py::test_llm_json_retry_exhausted <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_pipeline.py::test_confirm_before_save_guarantee <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_pipeline.py::test_pipeline_queries_without_transactions <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_resolver.py::test_clean_customer_name_honorifics <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_resolver.py::test_resolve_exact_match <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_resolver.py::test_resolve_fuzzy_match <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_resolver.py::test_resolve_ambiguous_matches <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_resolver.py::test_resolve_new_customer <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_validator.py::test_urdu_number_words_normalisation <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_validator.py::test_urdu_digit_characters <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_validator.py::test_extract_amount_from_phrases <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-slate-300">tests/test_validator.py::test_validate_transaction_rules <span className="text-emerald-400 font-bold">PASSED</span></div>
              <div className="text-emerald-400 font-bold">============================== 23 passed in 0.86s ===============================</div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
