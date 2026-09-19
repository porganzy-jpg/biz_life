# -*- coding: utf-8 -*-
"""4테마 24종 2.5D 몬스터를 flux 모델로 순차 생성 (Pollinations는 IP당 동시 1요청 → 반드시 순차).
python gen_all_flux.py [테마접두어...]   예) python gen_all_flux.py A_ D_"""
import urllib.parse, urllib.request, time, os, sys, json
from PIL import Image
STYLE = ("2.5D isometric game character render, soft cel shading with subtle 3D volume, clean outlines, vibrant colors, "
         "plain pastel background, centered full body, toy-like, high quality, sharp focus, detailed, no text, ")
JOBS = {
 # A 귀여운 식품
 "A_cute_food/01_gimbap_slime": ("a cute slime monster shaped like a triangular korean onigiri rice ball, white rice body with a black seaweed band, sharp triangle silhouette, tiny happy face, rosy cheeks", 7712),
 "A_cute_food/02_milk_carton_cat": ("a cute cat monster whose body is a white milk carton with blue stripes, cat ears on the carton top fold, tiny paws, curious eyes, drop of milk", 1202),
 "A_cute_food/03_cup_noodle_dragon": ("a small chubby dragon monster curled inside a red cup noodle bowl, noodles as mane, steam wisps, tiny wings, proud grin", 1303),
 "A_cute_food/04_banana_milk_duck": ("a cute duck monster shaped like a pale yellow banana milk bottle, round belly bottle body, duck beak and orange feet, cheerful", 1404),
 "A_cute_food/05_choco_pie_bear": ("a cute round bear monster whose body is a chocolate pie, brown glossy coating, marshmallow white belly showing, sleepy happy eyes", 1505),
 "A_cute_food/06_jelly_jellyfish": ("a translucent gummy jelly jellyfish monster, rainbow gradient bear-shaped gummies as tentacles, glossy candy shine, sweet smile", 1606),
 # B 멋있는 전자기기
 "B_cool_tech/01_battery_golem": ("a cool sleek battery golem monster, torso shaped like a giant battery cell with glowing cyan charge bars, armored limbs, copper terminal horns, heroic pose, electric sparks", 41001),
 "B_cool_tech/02_earbud_wolf": ("a sleek wolf monster inspired by wireless earbuds, glossy white and matte black panels, ears shaped like earbuds with glowing blue LED rings, dynamic stride", 41002),
 "B_cool_tech/03_gamepad_robo_pup": ("a robot puppy monster built from a game controller, joystick ears, colorful button spots, D-pad chest, wagging cable tail, playful", 41003),
 "B_cool_tech/04_drone_hawk": ("a hawk monster with quadcopter drone rotors as wings, camera lens eye, carbon fiber feathers, hovering, cool and sharp", 41004),
 "B_cool_tech/05_smartphone_chameleon": ("a chameleon monster whose body is a sleek smartphone, screen skin shifting colors, curled charging-cable tail, clever eyes", 41005),
 "B_cool_tech/06_outlet_octopus": ("an octopus monster shaped like a power strip, tentacles are glowing plugs and cables, socket-face eyes, mischievous grin", 41006),
 # C 생활용품
 "C_household/01_detergent_jellyfish": ("a jellyfish monster whose bell is a blue laundry detergent bottle with a cap, soap bubble tentacles, sparkling clean, gentle face", 5101),
 "C_household/02_flowerpot_turtle": ("a turtle monster whose shell is a terracotta flower pot with a blooming flower on top, mossy legs, kind eyes", 5102),
 "C_household/03_umbrella_bat": ("a bat monster made from a folded black umbrella, umbrella canopy wings, hooked handle tail, big cute eyes, slightly spooky", 5103),
 "C_household/04_towel_ghost": ("a ghost monster made of a soft folded white bath towel, fluffy texture, two shy eyes, floating, steam", 5104),
 "C_household/05_toothbrush_hedgehog": ("a hedgehog monster with colorful toothbrush bristles as spines, minty sparkle, tiny nose, cheerful", 5105),
 "C_household/06_candle_dokkaebi": ("a korean dokkaebi goblin monster shaped like a lit candle, flame hair, dripping wax cloak, holding a tiny club, mischievous warm glow", 5106),
 # D 전설·국가코드
 "D_legendary_country/01_taegeuk_tiger": ("a legendary chibi white tiger guardian monster with red and blue taegeuk yin-yang symbol on its chest, golden aura, jewel eyes, majestic but cute", 6101),
 "D_legendary_country/02_ninetail_fox": ("a legendary chibi nine-tailed fox monster, ivory fur, tails tipped with blue foxfire, red shrine ribbon, jewel-like glow", 6102),
 "D_legendary_country/03_star_eagle": ("a legendary chibi eagle monster with star-pattern navy wings and red-white striped tail, golden crest, proud, glowing", 6103),
 "D_legendary_country/04_gear_bear": ("a legendary chibi mechanical bear monster with brass gears and clockwork joints, black-red-gold accents, steam, sturdy", 6104),
 "D_legendary_country/05_macaron_unicorn": ("a legendary chibi unicorn monster with pastel macaron mane in pink mint and lavender, golden horn, sparkles, elegant", 6105),
 "D_legendary_country/06_panda_dragon": ("a legendary chibi panda dragon monster, black and white panda face and paws with red-gold dragon scales and whiskers, bamboo, jade glow", 6106),
}
only = sys.argv[1:]
log = open("gen_all_flux.log","a",encoding="utf-8")
for rel,(desc,seed) in JOBS.items():
    if only and not any(rel.startswith(o) for o in only): continue
    out = rel+".png"
    url = "https://image.pollinations.ai/prompt/"+urllib.parse.quote(STYLE+desc)+f"?width=768&height=768&seed={seed}&nologo=true&model=flux"
    ok=False
    for a in range(12):
        try:
            t=time.time(); data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=240).read()
            if len(data) < 25000: raise RuntimeError(f"small {len(data)}")
            tmp=out+".jpg"; open(tmp,"wb").write(data); im=Image.open(tmp).convert("RGB"); w,h=im.size
            im.crop((0,0,w,int(h*0.955))).save(out); os.remove(tmp)
            msg=f"ok   {rel} {len(data)//1024}KB {time.time()-t:.0f}s seed={seed}"; ok=True; break
        except Exception as e:
            msg=f"retry {rel} #{a+1}: {str(e)[:60]}"; print(msg, flush=True); log.write(msg+"\n"); log.flush(); time.sleep(6+a*3)
    print(msg, flush=True); log.write(msg+"\n"); log.flush()
    time.sleep(3)
json.dump({k:{"prompt":STYLE+v[0],"seed":v[1]} for k,v in JOBS.items()}, open("prompts_flux.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("ALL DONE", flush=True); log.write("ALL DONE\n")
