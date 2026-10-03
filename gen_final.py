import json, os, base64, re, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else 'bf6-armory.html'
TEMPLATE = 'template.html'

sym = json.load(open('bf6.json')); sym_info = sym.pop('info')
rws = {r['id']: r for r in json.load(open('rd_weapons.json'))}
att = json.load(open('rd_attachments.json'))
tips = json.load(open('rd_attachment-tooltips.json'))
amd = json.load(open('rd_ammo.json'))

CLASS_LABEL = {'assaultrifle':'Assault Rifle','carbine':'Carbine','smg':'SMG','mg':'LMG',
               'dmr':'DMR','boltaction':'Sniper Rifle','shotgun':'Shotgun','secondary':'Sidearm'}
CLASS_ORDER = list(CLASS_LABEL)

def norm(s): return re.sub(r'[^a-z0-9]','', s.lower())
by_name = {norm(r['name']): rid for rid, r in rws.items()}

AMMO_PRETTY = {
  '.300blk':'7.62×35mm .300 BLK', '.300winmag':'.300 Win Mag',
  '.338lapuamagnum':'.338 Lapua Mag', '.338lapuamagnum2':'.338 Lapua Mag',
  '.338normamagnum':'.338 Norma Mag', '.357magnum':'.357 Magnum',
  '.40sw':'.40 S&W', '.416barrett':'.416 Barrett', '.44magnum':'.44 Magnum',
  '.45acp':'.45 ACP', '10x25mm':'10×25mm', '12gano01buck275':'12ga #1 Buck',
  '12gano01buck300':'12ga #1 Buck (3")', '32acp':'.32 ACP', '46x30':'4.6×30mm',
  '545x39mm':'5.45×39mm', '556x45mm NATO':'5.56×45mm NATO', '57x28mm':'5.7×28mm',
  '58x42mm':'5.8×42mm', '68x51mm':'6.8×51mm', '762x39mm':'7.62×39mm',
  '762x51mm NATO':'7.62×51mm NATO', '762x54mmr':'7.62×54mmR',
  '9x19mm':'9×19mm', '9x39mm':'9×39mm',
}

def num(v): return round(v,2) if isinstance(v,(int,float)) else None

def points(dmg):
    p=[]
    for d,v in zip(dmg['dists'], dmg['dmgs']):
        if p and p[-1][0]==round(d,1): p[-1][1]=round(v,1)
        else: p.append([round(d,1), round(v,1)])
    m=[]
    for x,y in p:
        if m and m[-1][1]==y: continue
        m.append([x,y])
    return m

# ---- attachment name/cost catalogues ----
CAT = {'muzzle':'MUZZLES','barrel':'BARRELS','grip':'GRIPS','laser':'LASERS',
       'light':'LIGHTS','ergo':'ERGOS','sight':'SIGHTS','accessory':'ACCESSORIES'}
aname = {}; apts = {}
for slot,key in CAT.items():
    for x in att[key]:
        aname[(slot,x['id'])]=x['name']; apts[(slot,x['id'])]=x.get('pts',0)
ammo_name = {x['id']: x['name'] for x in amd['AMMO']}
SLOTS = [('sight','Optic'),('muzzle','Muzzle'),('barrel','Barrel'),('mag','Magazine'),
         ('ammo','Ammo'),('grip','Underbarrel'),('laser','Laser'),('light','Light'),
         ('ergo','Ergonomics'),('accessory','Accessory')]

# ---- playground: catalogue records keyed by (slot,id) are the numeric effect source ----
ACAT = {}
for _slot,_key in CAT.items():
    for _x in att[_key]: ACAT[(_slot,_x['id'])] = _x
AMMO_CAT = {x['id']: x for x in amd['AMMO']}

# The data speaks two units. Multipliers are absolute (velocity ×1.25, spot range ×0.14);
# tier fields are the in-game UI ladder and their sign convention comes from each
# attachment's own panel text — recoil / ADS-time / moving-spread tiers are higher-is-better,
# hip-spread and the *TierShift family (deploy, sprint recovery, ADS move speed) are lower-is-better.
P_MULT = ('velMult','adsSpreadIncMult','hipSpreadIncMult','adsRecoilDecayMult','hipRecoilDecayMult',
          'reloadSpeedMult','weaponSwayMult','worldSpotMult','minimapSpotMult')
P_TIER = ('velTierMod','adsRecoilTierMod','hipRecoilTierMod','adsRecoilVariationTierMod',
          'hipRecoilVariationTierMod','hipSpreadTierMod','movingAdsSpreadTierMod','adsTimeTierMod',
          'adsTimeTierShift','adsMoveSpeedTierShift','sprintRecoveryTierShift','deployTimeTierShift',
          'reloadSpeedTier')

