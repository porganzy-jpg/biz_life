# -*- coding: utf-8 -*-
"""2.5D 몬스터 24종 — Pollinations(sana) 대응 레시피: 짧은 마스코트 프리픽스 + 소재 하나 + 얼굴 묘사. 순차 실행 필수.
python gen_all_v2.py [A_ B_ ...]"""
import urllib.parse, urllib.request, time, os, sys, json
from PIL import Image
STYLE = "kawaii mascot character design, 3D render, chibi proportions, isometric three-quarter view, studio lighting, sharp focus, "
JOBS = {
 "A_cute_food/01_gimbap_slime":      ("a triangular onigiri rice ball character with black seaweed band, big sparkling eyes, rosy cheeks, tiny arms", 42),
 "A_cute_food/02_milk_carton_cat":   ("a white milk carton character with cat ears and a cat face, blue stripe, tiny paws", 1202),
 "A_cute_food/03_cup_noodle_dragon": ("a baby dragon character sitting in a red cup noodle bowl, noodle mane, steam, big eyes", 1303),
 "A_cute_food/04_banana_milk_duck":  ("a yellow banana milk bottle character with a duck beak and orange duck feet, big eyes", 1404),
 "A_cute_food/05_choco_pie_bear":    ("a round chocolate pie character with bear ears and a sleepy bear face, marshmallow belly", 1505),
 "A_cute_food/06_jelly_jellyfish":   ("a translucent gummy candy jellyfish character, rainbow gradient, glossy, sweet smile", 1606),
 "B_cool_tech/01_battery_golem":     ("a battery golem robot character, body is a battery cell with glowing cyan charge bars, copper horns, cool eyes", 41001),
 "B_cool_tech/02_earbud_wolf":       ("a sleek white wolf robot character with earbud ears glowing blue, cool expression", 41002),
 "B_cool_tech/03_gamepad_robo_pup":  ("a robot puppy character made from a game controller, joystick ears, colorful buttons, happy", 41003),
 "B_cool_tech/04_drone_hawk":        ("a hawk robot character with drone rotor wings, camera lens eye, hovering, cool", 41004),
 "B_cool_tech/05_smartphone_chameleon": ("a chameleon character with a smartphone screen body glowing in rainbow colors, curled tail, clever eyes", 41005),
 "B_cool_tech/06_outlet_octopus":    ("an octopus character shaped like a power strip, plug tentacles glowing, socket eyes, mischievous grin", 41006),
 "C_household/01_detergent_jellyfish": ("a jellyfish character whose head is a blue detergent bottle, soap bubble tentacles, gentle face", 5101),
 "C_household/02_flowerpot_turtle":  ("a turtle character with a terracotta flower pot shell and a blooming flower on top, kind eyes", 5102),
 "C_household/03_umbrella_bat":      ("a bat character made from a black umbrella, umbrella wings, big cute eyes, slightly spooky", 5103),
 "C_household/04_towel_ghost":       ("a ghost character made of a fluffy folded white towel, two shy eyes, floating", 5104),
 "C_household/05_toothbrush_hedgehog": ("a hedgehog character with colorful toothbrush bristle spines, tiny nose, cheerful", 5105),
 "C_household/06_candle_dokkaebi":   ("a korean goblin character shaped like a lit candle, flame hair, wax cloak, holding a tiny club, warm glow", 5106),
 "D_legendary_country/01_taegeuk_tiger": ("a white tiger cub character with a red and blue yin-yang symbol on its chest, golden aura, jewel eyes", 42),
 "D_legendary_country/02_ninetail_fox":  ("a nine-tailed fox character, ivory fur, tails tipped with blue fire, red ribbon, glowing", 6102),
 "D_legendary_country/03_star_eagle":    ("an eagle character with navy star-pattern wings and red-white striped tail, golden crest, proud", 6103),
 "D_legendary_country/04_gear_bear":     ("a mechanical bear character with brass gears and clockwork joints, black red gold colors, steam", 6104),
 "D_legendary_country/05_macaron_unicorn": ("a unicorn character with a pastel macaron mane in pink mint lavender, golden horn, sparkles", 6105),
 "D_legendary_country/06_panda_dragon":  ("a panda dragon character, panda face and paws with red and gold dragon scales, holding bamboo, jade glow", 6106),
}
only = sys.argv[1:]; log = open("gen_all_v2.log","a",encoding="utf-8")
for rel,(desc,seed) in JOBS.items():
    if only and not any(rel.startswith(o) for o in only): continue
    out = rel+".png"
    url = "https://image.pollinations.ai/prompt/"+urllib.parse.quote(STYLE+desc+", no text")+f"?width=768&height=768&seed={seed}&nologo=true"
    for a in range(10):
        try:
            t=time.time(); data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=240).read()
            if len(data) < 22000: raise RuntimeError(f"small {len(data)}")
            tmp=out+".jpg"; open(tmp,"wb").write(data); im=Image.open(tmp).convert("RGB"); w,h=im.size
            im.crop((0,0,w,int(h*0.955))).save(out); os.remove(tmp)
            msg=f"ok   {rel} {len(data)//1024}KB {time.time()-t:.0f}s"; break
        except Exception as e:
            msg=f"retry {rel} #{a+1}: {str(e)[:50]}"; print(msg, flush=True); log.write(msg+"\n"); log.flush(); time.sleep(6+a*3)
    print(msg, flush=True); log.write(msg+"\n"); log.flush(); time.sleep(3)
json.dump({k:{"prompt":STYLE+v[0]+", no text","seed":v[1]} for k,v in JOBS.items()}, open("prompts_v2.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("ALL DONE", flush=True); log.write("ALL DONE\n")
