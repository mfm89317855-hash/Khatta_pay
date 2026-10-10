import express from "express";
import http from "http";
import path from "path";
import dotenv from "dotenv";
import { WebSocketServer, WebSocket } from "ws";
import { GoogleGenAI, LiveServerMessage, Modality } from "@google/genai";

dotenv.config();

const app = express();
app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ extended: true, limit: "50mb" }));

// Server-side Gemini Client with required User-Agent
const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
  httpOptions: {
    headers: {
      "User-Agent": "aistudio-build",
    },
  },
});

// API Route: Transcribe audio using gemini-3.5-transcribe
app.post("/api/transcribe", async (req, res) => {
  try {
    const { audioData, mimeType } = req.body;
    if (!audioData) {
      return res.status(400).json({ error: "Missing audioData in request body" });
    }

    const audioPart = {
      inlineData: {
        mimeType: mimeType || "audio/webm",
        data: audioData,
      },
    };

    const response = await ai.models.generateContent({
      model: "gemini-3.5-transcribe",
      contents: {
        parts: [
          audioPart,
          {
            text: "Transcribe this audio verbatim. The speech is from a Pakistani shopkeeper recording transactions or asking questions and may be spoken in Urdu, Roman Urdu, English, or a code-switched mix (e.g. 'Ahmed ko do kilo cheeni udhaar di, 400 rupay'). Output strictly the transcribed text without conversational commentary.",
          },
        ],
      },
    });

    const transcript = response.text?.trim() || "";
    return res.json({ transcript });
  } catch (error: any) {
    console.error("Transcription error:", error);
    return res.status(500).json({
      error: error.message || "Failed to transcribe audio with gemini-3.5-transcribe",
    });
  }
});

// API Route: Process transaction via local Ollama model
app.post("/api/process", async (req, res) => {
  try {
    const { text } = req.body;
    if (!text || !text.trim()) {
      return res.status(400).json({ error: "Missing text to process" });
    }

    const model = process.env.KHATATALK_MODEL || "qwen2.5:3b";
    const host = process.env.OLLAMA_HOST || "http://localhost:11434";

    const prompt = `You are a ledger parser for Pakistani dukandaars.
Analyze this utterance in Urdu, Roman Urdu, or English: "${text.trim()}"
Output STRICT JSON with keys:
- "intent": "add_credit" (giving udhaar) | "add_payment" (receiving money back) | "ask_balance" | "daily_summary" | "top_debtors" | "unknown"
- "customer": extracted customer name without honorifics like bhai, sahab, sb
- "amount": integer rupee amount, or null
- "item": item name if mentioned, or null
- "quantity": quantity if mentioned, or null`;

    try {
      const ollamaRes = await fetch(`${host}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          prompt,
          format: "json",
          stream: false,
          options: { temperature: 0.0 },
        }),
      });

      if (ollamaRes.ok) {
        const oData = await ollamaRes.json();
        const parsed = JSON.parse(oData.response);
        return res.json({
          status: "success",
          source: "local_ollama",
          model,
          parsed,
        });
      }
    } catch (ollamaErr: any) {
      console.warn("Local Ollama call notice:", ollamaErr.message);
    }

    // Heuristic fallback if Ollama is offline
    return res.json({
      status: "fallback",
      source: "rule_engine",
      rawText: text.trim(),
    });
  } catch (err: any) {
    return res.status(500).json({ error: err.message });
  }
});

// API Route: Health & status
app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    hasApiKey: !!process.env.GEMINI_API_KEY,
    models: {
      transcribe: "gemini-3.5-transcribe",
      live: "gemini-3.8-live",
    },
  });
});

const server = http.createServer(app);

// WebSocket server for Real-Time Voice Conversation with gemini-3.8-live (Live API)
const wss = new WebSocketServer({ noServer: true });

server.on("upgrade", (request, socket, head) => {
  const url = new URL(request.url || "", `http://${request.headers.host || "localhost"}`);
  if (url.pathname === "/api/live" || url.pathname === "/live") {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit("connection", ws, request);
    });
  } else {
    // If not matching, don't destroy immediately if Vite uses HMR
    if (!request.headers["sec-websocket-protocol"]?.includes("vite-hmr")) {
      socket.destroy();
    }
  }
});

wss.on("connection", async (clientWs: WebSocket) => {
  console.log("Client connected to Gemini Live voice session");
  let liveSession: any = null;

  try {
    liveSession = await ai.live.connect({
      model: "gemini-3.8-live",
      config: {
        responseModalities: [Modality.AUDIO],
        speechConfig: {
          voiceConfig: {
            prebuiltVoiceConfig: { voiceName: "Zephyr" },
          },
        },
        systemInstruction:
          "You are KhataTalk Live Voice Assistant, a friendly, respectful Pakistani AI companion for local shopkeepers (kiryana and general stores). " +
          "You understand and converse naturally in polite Roman Urdu, standard Urdu, and English. " +
          "Help the shopkeeper manage udhaar (credit) and wasooli (payments), check balances, answer questions about store finances, and offer polite reminders. " +
          "Keep answers brief, conversational, and direct, suitable for voice playback.",
      },
      callbacks: {
        onmessage: (message: LiveServerMessage) => {
          const parts = message.serverContent?.modelTurn?.parts || [];
          for (const part of parts) {
            if (part.inlineData?.data) {
              clientWs.send(
                JSON.stringify({
                  audio: part.inlineData.data,
                })
              );
            }
            if (part.text) {
              clientWs.send(
                JSON.stringify({
                  text: part.text,
                })
              );
            }
          }
          if (message.serverContent?.interrupted) {
            clientWs.send(JSON.stringify({ interrupted: true }));
          }
        },
        onclose: () => {
          console.log("Gemini Live session closed");
          if (clientWs.readyState === WebSocket.OPEN) {
            clientWs.send(JSON.stringify({ closed: true }));
          }
        },
        onerror: (err: any) => {
          console.error("Gemini Live session error:", err);
          if (clientWs.readyState === WebSocket.OPEN) {
            clientWs.send(JSON.stringify({ error: String(err.message || err) }));
          }
        },
      },
    });

    clientWs.send(JSON.stringify({ ready: true, model: "gemini-3.8-live" }));

    clientWs.on("message", (raw) => {
      try {
        const data = JSON.parse(raw.toString());
        if (data.audio && liveSession) {
          liveSession.sendRealtimeInput({
            audio: {
              data: data.audio,
              mimeType: "audio/pcm;rate=16000",
            },
          });
        }
      } catch (err) {
        console.error("Failed to parse client message:", err);
      }
    });

    clientWs.on("close", () => {
      if (liveSession) {
        try {
          liveSession.close();
        } catch (_) {}
      }
    });
  } catch (err: any) {
    console.error("Failed to initialize Gemini Live session:", err);
    if (clientWs.readyState === WebSocket.OPEN) {
      clientWs.send(
        JSON.stringify({
          error:
            err.message ||
            "Could not connect to Gemini Live API. Please verify GEMINI_API_KEY.",
        })
      );
      clientWs.close();
    }
  }
});

// Mount Vite in dev mode or serve static files in production
const isProduction = process.env.NODE_ENV === "production";
const PORT = Number(process.env.PORT) || 3000;

async function startServer() {
  if (!isProduction) {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.resolve("dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`Server listening on port ${PORT} (Live API on /api/live, Transcribe on /api/transcribe)`);
  });
}

startServer().catch((err) => {
  console.error("Fatal error starting server:", err);
  process.exit(1);
});
