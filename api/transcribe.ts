import type { IncomingMessage, ServerResponse } from "http";

export const config = {
  api: {
    bodyParser: {
      sizeLimit: "10mb",
    },
  },
};

export default async function handler(req: any, res: any) {
  // Set CORS headers
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS,PATCH,DELETE,POST,PUT");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version"
  );

  if (req.method === "OPTIONS") {
    res.status(200).end();
    return;
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed. Use POST." });
  }

  try {
    let body = req.body;
    if (typeof body === "string") {
      try {
        body = JSON.parse(body);
      } catch (_) {}
    }
    const { audioData, mimeType } = body || {};
    if (!audioData) {
      return res.status(400).json({ error: "Missing audioData in request body." });
    }

    const geminiKey = process.env.GEMINI_API_KEY;
    const openaiKey = process.env.OPENAI_API_KEY;

    // 1. Try Gemini if GEMINI_API_KEY is configured
    if (geminiKey) {
      try {
        const { GoogleGenAI } = await import("@google/genai");
        const ai = new GoogleGenAI({
          apiKey: geminiKey,
          httpOptions: {
            headers: {
              "User-Agent": "aistudio-build",
            },
          },
        });

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
        if (transcript) {
          return res.status(200).json({ transcript });
        }
      } catch (geminiErr: any) {
        console.warn("Gemini transcription failed, attempting OpenAI Whisper fallback:", geminiErr);
      }
    }

    // 2. Try OpenAI Whisper if OPENAI_API_KEY is configured
    if (openaiKey) {
      try {
        const buffer = Buffer.from(audioData, "base64");
        const ext = mimeType?.includes("mp4") ? "mp4" : mimeType?.includes("wav") ? "wav" : "webm";
        const formData = new FormData();
        const blob = new Blob([buffer], { type: mimeType || "audio/webm" });
        formData.append("file", blob, `audio.${ext}`);
        formData.append("model", "whisper-1");
        formData.append(
          "prompt",
          "Pakistani shopkeeper transaction in Urdu, Roman Urdu, or English (e.g. 'Ahmed ko 2 kilo cheeni udhaar di 400 rupay')."
        );

        const openAiRes = await fetch("https://api.openai.com/v1/audio/transcriptions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${openaiKey}`,
          },
          body: formData,
        });

        if (openAiRes.ok) {
          const result: any = await openAiRes.json();
          const transcript = result.text?.trim() || "";
          if (transcript) {
            return res.status(200).json({ transcript });
          }
        }
      } catch (openAiErr) {
        console.warn("OpenAI Whisper transcription failed:", openAiErr);
      }
    }

    // If neither key is configured or both failed
    return res.status(200).json({
      transcript: "",
      warning: "No transcription API key configured on server. Used client-side recognition.",
    });
  } catch (error: any) {
    console.error("Transcription endpoint error:", error);
    return res.status(500).json({ error: error.message || "Failed to process audio." });
  }
}
