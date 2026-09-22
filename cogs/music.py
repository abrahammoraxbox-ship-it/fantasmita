import asyncio, collections, re, sys, time, math, struct, discord, shutil, subprocess, importlib.metadata, os
from urllib.parse import urlparse, parse_qs
from discord.ext import commands
import yt_dlp, imageio_ffmpeg

# Wispbyte usa `pip --prefix .local`, por lo que los ejecutables Python quedan
# normalmente en /home/container/.local/bin, ruta que no viene en PATH.
_LOCAL_BIN = os.path.join(os.path.expanduser("~"), ".local", "bin")
if os.path.isdir(_LOCAL_BIN) and _LOCAL_BIN not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = _LOCAL_BIN + os.pathsep + os.environ.get("PATH", "")

def _find_deno():
    candidates = [
        shutil.which("deno"),
        os.path.join(_LOCAL_BIN, "deno"),
        "/home/container/.local/bin/deno",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return os.path.realpath(candidate)
    return None

DENO_PATH = _find_deno()

YDL_OPTS={"format":"bestaudio/best","quiet":True,"no_warnings":True,"noplaylist":True,
          "extract_flat":False,"skip_download":True}
# yt-dlp acepta una ruta explícita al runtime desde su API Python. Esto evita
# depender del PATH del contenedor de Wispbyte.
if DENO_PATH:
    YDL_OPTS["js_runtimes"] = {"deno": {"path": DENO_PATH}}
FFMPEG_OPTS={"before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5","options":"-vn"}
URL_RE=re.compile(r"^https?://",re.I)

# PlayerView dinámico desactivado para evitar un segundo sistema de controles.
# Se conserva únicamente MusicControlView persistente de views.py.

class _ToneSource(discord.AudioSource):
    """PCM estéreo 48 kHz para diagnosticar Discord Voice sin YouTube/FFmpeg."""
    def __init__(self,seconds=3.0,freq=440.0,volume=0.18):
        self.frames_left=int(seconds*50);self.phase=0;self.freq=freq;self.volume=volume
    def read(self):
        if self.frames_left<=0:return b""
        out=bytearray()
        for _ in range(960):
            sample=int(32767*self.volume*math.sin(2*math.pi*self.freq*self.phase/48000))
            self.phase+=1;out.extend(struct.pack("<hh",sample,sample))
        self.frames_left-=1
        return bytes(out)
    def is_opus(self):return False

class Music(commands.Cog):
    def __init__(self,b):
        self.b=b;self.queues=collections.defaultdict(collections.deque);self.current={}
        self.volumes=collections.defaultdict(lambda:0.5);self.music_channels={}
        self._print_music_diagnostic()

    @staticmethod
    def _runtime_version(executable):
        path=shutil.which(executable)
        if not path:
            return "NO"
        try:
            r=subprocess.run([path,"--version"],capture_output=True,text=True,timeout=4)
            first=(r.stdout or r.stderr or "").strip().splitlines()
            return first[0] if first else f"OK ({path})"
        except Exception as e:
            return f"ERROR {type(e).__name__}"

    def _print_music_diagnostic(self):
        try:
            ytdlp_ver=getattr(yt_dlp.version,"__version__","desconocida")
        except Exception:
            ytdlp_ver="desconocida"
        try:
            ejs_ver=importlib.metadata.version("yt-dlp-ejs")
        except importlib.metadata.PackageNotFoundError:
            ejs_ver="NO"
        try:
            ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg_state=f"OK ({ffmpeg})"
        except Exception as e:
            ffmpeg_state=f"ERROR {e!r}"
        print("="*78)
        print("🎵 MUSIC DIAGNOSTIC")
        print(f"FFmpeg: {ffmpeg_state}")
        print(f"yt-dlp: {ytdlp_ver}")
        print(f"yt-dlp-ejs: {ejs_ver}")
        if DENO_PATH:
            print(f"Deno: {self._runtime_version(DENO_PATH)}")
            print(f"Deno path: {DENO_PATH}")
            print("yt-dlp JS runtime: deno (ruta explícita) OK")
        else:
            print("Deno: NO")
            print("yt-dlp JS runtime: deno NO")
        print(f"Node: {self._runtime_version('node')}")
        print(f"Discord Voice/PyNaCl: {'OK' if discord.opus.is_loaded() or shutil.which('ffmpeg') or True else 'REVISAR'}")
        print("="*78)

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
        # Actualiza ÚNICAMENTE el panel MUSIC fijo creado por core.ensure_structure.
        # No crea mensajes nuevos, no añade una segunda View y no toca otros sistemas.
        cur=self.current.get(guild.id)
        q=list(self.queues[guild.id])
        volume=round(self.volumes[guild.id]*100)

        if cur:
            duration=cur.get("duration")
            if isinstance(duration,(int,float)) and duration>0:
                total=int(duration);mins,secs=divmod(total,60)
                duration_text=f"{mins}:{secs:02d}"
            else:
                duration_text="Desconocida"
            description=(
                f"▶️ **Reproduciendo ahora**\n[{cur.get('title','Audio')}]({cur.get('webpage') or cur.get('query') or ''})\n"
                f"⏱️ Duración: **{duration_text}** • 🔊 Volumen: **{volume}%**\n\n"
            )
        else:
            description=(
                "⏹️ **Nada reproduciéndose ahora.**\n"
                f"🔊 Volumen: **{volume}%**\n\n"
            )

        if q:
            upcoming="\n".join(f"`{n}.` {x.get('title','Audio')}" for n,x in enumerate(q[:5],1))
            description+=f"📜 **Siguiente en la cola**\n{upcoming}\n\n"
        else:
            description+="📭 **Cola vacía.**\n\n"

        description+=(
            "Entra a un canal de voz y usa **`/play`** en este canal.\n"
            "Puedes pegar un enlace de YouTube o escribir el nombre de una canción."
        )
        embed=discord.Embed(title="🎵 FANTASMITA • CENTRO MUSICAL",description=description,colour=0xA855F7)

        # El ID del panel fijo ya está guardado por core.ensure_panel. Solo lo editamos.
        try:
            row=self.b.db.execute(
                "SELECT channel_id,message_id FROM panel_messages WHERE guild_id=? AND panel_key=?",
                (guild.id,"MUSIC")
            ).fetchone()
            if not row:return
            ch=guild.get_channel(row[0])
            if not ch:return
            msg=await ch.fetch_message(row[1])
            await msg.edit(embed=embed)
        except discord.NotFound:
            # Si alguien borró manualmente el panel, no creamos duplicados aquí.
            # core.ensure_structure será quien lo reconstruya de forma segura.
            return
        except (discord.Forbidden,discord.HTTPException) as e:
            print("MUSIC PANEL:",repr(e))

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
        # Detener audio nunca toca el panel fijo de #musica.
        self.queues[guild.id].clear();self.current.pop(guild.id,None)
        vc=guild.voice_client
        if vc:await vc.disconnect(force=True)

    @commands.hybrid_command(description="Reproduce audio o añade a la cola")
    async def play(self,ctx,*,busqueda:str):
        if not await self.require_music(ctx):return

        # Discord exige confirmar un slash command en pocos segundos. Lo hacemos de forma
        # efímera y eliminamos esa respuesta al terminar, para que /play no deje texto,
        # tarjeta ni un segundo panel visible en #musica.
        interaction=ctx.interaction
        if interaction and not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        vc=await self.ensure_voice(ctx)
        if not vc:
            if interaction:
                try:await interaction.delete_original_response()
                except (discord.NotFound,discord.HTTPException):pass
            return

        try:
            item=await self.resolve(busqueda)
        except Exception as e:
            print("MUSIC RESOLVE:",repr(e))
            print("MUSIC HINT: si ves avisos de JS challenge, revisa MUSIC DIAGNOSTIC (Deno/Node + yt-dlp-ejs).")
            if interaction:
                try:await interaction.delete_original_response()
                except (discord.NotFound,discord.HTTPException):pass
            return await ctx.send("❌ No pude obtener audio de esa fuente.",delete_after=8)

        self.music_channels[ctx.guild.id]=ctx.channel
        self.queues[ctx.guild.id].append(item)
        if not vc.is_playing() and not vc.is_paused():await self.start_next(ctx.guild)
        else:await self.update_player(ctx.guild)

        # Borra el acuse temporal del slash command. El panel MUSIC fijo es el único
        # elemento musical que debe permanecer en el canal.
        if interaction:
            try:await interaction.delete_original_response()
            except (discord.NotFound,discord.HTTPException):pass

    @commands.hybrid_command(description="Prueba Discord Voice sin YouTube ni FFmpeg")
    async def pruebavoz(self,ctx):
        if not await self.require_music(ctx):return
        interaction=ctx.interaction
        if interaction and not interaction.response.is_done():await interaction.response.defer(ephemeral=True)
        vc=await self.ensure_voice(ctx)
        if not vc:return
        if vc.is_playing() or vc.is_paused():vc.stop()
        try:
            vc.play(_ToneSource(),after=lambda e: print("VOICE TEST END:",repr(e)) if e else print("VOICE TEST END: OK"))
            print(f"VOICE TEST START: PCM 440Hz | voice={vc.channel}")
        except Exception as e:
            print("VOICE TEST START ERROR:",repr(e))
        if interaction:
            try:await interaction.delete_original_response()
            except (discord.NotFound,discord.HTTPException):pass

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
        self.queues.clear();self.current.clear();self.music_channels.clear()

async def setup(b):await b.add_cog(Music(b))
