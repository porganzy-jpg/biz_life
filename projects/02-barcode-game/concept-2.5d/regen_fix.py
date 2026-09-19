# -*- coding: utf-8 -*-
"""검수에서 어긋난 몬스터만 강화 프롬프트로 재생성. 기존 파일은 *_alt.png로 보존."""
import urllib.parse, urllib.request, time, os, shutil
from PIL import Image
JOBS = {
 "A_cute_food/01_gimbap_slime":      ("kawaii food mascot character design, 3D render, chibi, isometric view, studio lighting, sharp focus, triangular korean onigiri rice ball character with a black seaweed band, white rice texture, big sparkling eyes, tiny arms", 42),
 "A_cute_food/02_milk_carton_cat":   ("kawaii food mascot character design, 3D render, chibi, isometric view, studio lighting, sharp focus, a milk carton box character with gable top, white carton body with blue cow spots, cat ears and whiskers, big eyes", 2202),
 "B_cool_tech/03_gamepad_robo_pup":  ("kawaii robot mascot character design, 3D render, chibi, isometric view, studio lighting, sharp focus, a puppy robot whose body is a video game controller with colorful buttons and two joysticks, wagging tail, big eyes", 43003),
 "B_cool_tech/04_drone_hawk":        ("kawaii robot mascot character design, 3D render, chibi, isometric view, studio lighting, sharp focus, a hawk bird robot with four quadcopter drone propellers on its wings, camera lens eye, metallic feathers", 43004),
 "B_cool_tech/05_smartphone_chameleon": ("kawaii robot mascot character design, 3D render, chibi, isometric view, studio lighting, sharp focus, a chameleon robot with a glowing smartphone screen on its back, rainbow pixels, curled tail, big eyes", 43005),
 "B_cool_tech/06_outlet_octopus":    ("kawaii robot mascot character design, 3D render, chibi, isometric view, studio lighting, sharp focus, an octopus robot whose head is a white power strip with sockets, tentacles ending in electric plugs, glowing", 43006),
 "D_legendary_country/05_macaron_unicorn": ("kawaii mascot character design, 3D render, chibi, isometric view, studio lighting, sharp focus, a small white unicorn pony with a golden horn, mane made of pastel pink mint and lavender macarons, sparkles, big eyes", 6205),
}
for rel,(prompt,seed) in JOBS.items():
    out=rel+".png"
    if os.path.exists(out) and not os.path.exists(rel+"_alt.png"): shutil.copy(out, rel+"_alt.png")
    url="https://image.pollinations.ai/prompt/"+urllib.parse.quote(prompt+", no text")+f"?width=768&height=768&seed={seed}&nologo=true"
    for a in range(10):
        try:
            t=time.time(); data=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=240).read()
            if len(data)<22000: raise RuntimeError("small")
            tmp=out+".jpg"; open(tmp,"wb").write(data); im=Image.open(tmp).convert("RGB"); w,h=im.size; im.crop((0,0,w,int(h*0.955))).save(out); os.remove(tmp)
            print(f"ok   {rel} {len(data)//1024}KB {time.time()-t:.0f}s", flush=True); break
        except Exception as e: print(f"retry {rel} #{a+1}: {str(e)[:40]}", flush=True); time.sleep(6+a*3)
    time.sleep(3)
print("REGEN DONE")
