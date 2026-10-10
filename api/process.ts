export const config = {
  api: {
    bodyParser: {
      sizeLimit: "2mb",
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
    const { text } = body || {};
    if (!text || !text.trim()) {
      return res.status(400).json({ error: "Missing text to process" });
    }

    const raw = text.trim();
    const geminiKey = process.env.GEMINI_API_KEY;

    // 1. If GEMINI_API_KEY is available, analyze with Gemini
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

        const prompt = `You are a financial ledger parser for Pakistani dukandaars (shopkeepers).
Analyze this customer transaction utterance in Urdu, Roman Urdu, or English: "${raw}"

Output STRICT JSON with exactly these keys:
{
  "intent": "add_credit" (giving udhaar/loan) | "add_payment" (receiving money back / wasool / jama) | "ask_balance" | "daily_summary" | "top_debtors" | "unknown",
  "customer": extracted customer name without honorifics like bhai, sahab, sb, or null,
  "amount": integer rupee amount, or null,
  "item": item name if mentioned (e.g. cheeni, atta, doodh, oil, anday), or null,
  "quantity": quantity if mentioned (e.g. 2 kilo, 1 darjan), or null
}`;

        const response = await ai.models.generateContent({
          model: "gemini-2.5-flash",
          contents: prompt,
          config: {
            responseMimeType: "application/json",
          },
        });

        const responseText = response.text?.trim() || "";
        if (responseText) {
          const parsed = JSON.parse(responseText);
          return res.status(200).json({
            status: "success",
            source: "gemini_cloud",
            parsed,
          });
        }
      } catch (geminiErr: any) {
        console.warn("Gemini process error, using fallback engine:", geminiErr.message);
      }
    }

    // 2. Serverless Rule Engine Fallback (Instant, Zero Latency)
    const lower = raw.toLowerCase();
    let intent = "add_credit";
    if (lower.includes("aaj ka hisaab") || lower.includes("daily summary") || lower.includes("aaj ka total")) {
      intent = "daily_summary";
    } else if (lower.includes("sab se zyada") || lower.includes("top debtor") || lower.includes("highest udhaar")) {
      intent = "top_debtors";
    } else if (lower.includes("kitna baqaya") || lower.includes("balance") || lower.includes("kitna dena")) {
      intent = "ask_balance";
    } else if ((lower.includes("wapas") || lower.includes("jama") || lower.includes("wasool") || lower.includes("ada")) && !lower.includes("udhaar")) {
      intent = "add_payment";
    }

    // Extract amount
    let amount: number | null = null;
    const numMatch = raw.match(/\b\d+\b/);
    if (numMatch) {
      amount = parseInt(numMatch[0], 10);
    } else {
      const wordMap: Record<string, number> = {
        "sau": 100, "so": 100,
        "do sau": 200, "teen sau": 300, "char sau": 400, "paanch sau": 500, "panch sau": 500,
        "hazaar": 1000, "hazar": 1000, "ek hazaar": 1000, "do hazaar": 2000, "teen hazaar": 3000,
        "paanch hazaar": 5000, "panch hazaar": 5000,
      };
      for (const [k, v] of Object.entries(wordMap)) {
        if (lower.includes(k)) {
          amount = v;
          break;
        }
      }
    }

    // Extract customer
    let customer: string | null = null;
    const custMatch = raw.match(/^(.*?)(?:\s+(?:ko|ne|ka|se|say|کو|نے|کا|سے)\b)/i);
    if (custMatch && custMatch[1]) {
      customer = custMatch[1].replace(/\b(?:bhai|sahab|sb|janab|uncle)\b/gi, "").trim();
    } else {
      customer = raw.split(" ")[0];
    }

    // Extract item & quantity
    let item: string | null = null;
    let quantity: string | null = null;
    if (lower.includes("cheeni")) item = "cheeni";
    else if (lower.includes("atta")) item = "atta";
    else if (lower.includes("anday") || lower.includes("ande")) item = "anday";
    else if (lower.includes("oil") || lower.includes("tail")) item = "oil";
    else if (lower.includes("doodh")) item = "doodh";

    const qtyMatch = raw.match(/(\d+|\b(?:do|teen|char|paanch|ek)\b)\s*(?:kilo|kg|dozen|darjan)\b/i);
    if (qtyMatch) quantity = qtyMatch[0];

    return res.status(200).json({
      status: "success",
      source: "rule_engine",
      parsed: {
        intent,
        customer,
        amount,
        item,
        quantity,
      },
    });
  } catch (error: any) {
    return res.status(500).json({ error: error.message || "Failed to process text." });
  }
}
