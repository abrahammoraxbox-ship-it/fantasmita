import os, sqlite3, time, discord
SCHEMA=13
SETUP_VERSION=13

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

async def ensure_category(guild,name,overwrites=None,position=None):
    found=discord.utils.get(guild.categories,name=name)
    if not found:
        kwargs={"reason":"Eco estable"}
        if overwrites is not None:kwargs["overwrites"]=overwrites
        found=await guild.create_category(name,**kwargs)
    elif overwrites is not None:
        try:await found.edit(overwrites=overwrites,reason="Eco: sincronizar permisos de categoría")
        except (discord.Forbidden,discord.HTTPException) as e:print("CATEGORY SYNC:",name,repr(e))
    if position is not None:
        try:await found.edit(position=position,reason="Eco: ordenar categorías")
        except (discord.Forbidden,discord.HTTPException):pass
    return found

async def ensure_text(category,name,overwrites=None,position=None,topic=None):
    found=discord.utils.get(category.text_channels,name=name)
    if not found:
        kwargs={"reason":"Eco estable"}
        if overwrites is not None:kwargs["overwrites"]=overwrites
        if topic is not None:kwargs["topic"]=topic
        found=await category.create_text_channel(name,**kwargs)
    else:
        changes={}
        if overwrites is not None:changes["overwrites"]=overwrites
        if topic is not None:changes["topic"]=topic
        if changes:
            try:await found.edit(reason="Eco: sincronizar canal administrado",**changes)
            except (discord.Forbidden,discord.HTTPException) as e:print("CHANNEL SYNC:",name,repr(e))
    if position is not None:
        try:await found.edit(position=position,reason="Eco: ordenar canal administrado")
        except (discord.Forbidden,discord.HTTPException):pass
    return found

async def ensure_voice(category,name,overwrites=None,position=None):
    found=discord.utils.get(category.voice_channels,name=name)
    if not found:
        kwargs={"reason":"Eco estable"}
        if overwrites is not None:kwargs["overwrites"]=overwrites
        found=await category.create_voice_channel(name,**kwargs)
    elif overwrites is not None:
        try:await found.edit(overwrites=overwrites,reason="Eco: sincronizar voz administrada")
        except (discord.Forbidden,discord.HTTPException) as e:print("VOICE SYNC:",name,repr(e))
    if position is not None:
        try:await found.edit(position=position,reason="Eco: ordenar voz administrada")
        except (discord.Forbidden,discord.HTTPException):pass
    return found

async def ensure_panel(bot,channel,key,embed,view=None):
    marker=f"||ECO:{key}||"
    row=bot.db.execute("""SELECT channel_id,message_id FROM panel_messages
                          WHERE guild_id=? AND panel_key=?""",(channel.guild.id,key)).fetchone()
    if row:
        old_channel=channel.guild.get_channel(row[0])
        if old_channel and old_channel.id==channel.id:
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
        async for msg in channel.history(limit=250):
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

async def sync_member_access(bot,guild,pending,gamer):
    approved={r[0] for r in bot.db.execute(
        "SELECT user_id FROM access_requests WHERE guild_id=? AND status='approved'",(guild.id,)
    ).fetchall()}
    for m in guild.members:
        if m.bot or m.id==guild.owner_id or m.guild_permissions.administrator:
            continue
        has_access=(m.id in approved) or (gamer in m.roles)
        try:
            if has_access:
                if gamer not in m.roles:
                    await m.add_roles(gamer,reason="Eco: reparar acceso aprobado")
                if pending in m.roles:
                    await m.remove_roles(pending,reason="Eco: acceso ya aprobado")
            else:
                if pending not in m.roles:
                    await m.add_roles(pending,reason="Eco: acceso pendiente")
        except (discord.Forbidden,discord.HTTPException) as e:
            print("MEMBER ACCESS SYNC:",m.id,repr(e))

