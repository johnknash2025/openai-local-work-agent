#!/usr/bin/env python3
"""Minimal Discord bot for local-content-agent ops."""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from typing import Iterable

import discord
from discord.ext import commands


STARTED_AT = time.time()
BASE_DIR = Path(__file__).resolve().parent
PROJECT_LINKS = [
    ("local-content-agent", "file:///Users/keigofukumoto/github/local-content-agent/"),
    ("local-agent-orchestrator", "file:///Users/keigofukumoto/github/local-agent-orchestrator/"),
    ("project-dashboard", "file:///Users/keigofukumoto/github/project-dashboard/"),
]


def chunk_text(lines: Iterable[str], limit: int = 1800) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def is_manager(interaction: discord.Interaction) -> bool:
    perms = interaction.user.guild_permissions if interaction.guild and interaction.user else None
    return bool(perms and (perms.manage_channels or perms.administrator))


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        if not getattr(bot, "_tree_synced", False):
            await bot.tree.sync()
            bot._tree_synced = True
        print(f"Logged in as {bot.user} (id={bot.user.id if bot.user else 'unknown'})")

    @bot.tree.command(name="ping", description="Check whether the bot is alive.")
    async def ping(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("pong", ephemeral=False)

    @bot.tree.command(name="status", description="Show a short ops status.")
    async def status(interaction: discord.Interaction) -> None:
        uptime = int(time.time() - STARTED_AT)
        message = (
            "local-content-agent status\n"
            f"- host: {platform.node()}\n"
            f"- platform: {platform.system()} {platform.release()}\n"
            f"- uptime_s: {uptime}\n"
            f"- repo: {BASE_DIR}\n"
            f"- cwd: {Path.cwd()}"
        )
        await interaction.response.send_message(f"```text\n{message}\n```", ephemeral=False)

    @bot.tree.command(name="handoff", description="Show the current handoff preview.")
    async def handoff(interaction: discord.Interaction) -> None:
        handoff_path = BASE_DIR / "HANDOFF.md"
        if not handoff_path.exists():
            await interaction.response.send_message("HANDOFF.md not found", ephemeral=False)
            return
        text = handoff_path.read_text(encoding="utf-8")
        preview = text[:1700]
        await interaction.response.send_message(f"```md\n{preview}\n```", ephemeral=False)

    @bot.tree.command(name="links", description="Show canonical local project links.")
    async def links(interaction: discord.Interaction) -> None:
        lines = ["canonical links"]
        lines.extend(f"- {name}: {url}" for name, url in PROJECT_LINKS)
        await interaction.response.send_message(f"```text\n" + "\n".join(lines) + "\n```", ephemeral=False)

    @bot.tree.command(name="guilds", description="List guilds the bot can currently see.")
    async def guilds(interaction: discord.Interaction) -> None:
        lines = ["visible guilds"]
        for guild in sorted(bot.guilds, key=lambda g: g.name.lower()):
            lines.append(f"- {guild.name} (id={guild.id}, members={guild.member_count or 'unknown'})")
        await interaction.response.send_message(f"```text\n" + "\n".join(lines) + "\n```", ephemeral=False)

    @bot.tree.command(name="channels", description="List categories and channels in this guild.")
    async def channels(interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run inside a guild.", ephemeral=True)
            return

        lines = [f"channels for {guild.name}"]
        categorized_ids: set[int] = set()
        for category in guild.categories:
            lines.append(f"[category] {category.name} (id={category.id})")
            for channel in sorted(category.channels, key=lambda c: c.position):
                categorized_ids.add(channel.id)
                lines.append(
                    f"  - #{channel.name} [{channel.__class__.__name__}] (id={channel.id})"
                )

        uncategorized = [
            channel for channel in guild.channels if channel.category is None and channel.id not in categorized_ids
        ]
        if uncategorized:
            lines.append("[category] uncategorized")
            for channel in sorted(uncategorized, key=lambda c: c.position):
                lines.append(f"  - #{channel.name} [{channel.__class__.__name__}] (id={channel.id})")

        parts = chunk_text(lines)
        await interaction.response.send_message(f"```text\n{parts[0]}\n```", ephemeral=False)
        for part in parts[1:]:
            await interaction.followup.send(f"```text\n{part}\n```", ephemeral=False)

    @bot.tree.command(name="channelinfo", description="Show details for a channel by id.")
    async def channelinfo(interaction: discord.Interaction, channel_id: str) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run inside a guild.", ephemeral=True)
            return
        try:
            numeric_id = int(channel_id.strip())
        except ValueError:
            await interaction.response.send_message("channel_id must be numeric.", ephemeral=True)
            return

        channel = guild.get_channel(numeric_id)
        if channel is None:
            await interaction.response.send_message(f"Channel {numeric_id} not found in this guild.", ephemeral=True)
            return

        lines = [
            f"name: {channel.name}",
            f"id: {channel.id}",
            f"type: {channel.__class__.__name__}",
            f"category: {channel.category.name if channel.category else 'none'}",
            f"position: {channel.position}",
            f"mention: {channel.mention}",
        ]
        topic = getattr(channel, "topic", None)
        if topic:
            lines.append(f"topic: {topic}")
        await interaction.response.send_message(f"```text\n" + "\n".join(lines) + "\n```", ephemeral=False)

    @bot.tree.command(name="create_category", description="Create a category in this guild.")
    async def create_category(interaction: discord.Interaction, name: str) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run inside a guild.", ephemeral=True)
            return
        if not is_manager(interaction):
            await interaction.response.send_message("Manage Channels permission is required.", ephemeral=True)
            return
        category = await guild.create_category(name=name, reason=f"Requested by {interaction.user}")
        await interaction.response.send_message(
            f"Created category `{category.name}` (id={category.id}).",
            ephemeral=False,
        )

    @bot.tree.command(name="create_text_channel", description="Create a text channel in this guild.")
    async def create_text_channel(
        interaction: discord.Interaction,
        name: str,
        category_id: str | None = None,
        topic: str | None = None,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run inside a guild.", ephemeral=True)
            return
        if not is_manager(interaction):
            await interaction.response.send_message("Manage Channels permission is required.", ephemeral=True)
            return
        category = None
        if category_id:
            try:
                category = guild.get_channel(int(category_id.strip()))
            except ValueError:
                await interaction.response.send_message("category_id must be numeric.", ephemeral=True)
                return
            if category is None or not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message("Category not found.", ephemeral=True)
                return
        channel = await guild.create_text_channel(
            name=name,
            category=category,
            topic=topic,
            reason=f"Requested by {interaction.user}",
        )
        await interaction.response.send_message(
            f"Created text channel {channel.mention} (id={channel.id}).",
            ephemeral=False,
        )

    @bot.tree.command(name="rename_channel", description="Rename a channel by id.")
    async def rename_channel(interaction: discord.Interaction, channel_id: str, new_name: str) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run inside a guild.", ephemeral=True)
            return
        if not is_manager(interaction):
            await interaction.response.send_message("Manage Channels permission is required.", ephemeral=True)
            return
        try:
            channel = guild.get_channel(int(channel_id.strip()))
        except ValueError:
            await interaction.response.send_message("channel_id must be numeric.", ephemeral=True)
            return
        if channel is None:
            await interaction.response.send_message("Channel not found.", ephemeral=True)
            return
        old_name = channel.name
        await channel.edit(name=new_name, reason=f"Requested by {interaction.user}")
        await interaction.response.send_message(
            f"Renamed `{old_name}` to `{new_name}`.",
            ephemeral=False,
        )

    @bot.tree.command(name="move_channel", description="Move a channel into a category.")
    async def move_channel(interaction: discord.Interaction, channel_id: str, category_id: str) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run inside a guild.", ephemeral=True)
            return
        if not is_manager(interaction):
            await interaction.response.send_message("Manage Channels permission is required.", ephemeral=True)
            return
        try:
            channel = guild.get_channel(int(channel_id.strip()))
            category = guild.get_channel(int(category_id.strip()))
        except ValueError:
            await interaction.response.send_message("channel_id and category_id must be numeric.", ephemeral=True)
            return
        if channel is None:
            await interaction.response.send_message("Channel not found.", ephemeral=True)
            return
        if category is None or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("Category not found.", ephemeral=True)
            return
        await channel.edit(category=category, reason=f"Requested by {interaction.user}")
        await interaction.response.send_message(
            f"Moved `{channel.name}` into category `{category.name}`.",
            ephemeral=False,
        )

    @bot.tree.command(name="set_channel_topic", description="Set the topic for a text channel.")
    async def set_channel_topic(interaction: discord.Interaction, channel_id: str, topic: str) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be run inside a guild.", ephemeral=True)
            return
        if not is_manager(interaction):
            await interaction.response.send_message("Manage Channels permission is required.", ephemeral=True)
            return
        try:
            channel = guild.get_channel(int(channel_id.strip()))
        except ValueError:
            await interaction.response.send_message("channel_id must be numeric.", ephemeral=True)
            return
        if channel is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Text channel not found.", ephemeral=True)
            return
        await channel.edit(topic=topic, reason=f"Requested by {interaction.user}")
        await interaction.response.send_message(
            f"Updated topic for {channel.mention}.",
            ephemeral=False,
        )

    return bot


def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("DISCORD_BOT_TOKEN is not set")
    bot = build_bot()
    bot.run(token)


if __name__ == "__main__":
    main()
