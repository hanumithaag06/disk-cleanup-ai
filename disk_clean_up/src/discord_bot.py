# discord_bot.py
import discord
import asyncio
import logging
import os
import sys
from pathlib import Path
import io
from datetime import datetime, UTC
from functools import partial
from demo_files_creator import generate_demo_files
# ── Step 1: add src/ to path so plain imports resolve ─────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from discord.ui import View
from models import FileEntry
from config import (
    DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID,
    AUTHORIZED_USER_ID, MONITORED_FOLDER, DELETED_FOLDER, THRESHOLD_DAYS
)

# ── PDF generation ────────────────────────────────────────
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Real integrations ─────────────────────────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from scanner import scan_folder
from classifier import classify_files as _classify_files
from cleanup import move_safe_files, restore_all_files, permanently_delete_all
from config import MONITORED_FOLDER, DELETED_FOLDER, THRESHOLD_DAYS

def _to_file_entry(d: dict) -> FileEntry:
    """Bridge: classifier dict → FileEntry for the bot UI."""
    return FileEntry(
        path           = d.get("path", d.get("name", "unknown")),
        size_kb        = d.get("size_mb", 0) * 1024,
        age_days       = d.get("days_since_last_access", 0),
        classification = "safe_to_delete" if d.get("decision") == "SAFE_DELETE" else "keep",
        explanation    = d.get("reason", ""),
        confidence     = d.get("confidence", 0.0),
        is_duplicate   = d.get("is_duplicate", False),
        duplicate_of   = d.get("duplicate_of", None),
    )

def scan_directory(root: str, max_age_days: int | None = None) -> list[FileEntry]:
    raw   = scan_folder(root)
    threshold = max_age_days or THRESHOLD_DAYS
    classified = _classify_files(raw, threshold_days=threshold)
    return [_to_file_entry(d) for d in classified]

async def async_scan(root: str, max_age_days: int | None = None) -> list[FileEntry]:
    loop = asyncio.get_event_loop()
    from functools import partial
    return await loop.run_in_executor(None, partial(scan_directory, root, max_age_days))

def delete_files(files: list[FileEntry]) -> float:
    as_dicts = [
        {"decision": "SAFE_DELETE", "path": f.path}
        for f in files
    ]
    
    move_safe_files(as_dicts)  
    
    for f in files:
        f.deleted = True
    return sum(f.size_kb for f in files)

def restore_files(filenames: list[str]) -> int:
    restored = restore_all_files()   # moves everything in deleted_files/ → monitored_folder/
    return len(restored)

def permanent_delete(filenames: list[str]) -> int:
    deleted = permanently_delete_all()
    return len(deleted)

# ── Discord client ────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ── Auth check ────────────────────────────────────────────
def is_authorized(interaction: discord.Interaction) -> bool:
    return interaction.user.id == AUTHORIZED_USER_ID


# ── Helper: disable all buttons in a view after selection ─
async def lock_view(view: View, interaction: discord.Interaction):
    """Disables all buttons and updates the original message."""
    for item in view.children:
        item.disabled = True
    await interaction.message.edit(view=view)