async def cleanup_managed_duplicates(bot,guild):
    """Elimina solo duplicados claros de canales administrados por Fantasmita.
    Nunca borra canales personalizados que no coincidan con la estructura propia."""
    cfg=bot.db.execute(
        """SELECT access_ch,suggest_ch,ticket_ch,voice_panel_ch,requests_ch,
                  logs_ch,owner_ch FROM guild_config WHERE guild_id=?""",
        (guild.id,)
    ).fetchone()
    if not cfg:
        return 0

    canonical=dict(zip(
        ["access_ch","suggest_ch","ticket_ch","voice_panel_ch",
         "requests_ch","logs_ch","owner_ch"],cfg
    ))
    managed={
        "bienvenida-y-acceso":"access_ch",
        "sugerencias":"suggest_ch",
        "abrir-ticket":"ticket_ch",
        "control-de-voz":"voice_panel_ch",
        "solicitudes-acceso":"requests_ch",
        "logs":"logs_ch",
        "panel-fundador":"owner_ch",
    }
    deleted=0
    for ch in list(guild.text_channels):
        col=managed.get(ch.name)
        if not col:
            continue
        keep_id=canonical.get(col) or 0
        if keep_id and ch.id!=keep_id and guild.get_channel(keep_id):
            try:
                await ch.delete(reason="Eco: limpieza automática de duplicado administrado")
                deleted+=1
            except (discord.Forbidden,discord.HTTPException) as e:
                print("AUTO CLEANUP:",ch.id,repr(e))
    return deleted

