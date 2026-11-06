"""Builds wordmarks, wallpaper and boot splash around the official logo (logo.svg)."""
import random, math, subprocess, base64, os
here=os.path.dirname(os.path.abspath(__file__)); os.chdir(here)
png=subprocess.run(["rsvg-convert","-w","640","-h","640","logo.svg"],capture_output=True,check=True).stdout
B64=base64.b64encode(png).decode()
IMG=lambda x,y,s: f'<image x="{x}" y="{y}" width="{s}" height="{s}" xlink:href="data:image/png;base64,{B64}"/>'
NS='xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
GR='''<linearGradient id="word" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#E0E7FF"/></linearGradient>
<linearGradient id="osg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22D3EE"/><stop offset="0.5" stop-color="#8B5CF6"/><stop offset="1" stop-color="#F472B6"/></linearGradient>'''
def wordmark(bg, txt="url(#word)", sub="#94A3B8"):
    return f'''<svg {NS} viewBox="0 0 2000 600" width="2000" height="600"><defs>{GR}</defs>{bg}
{IMG(50,50,500)}
<text x="620" y="360" font-family="Inter Display, Inter" font-weight="800" font-size="230" letter-spacing="-6" fill="{txt}">ASKus</text>
<text x="1395" y="360" font-family="Inter Display, Inter" font-weight="300" font-size="230" letter-spacing="-2" fill="url(#osg)">OS</text>
<text x="628" y="452" font-family="DejaVu Sans Mono" font-size="40" letter-spacing="8" fill="{sub}">PRIVATE · AMNESIC · YOURS</text></svg>'''
open("logo-wordmark.svg","w").write(wordmark(""))
open("logo-wordmark-on-dark.svg","w").write(wordmark('<rect width="2000" height="600" rx="80" fill="#070A1F"/>'))
open("logo-wordmark-light.svg","w").write(wordmark("", "#0F172A", "#475569"))

rnd=random.Random(9)
W,H=3840,2160
def hexgrid(r=46):
    out=[];w=math.sqrt(3)*r
    for row in range(-1,int(H/(1.5*r))+2):
        for col in range(-1,int(W/w)+2):
            x=col*w+(row%2)*w/2; y=row*1.5*r
            p=" L".join(f"{x+r*0.92*math.cos(math.radians(60*i+30)):.0f} {y+r*0.92*math.sin(math.radians(60*i+30)):.0f}" for i in range(6))
            out.append(f"M{p}Z")
    return f'<path d="{" ".join(out)}" fill="none" stroke="#8B5CF6" stroke-opacity="0.07" stroke-width="2"/>'
def circuits(n):
    out=""
    for _ in range(n):
        x=rnd.randrange(0,W,60); y=rnd.randrange(0,H,60); pts=[(x,y)]
        for _ in range(4):
            dx,dy=rnd.choice([(1,0),(0,1),(1,1),(-1,1),(1,-1)]); L=rnd.choice([60,120,180,240]); x+=dx*L; y+=dy*L; pts.append((x,y))
        out+=f'<path d="M{" L".join(f"{a} {b}" for a,b in pts)}" fill="none" stroke="#22D3EE" stroke-opacity="0.16" stroke-width="2.5"/><circle cx="{pts[-1][0]}" cy="{pts[-1][1]}" r="6" fill="none" stroke="#22D3EE" stroke-opacity="0.4" stroke-width="2.5"/>'
    return out
NEON=["#22D3EE","#8B5CF6","#F472B6","#A78BFA","#67E8F9","#F0ABFC"]
def splat(n,cx,cy,sp,rmax):
    s=""
    for _ in range(n):
        a=rnd.uniform(0,6.283); d=abs(rnd.gauss(0,sp))
        s+=f'<circle cx="{cx+d*math.cos(a):.0f}" cy="{cy+d*math.sin(a)*0.8:.0f}" r="{rnd.uniform(1,rmax):.1f}" fill="{rnd.choice(NEON)}" opacity="{rnd.uniform(.3,1):.2f}"/>'
    return s
