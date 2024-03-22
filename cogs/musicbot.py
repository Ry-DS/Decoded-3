# Inspired by https://github.com/afazio1/robotic-nation-proj/blob/main/projects/discord-bot/new-music-bot/music-yt.py

import os
import subprocess
import time

import discord
import requests
import wavelink
from discord.ext import commands
from dotenv import load_dotenv


class MusicBot(commands.Cog):
    voice_clients = {}

    def __init__(self, client):
        self.client = client

    @commands.command()
    async def join(self, ctx: commands.Context):
        # Leave current channel
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
        if not ctx.message.author.voice:
            await ctx.send('You are not in a voice channel')
            return
        channel = ctx.message.author.voice.channel
        self.voice_clients[ctx.guild.id] = await channel.connect(cls=wavelink.Player())
        await ctx.send(f'Joined {channel}')

    @commands.command()
    async def leave(self, ctx):
        if ctx.guild.id in self.voice_clients:
            await self.voice_clients[ctx.guild.id].stop()
            del self.voice_clients[ctx.guild.id]
            await ctx.send('Left')
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()

    @commands.command()
    async def play(self, ctx, *, search: str):
        if ctx.guild.id not in self.voice_clients:
            # Join the user's voice channel
            await self.join(ctx)
        if ctx.guild.id not in self.voice_clients:
            return
        voice = self.voice_clients[ctx.guild.id]

        tracks: wavelink.Search = await wavelink.Playable.search(search)
        if not tracks:
            await ctx.send('Found nothing')
            return

        if isinstance(tracks, wavelink.Playlist):
            # tracks is a playlist...
            added: int = await voice.queue.put_wait(tracks)
            await ctx.send(f"Added the playlist **`{tracks.name}`** ({added} songs) to the queue.")
        else:
            track: wavelink.Playable = tracks[0]
            await voice.queue.put_wait(track)
            embed = discord.Embed(
                title=track.title,
                url=track.uri,
                description=f"Playing {track.title} in {voice.channel} ({voice.queue.count} items in queue)"
            )
            embed.set_image(url=track.artwork)
            if hasattr(ctx.author, 'avatar'):
                embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar.url)
            await ctx.send(embed=embed)

        if not voice.playing:
            await voice.play(voice.queue.get())

    @commands.command()
    async def stop(self, ctx):
        if ctx.guild.id in self.voice_clients:
            await self.voice_clients[ctx.guild.id].stop()
            await ctx.send('Stopped')
        else:
            await ctx.send('Not in a voice channel')

    @commands.command()
    async def pause(self, ctx):
        if ctx.guild.id in self.voice_clients:
            player = self.voice_clients[ctx.guild.id]
            await player.pause(True)
            await ctx.send('Paused')
        else:
            await ctx.send('Not in a voice channel')

    @commands.command()
    async def resume(self, ctx):
        if ctx.guild.id in self.voice_clients:
            await self.voice_clients[ctx.guild.id].pause(False)
            await ctx.send('Resumed')
        else:
            await ctx.send('Not in a voice channel')

    # Start the bot
    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged in as')
        print(self.client.user.name)
        print(self.client.user.id)
        print('------')
        # Try start Lavafront server
        subprocess.Popen(["java", "-jar", "Lavalink.jar"])
        # wait for port to open
        while True:
            try:
                r = requests.get('http://localhost:2333')
                break
            except requests.exceptions.ConnectionError:
                print("Waiting for lavalink to go live...")
                time.sleep(1)
                continue

        async def connect_wavefront():
            await self.client.wait_until_ready()
            nodes = [wavelink.Node(uri="http://localhost:2333", password="youshallnotpass")]

            # cache_capacity is EXPERIMENTAL. Turn it off by passing None
            await wavelink.Pool.connect(nodes=nodes, client=self.client, cache_capacity=100)

        self.client.loop.create_task(connect_wavefront())

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.NodeReadyEventPayload):
        print(f'Connected to wavefront! ID: {node.session_id}')

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, _, __):
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)


async def setup(bot):
    await bot.add_cog(MusicBot(bot))


if __name__ == '__main__':
    load_dotenv()
    TOKEN = os.getenv('TOKEN')

    client = commands.Bot(command_prefix='!')
    client.add_cog(MusicBot(client))
    client.run(TOKEN)
