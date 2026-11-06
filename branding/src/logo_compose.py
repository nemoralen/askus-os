import random, math, re
base=open(__import__("os").environ.get("ASKUS_BASE","h5-neon-honeycomb.svg")).read()
BLUE="#22D3EE"; PINK="#F472B6"
NEON=["#22D3EE","#8B5CF6","#F472B6","#A78BFA","#67E8F9","#F0ABFC"]
def splat(rng,n,cx,cy,spread,rmax,cols=NEON):
    out=[]
    for _ in range(n):
        a=rng.uniform(0,2*math.pi); d=abs(rng.gauss(0,spread))
        x=cx+d*math.cos(a); y=cy+d*math.sin(a)*0.8
        r=rng.uniform(0.8,rmax)*(1.4 if d<spread*0.3 else 1)
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="{rng.choice(cols)}" opacity="{rng.uniform(.35,1):.2f}"/>')
    return "".join(out)
def bee(col,x,y,rot,sc,ghost=False):
    body=f'''<ellipse cx="-14" cy="-46" rx="34" ry="52" transform="rotate(-25 -14 -46)" fill="{col}" opacity="0.5"/>
  <ellipse cx="18" cy="-44" rx="30" ry="46" transform="rotate(20 18 -44)" fill="{col}" opacity="0.72"/>
  <ellipse cx="0" cy="20" rx="66" ry="36" fill="{col}"/>
  <circle cx="80" cy="12" r="25" fill="{col}"/>
  <path d="M90 -8C100 -34 112 -42 122 -44 M76 -10C80 -36 88 -48 96 -54" fill="none" stroke="{col}" stroke-width="6" stroke-linecap="round"/>
  <path d="M-64 18L-92 24L-64 30Z" fill="{col}"/>'''
    g=""
    if ghost:  # motion echoes
        for i,(dx,op) in enumerate([(-70,0.18),(-140,0.08)]):
            g+=f'<g transform="translate({x+dx*math.cos(math.radians(rot)):.0f} {y+dx*math.sin(math.radians(rot)):.0f}) rotate({rot}) scale({sc})" opacity="{op}">{body}</g>'
    return g+f'<g transform="translate({x} {y}) rotate({rot}) scale({sc})" filter="url(#beeglow)">{body}</g>'
DEFS='''<defs>
<filter id="beeglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>
<filter id="aur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="90"/></filter>
<linearGradient id="rimn" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22D3EE"/><stop offset="0.5" stop-color="#8B5CF6"/><stop offset="1" stop-color="#F472B6"/></linearGradient>
<pattern id="scan" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="1.4" fill="#22D3EE" opacity="0.06"/></pattern>
</defs>'''
BIGPOS=(775,255,-16,1.05); SMALLPOS=(150,866,-24,0.4)
def compose(seed, extra_front="", extra_back="", ghost=False, splat_scale=1.0, glow=False, rim=None):
    rng=random.Random(seed)
    s=base
    k=s.find('/>', s.find('fill="url(#bgn)"'))+2
    s=s[:k]+extra_back+s[k:]
    if glow: s=s.replace('<g filter="url(#g1)" opacity="0.7">','<g filter="url(#g1)" opacity="1">')
    n=lambda v:int(v*splat_scale)
    add=DEFS+f'''
<g filter="url(#soft)" opacity="0.8">{splat(rng,n(55),800,250,130,8)}</g>
<g filter="url(#beeglow)">{splat(rng,n(170),790,260,160,4.5)}</g>
<g filter="url(#beeglow)">{splat(rng,n(40),150,862,70,3,[PINK,"#F0ABFC","#A78BFA"])}</g>
{bee(BLUE,*BIGPOS,ghost=ghost)}
{bee(PINK,*SMALLPOS,ghost=ghost)}
{extra_front}'''
    i=s.rfind("</g>"); s=s[:i]+add+s[i:]
    if rim: s=s.replace('stroke="#8B5CF6" stroke-opacity="0.35" stroke-width="5"', rim)
    return s