def generate_pdf_report(
    files,
    action_taken: str,
    files_affected: int,
    space_freed_kb: float,
    timestamp: datetime
) -> io.BytesIO:
    """
    Generates an in-memory PDF cleanup report and returns it as a BytesIO buffer.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.HexColor("#5865F2"),  # Discord blurple
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#23272A"),
        spaceBefore=14,
        spaceAfter=4,
    )
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=normal, fontSize=9, textColor=colors.grey)

    safe   = [f for f in files if f.classification == "safe_to_delete"]
    keep   = [f for f in files if f.classification == "keep"]
    review = [f for f in files if f.confidence and f.confidence < 0.75]

    story = []

    # ── Header ──
    story.append(Paragraph("Disk Cleanup Report", title_style))
    story.append(Paragraph(
        f"Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        small
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#5865F2"), spaceAfter=10))

    # ── Summary table ──
    story.append(Paragraph("Summary", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Action taken", action_taken],
        ["Files affected", str(files_affected)],
        ["Space freed", f"{space_freed_kb / (1024 * 1024):.2f} GB"],
        ["Total files scanned", str(len(files))],
        ["Safe to delete", str(len(safe))],
        ["Kept", str(len(keep))],
        ["Needs manual review", str(len(review))],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 4 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#5865F2")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F2F3F5"), colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # ── Safe to delete ──
    if safe:
        story.append(Paragraph("Files Marked Safe to Delete", heading_style))
        del_data = [["File", "Size (MB)", "Age (days)", "Confidence", "Reason"]]
        for f in safe:
            del_data.append([
                os.path.basename(f.path),
                f"{f.size_kb / 1024:.1f}",
                str(f.age_days),
                f"{int((f.confidence or 0) * 100)}%",
                f.explanation[:50],
            ])
        del_table = Table(del_data, colWidths=[1.6*inch, 0.9*inch, 0.85*inch, 0.85*inch, 2.3*inch])
        del_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#ED4245")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#FFF0F0"), colors.white]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("WORDWRAP",      (0, 0), (-1, -1), True),
        ]))
        story.append(del_table)
        story.append(Spacer(1, 14))

    # ── Keep ──
    if keep:
        story.append(Paragraph("Files to Keep", heading_style))
        keep_data = [["File", "Size (KB)", "Age (days)", "Confidence", "Reason"]]
        for f in keep:
            keep_data.append([
                os.path.basename(f.path),
                str(f.size_kb),
                str(f.age_days),
                f"{int((f.confidence or 0) * 100)}%",
                f.explanation[:50],
            ])
        keep_table = Table(keep_data, colWidths=[1.6*inch, 0.9*inch, 0.85*inch, 0.85*inch, 2.3*inch])
        keep_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#57F287")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.HexColor("#23272A")),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#F0FFF4"), colors.white]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(keep_table)
        story.append(Spacer(1, 14))

    # ── Needs manual review ──
    if review:
        story.append(Paragraph("Files Needing Manual Review", heading_style))
        rev_data = [["File", "Confidence", "Reason"]]
        for f in review:
            rev_data.append([
                os.path.basename(f.path),
                f"{int((f.confidence or 0) * 100)}%",
                f.explanation[:70],
            ])
        rev_table = Table(rev_data, colWidths=[2.5*inch, 1*inch, 4*inch])
        rev_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#FEE75C")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.HexColor("#23272A")),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#FFFBF0"), colors.white]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(rev_table)

    # ── Footer ──
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Generated by Disk Cleanup Recommender Bot — Confidential",
        small
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ── Helper: send final report embed + PDF ────────────────
async def send_final_report(
    channel,
    files,
    action_taken,
    files_affected,
    space_freed_kb
):
    print("SEND_FINAL_REPORT CALLED")
    try:
        now = datetime.now(UTC)

        embed = discord.Embed(
            title="📋 Session Report — Disk Cleanup Complete",
            description="Full PDF report attached below.",
            color=discord.Color.blurple(),
            timestamp=now
        )

        await channel.send(embed=embed)

        pdf_buffer = generate_pdf_report(
            files,
            action_taken,
            files_affected,
            space_freed_kb,
            now
        )

        filename = f"cleanup_report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"

        await channel.send(
            content="📎 Cleanup report PDF:",
            file=discord.File(
                fp=pdf_buffer,
                filename=filename
            )
        )

    except Exception as e:
        await channel.send(f"❌ PDF generation failed:\n```{e}```")


# ─────────────────────────────────────────────────────────
# STEP 1 — Choose analysis mode
# ─────────────────────────────────────────────────────────
class ChooseModeView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Agent threshold analysis",
        style=discord.ButtonStyle.primary,
        emoji="🤖"
    )
    async def agent_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return

        await lock_view(self, interaction)
        await interaction.response.send_message(
            "🔍 Scanning and classifying files…", ephemeral=True
        )

        files = await async_scan(str(MONITORED_FOLDER))

        embed, view = build_results_embed(files)
        await interaction.channel.send(embed=embed, view=view)

    @discord.ui.button(
        label="Custom threshold",
        style=discord.ButtonStyle.secondary,
        emoji="⚙️"
    )
    async def custom_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return

        await lock_view(self, interaction)
        await interaction.response.send_message(
            "⚙️ Type the threshold in days (e.g. `90`, `180`, `365`) and send it here:"
        )

        def check(m):
            return (
                m.author.id == AUTHORIZED_USER_ID
                and m.channel.id == DISCORD_CHANNEL_ID
                and m.content.strip().isdigit()
            )

        try:
            msg = await client.wait_for("message", check=check, timeout=30)
            days = int(msg.content.strip())

            await interaction.channel.send(
                f"🔍 Scanning with threshold: **{days} days**…"
            )

            files = await async_scan(str(MONITORED_FOLDER), max_age_days=days)

            embed, view = build_results_embed(files, threshold=days)
            await interaction.channel.send(embed=embed, view=view)

        except asyncio.TimeoutError:
            await interaction.channel.send(
                "⏱️ No input received in 30 seconds. Use the menu above to try again."
            )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="✖️"
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return

        await lock_view(self, interaction)
        await interaction.response.send_message("✖️ Cancelled.", ephemeral=True)



# ─────────────────────────────────────────────────────────
# STEP 2 — Review recommendations
# ─────────────────────────────────────────────────────────
class ReviewView(View):
    def __init__(self, files):
        super().__init__(timeout=120)
        self.files = files

    @discord.ui.button(
        label="Move suggested files to recycle bin",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def move_files(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return

        to_delete = [f for f in self.files if f.classification == "safe_to_delete"]
        if not to_delete:
            await interaction.response.send_message(
                "No files marked as safe to delete.", ephemeral=True
            )
            return

        await lock_view(self, interaction)
        recovered_kb = delete_files(to_delete)

        embed = discord.Embed(
            title="🗑️ Files moved to recycle bin",
            description=(
                f"**{len(to_delete)}** files moved to `deleted_files/`\n"
                f"**Space freed:** {recovered_kb / (1024 * 1024):.2f} GB\n\n"
                "What would you like to do next?"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text="Use the buttons below to restore or permanently delete")
        await interaction.response.send_message(
            embed=embed,
            view=RecycleBinView(self.files, recovered_kb)
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="✖️"
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await lock_view(self, interaction)
        await interaction.response.send_message(
            "✖️ Cancelled. No files were moved.", ephemeral=True
        )


# ─────────────────────────────────────────────────────────
# STEP 3 — Restore or permanently delete
# Mutex: once any action button is pressed, all others are
# immediately disabled so only one path can execute.
# ─────────────────────────────────────────────────────────
class RecycleBinView(View):
    def __init__(self, all_files, recovered_kb: float = 0):
        super().__init__(timeout=None)
        self.all_files   = all_files    # full file list for the report
        self.recovered_kb = recovered_kb
        self._acted      = False        # ← mutex flag

    async def _acquire(self, interaction: discord.Interaction) -> bool:
        """
        Returns True if this interaction won the mutex and may proceed.
        Returns False (and sends an ephemeral notice) if already taken.
        """
        if self._acted:
            await interaction.response.send_message(
                "⚠️ An action has already been taken for this session.",
                ephemeral=True
            )
            return False
        self._acted = True
        await lock_view(self, interaction)  # disable every button immediately
        return True

    @discord.ui.button(
        label="Restore files",
        style=discord.ButtonStyle.success,
        emoji="♻️"
    )
    async def restore(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        if not await self._acquire(interaction):
            return

        deleted_dir = "./deleted_files"
        files_in_bin = (
            os.listdir(deleted_dir) if os.path.exists(deleted_dir) else []
        )

        if not files_in_bin:
            await interaction.response.send_message("Recycle bin is empty.", ephemeral=True)
            self._acted = False   # release mutex so user can try again
            return

        file_list = "\n".join([f"`{f}`" for f in files_in_bin[:10]])
        if len(files_in_bin) > 10:
            file_list += f"\n… and {len(files_in_bin) - 10} more"

        restored = restore_files(files_in_bin)
        embed = discord.Embed(
            title="♻️ Files restored",
            description=f"{file_list}\n\n**{restored} file(s)** returned to `sandbox/`",
            color=discord.Color.green(),
            timestamp=datetime.now(UTC)
        )
        await interaction.response.send_message(embed=embed)

        # ── Final session report + PDF ──
        await send_final_report(
            channel        = interaction.channel,
            files          = self.all_files,
            action_taken   = "Restored to sandbox",
            files_affected = restored,
            space_freed_kb = 0,
        )

    @discord.ui.button(
        label="Permanently delete",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def perm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        if not await self._acquire(interaction):
            return

        deleted_dir = "./deleted_files"
        files_in_bin = (
            os.listdir(deleted_dir) if os.path.exists(deleted_dir) else []
        )

        if not files_in_bin:
            await interaction.response.send_message("Recycle bin is empty.", ephemeral=True)
            self._acted = False
            return

        file_list = "\n".join([f"`{f}`" for f in files_in_bin[:10]])
        if len(files_in_bin) > 10:
            file_list += f"\n… and {len(files_in_bin) - 10} more"

        embed = discord.Embed(
            title="⚠️ Confirm permanent deletion",
            description=f"{file_list}\n\n**This cannot be undone.**",
            color=discord.Color.red(),
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text="You have 60 seconds to confirm")
        await interaction.response.send_message(
            embed=embed,
            view=ConfirmDeleteView(files_in_bin, self.all_files, self.recovered_kb)
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="✖️"
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._acquire(interaction):
            return
        await interaction.response.send_message(
            "✖️ No action taken. Files remain in the recycle bin.", ephemeral=True
        )


# ─────────────────────────────────────────────────────────
# STEP 3b — Confirm permanent delete
# ─────────────────────────────────────────────────────────
class ConfirmDeleteView(View):
    def __init__(self, files_in_bin, all_files, recovered_kb: float = 0):
        super().__init__(timeout=60)
        self.files_in_bin = files_in_bin
        self.all_files    = all_files
        self.recovered_kb = recovered_kb
        self._acted       = False

    async def _acquire(self, interaction: discord.Interaction) -> bool:
        if self._acted:
            await interaction.response.send_message(
                "⚠️ An action has already been taken.", ephemeral=True
            )
            return False
        self._acted = True
        await lock_view(self, interaction)
        return True

    @discord.ui.button(
        label="Confirm — delete permanently",
        style=discord.ButtonStyle.danger,
        emoji="⚠️"
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("Unauthorized.", ephemeral=True)
            return
        if not await self._acquire(interaction):
            return

        count = permanent_delete(self.files_in_bin)

        embed = discord.Embed(
            title="🗑️ Permanent deletion complete",
            description=f"**{count} file(s)** have been permanently deleted.",
            color=discord.Color.red(),
            timestamp=datetime.now(UTC)
        )
        await interaction.response.send_message(embed=embed)

        # Generate PDF
        now = datetime.now(UTC)
        pdf_buffer = generate_pdf_report(
            self.all_files,
            "Permanently deleted",
            count,
            self.recovered_kb,
            now
        )
        filename = f"cleanup_report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"

        # Send the PDF using interaction.channel.send
        await interaction.channel.send(
            content="📎 Cleanup report",
            file=discord.File(fp=pdf_buffer, filename=filename)
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="✖️"
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._acquire(interaction):
            return
        await interaction.response.send_message(
            "✖️ Permanent delete cancelled. Files remain in the recycle bin.",
            ephemeral=True
        )


# ── Embed builder ─────────────────────────────────────────
def build_results_embed(files, threshold=None):
    safe   = [f for f in files if f.classification == "safe_to_delete" and not f.is_duplicate]
    dupes  = [f for f in files if f.is_duplicate]
    keep   = [f for f in files if f.classification == "keep"]
    review = [f for f in files if f.confidence and f.confidence < 0.75]

    title = (
        "🤖 AI analysis complete"
        if not threshold
        else f"⚙️ AI analysis complete — threshold: {threshold} days"
    )
    total_kb = sum(f.size_kb for f in safe) + sum(f.size_kb for f in dupes)

    embed = discord.Embed(
        title=title,
        description=(
            f"**{len(files)}** files analysed · "
            f"**{len(safe) + len(dupes)}** suggested for deletion · "
            f"**{total_kb / (1024 * 1024):.2f} GB** recoverable"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(UTC)
    )

    # ── Duplicates section ────────────────────────────────
    if dupes:
        lines = []
        for f in dupes[:5]:
            original_name = os.path.basename(f.duplicate_of) if f.duplicate_of else "unknown"
            lines.append(
                f"`{os.path.basename(f.path)}`\n"
                f"> Exact copy of `{original_name}`"
            )
        if len(dupes) > 5:
            lines.append(f"> … and {len(dupes) - 5} more duplicates")
        embed.add_field(
            name=f"🔁  Duplicates — {len(dupes)} file(s)",
            value="\n\n".join(lines),
            inline=False
        )

    # ── Safe to delete (non-duplicate) ───────────────────
    if safe:
        lines = []
        for f in safe[:6]:
            conf = int((f.confidence or 0) * 100)
            bar  = "█" * (conf // 10) + "░" * (10 - conf // 10)
            lines.append(
                f"`{os.path.basename(f.path)}`\n"
                f"> {f.explanation[:70]}\n"
                f"> Confidence: `{bar}` {conf}%"
            )
        embed.add_field(
            name=f"🗑️  Safe to delete — {len(safe)} file(s)",
            value="\n\n".join(lines),
            inline=False
        )

    if keep:
        lines = []
        for f in keep[:4]:
            conf = int((f.confidence or 0) * 100)
            lines.append(
                f"`{os.path.basename(f.path)}` — {conf}% confidence\n"
                f"> {f.explanation[:70]}"
            )
        embed.add_field(
            name=f"✅  Keep — {len(keep)} file(s)",
            value="\n\n".join(lines),
            inline=False
        )

    if review:
        lines = [
            f"`{os.path.basename(f.path)}` — {int((f.confidence or 0) * 100)}% confidence"
            for f in review[:3]
        ]
        embed.add_field(
            name=f"⚠️  Needs manual review — {len(review)} file(s)",
            value="\n".join(lines),
            inline=False
        )

    embed.set_footer(text="Review the suggestions above, then choose an action")
    return embed, ReviewView(files)


# ── Helper: post the startup embed ──────────────────────
async def post_start_embed(channel):
    embed = discord.Embed(
        title="💾 Disk Cleanup Recommender",
        description=(
            "AI-powered file analysis — choose a mode to begin.\n\n"
            "**🤖 Agent threshold** — uses AI default settings\n"
            "**⚙️ Custom threshold** — set your own age cutoff in days"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(UTC)
    )
    embed.set_footer(text="Only authorized users can interact with these controls")
    await channel.send(embed=embed, view=ChooseModeView())


# ── /start slash command ──────────────────────────────────
@tree.command(name="start", description="Launch the Disk Cleanup Recommender")
async def start(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("Unauthorized.", ephemeral=True)
        return

    await interaction.response.send_message("✅ Starting…", ephemeral=True)
    await post_start_embed(interaction.channel)

@tree.command(
    name="create_test_data",
    description="Generate test files"
)
async def create_test_data(
    interaction: discord.Interaction,
    count: int
):
    if not is_authorized(interaction):
        await interaction.response.send_message(
            "Unauthorized.",
            ephemeral=True
        )
        return

    if count < 1 or count > 500:
        await interaction.response.send_message(
            "Count must be between 1 and 500.",
            ephemeral=True
        )
        return

    generate_demo_files(
        folder=str(MONITORED_FOLDER),
        files_per_run=count
    )

    await interaction.response.send_message(
        f"✅ Generated {count} demo files."
    )
@tree.command(
    name="list_files",
    description="List files in monitored folder"
)
async def list_files(
    interaction: discord.Interaction
):
    if not is_authorized(interaction):
        await interaction.response.send_message(
            "Unauthorized.",
            ephemeral=True
        )
        return

    files = scan_folder(
        str(MONITORED_FOLDER)
    )

    if not files:
        await interaction.response.send_message(
            "No files found."
        )
        return

    lines = []

    for f in files[:50]:

        lines.append(
            f"📄 {f['name']} | "
            f"{f['size_mb']} MB | "
            f"{f['days_since_last_access']} days"
        )

    await interaction.response.send_message(
        "\n".join(lines)
    )
@tree.command(
    name="list_files_rb",
    description="List recycle bin files"
)
async def list_files_rb(
    interaction: discord.Interaction
):
    if not is_authorized(interaction):
        await interaction.response.send_message(
            "Unauthorized.",
            ephemeral=True
        )
        return

    files = list(
        Path(DELETED_FOLDER).glob("*")
    )

    if not files:
        await interaction.response.send_message(
            "Recycle bin empty."
        )
        return

    lines = []

    for file in files[:50]:

        size_mb = round(
            file.stat().st_size /
            (1024 * 1024),
            2
        )

        lines.append(
            f"🗑️ {file.name} | "
            f"{size_mb} MB"
        )

    await interaction.response.send_message(
        "\n".join(lines)
    )
@tree.command(
    name="help",
    description="Show commands"
)
async def help_cmd(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="Disk Cleanup Commands",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="/start",
        value="Start cleanup workflow",
        inline=False
    )

    embed.add_field(
        name="/create_test_data count",
        value="Generate demo files",
        inline=False
    )

    embed.add_field(
        name="/list_files",
        value="List sandbox files",
        inline=False
    )

    embed.add_field(
        name="/list_files_rb",
        value="List recycle bin files",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )
# ── Bot startup ───────────────────────────────────────────
@client.event
async def on_ready():
    logger.info(f"Bot online as {client.user}")
    await tree.sync()
    logger.info("Slash commands synced — use /start to begin a session")


def start_bot():
    client.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    start_bot()
