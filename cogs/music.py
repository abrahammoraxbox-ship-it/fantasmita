import asyncio, collections, re, sys, time, discord
from urllib.parse import urlparse, parse_qs
from discord.ext import commands
import yt_dlp, imageio_ffmpeg

YDL_OPTS={"format":"bestaudio/best","quiet":True,"no_warnings":True,"noplaylist":True,
          "extract_flat":False,"skip_download":True}
FFMPEG_OPTS={"before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5","options":"-vn"}
URL_RE=re.compile(r"^https?://",re.I)

# PlayerView dinámico desactivado para evitar un segundo sistema de controles.
# Se conserva únicamente MusicControlView persistente de views.py.

class Music(commands.Cog):
    def __init__(self,b):
        self.b=b;self.queues=collections.defaultdict(collections.deque);self.current={}
        self.volumes=collections.defaultdict(lambda:0.5);self.player_messages={};self.music_channels={}

    def in_music(self,ctx):return bool(ctx.guild and getattr(ctx.channel,"name",None)=="musica")
    async def require_music(self,ctx):
        if self.in_music(ctx):return True
        await ctx.send("🎵 Los comandos de música funcionan **solo en #musica**.",delete_after=8);return False

    @staticmethod
    def _pick_audio_url(info):
        if not isinstance(info,dict):return None
        if info.get("url"):return info["url"]
        fs=[f for f in (info.get("formats") or []) if isinstance(f,dict) and f.get("url") and f.get("acodec") not in (None,"none")]
        fs.sort(key=lambda f:(f.get("abr") or 0,f.get("tbr") or 0),reverse=True)
        return fs[0]["url"] if fs else None

    @staticmethod
    def normalize_query(q):
        q=q.strip()
        if not URL_RE.match(q):return q
        try:
            u=urlparse(q)
            host=u.netloc.lower().split(":")[0]
            if host in {"youtube.com","www.youtube.com","m.youtube.com","music.youtube.com"} and u.path=="/watch":
                vid=parse_qs(u.query).get("v",[None])[0]
                if vid:return f"https://www.youtube.com/watch?v={vid}"
            if host=="youtu.be":
                vid=u.path.strip("/").split("/")[0]
                if vid:return f"https://youtu.be/{vid}"
        except Exception as e:
            print("MUSIC URL NORMALIZE:",repr(e))
        return q

    async def resolve(self,q):
        q=self.normalize_query(q);target=q if URL_RE.match(q) else f"ytsearch1:{q}";loop=asyncio.get_running_loop()
        def work():
            with yt_dlp.YoutubeDL(YDL_OPTS) as y:
                info=y.extract_info(target,download=False)
                if isinstance(info,dict) and info.get("entries") is not None:info=next((x for x in info["entries"] if x),None)
                if not info:raise RuntimeError("Sin resultados")
                if info.get("_type") in {"url","url_transparent"} and info.get("url"):info=y.extract_info(info["url"],download=False)
                u=self._pick_audio_url(info)
                if not u:raise RuntimeError("Sin formato de audio")
                return {"url":u,"title":info.get("title") or "Audio","webpage":info.get("webpage_url") or info.get("original_url") or q,
                        "duration":info.get("duration"),"query":q,"http_headers":info.get("http_headers") or {},
                        "resolved_at":time.time()}
        return await loop.run_in_executor(None,work)

    async def ensure_voice(self,ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("🎧 Entra primero a un canal de voz.");return None
        target=ctx.author.voice.channel;vc=ctx.guild.voice_client
        try:
            if not vc:vc=await target.connect()
            elif vc.channel!=target:await vc.move_to(target)
            return vc
        except Exception as e:
            print("MUSIC VOICE:",repr(e));await ctx.send("❌ No pude entrar al canal de voz.");return None

    def queue_text(self,gid):
        cur=self.current.get(gid);q=list(self.queues[gid]);lines=[]
        if cur:lines.append(f"▶️ **{cur['title']}**")
        lines += [f"{n}. {x['title']}" for n,x in enumerate(q[:15],1)]
        return "\n".join(lines) if lines else "📭 Cola vacía."

    async def update_player(self,guild):
        # Panel dinámico desactivado: el servidor ya tiene MusicControlView persistente.
        # Mantener este método permite conservar cola, volumen y comandos sin duplicar paneles.
        return

    async def start_next(self,guild):
        vc=guild.voice_client
        if not vc or not vc.is_connected():return
        if not self.queues[guild.id]:
            self.current.pop(guild.id,None);await self.update_player(guild);return
        item=self.queues[guild.id].popleft() # played item disappears from pending queue immediately
        self.current[guild.id]=item;await self.update_player(guild)
        # /play ya resolvió una URL de audio fresca. No volvemos a consultar YouTube
        # inmediatamente: la doble extracción podía fallar/rate-limitar y hacía desaparecer
        # la tarjeta sin llegar a FFmpeg. Solo refrescamos pistas que esperaron en cola.
        age=time.time()-float(item.get("resolved_at") or 0)
        if not item.get("url") or age>300:
            try:
                fresh=await self.resolve(item.get("webpage") or item.get("query") or item.get("url",""))
                item.update(fresh)
                self.current[guild.id]=item
                await self.update_player(guild)
                print(f"MUSIC REFRESH OK: {item.get('title','Audio')} | age={age:.0f}s")
            except Exception as e:
                print("MUSIC REFRESH:",repr(e))
                ch=self.music_channels.get(guild.id)
                if ch:
                    try:await ch.send(f"⚠️ No pude preparar **{item.get('title','esa pista')}**. La salto sin detener Fantasmita.",delete_after=12)
                    except discord.HTTPException:pass
                self.current.pop(guild.id,None)
                return await self.start_next(guild)
        try:
            # yt-dlp entrega cabeceras que algunos CDN (incluido YouTube) exigen también a FFmpeg.
            headers=item.get("http_headers") or {}
            header_blob="".join(f"{k}: {v}\r\n" for k,v in headers.items() if v)
            before="-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            if header_blob:
                safe_headers=header_blob.replace('"','\\"')
                before += f' -headers "{safe_headers}"'
            ffmpeg_path=imageio_ffmpeg.get_ffmpeg_exe()
            print(f"MUSIC FFMPEG: {ffmpeg_path}")
            ffmpeg=discord.FFmpegPCMAudio(
                item["url"],executable=ffmpeg_path,
                before_options=before,options="-vn -loglevel warning",stderr=sys.stderr)
            src=discord.PCMVolumeTransformer(ffmpeg,volume=self.volumes[guild.id])
        except Exception as e:
            print("MUSIC SOURCE:",repr(e))
            ch=self.music_channels.get(guild.id)
            if ch:
                try:await ch.send("⚠️ FFmpeg no pudo preparar esa pista. La salto sin detener Fantasmita.",delete_after=12)
                except discord.HTTPException:pass
            self.current.pop(guild.id,None);return await self.start_next(guild)
        loop=asyncio.get_running_loop()
        def after(err):
            if err:print("MUSIC PLAYER:",repr(err))
            fut=asyncio.run_coroutine_threadsafe(self.start_next(guild),loop)
            fut.add_done_callback(lambda f: print("MUSIC NEXT:",repr(f.exception())) if f.exception() else None)
        try:
            vc.play(src,after=after)
            print(f"MUSIC PLAYING: {item.get('title','Audio')} | voice={vc.channel}")
        except Exception as e:
            print("MUSIC PLAY START:",repr(e))
            try:src.cleanup()
            except Exception:pass
            ch=self.music_channels.get(guild.id)
            if ch:
                try:await ch.send("⚠️ No pude iniciar el audio en Discord. Revisa la consola: MUSIC PLAY START.",delete_after=12)
                except discord.HTTPException:pass
            self.current.pop(guild.id,None)
            return await self.start_next(guild)

    async def change_volume(self,guild,delta):
        v=max(0.1,min(1.0,self.volumes[guild.id]+delta/100));self.volumes[guild.id]=v
        vc=guild.voice_client
        if vc and isinstance(vc.source,discord.PCMVolumeTransformer):vc.source.volume=v
        await self.update_player(guild)

    async def stop_guild(self,guild,delete_player=True):
        self.queues[guild.id].clear();self.current.pop(guild.id,None)
        vc=guild.voice_client
        if vc:await vc.disconnect(force=True)
        if delete_player:
            old=self.player_messages.pop(guild.id,None)
            if old:
                try:await old.delete()
                except discord.HTTPException:pass

    @commands.hybrid_command(description="Reproduce audio o añade a la cola")
    async def play(self,ctx,*,busqueda:str):
        if not await self.require_music(ctx):return
        vc=await self.ensure_voice(ctx)
        if not vc:return
        if ctx.interaction and not ctx.interaction.response.is_done():await ctx.defer()
        try:item=await self.resolve(busqueda)
        except Exception as e:
            print("MUSIC RESOLVE:",repr(e));return await ctx.send("❌ No pude obtener audio de esa fuente.")
        self.music_channels[ctx.guild.id]=ctx.channel
        self.queues[ctx.guild.id].append(item)
        # /play no crea mensajes ni tarjetas adicionales: el único panel visual es el panel MUSIC fijo.
        if not vc.is_playing() and not vc.is_paused():await self.start_next(ctx.guild)
        else:await self.update_player(ctx.guild)

    @commands.hybrid_command(description="Pausa la música")
    async def pause(self,ctx):
        if not await self.require_music(ctx):return
        vc=ctx.guild.voice_client
        if vc and vc.is_playing():vc.pause();return await ctx.send("⏸️ Pausado.",delete_after=4)
        await ctx.send("No hay música reproduciéndose.",delete_after=4)

    @commands.hybrid_command(description="Continúa la música")
    async def resume(self,ctx):
        if not await self.require_music(ctx):return
        vc=ctx.guild.voice_client
        if vc and vc.is_paused():vc.resume();return await ctx.send("▶️ Continuando.",delete_after=4)
        await ctx.send("No hay música pausada.",delete_after=4)

    @commands.hybrid_command(description="Salta la pista")
    async def skip(self,ctx):
        if not await self.require_music(ctx):return
        vc=ctx.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):vc.stop();return await ctx.send("⏭️ Siguiente.",delete_after=4)
        await ctx.send("No hay pista activa.",delete_after=4)

    @commands.hybrid_command(description="Muestra la cola")
    async def queue(self,ctx):
        if not await self.require_music(ctx):return
        await ctx.send(self.queue_text(ctx.guild.id),delete_after=12)

    @commands.hybrid_command(description="Cambia volumen 1-100")
    async def volume(self,ctx,nivel:int):
        if not await self.require_music(ctx):return
        nivel=max(1,min(100,nivel));self.volumes[ctx.guild.id]=nivel/100
        vc=ctx.guild.voice_client
        if vc and isinstance(vc.source,discord.PCMVolumeTransformer):vc.source.volume=nivel/100
        await self.update_player(ctx.guild);await ctx.send(f"🔊 {nivel}%",delete_after=4)

    @commands.hybrid_command(description="Muestra la pista actual")
    async def nowplaying(self,ctx):
        if not await self.require_music(ctx):return
        await self.update_player(ctx.guild)
        if not self.current.get(ctx.guild.id):await ctx.send("Nada sonando.",delete_after=4)

    @commands.hybrid_command(description="Detiene música y limpia la cola")
    async def stop(self,ctx):
        if not await self.require_music(ctx):return
        await self.stop_guild(ctx.guild,True);await ctx.send("⏹️ Música detenida.",delete_after=4)

    def cog_unload(self):
        self.queues.clear();self.current.clear();self.player_messages.clear();self.music_channels.clear()

async def setup(b):await b.add_cog(Music(b))
