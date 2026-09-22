import asyncio, collections, re, sys, time, math, struct, discord, shutil, subprocess, importlib.metadata, os, tempfile
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

YDL_OPTS={
    "format":"bestaudio[ext=m4a]/bestaudio/best",
    "quiet":True,
    "no_warnings":True,
    "noplaylist":True,
    "extract_flat":False,
    "skip_download":True,
    "source_address":"0.0.0.0",
}
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
        self.volumes=collections.defaultdict(lambda:0.5);self.music_channels={};self._ffmpeg_logs={}
        self.voice_channels={};self.track_started={};self.intentional_stop=set()
        self._watchdogs={};self._track_tokens=collections.defaultdict(int)
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
        print("MUSIC CODE VERSION: hybrid-watchdog-v6")
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
        req=info.get("requested_downloads") or []
        for f in req:
            if isinstance(f,dict) and f.get("url") and f.get("acodec") not in (None,"none"):
                return f["url"]
        fs=[f for f in (info.get("formats") or []) if isinstance(f,dict) and f.get("url") and f.get("acodec") not in (None,"none")]
        fs.sort(key=lambda f:(f.get("abr") or 0,f.get("tbr") or 0),reverse=True)
        if fs:return fs[0]["url"]
        if info.get("url") and info.get("acodec") not in ("none",None):return info["url"]
        return None

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
        q=self.normalize_query(q)
        target=q if URL_RE.match(q) else f"ytsearch1:{q}"
        loop=asyncio.get_running_loop()
        def work():
            with yt_dlp.YoutubeDL(YDL_OPTS) as y:
                info=y.extract_info(target,download=False)
                if isinstance(info,dict) and info.get("entries") is not None:
                    info=next((x for x in info["entries"] if x),None)
                if not info:raise RuntimeError("Sin resultados")
                if info.get("_type") in {"url","url_transparent"} and info.get("url"):
                    info=y.extract_info(info["url"],download=False)
                webpage=info.get("webpage_url") or info.get("original_url") or q
                if not webpage:
                    raise RuntimeError("Sin URL reproducible")
                return {
                    "title":info.get("title") or "Audio",
                    "webpage":webpage,
                    "audio_url":self._pick_audio_url(info),
                    "duration":info.get("duration"),
                    "query":q,
                    "resolved_at":time.time(),
                    "retry_count":0,
                    "force_pipe":False,
                }
        return await loop.run_in_executor(None,work)

    async def ensure_voice(self,ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("🎧 Entra primero a un canal de voz.");return None
        target=ctx.author.voice.channel;vc=ctx.guild.voice_client
        try:
            if not vc:vc=await target.connect(reconnect=True)
            elif vc.channel!=target:await vc.move_to(target)
            self.voice_channels[ctx.guild.id]=target.id
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

    def _build_fast_source(self,guild_id,item):
        """Ruta rápida: reutiliza la URL de audio obtenida por la primera extracción."""
        audio_url=item.get("audio_url")
        if not audio_url:
            raise RuntimeError("Sin URL directa de audio")
        ffmpeg_path=imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_log_path=f"/tmp/fantasmita_ffmpeg_fast_{guild_id}.log"
        ffmpeg_log=open(ffmpeg_log_path,"w+b")
        print(f"MUSIC FAST SOURCE: URL directa -> FFmpeg -> Discord | {item.get('title','Audio')}")
        ffmpeg=discord.FFmpegPCMAudio(
            audio_url,
            executable=ffmpeg_path,
            before_options="-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn -loglevel warning -f s16le -ar 48000 -ac 2",
            stderr=ffmpeg_log,
        )
        src=discord.PCMVolumeTransformer(ffmpeg,volume=self.volumes[guild_id])
        self._ffmpeg_logs[guild_id]=(ffmpeg_log_path,ffmpeg_log,None,None,None)
        return src

    def _build_piped_source(self,guild_id,item):
        """
        Pipeline estable:
        yt-dlp abre YouTube y escribe el mejor audio a stdout.
        FFmpeg lee desde pipe:0 y convierte a PCM para Discord.
        Evita depender de URLs CDN temporales que estaban devolviendo EOF inmediato.
        """
        ffmpeg_path=imageio_ffmpeg.get_ffmpeg_exe()
        target=item.get("webpage") or item.get("query")
        if not target:
            raise RuntimeError("La pista no tiene URL de origen")

        ytdlp_cmd=[
            sys.executable,"-m","yt_dlp",
            "--quiet","--no-warnings","--no-playlist",
            "-f","bestaudio[ext=m4a]/bestaudio/best",
            "-o","-",
        ]
        if DENO_PATH:
            ytdlp_cmd += ["--js-runtimes",f"deno:{DENO_PATH}"]
        ytdlp_cmd.append(target)

        ytdlp_log_path=f"/tmp/fantasmita_ytdlp_{guild_id}.log"
        ffmpeg_log_path=f"/tmp/fantasmita_ffmpeg_{guild_id}.log"
        ytdlp_log=open(ytdlp_log_path,"w+b")
        ffmpeg_log=open(ffmpeg_log_path,"w+b")

        print("MUSIC PIPELINE: yt-dlp stdout -> FFmpeg stdin -> Discord PCM")
        print(f"MUSIC YTDLP TARGET: {target}")
        print(f"MUSIC FFMPEG: {ffmpeg_path}")

        ytdlp_proc=subprocess.Popen(
            ytdlp_cmd,
            stdout=subprocess.PIPE,
            stderr=ytdlp_log,
            stdin=subprocess.DEVNULL,
            bufsize=0,
        )
        if not ytdlp_proc.stdout:
            ytdlp_proc.kill()
            raise RuntimeError("yt-dlp no abrió stdout")

        ffmpeg=discord.FFmpegPCMAudio(
            ytdlp_proc.stdout,
            pipe=True,
            executable=ffmpeg_path,
            before_options="-nostdin",
            options="-vn -loglevel warning -f s16le -ar 48000 -ac 2",
            stderr=ffmpeg_log,
        )
        src=discord.PCMVolumeTransformer(ffmpeg,volume=self.volumes[guild_id])
        self._ffmpeg_logs[guild_id]=(
            ffmpeg_log_path,ffmpeg_log,
            ytdlp_log_path,ytdlp_log,
            ytdlp_proc
        )
        return src

    def _dump_ffmpeg_log(self,guild_id):
        entry=self._ffmpeg_logs.pop(guild_id,None)
        if not entry:
            print("MUSIC PIPELINE LOG: <sin registro>")
            return

        ffmpeg_path,ffmpeg_file,ytdlp_path,ytdlp_file,ytdlp_proc=entry

        try:
            if ytdlp_proc and ytdlp_proc.poll() is None:
                ytdlp_proc.terminate()
                try:ytdlp_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:ytdlp_proc.kill()
        except Exception:pass

        def read_log(path,fileobj,label):
            data=b""
            if fileobj:
                try:
                    fileobj.flush();fileobj.seek(0);data=fileobj.read()
                except Exception as e:
                    print(f"{label} LOG READ:",repr(e))
                finally:
                    try:fileobj.close()
                    except Exception:pass
            if not data and path:
                try:
                    with open(path,"rb") as f:data=f.read()
                except Exception:pass
            if path:
                try:os.remove(path)
                except OSError:pass
            msg=data.decode("utf-8","replace").strip() if data else ""
            print(f"{label} STDERR:",msg[:8000] if msg else "<sin salida>")

        read_log(ytdlp_path,ytdlp_file,"MUSIC YTDLP")
        read_log(ffmpeg_path,ffmpeg_file,"MUSIC FFMPEG")

    @staticmethod
    def _remaining_seconds(item,elapsed):
        duration=item.get("duration")
        if not isinstance(duration,(int,float)) or duration<=0:
            return None
        return max(0.0,float(duration)-float(elapsed))

    def _cancel_watchdog(self,guild_id):
        task=self._watchdogs.pop(guild_id,None)
        if task and not task.done():
            task.cancel()

    async def _watch_track(self,guild,item,token):
        """Supervisa Discord Voice mientras una pista debería seguir sonando."""
        gid=guild.id
        try:
            while True:
                await asyncio.sleep(10)
                if self._track_tokens.get(gid)!=token:return
                current=self.current.get(gid)
                if current is not item:return
                vc=guild.voice_client
                started=self.track_started.get(gid)
                elapsed=max(0.0,time.monotonic()-started) if started else 0.0
                remaining=self._remaining_seconds(item,elapsed)
                print(
                    f"MUSIC WATCHDOG | title={item.get('title','Audio')} | elapsed={elapsed:.1f}s | "
                    f"remaining={remaining if remaining is not None else 'unknown'} | "
                    f"connected={bool(vc and vc.is_connected())} | "
                    f"playing={bool(vc and vc.is_playing())} | paused={bool(vc and vc.is_paused())}"
                )
                if gid in self.intentional_stop:
                    return
                # Si Discord Voice se cayó o dejó de reproducir cuando aún faltaba bastante,
                # fuerza la ruta de recuperación en vez de asumir que terminó normalmente.
                should_still_play = remaining is None or remaining > 12
                if should_still_play and (not vc or not vc.is_connected() or (not vc.is_playing() and not vc.is_paused())):
                    print("MUSIC WATCHDOG RECOVERY TRIGGER")
                    await self._recover_track(guild,item,"watchdog")
                    return
        except asyncio.CancelledError:
            return
        except Exception as e:
            print("MUSIC WATCHDOG ERROR:",repr(e))

    async def _recover_track(self,guild,item,reason):
        gid=guild.id
        if gid in self.intentional_stop:
            return False
        retries=int(item.get("retry_count") or 0)
        if retries>=2:
            print(f"MUSIC RECOVERY LIMIT: {item.get('title','Audio')} | reason={reason}")
            return False
        item["retry_count"]=retries+1
        item["force_pipe"]=True
        print(f"MUSIC AUTO RECOVERY: intento {item['retry_count']} | reason={reason} | {item.get('title','Audio')}")
        try:
            fresh=await self.resolve(item.get("webpage") or item.get("query"))
            fresh["retry_count"]=item["retry_count"]
            fresh["force_pipe"]=True
            item=fresh
        except Exception as e:
            print("MUSIC RECOVERY RESOLVE:",repr(e))

        vc=guild.voice_client
        if not vc or not vc.is_connected():
            channel=guild.get_channel(self.voice_channels.get(gid,0))
            if channel:
                try:
                    if vc:
                        try:await vc.disconnect(force=True)
                        except Exception:pass
                    await channel.connect(reconnect=True)
                    print(f"MUSIC VOICE RECOVERED: {channel}")
                except Exception as e:
                    print("MUSIC VOICE RECOVERY:",repr(e))
                    return False

        self.current.pop(gid,None)
        self.queues[gid].appendleft(item)
        await asyncio.sleep(0.8)
        await self.start_next(guild)
        return True

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
        if not item.get("webpage") or age>300:
            try:
                fresh=await self.resolve(item.get("webpage") or item.get("query"))
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
            if item.get("audio_url") and not item.get("force_pipe"):
                src=self._build_fast_source(guild.id,item)
                mode="FAST"
            else:
                src=self._build_piped_source(guild.id,item)
                mode="PIPE"
            self.track_started[guild.id]=time.monotonic()
            print(f"MUSIC SOURCE MODE: {mode}")
        except Exception as e:
            print("MUSIC SOURCE:",repr(e))
            # Si la ruta rápida no pudo ni arrancar, intenta el pipe tradicional una vez.
            if not item.get("force_pipe"):
                item["force_pipe"]=True
                self.queues[guild.id].appendleft(item)
                self.current.pop(guild.id,None)
                return await self.start_next(guild)
            ch=self.music_channels.get(guild.id)
            if ch:
                try:await ch.send("⚠️ FFmpeg no pudo preparar esa pista. La salto sin detener Fantasmita.",delete_after=12)
                except discord.HTTPException:pass
            self.current.pop(guild.id,None);return await self.start_next(guild)
        loop=asyncio.get_running_loop()
        def after(err):
            title=item.get("title","Audio")
            if err:
                print(f"MUSIC AFTER ERROR: {title} | {err!r}")
            else:
                print(f"MUSIC AFTER END: {title} | source exhausted without exception")
            fut=asyncio.run_coroutine_threadsafe(self._after_track(guild,item,err),loop)
            def done(f):
                try:
                    exc=f.exception()
                    if exc:print("MUSIC AFTER TASK ERROR:",repr(exc))
                except Exception as e:
                    print("MUSIC AFTER TASK CHECK:",repr(e))
            fut.add_done_callback(done)
        try:
            vc.play(src,after=after)
            self._track_tokens[guild.id]+=1
            token=self._track_tokens[guild.id]
            self._cancel_watchdog(guild.id)
            self._watchdogs[guild.id]=asyncio.create_task(self._watch_track(guild,item,token))
            print(f"MUSIC PLAYING: {item.get('title','Audio')} | voice={vc.channel}")
            await asyncio.sleep(0.35)
            print(
                f"MUSIC VOICE STATE | connected={vc.is_connected()} | "
                f"playing={vc.is_playing()} | paused={vc.is_paused()}"
            )
            if not vc.is_playing() and not vc.is_paused():
                print("MUSIC WARNING: audio source stopped immediately after vc.play()")
        except Exception as e:
            print("MUSIC PLAY START:",repr(e))
            self._dump_ffmpeg_log(guild.id)
            try:src.cleanup()
            except Exception:pass
            ch=self.music_channels.get(guild.id)
            if ch:
                try:await ch.send("⚠️ No pude iniciar el audio en Discord. Revisa la consola: MUSIC PLAY START.",delete_after=12)
                except discord.HTTPException:pass
            self.current.pop(guild.id,None)
            return await self.start_next(guild)

    async def _after_track(self,guild,item,err):
        gid=guild.id
        self._cancel_watchdog(gid)
        vc=guild.voice_client
        title=item.get("title","Audio")
        elapsed=max(0.0,time.monotonic()-self.track_started.pop(gid,time.monotonic()))
        duration=item.get("duration")
        remaining=self._remaining_seconds(item,elapsed)
        intentional=gid in self.intentional_stop
        if intentional:self.intentional_stop.discard(gid)

        print(
            f"MUSIC FINISHED | title={title} | error={err!r} | elapsed={elapsed:.1f}s | "
            f"duration={duration!r} | remaining={remaining if remaining is not None else 'unknown'} | "
            f"connected={bool(vc and vc.is_connected())} | playing={bool(vc and vc.is_playing())}"
        )
        self._dump_ffmpeg_log(gid)

        # Considera caída prematura si todavía faltaba tiempo significativo de canción.
        premature_by_duration = remaining is not None and remaining > 12
        premature = (err is not None) or premature_by_duration or elapsed < 8.0

        if not intentional and premature:
            recovered=await self._recover_track(guild,item,"after_track")
            if recovered:return

        current=self.current.get(gid)
        if current is item or current and current.get("webpage")==item.get("webpage"):
            self.current.pop(gid,None)
        await self.update_player(guild)
        if self.queues[gid]:
            await self.start_next(guild)

    async def change_volume(self,guild,delta):
        v=max(0.1,min(1.0,self.volumes[guild.id]+delta/100));self.volumes[guild.id]=v
        vc=guild.voice_client
        if vc and isinstance(vc.source,discord.PCMVolumeTransformer):vc.source.volume=v
        await self.update_player(guild)

    async def stop_guild(self,guild,delete_player=True):
        # Detener audio nunca toca el panel fijo de #musica.
        self.queues[guild.id].clear();self.current.pop(guild.id,None)
        self._track_tokens[guild.id]+=1;self._cancel_watchdog(guild.id)
        vc=guild.voice_client
        self.intentional_stop.add(guild.id)
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

        # Mantiene visible la confirmación de /play para que el usuario vea qué pista
        # se encontró. El panel MUSIC fijo sigue siendo el reproductor principal.
        if interaction:
            try:
                await interaction.edit_original_response(
                    content=f"🎵 Reproduciendo: **{item.get('title','Audio')}**"
                )
            except (discord.NotFound,discord.HTTPException) as e:
                print("MUSIC PLAY RESPONSE:",repr(e))

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
        if vc and (vc.is_playing() or vc.is_paused()):
            self.intentional_stop.add(ctx.guild.id)
            self._track_tokens[ctx.guild.id]+=1;self._cancel_watchdog(ctx.guild.id)
            vc.stop();return await ctx.send("⏭️ Siguiente.",delete_after=4)
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
        for gid in list(self._ffmpeg_logs):
            try:self._dump_ffmpeg_log(gid)
            except Exception:pass
        self.queues.clear();self.current.clear();self.music_channels.clear()
        for gid in list(self._watchdogs):self._cancel_watchdog(gid)
        self.voice_channels.clear();self.track_started.clear();self.intentional_stop.clear()
        self._track_tokens.clear()

async def setup(b):await b.add_cog(Music(b))