def p_resolve(rec, rid):
    """Attachment record with this weapon's own overrides folded in."""
    src = dict(rec)
    wo = rec.get('weaponOverrides') or {}
    if rid in wo: src.update(wo[rid])
    fm = (rec.get('frostyModifiers') or {}).get(rid) or {}
    if fm: src.update(fm)
    atm = rec.get('adsTimeTierModByWeapon') or {}
    if rid in atm: src['adsTimeTierMod'] = atm[rid]
    wsm = rec.get('weaponSwayMultByWeapon') or {}
    if rid in wsm: src['weaponSwayMult'] = wsm[rid]
    return src

def p_fx(src):
    fx = {}
    for k in P_MULT:
        v = src.get(k)
        if isinstance(v,(int,float)) and abs(float(v)-1) > 1e-9: fx[k] = round(float(v),4)
    for k in P_TIER:
        v = src.get(k)
        if isinstance(v,(int,float)) and v:
            fx[k] = int(v) if float(v).is_integer() else round(float(v),2)
    for k,dk in (('adsSpreadDynOverride','adsInc'),('hipSpreadDynOverride','hipInc')):
        v = src.get(k)
        if isinstance(v,dict) and isinstance(v.get('inc'),(int,float)): fx[dk] = round(float(v['inc']),4)
    v = src.get('mag')
    if isinstance(v,(int,float)) and v: fx['mag'] = int(v)
    if src.get('suppressor'): fx['supp'] = 1
    if 'laserVisible' in src: fx['vis'] = 1 if src.get('laserVisible') else 0
    v = src.get('recoilDurationOverride')
    if isinstance(v,(int,float)): fx['dur'] = round(float(v),4)
    v = src.get('healthRegenDelayAddS')
    if isinstance(v,(int,float)) and v: fx['regen'] = v
    return fx

def p_pts(dmg):
    p = []
    for d in dmg:
        if p and p[-1][0]==round(d['r'],1): p[-1][1]=round(d['d'],1)
        else: p.append([round(d['r'],1), round(d['d'],1)])
    m = []
    for x,y in p:
        if m and m[-1][1]==y: continue
        m.append([x,y])
    return m

PLAY_SLOTS = [('sight','Optic'),('muzzle','Muzzle'),('barrel','Barrel'),('grip','Underbarrel'),
              ('laser','Laser'),('light','Light'),('ergo','Ergonomics'),('mag','Magazine'),
              ('ammo','Ammo'),('accessory','Accessory')]
OPTIONAL = ('muzzle','grip','laser','light','ergo','accessory')
COLL_BASE = next((x.get('collateralMult') for x in amd['AMMO'] if x['id']=='standard' and isinstance(x.get('collateralMult'),dict)), {})

TIPS=[]; tip_idx={}
def tip(h):
    if not h: return -1
    if h in tip_idx: return tip_idx[h]
    txt = tips['descriptions'].get(h,'')
    if not txt: return -1
    tip_idx[h]=len(TIPS); TIPS.append(txt); return tip_idx[h]

# ---- real attachment icons: {"slot|id": "path.webp"} or {"slot|*": "path.webp"} ----
ICONS=[]; icon_idx={}
ICONMAP = json.load(open('att_icons.json')) if os.path.exists('att_icons.json') else {}
def icon_for(slot, aid):
    p = ICONMAP.get(f'{slot}|{aid}') or ICONMAP.get(f'{slot}|*')
    if not p or not os.path.exists(p): return -1
    b = open(p,'rb').read()
    if b in icon_idx: return icon_idx[b]
    icon_idx[b]=len(ICONS)
    ICONS.append('data:image/webp;base64,'+base64.b64encode(b).decode())
    return icon_idx[b]

