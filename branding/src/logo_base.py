import math, random
random.seed(7)
S3=math.sqrt(3)
def hexpts(cx,cy,r,rot=30):
    return [(cx+r*math.cos(math.radians(60*i+rot)), cy+r*math.sin(math.radians(60*i+rot))) for i in range(6)]
def hexpath(cx,cy,r,rot=30):
    p=hexpts(cx,cy,r,rot); return "M"+" L".join(f"{x:.1f} {y:.1f}" for x,y in p)+"Z"
n=5.0;a=472;c=512;pts=[]
for i in range(0,360,3):
    t=math.radians(i);ct,st=math.cos(t),math.sin(t)
    pts.append(f"{c+a*math.copysign(abs(ct)**(2/n),ct):.1f} {c+a*math.copysign(abs(st)**(2/n),st):.1f}")
SQ="M"+" L".join(pts)+"Z"
DEFS=f'''<defs>
<linearGradient id="gold" gradientUnits="userSpaceOnUse" x1="150" y1="900" x2="880" y2="120"><stop offset="0" stop-color="#E07B00"/><stop offset="0.5" stop-color="#FFB020"/><stop offset="1" stop-color="#FFE9A8"/></linearGradient>
<linearGradient id="goldv" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#D96A00"/><stop offset="1" stop-color="#FFE08A"/></linearGradient>
<linearGradient id="neon" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#22D3EE"/><stop offset="0.5" stop-color="#8B5CF6"/><stop offset="1" stop-color="#F472B6"/></linearGradient>
<linearGradient id="tealgold" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5EEAD4"/><stop offset="0.5" stop-color="#9CA3AF"/><stop offset="1" stop-color="#E5E04A"/></linearGradient>
<radialGradient id="bgw" cx="0.5" cy="0.5" r="0.7"><stop offset="0" stop-color="#1A1206"/><stop offset="1" stop-color="#050403"/></radialGradient>
<radialGradient id="bgn" cx="0.5" cy="0.45" r="0.7"><stop offset="0" stop-color="#1B1650"/><stop offset="1" stop-color="#05060F"/></radialGradient>
<radialGradient id="core" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#FFD166" stop-opacity="0.55"/><stop offset="1" stop-color="#FF9F1C" stop-opacity="0"/></radialGradient>
<filter id="g1" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter>
<filter id="g2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter>
<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="sq"><path d="{SQ}"/></clipPath>
</defs>'''
def tile(inner,bg="bgw",rim="#FFB020"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">{DEFS}
<g clip-path="url(#sq)"><rect width="1024" height="1024" fill="url(#{bg})"/>{inner}</g>
<path d="{SQ}" fill="none" stroke="{rim}" stroke-opacity="0.35" stroke-width="5"/></svg>'''
def particles(n,x0,y0,x1,y1,col="#FFD166",rmax=4):
    return "".join(f'<circle cx="{random.uniform(x0,x1):.0f}" cy="{random.uniform(y0,y1):.0f}" r="{random.uniform(1,rmax):.1f}" fill="{col}" opacity="{random.uniform(.3,1):.2f}"/>' for _ in range(n))
def hexgrid(cx,cy,R,r,cls=""):
    out=[]; w=S3*r
    for q in range(-12,13):
        for k in range(-12,13):
            x=cx+w*(q+k/2); y=cy+1.5*r*k
            if math.hypot(x-cx,y-cy)<R: out.append((x,y))
    return out
def in_A(x,y):
    # A: apex (512,200), base y 820, half-width 300 at base; counter triangle and crossbar
    if y<200 or y>820: return False
    hw=(y-200)/620*300
    if abs(x-512)>hw: return False
    inner=hw-150*(1 if y>260 else 0)
    # leg thickness ~ 150 horizontally
    if y>360 and abs(x-512)<hw-150:
        if 560<y<650: return True   # crossbar
        return False
    return True
V={}

# 1 Gold hex + isometric cube emblem
r=300; cx,cy=512,512
top=(cx,cy-r); P=hexpts(cx,cy,r,-90)
cube_lines=[(P[i],P[(i+1)%6]) for i in range(6)]+[((cx,cy),P[0]),((cx,cy),P[2]),((cx,cy),P[4])]
small=hexpts(cx,cy-62,120,-90); cl2=[(small[i],small[(i+1)%6]) for i in range(6)]+[((cx,cy-62),small[0]),((cx,cy-62),small[2]),((cx,cy-62),small[4])]
L=lambda ls,sw,col: "".join(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{col}" stroke-width="{sw}" stroke-linecap="round"/>' for a,b in ls)
faceL="M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f Z"%(cx,cy,*P[2],*P[3],*P[4])
V["h1-gold-cube"]=tile(f'''<circle cx="512" cy="512" r="420" fill="url(#core)"/>
<path d="{faceL}" fill="url(#goldv)" opacity="0.28"/>
<g filter="url(#glow)">{L(cube_lines,10,"url(#gold)")}{L(cl2,6,"#FFE9A8")}</g>
<g fill="#FFF3C4" filter="url(#glow)">{"".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="11"/>' for x,y in P+[(cx,cy)])}</g>
{particles(70,560,90,960,420)}''')

# 2 Honeycomb A (gold)
cells=[(x,y) for x,y in hexgrid(512,520,520,34) if in_A(x,y)]
bgcells=hexgrid(512,512,700,34)
hc="".join(f'<path d="{hexpath(x,y,30,30)}" fill="url(#gold)" opacity="{0.55+0.45*(1-(y-200)/700):.2f}"/>' for x,y in cells)
bgc="".join(f'<path d="{hexpath(x,y,30,30)}" fill="none" stroke="#FFB020" stroke-opacity="0.08" stroke-width="2"/>' for x,y in bgcells)
V["h2-honeycomb-a"]=tile(f'''{bgc}<circle cx="512" cy="560" r="380" fill="url(#core)" opacity="0.7"/>
<g filter="url(#g1)" opacity="0.6">{hc}</g>{hc}''')

# 3 Wireframe pyramid over isometric hex floor + particle spiral
def iso(x,y): return (512+(x-y)*0.866, 700+(x+y)*0.36)
floor=""
for q in range(-6,7):
    for k in range(-6,7):
        x=q*60+k*30; y=k*52
        if abs(q+k/2)<=5.5 and abs(k)<=5:
            hp=[(x+34*math.cos(math.radians(60*i+30)), y+34*math.sin(math.radians(60*i+30))) for i in range(6)]
            pp=[iso(a*0.75,b*0.75) for a,b in hp]
            if max(abs(px-512) for px,_ in pp)<390:
                floor+='<path d="M'+" L".join(f"{a:.0f} {b:.0f}" for a,b in pp)+f'Z" fill="#FFB020" fill-opacity="{random.uniform(.03,.14):.2f}" stroke="#FFB020" stroke-opacity="0.45" stroke-width="2"/>'
apex=(512,150); base=[(170,700),(512,560),(854,700),(512,860)]
pl=[(apex,b) for b in base]+[(base[i],base[(i+1)%4]) for i in range(4)]+[((512,430),b) for b in base]
spiral="".join(f'<circle cx="{512+ (70*(1-t))*math.sin(t*14):.0f}" cy="{820-t*600:.0f}" r="{random.uniform(1.5,5):.1f}" fill="#FFD166" opacity="{random.uniform(.4,1):.2f}"/>' for t in [i/160 for i in range(160)])
V["h3-pyramid-wire"]=tile(f'''{floor}<circle cx="512" cy="430" r="300" fill="url(#core)"/>
<g filter="url(#glow)">{L(pl,5,"url(#gold)")}</g>
<g filter="url(#glow)">{spiral}</g>
<g fill="#FFF3C4" filter="url(#glow)">{"".join(f'<circle cx="{x}" cy="{y}" r="10"/>' for x,y in [apex]+base+[(512,430)])}</g>
{particles(60,600,60,980,380)}''')

# 4 Hex mandala (teal -> yellow) with cube emblem
grid=hexgrid(512,512,560,40)
md=""
for x,y in grid:
    d=math.hypot(x-512,y-512)
    if d<150: continue
    t=(x-y)/1024*0.5+0.5  # teal top-right, yellow bottom-left
    col=f"rgb({int(229*(1-t)+94*t)},{int(224*(1-t)+234*t)},{int(74*(1-t)+212*t)})"
    rr=34 if d<420 else max(14,34-(d-420)/9)
    md+=f'<path d="{hexpath(x,y,rr,30)}" fill="{col}" fill-opacity="{0.25+0.55*min(1,d/450):.2f}" stroke="#C2703D" stroke-width="3"/>'
    md+=f'<path d="{hexpath(x,y,rr*0.45,30)}" fill="none" stroke="#fff" stroke-opacity="0.35" stroke-width="2"/>'
P4=hexpts(512,512,95,-90)
c4=[(P4[i],P4[(i+1)%6]) for i in range(6)]+[((512,512),P4[0]),((512,512),P4[2]),((512,512),P4[4])]
V["h4-hex-mandala"]=tile(f'''{md}<path d="{hexpath(512,512,150,30)}" fill="#050403" stroke="#C2703D" stroke-width="5"/>
{L(c4,5,"#F5F5F4")}
<text x="512" y="640" text-anchor="middle" font-family="Inter" font-weight="600" font-size="22" letter-spacing="10" fill="#E7E5E4">ASKUS</text>''',rim="#C2703D")

# 5 Neon honeycomb A (your original colours)
hcn="".join(f'<path d="{hexpath(x,y,30,30)}" fill="url(#neon)" opacity="{0.6+0.4*((x-200)/600):.2f}"/>' for x,y in cells)
bgn="".join(f'<path d="{hexpath(x,y,30,30)}" fill="none" stroke="#8B5CF6" stroke-opacity="0.10" stroke-width="2"/>' for x,y in bgcells)
V["h5-neon-honeycomb"]=tile(f'''{bgn}<g filter="url(#g1)" opacity="0.7">{hcn}</g>{hcn}''',bg="bgn",rim="#8B5CF6")

# 6 Gold hex frame + wireframe A constellation
H=hexpts(512,512,380,-90)
A_nodes=[(512,230),(320,780),(704,780),(400,560),(624,560),(512,420)]
al=[(A_nodes[0],A_nodes[1]),(A_nodes[0],A_nodes[2]),(A_nodes[3],A_nodes[4]),(A_nodes[5],A_nodes[3]),(A_nodes[5],A_nodes[4]),(A_nodes[0],A_nodes[5])]
spokes=[(A_nodes[0],H[0]),(A_nodes[1],H[3]),(A_nodes[2],H[1]),(A_nodes[3],H[4]),(A_nodes[4],H[2]),(A_nodes[1],H[4]),(A_nodes[2],H[2])]
V["h6-hex-constellation"]=tile(f'''<circle cx="512" cy="512" r="420" fill="url(#core)" opacity="0.6"/>
<path d="{hexpath(512,512,380,-90)}" fill="none" stroke="url(#gold)" stroke-width="12" filter="url(#glow)"/>
{L(spokes,2.5,"#FFB020")}
<g filter="url(#glow)">{L(al,16,"url(#gold)")}</g>
<g fill="#FFF3C4" filter="url(#glow)">{"".join(f'<circle cx="{x}" cy="{y}" r="14"/>' for x,y in A_nodes)}{"".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="8"/>' for x,y in H)}</g>
{particles(80,80,80,944,944,rmax=3)}''')

for k,v in V.items(): open(k+".svg","w").write(v)
