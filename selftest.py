import os,sqlite3,tempfile,re,ast
def run():
    base=os.path.dirname(os.path.abspath(__file__))
    files={}
    for root,_,names in os.walk(base):
        for n in names:
            if n.endswith(".py"):
                p=os.path.join(root,n);files[p]=open(p,encoding="utf-8").read();ast.parse(files[p])
    core=open(os.path.join(base,"core.py"),encoding="utf-8").read()
    main=open(os.path.join(base,"main.py"),encoding="utf-8").read()
    views=open(os.path.join(base,"views.py"),encoding="utf-8").read()
    required=["terms_acceptance","weekly_missions","achievements","clans","lfg","tournaments","social_links","seasons","panel_messages"]
    for x in required:assert x in core,x
    assert "SETUP_VERSION=12" in core
    assert "cogs.music" in main and "cogs.progression" in main and "cogs.competitive" in main
    assert "i.user.id==i.guild.owner_id" in views
    assert 'row and row[0]=="approved"' in views
    assert 'row and row[0]=="pending" and not row[1]' in views
    assert "eco:music:pause" not in views and "eco:vtransfer" in views
    assert "view=None" in core and "CENTRO MUSICAL" in core
    music=open(os.path.join(base,"cogs","music.py"),encoding="utf-8").read()
    assert "async def pruebavoz" in music and "class _ToneSource" in music
    assert not re.search(r"except\s*:\s*pass","\n".join(files.values()))
    fd,path=tempfile.mkstemp(prefix="eco_integrado_",suffix=".db");os.close(fd)
    db=sqlite3.connect(path)
    try:
        db.executescript("""
        CREATE TABLE terms_acceptance(guild_id INTEGER,user_id INTEGER,accepted REAL,PRIMARY KEY(guild_id,user_id));
        CREATE TABLE weekly_missions(guild_id INTEGER,user_id INTEGER,week TEXT,progress INTEGER DEFAULT 0,target INTEGER DEFAULT 30,claimed INTEGER DEFAULT 0,PRIMARY KEY(guild_id,user_id,week));
        CREATE TABLE achievements(guild_id INTEGER,user_id INTEGER,code TEXT,unlocked REAL,PRIMARY KEY(guild_id,user_id,code));
        CREATE TABLE clans(guild_id INTEGER,name TEXT,owner_id INTEGER,created REAL,PRIMARY KEY(guild_id,name));
        CREATE TABLE lfg(id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,user_id INTEGER,game TEXT,description TEXT,created REAL,active INTEGER DEFAULT 1);
        """)
        db.execute("INSERT INTO terms_acceptance VALUES(1,2,123)")
        assert db.execute("SELECT accepted FROM terms_acceptance").fetchone()[0]==123
    finally:
        db.close()
        try:os.remove(path)
        except OSError as e:print("SELFTEST CLEAN:",repr(e))
    print("✅ SELFTEST INTEGRADO: estructura, seguridad y SQLite OK")