weapons=[]
for slug,w in sym.items():
    rof=w['rof']; sp=w['spread']
    rid = by_name.get(norm(w['displayname']))
    rw = rws.get(rid, {}) if rid else {}
    e=dict(slug=slug,name=w['displayname'],cls=w['class'],clsLabel=CLASS_LABEL[w['class']],
      ammo=AMMO_PRETTY.get(w['ammo'], w['ammo']), mag=w['mags']['MagSize'], mags=w['mags']['NumMags'],
      rof=round(rof['RoF'],1),burst=round(rof['BurstRoF'],1),single=round(rof['SingleRoF'],1),
      velocity=round(w['velocity']),drag=w['drag'],pellets=w['pellets'],pts=points(w['damage']),
      reloadLeft=num(w['reload']['ReloadLeft']),reloadEmpty=num(w['reload']['ReloadEmpty']),
      deploy=round(w['deploy']['DeployTime'],2),undeploy=round(w['deploy']['UnDeployTime'],2),
      adsStand=round(sp['ADSStandBaseMin'],2),adsMove=round(sp['ADSStandMoveMin'],2),
      hipStand=round(sp['HIPStandBaseMin'],2),hipMove=round(sp['HIPStandMoveMin'],2))
    for cand in (f'webp/{slug}.webp',):
        if os.path.exists(cand):
            e['img']='data:image/webp;base64,'+base64.b64encode(open(cand,'rb').read()).decode()
            break
    else:
        e['img']=''
    if rw:
        e['desc']=rw.get('description','')
        e['modes']=rw.get('availableFireModes') or []
        e['modeData']={m: round(fm.get('rpm',0)) for m,fm in (rw.get('fireModes') or {}).items()}
        e['recoil']=dict(v=num(rw.get('recoilV')),dir=num(rw.get('recoilDir')),var=num(rw.get('recoilVar')),incAds=num(rw.get('recoilIncAds')))
        e['mech']=((rw.get('fireModes') or {}).get('single') or {}).get('mechanism') or ''
    # ---- cadence: reload breakdown, box magazine vs shell-by-shell tube ----
    rl = w.get('reload') or {}
    def sec(v):
        if isinstance(v,(int,float)): return float(v)
        if isinstance(v,str) and v.endswith('s'):
            try: return float(v[:-1])
            except ValueError: return None
        return None
    tac_rl  = sec(rl.get('ReloadLeft'))
    empt_rl = sec(rl.get('ReloadEmpty'))
    cr = rl.get('CustomReload') or []
    per_shell = bool(cr)                 # tube mags feed one shell at a time
    est = False
    if empt_rl is None and cr:
        vals = {k:sec(v) for k,v in (cr[-1].get('values') or [])}   # 0-0 profile = from empty
        pre, first, per, post = vals.get('Pre-delay'), vals.get('1st-bullet reload'), vals.get('Bullet reload'), vals.get('Post-delay')
        if pre is not None and per is not None:
            n = w['mags']['MagSize']
            empt_rl = round(pre + (first if first is not None else per) + per*max(0, n-1) + (post or 0), 2)
            est = True
    if empt_rl is None and tac_rl is not None:
        empt_rl = tac_rl                 # no separate empty animation (revolvers, single shots)
    e['rl'] = dict(tac=num(tac_rl), empty=num(empt_rl), perShell=per_shell, est=est)
    slots={}
    tw = tips['byWeapon'].get(rid,{}) if rid else {}
    for slot,label in SLOTS:
        items=[]
        if slot in ('sight','muzzle','barrel','grip','laser','light','ergo'):
            for aid in tw.get(slot,{}):
                nm = aname.get((slot,aid))
                if nm is None: continue
                items.append([nm, apts.get((slot,aid),0), tip(tw[slot][aid]), icon_for(slot,aid)])
        elif slot=='mag':
            for mid,mm in (att['WEAPON_MAG'].get(rid,{}).get('mags') or {}).items():
                if mid in tw.get('mag',{}):
                    items.append([mm.get('name',mid), mm.get('pts',0), tip(tw['mag'][mid]), icon_for('mag',mid)])
        elif slot=='ammo':
            for aid in tw.get('ammo',{}):
                items.append([ammo_name.get(aid,aid), 0, tip(tw['ammo'][aid]), icon_for('ammo',aid)])
        elif slot=='accessory':
            for aid in (att['WEAPON_ACCESSORY'].get(rid,{}).get('avail') or []):
                nm = aname.get((slot,aid), aid)
                if nm=='None': continue
                items.append([nm, apts.get((slot,aid),0), -1, icon_for(slot,aid)])
        if items: slots[label]=items
    e['atts']=slots

    # ---- playground payload: same options as the pane, plus their resolved numeric/tier effects ----
    p_slots=[]; p_def={}
    for ps,pl in PLAY_SLOTS:
        o=[]
        if ps in ('sight','muzzle','barrel','grip','laser','light','ergo'):
            for aid in (tw.get(ps) or {}):
                rec = ACAT.get((ps,aid))
                if rec is None: continue
                o.append(dict(id=aid, n=rec.get('name',aid), p=int(rec.get('pts') or 0),
                              t=tip(tw[ps][aid]), ic=icon_for(ps,aid), fx=p_fx(p_resolve(rec,rid))))
        elif ps=='mag':
            for mid,mm in ((att['WEAPON_MAG'].get(rid,{}) or {}).get('mags') or {}).items():
                if mid not in (tw.get('mag') or {}): continue
                o.append(dict(id=mid, n=mm.get('name',mid), p=int(mm.get('pts') or 0),
                              t=tip(tw['mag'][mid]), ic=icon_for('mag',mid), fx=p_fx(mm)))
        elif ps=='ammo':
            wam = amd['WEAPON_AMMO'].get(rid) or {}
            order = wam.get('ammo') or {}
            for aid in sorted(order, key=lambda k:(order[k], k)):
                cat = AMMO_CAT.get(aid)
                if cat is None: continue
                src = dict(cat); src.update((wam.get('effectOverrides') or {}).get(aid) or {})
                fx = p_fx(src)
                cm = src.get('collateralMult')
                if isinstance(cm,dict) and CLASS_LABEL[w['class']] in cm:
                    fx['coll'] = round(float(cm[CLASS_LABEL[w['class']]]),3)
                po = (wam.get('projectileOverrides') or {}).get(aid)
                if po:
                    if po.get('pellets'): fx['pel'] = int(po['pellets'])
                    if po.get('dmg'): fx['dmg'] = p_pts(po['dmg'])
                    if po.get('vel'): fx['vel'] = round(float(po['vel']))
                o.append(dict(id=aid, n=cat.get('name',aid), p=int(order[aid] or 0),
                              t=tip((tw.get('ammo') or {}).get(aid)), ic=icon_for('ammo',aid), fx=fx))
        elif ps=='accessory':
            for aid in ((att['WEAPON_ACCESSORY'].get(rid,{}) or {}).get('avail') or []):
                rec = ACAT.get(('accessory',aid))
                if rec is None or rec.get('name')=='None': continue
                o.append(dict(id=aid, n=rec.get('name',aid), p=int(rec.get('pts') or 0),
                              t=-1, ic=icon_for('accessory',aid), fx=p_fx(p_resolve(rec,rid))))
        if ps in OPTIONAL:
            nrec = ACAT.get((ps,'none'))
            if nrec is not None and not any(x['id']=='none' for x in o):
                o.insert(0, dict(id='none', n='None', p=0, t=-1, ic=icon_for(ps,'none'),
                                 fx=p_fx(p_resolve(nrec,rid))))
        if not o or (len(o)==1 and o[0]['id']=='none'): continue
        p_slots.append(dict(k=ps, l=pl, o=o))
        if ps=='ammo':    p_def[ps] = (amd['WEAPON_AMMO'].get(rid) or {}).get('def')
        elif ps=='mag':   p_def[ps] = (att['WEAPON_MAG'].get(rid,{}) or {}).get('def')
        elif ps=='barrel':p_def[ps] = (att['WEAPON_ATTS'].get(rid,{}) or {}).get('barrelDef')
        elif ps=='sight': p_def[ps] = 'iron' if any(x['id']=='iron' for x in o) else o[0]['id']
        else:             p_def[ps] = 'none' if any(x['id']=='none' for x in o) else o[0]['id']
    # a slot with a single option offers no choice — drop it before the baseline is built,
    # so base_mult only ever reflects parts the player can actually change
    p_slots = [sl for sl in p_slots if len(sl['o'])>1]
    p_def = {k:v for k,v in p_def.items() if any(sl['k']==k for sl in p_slots)}
    # express every effect relative to the weapon's factory option in its slot, so a lane
    # index of 0 is exactly the gun as it ships, and record the factory part's own absolute
    # values (base['mult']) so the readout starts from the real weapon, not from a neutral 1.
    base_mult = {}
    for sl in p_slots:
        ref = next((x for x in sl['o'] if x['id']==p_def.get(sl['k'])), None)
        if ref is None: continue
        rfx = ref['fx']
        for k in P_MULT:
            if rfx.get(k):                           # a factory 0 cannot act as a ratio, so it
                base_mult[k] = round(base_mult.get(k,1.0) * rfx[k], 4)   # stays absolute below
        if sl['k']=='mag' and rfx.get('mag'):
            rm = rfx.pop('mag'); ref['fx'] = rfx
            for x in sl['o']:
                v = x['fx'].pop('mag', rm)
                if v - rm: x['fx']['magd'] = v - rm
        for x in sl['o']:
            f = x['fx']
            for k in P_MULT:
                if k not in f: continue
                rv = rfx.get(k)
                if rv:                               # ratio against the factory part
                    nv = f[k]/rv
                    if abs(nv-1) > 1e-9: f[k]=round(nv,4)
                    else: del f[k]
                elif k in rfx:                       # factory value is 0, so the ratio is
                    pass                             # undefined: every part keeps its absolute value
                elif x is ref: del f[k]              # no factory counterpart is the identity
            for k in P_TIER:
                nv = f.get(k,0) - rfx.get(k,0)
                if nv: f[k]=nv
                elif k in f: del f[k]
    # collateral baseline: the factory ammunition's own value, not the class standard
    base_coll = COLL_BASE.get(CLASS_LABEL[w['class']]) if COLL_BASE else None
    for sl in p_slots:
        if sl['k']!='ammo': continue
        ref = next((x for x in sl['o'] if x['id']==p_def.get('ammo')), None)
        if ref and ref['fx'].get('coll') is not None: base_coll = ref['fx']['coll']
    p_inc = rw.get('spreadDyn') or {}
    e['play']={'def':{k:v for k,v in p_def.items() if v},
        'slots':p_slots,
        'base':dict(vel=round(w['velocity']), mag=w['mags']['MagSize'], pel=w['pellets'],
                  mult=base_mult,
                  dmg=e['pts'], tac=num(tac_rl), empty=num(empt_rl),
                  dep=round(w['deploy']['DeployTime'],2), und=round(w['deploy']['UnDeployTime'],2),
                  ads=round(sp['ADSStandBaseMin'],3), hip=round(sp['HIPStandBaseMin'],3),
                  adsInc=(round(p_inc['ads']['inc'],3) if p_inc.get('ads') else None),
                  hipInc=(round(p_inc['hip']['inc'],3) if p_inc.get('hip') else None),
                  coll=base_coll)}
    weapons.append(e)

