"""KhataTalk - Voice-First AI Ledger for small shopkeepers in Pakistan.

Gradio UI entry point with microphone audio, editable transcript,
confirm-before-save workflow, and live ledger analytics.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

# Ensure khatatalk package is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from khatatalk.config import DEFAULT_DB_PATH, DEFAULT_LLM_MODEL, DEFAULT_WHISPER_MODEL
from khatatalk.db import init_db, list_customers
from khatatalk.pipeline import commit_transaction, process_utterance
from khatatalk.stt import transcribe_audio
from khatatalk.summary import answer_daily_summary, answer_top_debtors, draft_reminder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Initialise local database
init_db()


def get_ledger_dataframe() -> List[List[Any]]:
    """Fetches formatted customers ledger data for the UI table."""
    customers = list_customers()
    rows = []
    for c in customers:
        bal = c.get("balance", 0)
        status_tag = "🔴 Owed (Udhaar)" if bal > 0 else ("🟢 Paid (Clear)" if bal == 0 else "🔵 Advance")
        rows.append([
            c.get("id"),
            c.get("name"),
            f"Rs {bal:,}",
            status_tag,
            c.get("transaction_count", 0),
            c.get("last_transaction_at") or c.get("created_at"),
        ])
    return rows


def handle_transcription(audio_file: Optional[str], current_text: str) -> str:
    """If audio is recorded/uploaded, transcribes via faster-whisper; otherwise retains text."""
    if not audio_file:
        return current_text

    try:
        gr.Info("Transcribing voice audio with faster-whisper...")
        transcribed = transcribe_audio(audio_file)
        if transcribed:
            return transcribed
        return current_text
    except Exception as e:
        logger.error("STT error: %s", e)
        gr.Warning(f"Aawaz transcribe nahi ho saki: {e}. Baraye meherbani text likhein.")
        return current_text


def handle_process(
    text: str,
) -> Tuple[
    str,  # detected intent
    str,  # details json / summary
    str,  # confirmation prompt
    gr.update,  # confirm box visibility
    Optional[Dict[str, Any]],  # pending state
    str,  # status output
    List[List[Any]],  # refreshed ledger
]:
    """Processes user input through pipeline with confirm-before-save workflow."""
    if not text or not text.strip():
        return (
            "—",
            "—",
            "",
            gr.update(visible=False),
            None,
            "⚠️ Baraye meherbani pehle kuch bolain ya text darj karein.",
            get_ledger_dataframe(),
        )

    try:
        result = process_utterance(text.strip())

        if result.status == "error":
            return (
                result.intent.upper(),
                "—",
                "",
                gr.update(visible=False),
                None,
                f"❌ Khata Error: {result.error}",
                get_ledger_dataframe(),
            )

        if result.status == "clarification_needed":
            return (
                result.intent.upper(),
                f"Clarification required:\n{result.error}",
                "",
                gr.update(visible=False),
                None,
                f"❓ Wazahut Darkaar Hai: {result.error}",
                get_ledger_dataframe(),
            )

        if result.status == "completed":
            # For query actions (ask_balance, daily_summary, top_debtors, draft_reminder)
            query_res = result.query_result or {}
            display_text = query_res.get("text_response") or query_res.get("message") or json.dumps(query_res, indent=2)
            return (
                result.intent.upper(),
                display_text,
                "",
                gr.update(visible=False),
                None,
                f"ℹ️ {display_text}",
                get_ledger_dataframe(),
            )

        if result.requires_confirmation and result.pending_transaction:
            # Credit / Payment ready for confirmation
            details_str = json.dumps(result.pending_transaction, indent=2, ensure_ascii=False)
            prompt_str = result.confirmation_prompt or "Save transaction to ledger?"
            return (
                f"{result.intent.upper()} (Pending Confirmation)",
                details_str,
                prompt_str,
                gr.update(visible=True),
                result.pending_transaction,
                "⏳ Entry tayyar hai. Baraye meherbani tasdeeq karein (Please confirm below).",
                get_ledger_dataframe(),
            )

        return (
            result.intent,
            "Unknown state",
            "",
            gr.update(visible=False),
            None,
            "Kuch masla pesh aya.",
            get_ledger_dataframe(),
        )

    except Exception as err:
        logger.exception("Pipeline execution failed: %s", err)
        return (
            "ERROR",
            str(err),
            "",
            gr.update(visible=False),
            None,
            f"❌ Ghalti pesh aayi: {err}",
            get_ledger_dataframe(),
        )


def handle_confirm(
    pending_tx: Optional[Dict[str, Any]],
) -> Tuple[
    str,  # status output
    gr.update,  # confirm box visibility
    Optional[Dict[str, Any]],  # pending state
    List[List[Any]],  # refreshed ledger
]:
    """Saves pending transaction to SQLite upon user confirmation."""
    if not pending_tx:
        return (
            "⚠️ Koi pending entry mojood nahi hai.",
            gr.update(visible=False),
            None,
            get_ledger_dataframe(),
        )

    try:
        res = commit_transaction(pending_tx)
        msg = f"✅ {res['message']} (ID: #{res['transaction_id']})"
        return (
            msg,
            gr.update(visible=False),
            None,
            get_ledger_dataframe(),
        )
    except Exception as e:
        logger.exception("Failed to commit transaction: %s", e)
        return (
            f"❌ Save na ho saka: {e}",
            gr.update(visible=True),
            pending_tx,
            get_ledger_dataframe(),
        )


def handle_cancel() -> Tuple[str, gr.update, Optional[Dict[str, Any]]]:
    """Cancels and discards the pending transaction."""
    return (
        "❌ Entry mansookh kar di gayi (Cancelled. Nothing saved to database).",
        gr.update(visible=False),
        None,
    )


def refresh_analytics() -> Tuple[str, List[List[Any]]]:
    """Generates updated daily summary text and top debtors table."""
    summary_data = answer_daily_summary()
    debtors_data = answer_top_debtors(limit=10)

    debtor_rows = []
    for d in debtors_data.get("debtors", []):
        debtor_rows.append([d.get("id"), d.get("name"), f"Rs {d.get('balance', 0):,}", "Active Udhaar"])

    return summary_data["text_response"], debtor_rows


def generate_reminder_for_customer(customer_name: str) -> str:
    """Generates polite Roman Urdu debt recovery reminder for specific customer."""
    from khatatalk.db import get_customer_by_name
    cust = get_customer_by_name(customer_name.strip())
    if not cust:
        return f"Customer '{customer_name}' nahi mila."
    res = draft_reminder(cust["id"], cust["name"])
    return res["message"]


def build_app() -> gr.Blocks:
    """Builds the complete Gradio web UI."""
    custom_css = """
    .gradio-container { max-width: 1100px !important; margin: auto; }
    .confirm-panel { border: 2px solid #2563eb; background: #f0f7ff; padding: 16px; border-radius: 8px; }
    .ledger-badge { font-weight: bold; }
    """

    with gr.Blocks(title="KhataTalk — Voice-First AI Ledger") as demo:
        # Header
        gr.Markdown(
            """
            # 📒 KhataTalk (کھاتہ ٹاک)
            ### Offline, Voice-First AI Ledger for Pakistani Shopkeepers
            *Speak in **Urdu**, **Roman Urdu**, or **English** • Records credit & payments • Answers balances • 100% Offline with SQLite & Local Models*
            """
        )

        with gr.Tabs():
            # TAB 1: Voice & Ledger Operations
            with gr.Tab("🎙️ Voice Khata (Aawaz se Indraj)"):
                with gr.Row():
                    with gr.Column(scale=5):
                        mic_input = gr.Audio(
                            sources=["microphone", "upload"],
                            type="filepath",
                            label="🎙️ Speak Here (Aawaz Record Karein)",
                        )
                        text_input = gr.Textbox(
                            lines=3,
                            label="✍️ Spoken Transcript / Text Fallback (Baraye Meherbani Check/Edit Karein)",
                            placeholder="e.g. Ahmed ko do kilo cheeni udhaar di, 400 rupay",
                        )
                        mic_input.change(
                            fn=handle_transcription,
                            inputs=[mic_input, text_input],
                            outputs=[text_input],
                        )

                        with gr.Row():
                            process_btn = gr.Button("⚡ Process Utterance (Amal Karein)", variant="primary", scale=2)
                            clear_btn = gr.Button("🧹 Clear", scale=1)

                        gr.Markdown("#### 💡 Quick Voice / Text Examples (Click to Try):")
                        with gr.Row():
                            ex1 = gr.Button("Ahmed ko do kilo cheeni udhaar di, 400 rupay", size="sm")
                            ex2 = gr.Button("Bilal ne 500 rupay wapas kiye", size="sm")
                        with gr.Row():
                            ex3 = gr.Button("Ahmed ka kitna baqaya hai?", size="sm")
                            ex4 = gr.Button("ahmad bhai ko ek dozen anday udhaar, 360", size="sm")
                        with gr.Row():
                            ex5 = gr.Button("احمد کو دو کلو چینی ادھار دی چار سو روپے", size="sm")
                            ex6 = gr.Button("Aaj ka hisaab dikhao", size="sm")

                        ex1.click(lambda: "Ahmed ko do kilo cheeni udhaar di, 400 rupay", outputs=[text_input])
                        ex2.click(lambda: "Bilal ne 500 rupay wapas kiye", outputs=[text_input])
                        ex3.click(lambda: "Ahmed ka kitna baqaya hai?", outputs=[text_input])
                        ex4.click(lambda: "ahmad bhai ko ek dozen anday udhaar, 360", outputs=[text_input])
                        ex5.click(lambda: "احمد کو دو کلو چینی ادھار دی چار سو روپے", outputs=[text_input])
                        ex6.click(lambda: "Aaj ka hisaab dikhao", outputs=[text_input])

                    with gr.Column(scale=5):
                        status_box = gr.Textbox(
                            label="📢 Status / Guidance",
                            value="Ready. Speak or type to record transactions.",
                            interactive=False,
                        )
                        with gr.Row():
                            intent_output = gr.Textbox(label="🎯 Detected Intent", interactive=False)
                        details_output = gr.Textbox(
                            label="📋 Parsed Details / Answer",
                            lines=4,
                            interactive=False,
                        )

                        # Confirm-Before-Save Panel
                        with gr.Group(visible=False, elem_classes=["confirm-panel"]) as confirm_panel:
                            gr.Markdown("### ⚠️ Tasdeeq Karein (Confirm Before Save):")
                            confirm_text = gr.Markdown(value="")
                            with gr.Row():
                                confirm_btn = gr.Button("✅ Confirm & Save to Ledger", variant="primary")
                                cancel_btn = gr.Button("❌ Cancel", variant="stop")

                pending_state = gr.State(value=None)

                # Process event
                process_btn.click(
                    fn=handle_process,
                    inputs=[text_input],
                    outputs=[
                        intent_output,
                        details_output,
                        confirm_text,
                        confirm_panel,
                        pending_state,
                        status_box,
                        # ledger table below
                    ],
                )

                # Clear event
                clear_btn.click(
                    fn=lambda: ("", "", "Ready.", "—", "—", gr.update(visible=False), None),
                    outputs=[
                        mic_input,
                        text_input,
                        status_box,
                        intent_output,
                        details_output,
                        confirm_panel,
                        pending_state,
                    ],
                )

                gr.Markdown("---")
                # Live Ledger Table
                with gr.Row():
                    gr.Markdown("### 📖 Live Customer Ledger (Khata Register)")
                    refresh_table_btn = gr.Button("🔄 Refresh Ledger", size="sm")

                ledger_table = gr.Dataframe(
                    headers=["ID", "Customer Name", "Current Balance", "Status", "Total Entries", "Last Activity"],
                    datatype=["number", "str", "str", "str", "number", "str"],
                    value=get_ledger_dataframe,
                    interactive=False,
                )

                refresh_table_btn.click(fn=get_ledger_dataframe, outputs=[ledger_table])

                # Wire Confirm and Cancel buttons
                confirm_btn.click(
                    fn=handle_confirm,
                    inputs=[pending_state],
                    outputs=[status_box, confirm_panel, pending_state, ledger_table],
                )
                cancel_btn.click(
                    fn=handle_cancel,
                    outputs=[status_box, confirm_panel, pending_state],
                )

                # Also update ledger table on process completion
                process_btn.click(
                    fn=get_ledger_dataframe,
                    outputs=[ledger_table],
                )

            # TAB 2: Daily Summary & Top Debtors & Reminders
            with gr.Tab("📊 Daily Summary & Top Debtors (Hisaab Kitab)"):
                with gr.Row():
                    refresh_analytics_btn = gr.Button("🔄 Update Analytics Now", variant="primary")

                with gr.Row():
                    with gr.Column(scale=5):
                        daily_summary_output = gr.Textbox(
                            label="📅 Aaj Ka Kul Hisaab (Daily Ledger Summary)",
                            lines=7,
                            interactive=False,
                            value=lambda: answer_daily_summary()["text_response"],
                        )
                    with gr.Column(scale=5):
                        gr.Markdown("### 🏆 Sab Se Zyada Udhaar (Top Debtors)")
                        top_debtors_table = gr.Dataframe(
                            headers=["ID", "Name", "Outstanding Udhaar", "Status"],
                            datatype=["number", "str", "str", "str"],
                            value=lambda: refresh_analytics()[1],
                            interactive=False,
                        )

                refresh_analytics_btn.click(
                    fn=refresh_analytics,
                    outputs=[daily_summary_output, top_debtors_table],
                )

                gr.Markdown("---")
                gr.Markdown("### ✉️ WhatsApp / SMS Reminder Generator")
                with gr.Row():
                    reminder_cust_input = gr.Textbox(
                        label="Customer Name",
                        placeholder="e.g. Ahmed",
                    )
                    gen_reminder_btn = gr.Button("📝 Draft Polite Reminder", variant="secondary")

                reminder_message_box = gr.Textbox(
                    label="Drafted Polite Reminder (Roman Urdu)",
                    lines=3,
                    interactive=False,
                )

                gen_reminder_btn.click(
                    fn=generate_reminder_for_customer,
                    inputs=[reminder_cust_input],
                    outputs=[reminder_message_box],
                )

        # Footer
        gr.Markdown(
            """
            ---
            *KhataTalk • Offline Voice-First Ledger Architecture • MIT License • Built for Pakistani Shopkeepers*
            """
        )

    return demo


def main():
    """Starts the Gradio application."""
    port = int(os.getenv("PORT", "7860"))
    demo = build_app()
    logger.info("Starting KhataTalk Gradio interface on port %d...", port)
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)


if __name__ == "__main__":
    main()
