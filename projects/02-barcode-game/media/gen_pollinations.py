# -*- coding: utf-8 -*-
"""Pollinations.ai 배치 생성 — 바코드 게임 Heaven/Hell 컨셉 에셋."""
import urllib.parse, urllib.request, time, sys, os, json
HEAVEN = ("storybook fantasy illustration, impressionist oil painting with thick impasto brushstrokes, "
          "warm golden hour light, soft pastel palette, Studio Ghibli background art, highly detailed, no text, ")
HELL = ("dark fantasy game concept art, dramatic lighting, rich saturated colors, painterly, highly detailed, "
        "epic, Hades and Pokemon inspired, no text, ")
JOBS = {
 # Heaven — 버스여행
 "heaven/bus_night.jpg":      (HEAVEN+"a giant whimsical THREE-STORY BUS VEHICLE with four big wheels, a truck cab with round headlights at the front, an orange painted bus body, a wooden cottage built on top of the bus as the second floor with colorful curtains and flower boxes, a rooftop garden with laundry line and small chimney as the third floor, parked on a hill at dusk, all windows glowing warm orange, Howl's moving castle style camper bus, side three-quarter view, full vehicle visible", 1080, 1920, 4111),
 "heaven/bus_day_road.jpg":   (HEAVEN+"a giant whimsical THREE-STORY BUS VEHICLE with big wheels driving along a winding road through tuscan golden hills at sunset, orange bus body with a wooden cottage and rooftop garden stacked on top, flags fluttering, wildflowers along the road, full vehicle visible, cinematic", 1080, 1920, 4112),
 "heaven/jami.jpg":           (HEAVEN+"an ALL-WHITE fluffy cavalier king charles spaniel puppy, pure white fur, long soft floppy ears, BOTH EYES CLOSED as if peacefully asleep, gentle happy smile, round chubby chibi proportions, sitting on a wooden bus seat by a window with sea view, centered full body, storybook illustration", 1024, 1024, 4113),
 "heaven/land_cherry.jpg":    (HEAVEN+"a path under an arch of blooming cherry blossom trees, petals falling, stone lanterns, soft pink and warm light, vertical composition", 1080, 1920, 4104),
 "heaven/land_coast.jpg":     (HEAVEN+"dramatic coastal cliff at sunset with a white lighthouse, waves crashing, amber and rose sky, seagulls, vertical composition", 1080, 1920, 4105),
 "heaven/land_aurora.jpg":    (HEAVEN+"a snowy mountain village at night under green and violet aurora, warm light glowing from cottage windows, frozen lake reflecting the sky, vertical composition", 1080, 1920, 4106),
 "heaven/interior_kitchen.jpg":(HEAVEN+"cozy interior cross-section of a bus kitchen room, wooden shelves with jars, steaming pot, warm lamp, animal characters cooking, side view like Fallout Shelter room, wide", 1536, 864, 4107),
 # Hell — 바코드 몬스터
 "hell/mon_fire_chimera.jpg": (HELL+"a fire chimera monster creature, lion body with magma cracks glowing, flaming mane, cute but fierce eyes, centered full body, dark volcanic background", 1024, 1024, 4201),
 "hell/mon_ice_wolf.jpg":     (HELL+"an ice wolf monster creature made of blue crystal shards, frost breath, glowing cyan eyes, centered full body, dark frozen cavern background", 1024, 1024, 4202),
 "hell/mon_poison_serpent.jpg":(HELL+"a poison serpent monster creature with violet toxic scales and glowing green markings, coiled, centered full body, dark ruined temple background", 1024, 1024, 4203),
 "hell/dungeon_lava.jpg":     (HELL+"the first layer of hell, a vast lava dungeon with obsidian bridges, rivers of magma, distant fortress gates, ember particles, vertical composition", 1080, 1920, 4204),
 "hell/barcode_portal.jpg":   (HELL+"a glowing magical barcode floating in darkness, the black bars turning into a portal with crimson and violet energy leaking out, a monster silhouette emerging, vertical composition", 1080, 1920, 4205),
}
only = sys.argv[1:] 
for rel,(prompt,w,h,seed) in JOBS.items():
    if only and not any(o in rel for o in only): continue
    out = os.path.join("assets", rel)
    if os.path.exists(out) and os.path.getsize(out) > 20000: print("skip", rel); continue
    url = "https://image.pollinations.ai/prompt/"+urllib.parse.quote(prompt)+f"?width={w}&height={h}&seed={seed}&nologo=true&model=flux"
    for attempt in range(3):
        try:
            t=time.time(); data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=180).read()
            if len(data) < 20000: raise RuntimeError(f"too small {len(data)}")
            open(out,"wb").write(data); print(f"ok   {rel} {len(data)//1024}KB {time.time()-t:.0f}s", flush=True); break
        except Exception as e:
            print(f"retry {rel} #{attempt+1}: {e}", flush=True); time.sleep(8)
    time.sleep(3)
print("ALL DONE")