BEE=lambda col,x,y,rot,sc: f'''<g transform="translate({x} {y}) rotate({rot}) scale({sc})" filter="url(#gl)"><ellipse cx="-14" cy="-46" rx="34" ry="52" transform="rotate(-25 -14 -46)" fill="{col}" opacity="0.5"/><ellipse cx="18" cy="-44" rx="30" ry="46" transform="rotate(20 18 -44)" fill="{col}" opacity="0.72"/><ellipse cx="0" cy="20" rx="66" ry="36" fill="{col}"/><circle cx="80" cy="12" r="25" fill="{col}"/><path d="M90 -8C100 -34 112 -42 122 -44 M76 -10C80 -36 88 -48 96 -54" fill="none" stroke="{col}" stroke-width="6" stroke-linecap="round"/><path d="M-64 18L-92 24L-64 30Z" fill="{col}"/></g>'''
SCENE_DEFS='''<radialGradient id="bgn" cx="0.5" cy="0.45" r="0.8"><stop offset="0" stop-color="#1B1650"/><stop offset="1" stop-color="#04050D"/></radialGradient>
<filter id="aur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="200"/></filter>
<filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<pattern id="scan" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="2" fill="#22D3EE" opacity="0.035"/></pattern>'''
scene=f'''<rect width="{W}" height="{H}" fill="url(#bgn)"/>
<g filter="url(#aur)"><ellipse cx="700" cy="500" rx="900" ry="600" fill="#06B6D4" opacity="0.22"/><ellipse cx="3200" cy="1700" rx="1000" ry="650" fill="#DB2777" opacity="0.22"/><ellipse cx="1920" cy="1080" rx="900" ry="600" fill="#7C3AED" opacity="0.25"/></g>
{hexgrid()}{circuits(70)}
<g filter="url(#gl)">{splat(320,3150,420,380,6)}{splat(140,560,1780,260,4.5)}</g>
{BEE("#22D3EE",3150,430,-16,1.6)}{BEE("#F472B6",560,1780,-24,0.75)}
<rect width="{W}" height="{H}" fill="url(#scan)"/>'''
hud='''<g font-family="DejaVu Sans Mono" fill="#67E8F9">
<text x="140" y="150" font-size="34" letter-spacing="6" opacity="0.75">ASKUS//OS  SECURE_NODE</text><path d="M140 172H720" stroke="#22D3EE" stroke-opacity="0.5" stroke-width="3"/>
<text x="3700" y="2040" font-size="30" text-anchor="end" opacity="0.6" fill="#F0ABFC">TOR:ON ◆ AMNESIC ◆ ENCRYPTED</text></g>
<circle cx="3155" cy="425" r="260" fill="none" stroke="#22D3EE" stroke-opacity="0.35" stroke-width="3" stroke-dasharray="10 16"/>'''
open("wallpaper.svg","w").write(f'<svg {NS} viewBox="0 0 {W} {H}" width="{W}" height="{H}"><defs>{SCENE_DEFS}</defs>{scene}{hud}</svg>')
open("boot-splash.svg","w").write(f'''<svg {NS} viewBox="0 0 {W} {H}" width="{W}" height="{H}"><defs>{SCENE_DEFS}{GR}</defs>{scene}
<rect width="{W}" height="{H}" fill="#000" opacity="0.3"/>
{IMG(1580,380,680)}
<text x="1920" y="1300" text-anchor="middle" font-family="Inter Display, Inter" font-weight="800" font-size="200" letter-spacing="-4" fill="#fff">ASKus <tspan font-weight="300" fill="url(#osg)">OS</tspan></text>
<text x="1920" y="1400" text-anchor="middle" font-family="DejaVu Sans Mono" font-size="44" letter-spacing="12" fill="#94A3B8">PRIVATE · AMNESIC · YOURS</text></svg>''')
print("graphics written")
