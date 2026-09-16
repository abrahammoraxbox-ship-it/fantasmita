import os, sqlite3, time, discord
SCHEMA=10
SETUP_VERSION=10

class Database:
    def __init__(self,path):
        self.path=path
        os.makedirs(os.path.dirname(path),exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._schema()
        self._migrate()

    def _schema(self):
        q=self.db.execute
        q("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)")
        q("""CREATE TABLE IF NOT EXISTS users(
            guild_id INTEGER,user_id INTEGER,xp INTEGER DEFAULT 0,coins INTEGER DEFAULT 300,
            messages INTEGER DEFAULT 0,last_xp REAL DEFAULT 0,last_daily REAL DEFAULT 0,
            streak INTEGER DEFAULT 0,reputation INTEGER DEFAULT 0,last_rep REAL DEFAULT 0,
            PRIMARY KEY(guild_id,user_id))""")
        q("""CREATE TABLE IF NOT EXISTS guild_config(
            guild_id INTEGER PRIMARY KEY,setup_version INTEGER DEFAULT 0,rules TEXT DEFAULT '',
            security_level INTEGER DEFAULT 2,access_ch INTEGER DEFAULT 0,requests_ch INTEGER DEFAULT 0,
            ticket_ch INTEGER DEFAULT 0,voice_panel_ch INTEGER DEFAULT 0,voice_lobby INTEGER DEFAULT 0,
            logs_ch INTEGER DEFAULT 0,audit_ch INTEGER DEFAULT 0,owner_ch INTEGER DEFAULT 0,
            suggest_ch INTEGER DEFAULT 0)""")
        q("""CREATE TABLE IF NOT EXISTS access_requests(
            guild_id INTEGER,user_id INTEGER,status TEXT DEFAULT 'pending',message_id INTEGER DEFAULT 0,
            created REAL DEFAULT 0,decided_by INTEGER DEFAULT 0,decided REAL DEFAULT 0,
            PRIMARY KEY(guild_id,user_id))""")
        q("CREATE TABLE IF NOT EXISTS temp_voice(guild_id INTEGER,channel_id INTEGER PRIMARY KEY,owner_id INTEGER,created REAL)")
        q("CREATE TABLE IF NOT EXISTS warnings(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,user_id INTEGER,moderator_id INTEGER,reason TEXT,created REAL)")
        q("CREATE TABLE IF NOT EXISTS inventory(guild_id INTEGER,user_id INTEGER,item TEXT,qty INTEGER DEFAULT 1,PRIMARY KEY(guild_id,user_id,item))")
        q("CREATE TABLE IF NOT EXISTS suggestions(message_id INTEGER PRIMARY KEY,guild_id INTEGER,user_id INTEGER,status TEXT DEFAULT 'pending',text TEXT)")
        q("CREATE TABLE IF NOT EXISTS shop(item TEXT PRIMARY KEY,price INTEGER NOT NULL,description TEXT DEFAULT '')")
        q("CREATE TABLE IF NOT EXISTS missions(guild_id INTEGER,user_id INTEGER,day TEXT,progress INTEGER DEFAULT 0,target INTEGER DEFAULT 5,claimed INTEGER DEFAULT 0,PRIMARY KEY(guild_id,user_id,day))")
        q("CREATE TABLE IF NOT EXISTS tickets(guild_id INTEGER,user_id INTEGER,channel_id INTEGER PRIMARY KEY,created REAL,closed REAL DEFAULT 0,closed_by INTEGER DEFAULT 0,reason TEXT DEFAULT '')")
        q("CREATE TABLE IF NOT EXISTS panel_messages(guild_id INTEGER,panel_key TEXT,channel_id INTEGER,message_id INTEGER,PRIMARY KEY(guild_id,panel_key))")
        q("CREATE TABLE IF NOT EXISTS terms_acceptance(guild_id INTEGER,user_id INTEGER,accepted REAL NOT NULL,PRIMARY KEY(guild_id,user_id))")
        q("CREATE TABLE IF NOT EXISTS weekly_missions(guild_id INTEGER,user_id INTEGER,week TEXT,progress INTEGER DEFAULT 0,target INTEGER DEFAULT 30,claimed INTEGER DEFAULT 0,PRIMARY KEY(guild_id,user_id,week))")
        q("CREATE TABLE IF NOT EXISTS achievements(guild_id INTEGER,user_id INTEGER,code TEXT,unlocked REAL,PRIMARY KEY(guild_id,user_id,code))")
        q("CREATE TABLE IF NOT EXISTS clans(guild_id INTEGER,name TEXT,owner_id INTEGER,created REAL,PRIMARY KEY(guild_id,name))")
        q("CREATE TABLE IF NOT EXISTS clan_members(guild_id INTEGER,clan TEXT,user_id INTEGER,joined REAL,PRIMARY KEY(guild_id,user_id))")
        q("CREATE TABLE IF NOT EXISTS lfg(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,user_id INTEGER,game TEXT,description TEXT,created REAL,active INTEGER DEFAULT 1)")
        q("CREATE TABLE IF NOT EXISTS tournaments(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,name TEXT,event_at TEXT,status TEXT DEFAULT 'open',created_by INTEGER,created REAL)")
        q("CREATE TABLE IF NOT EXISTS community_events(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,name TEXT,event_at TEXT,description TEXT,created_by INTEGER,created REAL)")
        q("CREATE TABLE IF NOT EXISTS social_links(guild_id INTEGER,user_id INTEGER,platform TEXT,handle TEXT,PRIMARY KEY(guild_id,user_id,platform))")
        q("CREATE TABLE IF NOT EXISTS seasons(guild_id INTEGER PRIMARY KEY,name TEXT,start REAL,end REAL)")

        q("INSERT OR IGNORE INTO shop VALUES('💜 Insignia Violeta',500,'Objeto cosmético de perfil')")
        q("INSERT OR IGNORE INTO shop VALUES('🎟️ Ticket de Suerte',300,'Coleccionable del Vacío')")
        self.db.commit()

    def _cols(self,t):
        return {r[1] for r in self.db.execute(f"PRAGMA table_info({t})")}

    def _migrate(self):
        needed={
            "users":{"last_rep":"REAL DEFAULT 0"},
            "guild_config":{
                "access_ch":"INTEGER DEFAULT 0","requests_ch":"INTEGER DEFAULT 0",
                "ticket_ch":"INTEGER DEFAULT 0","voice_panel_ch":"INTEGER DEFAULT 0",
                "voice_lobby":"INTEGER DEFAULT 0","logs_ch":"INTEGER DEFAULT 0",
                "audit_ch":"INTEGER DEFAULT 0","owner_ch":"INTEGER DEFAULT 0",
                "suggest_ch":"INTEGER DEFAULT 0"
            },
            "tickets":{"type":"TEXT DEFAULT 'support'"}
        }
        for table,cols in needed.items():
            have=self._cols(table)
            for col,typ in cols.items():
                if col not in have:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema',?)",(str(SCHEMA),))
        self.db.commit()

    def execute(self,sql,args=()):
        cur=self.db.execute(sql,args)
        self.db.commit()
        return cur

    def ensure_user(self,g,u):
        self.execute("INSERT OR IGNORE INTO users(guild_id,user_id) VALUES(?,?)",(g,u))

    def stats(self,g,u):
        self.ensure_user(g,u)
        return self.execute("""SELECT xp,coins,messages,last_daily,streak,reputation,last_xp,last_rep
                             FROM users WHERE guild_id=? AND user_id=?""",(g,u)).fetchone()

    def backup(self,folder):
        os.makedirs(folder,exist_ok=True)
        dest=os.path.join(folder,f"eco_{int(time.time())}.db")
        out=sqlite3.connect(dest)
        try:self.db.backup(out)
        finally:out.close()
        old=sorted((os.path.join(folder,x) for x in os.listdir(folder) if x.endswith(".db")),
                   key=os.path.getmtime,reverse=True)
        for file in old[10:]:
            try:os.remove(file)
            except OSError as e:print("BACKUP CLEANUP:",repr(e))
        return dest

async def ensure_role(guild,name,color,permissions=None,hoist=False,mentionable=False):
    """Actualiza el mismo rol: nunca lo borra/recrea, por lo que conserva miembros."""
    role=discord.utils.get(guild.roles,name=name)
    wanted=permissions or discord.Permissions.none();wanted_colour=discord.Colour(color)
    if role:
        changes={}
        if role.permissions!=wanted:changes["permissions"]=wanted
        if role.colour!=wanted_colour:changes["colour"]=wanted_colour
        if role.hoist!=hoist:changes["hoist"]=hoist
        if role.mentionable!=mentionable:changes["mentionable"]=mentionable
        if changes:
            try:await role.edit(**changes,reason="Sincronización visual/segura Eco")
            except discord.Forbidden as e:print("ROLE SYNC:",name,repr(e))
        return role
    return await guild.create_role(name=name,colour=wanted_colour,permissions=wanted,
                                   hoist=hoist,mentionable=mentionable,reason="Eco estable")

async def sync_role_order(guild,roles):
    bot_member=guild.me
    if not bot_member:return
    ordered=[r for r in roles if r and r<bot_member.top_role]
    if not ordered:return
    top=max(1,bot_member.top_role.position-1)
    positions={role:max(1,top-i) for i,role in enumerate(ordered)}
    try:await guild.edit_role_positions(positions=positions,reason="Jerarquía visual Eco")
    except (discord.Forbidden,discord.HTTPException) as e:print("ROLE ORDER:",repr(e))

async def ensure_category(guild,name,overwrites=None):
    found=discord.utils.get(guild.categories,name=name)
    if found:return found
    kwargs={"reason":"Eco estable"}
    if overwrites is not None:kwargs["overwrites"]=overwrites
    return await guild.create_category(name,**kwargs)

async def ensure_text(category,name,overwrites=None):
    found=discord.utils.get(category.text_channels,name=name)
    if found:return found
    found=discord.utils.get(category.guild.text_channels,name=name)
    if found:
        try:
            if found.category_id!=category.id: await found.edit(category=category,reason="Eco: consolidar canal administrado")
        except (discord.Forbidden,discord.HTTPException) as e: print("CHANNEL MOVE:",name,repr(e))
        return found
    kwargs={"reason":"Eco estable"}
    if overwrites is not None:kwargs["overwrites"]=overwrites
    return await category.create_text_channel(name,**kwargs)

async def ensure_voice(category,name,overwrites=None):
    found=discord.utils.get(category.voice_channels,name=name)
    if found:return found
    found=discord.utils.get(category.guild.voice_channels,name=name)
    if found:
        try:
            if found.category_id!=category.id: await found.edit(category=category,reason="Eco: consolidar canal administrado")
        except (discord.Forbidden,discord.HTTPException) as e: print("VOICE MOVE:",name,repr(e))
        return found
    kwargs={"reason":"Eco estable"}
    if overwrites is not None:kwargs["overwrites"]=overwrites
    return await category.create_voice_channel(name,**kwargs)

async def ensure_panel(bot,channel,key,embed,view=None):
    marker=f"||ECO:{key}||"
    row=bot.db.execute("""SELECT channel_id,message_id FROM panel_messages
                          WHERE guild_id=? AND panel_key=?""",(channel.guild.id,key)).fetchone()
    if row:
        old_channel=channel.guild.get_channel(row[0])
        if old_channel:
            try:
                msg=await old_channel.fetch_message(row[1])
                await msg.edit(content=marker,embed=embed,view=view)
                return msg
            except discord.NotFound:
                # El mensaje guardado ya no existe: elimina la referencia obsoleta antes de reconstruir.
                bot.db.execute("DELETE FROM panel_messages WHERE guild_id=? AND panel_key=?",
                               (channel.guild.id,key))
            except (discord.Forbidden,discord.HTTPException) as e:
                print("PANEL STORED:",key,repr(e))

    # Migration fallback for panels created by older bot versions.
    try:
        async for msg in channel.history(limit=100):
            if msg.author==bot.user and marker in (msg.content or ""):
                await msg.edit(content=marker,embed=embed,view=view)
                bot.db.execute("INSERT OR REPLACE INTO panel_messages VALUES(?,?,?,?)",
                               (channel.guild.id,key,channel.id,msg.id))
                return msg
    except (discord.Forbidden,discord.HTTPException) as e:
        print("PANEL MIGRATION:",key,repr(e))

    msg=await channel.send(marker,embed=embed,view=view)
    bot.db.execute("INSERT OR REPLACE INTO panel_messages VALUES(?,?,?,?)",
                   (channel.guild.id,key,channel.id,msg.id))
    return msg

# Compatibility for owner.py.
panel=ensure_panel

async def repair_onboarding(bot,guild):
    """Revalida los paneles críticos; ensure_panel repara faltantes y evita duplicados."""
    row=bot.db.execute("SELECT access_ch FROM guild_config WHERE guild_id=?",(guild.id,)).fetchone()
    access=guild.get_channel(row[0]) if row and row[0] else discord.utils.get(guild.text_channels,name="bienvenida-y-acceso")
    if not access:return
    from views import TermsView,AccessRequestView
    await ensure_panel(bot,access,"TERMS",discord.Embed(
        title="📜 TÉRMINOS Y CONDICIONES",
        description="Lee las reglas y pulsa **Aceptar términos y continuar**. Después podrás solicitar acceso.",
        colour=0x8B5CF6),TermsView(bot))
    await ensure_panel(bot,access,"ACCESS",discord.Embed(
        title="👻 SOLICITAR ACCESO",
        description="Después de aceptar los términos, pulsa el botón para enviar tu solicitud al fundador.",
        colour=0x7C3AED),AccessRequestView(bot))

async def ensure_structure(bot,g):
    founder=await ensure_role(g,"👑 Fundador",0xFFD166,discord.Permissions(administrator=True),hoist=True)
    admin_perms=discord.Permissions(
        manage_guild=True,manage_roles=True,manage_channels=True,manage_messages=True,
        kick_members=True,ban_members=True,moderate_members=True,move_members=True,
        view_audit_log=True
    )
    admin=await ensure_role(g,"🛡️ Administrador",0xA855F7,admin_perms,hoist=True)
    guard=await ensure_role(g,"⚔️ Guardián",0x6366F1,discord.Permissions(
        manage_messages=True,kick_members=True,ban_members=True,moderate_members=True,move_members=True
    ),hoist=True)
    pending=await ensure_role(g,"⏳ Pendiente",0x64748B)
    gamer=await ensure_role(g,"🎮 Gamer",0x5865F2,hoist=True)
    decorative=[]
    # Orden de identidad: el rol más alto define el color visible del nombre en Discord.
    for name,color in [
        ("📺 Creador",0xEC4899),("💎 VIP",0x22D3EE),("🏆 Élite",0xF59E0B),
        ("🏅 Campeón",0xFBBF24),("🌙 Veterano",0x4F46E5)
    ]:
        decorative.append(await ensure_role(g,name,color,hoist=True))
    await sync_role_order(g,[founder,admin,guard,*decorative,gamer,pending])

    if g.owner and founder not in g.owner.roles:
        try:await g.owner.add_roles(founder,reason="Propietario del servidor")
        except discord.Forbidden as e:print("FOUNDER ROLE:",repr(e))

    everyone=g.default_role
    gate={
        everyone:discord.PermissionOverwrite(view_channel=True,send_messages=False),
        pending:discord.PermissionOverwrite(view_channel=True,send_messages=False),
        gamer:discord.PermissionOverwrite(view_channel=False),
        founder:discord.PermissionOverwrite(view_channel=True,send_messages=True),
        admin:discord.PermissionOverwrite(view_channel=True,send_messages=True),
        guard:discord.PermissionOverwrite(view_channel=True,send_messages=True)
    }
    public={
        everyone:discord.PermissionOverwrite(view_channel=False),
        pending:discord.PermissionOverwrite(view_channel=False),
        gamer:discord.PermissionOverwrite(view_channel=True)
    }
    staff={
        everyone:discord.PermissionOverwrite(view_channel=False),
        founder:discord.PermissionOverwrite(view_channel=True),
        admin:discord.PermissionOverwrite(view_channel=True),
        guard:discord.PermissionOverwrite(view_channel=True)
    }
    owner_only={
        everyone:discord.PermissionOverwrite(view_channel=False),
        founder:discord.PermissionOverwrite(view_channel=True)
    }

    access_cat=await ensure_category(g,"🚪 ACCESO")
    access=await ensure_text(access_cat,"bienvenida-y-acceso",gate)

    community=await ensure_category(g,"🌌 COMUNIDAD")
    await ensure_text(community,"general",public)
    await ensure_text(community,"gaming",public)
    suggest=await ensure_text(community,"sugerencias",public)
    await ensure_text(community,"eventos",public)
    music_ch=await ensure_text(community,"musica",public)

    voice_cat=await ensure_category(g,"🎧 VOZ")
    await ensure_voice(voice_cat,"🔊 General",public)
    await ensure_voice(voice_cat,"🎮 Gaming",public)
    lobby=await ensure_voice(voice_cat,"➕ Crear sala privada",public)
    voice_panel=await ensure_text(voice_cat,"control-de-voz",public)

    support=await ensure_category(g,"🆘 SOPORTE")
    ticket=await ensure_text(support,"abrir-ticket",public)
    help_ch=await ensure_text(support,"ayuda",public)

    staff_cat=await ensure_category(g,"🔒 STAFF",staff)
    requests=await ensure_text(staff_cat,"solicitudes-acceso",staff)
    logs=await ensure_text(staff_cat,"logs",staff)

    founder_cat=await ensure_category(g,"👑 FUNDADOR",owner_only)
    owner_ch=await ensure_text(founder_cat,"panel-fundador",owner_only)
    audit=await ensure_text(founder_cat,"auditoria-fundador",owner_only)

    bot.db.execute("INSERT OR IGNORE INTO guild_config(guild_id) VALUES(?)",(g.id,))
    bot.db.execute("""UPDATE guild_config SET setup_version=?,access_ch=?,requests_ch=?,ticket_ch=?,
                      voice_panel_ch=?,voice_lobby=?,logs_ch=?,audit_ch=?,owner_ch=?,suggest_ch=?
                      WHERE guild_id=?""",
                   (SETUP_VERSION,access.id,requests.id,ticket.id,voice_panel.id,lobby.id,
                    logs.id,audit.id,owner_ch.id,suggest.id,g.id))

    row=bot.db.execute("SELECT rules FROM guild_config WHERE guild_id=?",(g.id,)).fetchone()
    rules=(row[0] if row else "").strip()
    if not rules:
        rules=("1. Respeta a los demás.\n2. Sin spam, estafas, malware ni cheats.\n"
               "3. Protege la privacidad.\n4. Usa cada espacio correctamente.\n"
               "5. Juego limpio.\n6. Respeta las decisiones del staff.")
        bot.db.execute("UPDATE guild_config SET rules=? WHERE guild_id=?",(rules,g.id))

    from views import TermsView,AccessRequestView,TicketView,VoiceControlView,MusicControlView
    await ensure_panel(bot,access,"TERMS",discord.Embed(
        title="📜 TÉRMINOS Y CONDICIONES",
        description=rules+"\n\nAl pulsar **Aceptar términos y continuar**, confirmas que aceptas estas reglas. Después podrás solicitar acceso.",
        colour=0x8B5CF6),TermsView(bot))
    await ensure_panel(bot,access,"ACCESS",discord.Embed(
        title="👻 SOLICITAR ACCESO",
        description="Después de aceptar los términos, pulsa el botón para enviar tu solicitud al fundador.",
        colour=0x7C3AED),AccessRequestView(bot))
    # Panel musical fijo en #musica. ensure_panel evita duplicados y lo reconstruye si falta.
    await ensure_panel(bot,music_ch,"MUSIC",discord.Embed(
        title="🎵 FANTASMITA • CENTRO MUSICAL",
        description=(
            "Entra a un canal de voz y usa **`/play`** en este canal.\n"
            "Puedes pegar un enlace de YouTube o escribir el nombre de una canción.\n\n"
            "**Controles:** ⏸️ Pausa • ▶️ Continuar • ⏭️ Saltar • ⏹️ Detener\n"
            "La tarjeta de la canción actual aparecerá debajo de este panel."
        ),colour=0xA855F7),MusicControlView(bot))

    await ensure_panel(bot,help_ch,"ROLES",discord.Embed(
        title="🎭 ROLES • GUÍA RÁPIDA",
        description=(
            "👑 **Fundador** — propietario.\n🛡️ **Administrador** — administración.\n"
            "⚔️ **Guardián** — moderación/seguridad.\n📺 **Creador** — reconocimiento manual para creadores.\n"
            "💎 **VIP** — reconocimiento manual del fundador.\n🏆 **Élite** — automático al alcanzar 100 mensajes válidos.\n"
            "🏅 **Campeón** — reconocimiento competitivo/manual.\n🌙 **Veterano** — automático al alcanzar 500 mensajes válidos.\n"
            "🎮 **Gamer** — miembro con acceso aprobado.\n⏳ **Pendiente** — acceso aún no aprobado.\n\n"
            "Los roles decorativos no reciben permisos administrativos.\n\n"
            "🎭 Los roles personalizados creados por el fundador también pueden gestionarse desde `!panel` si están debajo de Fantasmita.\n\n"
            "🎨 Discord muestra el **color del rol más alto** en el nombre del miembro. "            "El emoji del rol identifica su insignia dentro del perfil/lista de roles."
        ),colour=0x8B5CF6))
    await ensure_panel(bot,help_ch,"HELP",discord.Embed(
        title="🧠 CENTRO DE COMANDOS",
        description=(
            "**Perfil:** `/perfil` `/top` `/reputacion` `/logros` `/temporada`\n"
            "**Economía:** `/daily` `/saldo` `/coinflip` `/tienda` `/comprar` `/inventario`\n"
            "**Misiones:** `/mision` `/semanal`\n"
            "**Comunidad:** `/dado` `/8ball` `/sugerir` `/lfg` `/lfg_lista`\n"
            "**Clanes:** `/clan_crear` `/clan_unir` `/clan_salir` `/clan_info`\n"
            "**Eventos/Torneos:** `/evento_crear` `/eventos_lista` `/torneo_crear` `/torneos` `/torneo_resultado`\n"
            "**Música:** usa `#musica` → `/play` `/pause` `/resume` `/skip` `/queue` `/volume` `/nowplaying` `/stop`\n"
            "**Perfiles sociales:** `/vincular` `/vinculos` (enlaces públicos; no OAuth)\n"
            "🎫 `#abrir-ticket` • 🎧 `➕ Crear sala privada`\n"
            "**Fundador:** `!panel` `!reglas` `!seguridad` `!backup` `!panico` `!instalarbranding` `!recortarcanales`"
        ),colour=0x22D3EE))
    await ensure_panel(bot,ticket,"TICKET",discord.Embed(
        title="🎫 SOPORTE",description="Un ticket activo por persona.",colour=0x22D3EE),TicketView(bot))
    await ensure_panel(bot,voice_panel,"VOICE",discord.Embed(
        title="🎧 TU SALA",
        description="Entra a ➕ Crear sala privada. Tu sala se crea automáticamente. **Los controles están aquí**, en #control-de-voz: bloquear, desbloquear, renombrar, permitir/expulsar usuarios, transferir propiedad y límite 1–10.",
        colour=0x8B5CF6),VoiceControlView(bot))
    await ensure_panel(bot,owner_ch,"OWNER",discord.Embed(
        title="👑 CENTRO DE CONTROL",
        description="`!panel` `!reglas` `!seguridad` `!backup`\nLas acciones sensibles quedan reservadas al propietario.",
        colour=0xFFD166))
