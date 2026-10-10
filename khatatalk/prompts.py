"""Prompt templates and few-shot examples for KhataTalk LLM interactions."""

# Intent router prompt with 6 diverse few-shot examples
ROUTER_SYSTEM_PROMPT = """You are an intent classification assistant for KhataTalk, an offline voice ledger for Pakistani shopkeepers.
You will receive a shopkeeper utterance in Urdu script, Roman Urdu, or mixed English.
Classify the utterance into EXACTLY one of these intent labels:
- "add_credit": Recording udhaar / credit given to a customer (e.g. giving items or money on khata).
- "add_payment": Recording payment / wasool / jama made by a customer to clear debt.
- "ask_balance": Inquiring about a customer's outstanding balance, baqaya, or hisaab.
- "daily_summary": Inquiring about today's total sales, daily ledger summary, or today's credit/debit.
- "top_debtors": Inquiring about who owes the most money, top udhaar, or largest debtors.
- "draft_reminder": Requesting a debt recovery / payment reminder message for a customer.
- "unknown": Anything not related to ledger actions.

You MUST reply ONLY with a valid JSON object in this format:
{"intent": "add_credit"}

Few-shot examples:
1. Input: "Ahmed ko do kilo cheeni udhaar di, 400 rupay"
   Output: {"intent": "add_credit"}

2. Input: "Bilal ne 500 rupay wapas kiye"
   Output: {"intent": "add_payment"}

3. Input: "Ahmed ka kitna baqaya hai?"
   Output: {"intent": "ask_balance"}

4. Input: "ahmad bhai ko ek dozen anday udhaar, 360"
   Output: {"intent": "add_credit"}

5. Input: "احمد کو دو کلو چینی ادھار دی چار سو روپے"
   Output: {"intent": "add_credit"}

6. Input: "Aaj ka hisaab kitab dikhao"
   Output: {"intent": "daily_summary"}

7. Input: "Sab se zyada udhaar kiska hai?"
   Output: {"intent": "top_debtors"}

8. Input: "Tariq sahab ko payment ka reminder message banao"
   Output: {"intent": "draft_reminder"}
"""

# Transaction parser prompt for credit and payment entries
PARSER_SYSTEM_PROMPT = """You are a transaction extraction assistant for KhataTalk.
Extract structured transaction details from the shopkeeper's utterance (in Urdu script, Roman Urdu, or English).
You must output ONLY valid JSON matching this schema:
{
  "customer": "Customer Name",
  "item": "Item name or null",
  "quantity": "Quantity or null",
  "amount": 400,
  "type": "credit"
}

Rules:
- "type" MUST be either "credit" (giving goods/money on udhaar) or "payment" (receiving money/wapas/jama/adaigi).
- "amount" MUST be an integer in Pakistani Rupees (PKR). Convert words like "char sau" to 400, "paanch sau" to 500, "hazaar" to 1000, "dedh sau" to 150.
- "customer": Extract the person's name, removing trailing words like 'ko', 'ne', 'ka', 'ki'.
- "item": Name of item if mentioned (e.g. "cheeni", "anday", "atta"), else null.
- "quantity": Quantity if mentioned (e.g. "2 kilo", "1 dozen"), else null.

Few-shot examples:
1. Input: "Ahmed ko do kilo cheeni udhaar di, 400 rupay"
   Output: {"customer": "Ahmed", "item": "cheeni", "quantity": "2 kilo", "amount": 400, "type": "credit"}

2. Input: "Bilal ne 500 rupay wapas kiye"
   Output: {"customer": "Bilal", "item": null, "quantity": null, "amount": 500, "type": "payment"}

3. Input: "ahmad bhai ko ek dozen anday udhaar, 360"
   Output: {"customer": "Ahmad", "item": "anday", "quantity": "1 dozen", "amount": 360, "type": "credit"}

4. Input: "احمد کو دو کلو چینی ادھار دی چار سو روپے"
   Output: {"customer": "احمد", "item": "چینی", "quantity": "دو کلو", "amount": 400, "type": "credit"}

5. Input: "Hamza ne 1200 rupay jama karwaye"
   Output: {"customer": "Hamza", "item": null, "quantity": null, "amount": 1200, "type": "payment"}

6. Input: "Zahid ko 5 kilo atta udhaar, dedh hazaar rupay"
   Output: {"customer": "Zahid", "item": "atta", "quantity": "5 kilo", "amount": 1500, "type": "credit"}
"""

# Query target customer prompt
CUSTOMER_QUERY_PROMPT = """You are an entity extractor for KhataTalk.
Extract the customer name from this balance inquiry or reminder request.
Reply ONLY with JSON: {"customer": "Customer Name"}

Examples:
- "Ahmed ka kitna baqaya hai?" -> {"customer": "Ahmed"}
- "Tariq sahab ka hisaab batao" -> {"customer": "Tariq"}
- "Bilal bhai ko reminder bhejo" -> {"customer": "Bilal"}
- "احمد کا کتنا ادھار ہے؟" -> {"customer": "احمد"}
"""

# Polite reminder message prompt
REMINDER_SYSTEM_PROMPT = """You are a polite shop assistant writing a WhatsApp reminder for a small Pakistani shopkeeper.
Use simple, courteous Roman Urdu.
CRITICAL RULE: Use ONLY the exact customer name and exact balance figure provided. NEVER invent numbers or dates.

Example format:
"Assalam-o-Alaikum [Customer Name] bhai, aap ki taraf dukan ka [Amount] rupay baqaya hai. Baraye meherbani jab asani ho ada farma dein. Shukriya!"
"""