weapons.sort(key=lambda e:(CLASS_ORDER.index(e['cls']), e['name'].lower()))

TIER = json.load(open('tiers.json')) if os.path.exists('tiers.json') else {}
REALMAPS = json.load(open('maps.json')) if os.path.exists('maps.json') else {'maps':[]}
MAPS = REALMAPS.get('maps', [])
# map art: local webp (base64) if downloaded, else remote URL
MAPIMG = {}
for m in MAPS:
    slug = m['slug']
    p = f'mapwebp/{slug}.webp'
    if os.path.exists(p):
        MAPIMG[slug] = 'data:image/webp;base64,' + base64.b64encode(open(p,'rb').read()).decode()
    else:
        u = (REALMAPS.get('imageUrls') or {}).get(slug) or f'https://bf6balancelog.com/img/items/{slug}.jpg'
        MAPIMG[slug] = u
RW   = json.load(open('realworld.json')) if os.path.exists('realworld.json') else {}
SEASON = open('season.txt').read().strip() if os.path.exists('season.txt') else ''
VER = 'v%s (%s)' % (sym_info['version'], sym_info['versionDate'])

tpl = open(TEMPLATE, encoding='utf-8').read()
html = (tpl.replace('/*__DATA__*/[]', json.dumps(weapons,ensure_ascii=False))
           .replace('/*__RW__*/{}', json.dumps(RW,ensure_ascii=False))
           .replace('/*__TIER__*/{}', json.dumps(TIER,ensure_ascii=False))
           .replace('/*__TIPS__*/[]', json.dumps(TIPS,ensure_ascii=False))
           .replace('/*__ICONS__*/[]', json.dumps(ICONS,ensure_ascii=False))
           .replace('/*__MAPS__*/[]', json.dumps(MAPS,ensure_ascii=False))
           .replace('/*__MAPIMG__*/{}', json.dumps(MAPIMG,ensure_ascii=False))
           .replace("/*__VER__*/''", json.dumps(VER))
           .replace("/*__SEASON__*/''", json.dumps(SEASON)))
for ph in ('__DATA__','__RW__','__TIER__','__TIPS__','__ICONS__','__MAPS__','__MAPIMG__','__VER__','__SEASON__'):
    assert ph not in html, ph
open(OUT,'w',encoding='utf-8').write(html)
n_att = sum(sum(len(v) for v in w['atts'].values()) for w in weapons)
print('wrote %s %d KB | weapons %d | maps %d (img %d) | tips %d | icons %d | slots %d | atts %d' % (
    OUT, len(html)//1024, len(weapons), len(MAPS), len(MAPIMG), len(TIPS), len(ICONS),
    sum(len(w['atts']) for w in weapons), n_att))