V={}
# 1 Clean
V["final-v1-clean"]=compose(42)
# 2 Neon splash: more splatter, brighter A, gradient rim
V["final-v2-splash"]=compose(11, splat_scale=1.7, glow=True,
    rim='stroke="url(#rimn)" stroke-opacity="1" stroke-width="9"',
    extra_back='<circle cx="512" cy="540" r="360" fill="#8B5CF6" opacity="0.22" filter="url(#aur)"/>')
# 3 Motion: echo trails behind bees + soft aurora
V["final-v3-motion"]=compose(23, ghost=True,
    extra_back='<g filter="url(#aur)"><ellipse cx="820" cy="230" rx="240" ry="180" fill="#22D3EE" opacity="0.12"/><ellipse cx="160" cy="860" rx="160" ry="120" fill="#F472B6" opacity="0.14"/></g>')
# 4 High-tech HUD
rng=random.Random(5)
def circuits():
    out=""
    for _ in range(14):
        x=rng.choice(range(60,980,40)); y=rng.choice(range(60,980,40))
        pts=[(x,y)]
        for _ in range(3):
            dx,dy=rng.choice([(1,0),(0,1),(1,1),(-1,1)]); L=rng.choice([40,80,120])
            x+=dx*L; y+=dy*L; pts.append((x,y))
        d="M"+" L".join(f"{a} {b}" for a,b in pts)
        out+=f'<path d="{d}" fill="none" stroke="#22D3EE" stroke-opacity="0.22" stroke-width="2"/><circle cx="{pts[-1][0]}" cy="{pts[-1][1]}" r="4" fill="none" stroke="#22D3EE" stroke-opacity="0.5" stroke-width="2"/>'
    return out
bx,by=BIGPOS[0]+5,BIGPOS[1]-5
br=lambda x,y,s,c: f'<path d="M{x-s} {y-s+22}V{y-s}H{x-s+22} M{x+s-22} {y-s}H{x+s}V{y-s+22} M{x+s} {y+s-22}V{y+s}H{x+s-22} M{x-s+22} {y+s}H{x-s}V{y+s-22}" fill="none" stroke="{c}" stroke-width="4"/>'
hud=f'''
<rect width="1024" height="1024" fill="url(#scan)"/>
<circle cx="{bx}" cy="{by}" r="118" fill="none" stroke="#22D3EE" stroke-opacity="0.5" stroke-width="2" stroke-dasharray="6 10"/>
<circle cx="{bx}" cy="{by}" r="140" fill="none" stroke="#22D3EE" stroke-opacity="0.25" stroke-width="1.5"/>
<path d="M{bx-160} {by}H{bx-125} M{bx+125} {by}H{bx+160} M{bx} {by-160}V{by-125} M{bx} {by+125}V{by+160}" stroke="#22D3EE" stroke-width="3"/>
{br(150,866,62,"#F472B6")}
<text x="{bx-118}" y="{by+178}" font-family="DejaVu Sans Mono" font-size="17" fill="#67E8F9" opacity="0.85">TRK·01  TOR:ON</text>
<text x="225" y="935" font-family="DejaVu Sans Mono" font-size="16" fill="#F0ABFC" opacity="0.7">ID·02 ◆ ANON</text>
<text x="150" y="128" font-family="DejaVu Sans Mono" font-size="18" letter-spacing="3" fill="#67E8F9" opacity="0.75">ASKUS//OS  SECURE_NODE</text>
<path d="M150 140H410" stroke="#22D3EE" stroke-opacity="0.5" stroke-width="2"/>
<g fill="#22D3EE" opacity="0.6">{"".join(f'<rect x="{900+i*12}" y="{940-h}" width="7" height="{h}"/>' for i,h in enumerate([18,30,22,40,26]))}</g>
'''
V["final-v4-hightech"]=compose(42, extra_back=circuits(), extra_front=hud,
    rim='stroke="url(#rimn)" stroke-opacity="0.9" stroke-width="6"')
for k,v in V.items(): open(k+".svg","w").write(v)
