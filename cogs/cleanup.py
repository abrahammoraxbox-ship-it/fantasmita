import discord
from discord.ext import commands

# IMPORTANT:
# La limpieza automática ahora vive en core.py y solo elimina duplicados claros del bot.
# This cleanup NEVER deletes channels based only on their name.
# It only removes duplicate channels that the current compact bot itself manages.
# A channel is considered removable only when:
#   1) its name is one of the current managed channel names,
#   2) another channel with that same managed name exists,
#   3) the bot keeps the canonical channel ID saved in guild_config.
# All old/custom channels (roles, memes, music, games, scrims, etc.) are untouched.

MANAGED_ID_COLUMNS = {
    "bienvenida-y-acceso": "access_ch",
    "sugerencias": "suggest_ch",
    "abrir-ticket": "ticket_ch",
    "control-de-voz": "voice_panel_ch",
    "solicitudes-acceso": "requests_ch",
    "logs": "logs_ch",
    "panel-fundador": "owner_ch",
}

class Cleanup(commands.Cog):
    def __init__(self,b):self.b=b

    def _duplicate_candidates(self,guild):
        cfg=self.b.db.execute(
            """SELECT access_ch,suggest_ch,ticket_ch,voice_panel_ch,requests_ch,
                      logs_ch,owner_ch FROM guild_config WHERE guild_id=?""",
            (guild.id,)
        ).fetchone()
        if not cfg:return []
        canonical=dict(zip(
            ["access_ch","suggest_ch","ticket_ch","voice_panel_ch",
             "requests_ch","logs_ch","owner_ch"], cfg
        ))
        candidates=[]
        for ch in guild.text_channels:
            col=MANAGED_ID_COLUMNS.get(ch.name)
            if not col:continue
            keep_id=canonical.get(col) or 0
            # Never delete the configured canonical channel.
            if keep_id and ch.id!=keep_id and guild.get_channel(keep_id):
                candidates.append(ch)
        return candidates

    @commands.command()
    @commands.guild_only()
    async def recortarcanales(self,ctx,confirmar:str=""):
        # Owner only: cleanup is destructive.
        if ctx.author.id!=ctx.guild.owner_id:
            return await ctx.send("🔒 Solo el propietario del servidor puede usar este comando.")

        candidates=self._duplicate_candidates(ctx.guild)
        if not candidates:
            return await ctx.send(
                "✅ No hay duplicados administrados por el bot para eliminar.\n"
                "**No se tocaron canales antiguos o personalizados.**"
            )

        preview="\n".join(f"• {c.mention} (`{c.id}`)" for c in candidates[:30])
        extra=len(candidates)-30
        if confirmar.lower()!="confirmar":
            text=(
                f"🛡️ **MODO SEGURO — Vista previa: {len(candidates)} duplicados del bot.**\n"
                f"{preview}"
            )
            if extra>0:text+=f"\n• … y {extra} más."
            text+=(
                "\n\nNo se borrará ningún canal por nombre heredado."
                "\nPara borrar **solo estos duplicados**, usa `!recortarcanales confirmar`."
            )
            return await ctx.send(text)

        deleted=[];failed=[]
        for ch in candidates:
            # Re-check immediately before each destructive action.
            fresh=self._duplicate_candidates(ctx.guild)
            if ch not in fresh:continue
            try:
                name=ch.name
                await ch.delete(reason=f"Duplicado administrado por Eco; confirmado por {ctx.author}")
                deleted.append(name)
            except (discord.Forbidden,discord.HTTPException) as e:
                failed.append(ch.name)
                print("SAFE CLEANUP:",ch.id,repr(e))

        await ctx.send(
            f"🧹 Eliminados: **{len(deleted)}** duplicados administrados por el bot."
            + (f" Fallaron: **{len(failed)}**." if failed else "")
            + "\nLos demás canales quedaron intactos."
        )

async def setup(b):await b.add_cog(Cleanup(b))