async def ensure_structure(bot,g):
    founder=await ensure_role(g,"👑 Fundador",0xFFD166,discord.Permissions.none(),hoist=True)
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
        everyone:discord.PermissionOverwrite(view_channel=True,send_messages=False,read_message_history=True),
        pending:discord.PermissionOverwrite(view_channel=True,send_messages=False,read_message_history=True),
        gamer:discord.PermissionOverwrite(view_channel=True,send_messages=False,read_message_history=True),
        founder:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),
        admin:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),
        guard:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)
    }
    public={
        everyone:discord.PermissionOverwrite(view_channel=False),
        pending:discord.PermissionOverwrite(view_channel=False),
        gamer:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)
    }
    staff={
        everyone:discord.PermissionOverwrite(view_channel=False),
        founder:discord.PermissionOverwrite(view_channel=True,send_messages=True),
        admin:discord.PermissionOverwrite(view_channel=True,send_messages=True),
        guard:discord.PermissionOverwrite(view_channel=True,send_messages=True)
    }
    owner_only={
        everyone:discord.PermissionOverwrite(view_channel=False)
    }
    if g.owner:
        owner_only[g.owner]=discord.PermissionOverwrite(
            view_channel=True,send_messages=True,read_message_history=True
        )

    access_category_overwrites={
        everyone:discord.PermissionOverwrite(view_channel=True,read_message_history=True),
        pending:discord.PermissionOverwrite(view_channel=True,read_message_history=True),
        gamer:discord.PermissionOverwrite(view_channel=True,read_message_history=True),
        founder:discord.PermissionOverwrite(view_channel=True,read_message_history=True),
        admin:discord.PermissionOverwrite(view_channel=True,read_message_history=True),
        guard:discord.PermissionOverwrite(view_channel=True,read_message_history=True)
    }
    access_cat=await ensure_category(g,"🚪 ACCESO",access_category_overwrites,position=0)
    access=await ensure_text(access_cat,"bienvenida-y-acceso",gate,position=0,topic="Lee los términos, acéptalos y solicita acceso.")

    community=await ensure_category(g,"🌌 COMUNIDAD",position=1)
    await ensure_text(community,"general",public,position=0)
    await ensure_text(community,"gaming",public,position=1)
    suggest=await ensure_text(community,"sugerencias",public,position=2)
    await ensure_text(community,"eventos",public,position=3)
    music_ch=await ensure_text(community,"musica",public,position=4)

    voice_cat=await ensure_category(g,"🎧 VOZ",position=2)
    await ensure_voice(voice_cat,"🔊 General",public,position=0)
    await ensure_voice(voice_cat,"🎮 Gaming",public,position=1)
    lobby=await ensure_voice(voice_cat,"➕ Crear sala privada",public,position=2)
    voice_panel=await ensure_text(voice_cat,"control-de-voz",public,position=3)

    support=await ensure_category(g,"🆘 SOPORTE",position=3)
    ticket=await ensure_text(support,"abrir-ticket",public,position=0)
    help_ch=await ensure_text(support,"ayuda",public,position=1)

    staff_cat=await ensure_category(g,"🔒 STAFF",staff)
    requests=await ensure_text(staff_cat,"solicitudes-acceso",staff,position=0)
    logs=await ensure_text(staff_cat,"logs",staff,position=1)

    founder_cat=await ensure_category(g,"👑 FUNDADOR",owner_only)
    owner_ch=await ensure_text(founder_cat,"panel-fundador",owner_only,position=0)
    audit=await ensure_text(founder_cat,"auditoria-fundador",owner_only,position=1)

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
        description=rules+"\n\nPulsa **Aceptar términos y continuar**. Después solicita acceso.",
        colour=0x8B5CF6),TermsView(bot))
    await ensure_panel(bot,access,"ACCESS",discord.Embed(
        title="👻 SOLICITAR ACCESO",
        description="Acepta los términos y después pulsa el botón para solicitar acceso al servidor.",
        colour=0x7C3AED),AccessRequestView(bot))

    await ensure_panel(bot,music_ch,"MUSIC",discord.Embed(
        title="🎵 FANTASMITA • CENTRO MUSICAL",
        description=(
            "Entra a un canal de voz y usa **`/play`** en este canal.\n"
            "Puedes pegar un enlace de YouTube o escribir el nombre de una canción.\n\n"
            "⏯️ Pausa/Reanuda • ⏭️ Salta • 🔉/🔊 Volumen • ⏹️ Detiene"
        ),colour=0xA855F7),view=MusicControlView(bot))

    await ensure_panel(bot,help_ch,"ROLES",discord.Embed(
        title="🎭 ROLES • GUÍA RÁPIDA",
        description=(
            "👑 **Fundador** — propietario del servidor.\n"
            "🛡️ **Administrador** — administración.\n"
            "⚔️ **Guardián** — moderación/seguridad.\n"
            "🎮 **Gamer** — miembro con acceso aprobado.\n"
            "⏳ **Pendiente** — aún no tiene acceso.\n\n"
            "Fantasmita no modifica tus roles personalizados."
        ),colour=0x8B5CF6))
    await ensure_panel(bot,help_ch,"HELP",discord.Embed(
        title="🧠 CENTRO DE COMANDOS",
        description=(
            "**Perfil:** `/perfil` `/top` `/reputacion` `/logros` `/temporada`\n"
            "**Economía:** `/daily` `/saldo` `/coinflip` `/tienda` `/comprar` `/inventario`\n"
            "**Música:** `/play` `/pause` `/resume` `/skip` `/queue` `/volume` `/nowplaying` `/stop`\n"
            "🎫 `#abrir-ticket` • 🎧 `➕ Crear sala privada`\n"
            "**Fundador:** `!panel` `!reglas` `!seguridad` `!backup` `!panico` `!repararservidor`"
        ),colour=0x22D3EE))
    await ensure_panel(bot,ticket,"TICKET",discord.Embed(
        title="🎫 SOPORTE",description="Un ticket activo por persona.",colour=0x22D3EE),TicketView(bot))
    await ensure_panel(bot,voice_panel,"VOICE",discord.Embed(
        title="🎧 TU SALA",
        description="Entra a ➕ Crear sala privada. Fantasmita creará tu sala y podrás controlarla desde aquí.",
        colour=0x8B5CF6),VoiceControlView(bot))
    await ensure_panel(bot,owner_ch,"OWNER",discord.Embed(
        title="👑 CENTRO DE CONTROL",
        description="Este espacio solo es visible para el propietario.\n\n`!panel` • `!reglas` • `!seguridad` • `!backup` • `!panico` • `!repararservidor`",
        colour=0xFFD166))

    # Orden determinista: aplica las posiciones finales en una sola pasada.
    category_order=[access_cat,community,voice_cat,support,staff_cat,founder_cat]
    try:
        await g.edit_channel_positions(
            positions={cat:i for i,cat in enumerate(category_order)},
            reason="Eco: orden final de categorías"
        )
    except Exception as e:
        print("CATEGORY ORDER FINAL:",repr(e))

    channel_groups=[
        (access_cat,["bienvenida-y-acceso"]),
        (community,["general","gaming","sugerencias","eventos","musica"]),
        (voice_cat,["🔊 General","🎮 Gaming","➕ Crear sala privada","control-de-voz"]),
        (support,["abrir-ticket","ayuda"]),
        (staff_cat,["solicitudes-acceso","logs"]),
        (founder_cat,["panel-fundador","auditoria-fundador"]),
    ]
    for cat,names in channel_groups:
        pos=0
        for name in names:
            ch=discord.utils.get(cat.channels,name=name)
            if not ch:continue
            try:
                await ch.edit(position=pos,reason="Eco: orden final de canales")
            except (discord.Forbidden,discord.HTTPException) as e:
                print("CHANNEL ORDER FINAL:",name,repr(e))
            pos+=1

    await sync_member_access(bot,g,pending,gamer)
    removed=await cleanup_managed_duplicates(bot,g)
    everyone_access=access.permissions_for(g.default_role).view_channel
    print(
        f"✅ AUTOSETUP V{SETUP_VERSION}: {g.name} organizado | "
        f"duplicados eliminados={removed} | permisos sincronizados | "
        f"ACCESO @everyone={everyone_access}"
    )

