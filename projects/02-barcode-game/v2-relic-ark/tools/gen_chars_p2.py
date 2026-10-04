# -*- coding: utf-8 -*-
"""
gen_chars_p2.py — P2(48px 생활형 도트) 확정판 · 전체 등장인물 세트 (스프린트 8-A)

사용자가 P2를 골랐다(DECISIONS 2026-10-01). 이 파일 하나가 8역할 · 6자세 ·
각인 12종 · 문어 · 뒷모습을 전부 찍는다. **생성 AI를 쓰지 않는다.**
모든 픽셀은 이 파일 안의 좌표 지정과 도형 원시함수(rect/ell/ell_in/outline)로만 만든다.

── 규약 (한 줄로 외울 것) ───────────────────────────────────────────────
  원화 1m = 27.5px.  맨머리 1.6m = **44 원화 px**.  아이 1.2m = **33 원화 px**.
  원화 셀 64×64, 발 기준선(발바닥 다음 줄) = 원화 y 60.
    ×4 → 셀 256 · 발 기준선 240 · 미터당 110px   ← 기존 front 규약과 **정확히** 일치
    ×3 → 셀 192 · 발 기준선 180 · 1.6m = 132px   ← 단면 렌더 방 안 실제 크기
  두 배율 모두 정수. S7 보고서가 지적한 「방향 간 키 ±12% 오차」가 여기서 사라진다.

출력: static/art/chars/front/p2/…   (상세는 같은 폴더 meta.json)
실행: python tools/gen_chars_p2.py
"""
import os, io, json, math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import time
_PIL_SAVE = Image.Image.save


def _save_retry(self, fp, *args, **kw):
    """S12: 서버·브라우저가 PNG 를 읽는 순간 윈도우가 쓰기를 거절한다(Errno 22). 잠깐 기다렸다 다시 쓴다."""
    for t in range(10):
        try:
            return _PIL_SAVE(self, fp, *args, **kw)
        except OSError:
            if t == 9:
                raise
            time.sleep(0.4)


Image.Image.save = _save_retry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'static', 'art', 'chars', 'front', 'p2')

# ── 규약 상수 ────────────────────────────────────────────────────────────
CELL = 64          # 원화 셀 (정사각)
BASE_Y = 60        # 원화 발 기준선 (발바닥 픽셀의 마지막 줄 = 59)
FOOT = BASE_Y - 1  # 59
PPM = 27.5         # 원화 미터당 픽셀
SHEET_K = 4        # 시트 배율 → 셀 256 · 기준선 240 · 110px/m
ROOM_K = 3         # 방 합성 배율 → 1.6m = 132px

H_ADULT = 44       # 1.600 m
H_KID = 33         # 1.200 m

CLIPS = [('idle', 2), ('walk', 3), ('work', 3), ('sit', 2), ('carry', 2),
         ('hurt', 2), ('back_walk', 3)]
CLIP_SEC = {'idle': 2.8, 'walk': 0.8, 'work': 1.4, 'sit': 3.2,
            'carry': 1.0, 'hurt': 2.0, 'back_walk': 0.8}
MAXF = 3

# ── S11: 방별 작업 · 엘리베이터 — **행을 뒤에 더하기만** 한다 ───────────────
#   기존 7행(0~6)은 한 픽셀도 바뀌지 않는다(출하물 해시 대조로 증명).
#   열 수(3)도 그대로 — 그래서 작업 동작은 전부 3프레임 이하다.
#   「동작이 방을 말한다」: 왼손이 방의 일을 하고(방 설비는 같은 셀에 함께 찍힌다),
#   오른손의 도구는 그대로 역할을 말한다. 두 손이 다 필요한 일(담요·상자)은 도구를 허리에 건다.
S11_CLIPS = [('work_quarters', 3), ('work_storage', 3), ('work_well', 3),
             ('work_greenhouse', 3), ('work_generator', 3), ('work_infirmary', 3),
             ('work_workshop', 3), ('work_decoder', 3), ('work_pantry', 3),
             ('work_airlock', 3), ('rest_lounge', 2),
             ('elevator_wait', 2), ('elevator_turn', 1), ('elevator_ride', 2)]
S11_IDS = [c for c, _n in S11_CLIPS]
CLIPS = CLIPS + S11_CLIPS
CLIP_SEC.update({'work_quarters': 1.8, 'work_storage': 1.6, 'work_well': 1.5,
                 'work_greenhouse': 2.0, 'work_generator': 1.4, 'work_infirmary': 1.6,
                 'work_workshop': 0.9, 'work_decoder': 2.2, 'work_pantry': 1.5,
                 'work_airlock': 1.2, 'rest_lounge': 3.2,
                 'elevator_wait': 1.6, 'elevator_turn': 0.25, 'elevator_ride': 2.4})
S11_KO = {
    'work_quarters':   ('거주실', '담요를 편다 → 반으로 접는다 → 작게 개어 든다', '두 손 · 도구는 허리에'),
    'work_storage':    ('창고', '바닥의 상자를 든다 → 가슴 높이 → 왼쪽 선반에 밀어 올린다', '두 손 · 도구는 허리에'),
    'work_well':       ('정수실', '배관의 붉은 밸브 바퀴를 돌린다 · 꼭지에서 물방울이 양동이로', '왼손 · 오른손 도구'),
    'work_greenhouse': ('온실', '화분의 시든 잎을 따서 떨군다', '왼손 · 오른손 도구'),
    'work_generator':  ('발전실', '계기함의 레버를 당긴다 → 바늘이 돌고 등이 켜진다', '왼손 · 오른손 도구'),
    'work_infirmary':  ('의무실', '십자 상자에서 흰 붕대를 감아 올린다(감을수록 두루마리가 굵어진다)', '왼손 · 오른손 도구'),
    'work_workshop':   ('공방', '모루 위 달군 쇠를 망치로 친다 · 칠 때 불똥', '왼손 · 오른손 도구'),
    'work_decoder':    ('해독실·서고', '독서대의 큰 책장을 넘긴다 · 촛불', '왼손 · 오른손 도구'),
    'work_pantry':     ('식량창고', '화로 위 냄비를 젓는다 · 김이 오른다', '왼손 · 오른손 도구'),
    'work_airlock':    ('에어락', '세워 둔 예비 공기통의 압력계를 두드린다', '왼손 · 오른손 도구'),
    'rest_lounge':     ('전망 라운지', '등을 돌리고 유리에 손을 대고 바깥을 본다(생산 0인 방 — 쉼)', '뒷모습'),
    'elevator_wait':   ('엘리베이터', '문 앞에서 기다린다 — 머리가 좌우로 1px 흔들린다', '정면'),
    'elevator_turn':   ('엘리베이터', '칸에 들어서며 몸을 돌리는 한 프레임(얼굴 반쪽)', '돌아섬'),
    'elevator_ride':   ('엘리베이터', '칸 안에 두 손을 모으고 정면으로 선다 — 거의 정지', '정면'),
}
# 방 id → 그 방에서 쓰는 행. id 는 server.py ROOM_TEXT_DEFAULT · economy.json 기준
# (플레이트 파일명의 power = generator).
ROOM_WORK = {
    'hall': 'idle', 'quarters': 'work_quarters', 'storage': 'work_storage',
    'well': 'work_well', 'greenhouse': 'work_greenhouse', 'generator': 'work_generator',
    'infirmary': 'work_infirmary', 'airlock': 'work_airlock', 'workshop': 'work_workshop',
    'decoder': 'work_decoder', 'library': 'work_decoder', 'pantry': 'work_pantry',
    'lounge': 'rest_lounge', 'bath': 'sit',
}
BACK_CLIPS = ('back_walk', 'rest_lounge')

# ── S12: 옆모습 — 가로 화면(M5 탑, 한 층 3칸)에서 층을 따라 엘리베이터까지 걷는다 ──
#   역시 **행을 뒤에 더하기만** 한다(0~20행 불변, 해시로 증명). 열 수 3 그대로.
#   오른쪽을 보는 것이 원본이고, 왼쪽은 개발이 좌우 반전한다.
#   보이는 쪽 = 각인 이름의 「오른」 쪽(오른 광대·오른 손목·오른 관자놀이·오른 옷깃·허리 오른 매듭).
#   오른쪽을 보고 걸으면 몸의 오른쪽이 보는 사람을 향하기 때문이다. 「왼」 각인 넷은 먼 쪽이라 끈다.
S12_CLIPS = [('walk_side', 3), ('carry_side', 2)]
S12_IDS = [c for c, _n in S12_CLIPS]
SIDE_IDS = set(S12_IDS)
CLIPS = CLIPS + S12_CLIPS
CLIP_SEC.update({'walk_side': 0.8, 'carry_side': 1.0})
S12_KO = {
    'walk_side':  ('층 복도', '오른쪽으로 걷는다 — 디딤(가까운 발 앞) → 지나감(먼 발 듦) → 디딤(먼 발 앞). 팔은 다리와 반대로 흔든다',
                   '가까운 손에 역할 도구'),
    'carry_side': ('층 복도', '유물 상자를 가슴 앞에 안고 오른쪽으로 걷는다 — 두 걸음. 역할 도구는 상자에 꽂혀 있다',
                   '두 손 · 도구는 상자 위'),
}
# 걸음 폭(원화 px) — 개발이 바닥을 미는 속도. 한 바퀴에 두 걸음.
S12_STRIDE = {'walk_side': {'adult': 16, 'kid': 12}, 'carry_side': {'adult': 12, 'kid': 8}}
SIDE_NEAR = ('warden', 'debt_paid', 'knock_heard', 'saved_breath', 'empty_stomach')
SIDE_CENTER = ('footprint', 'water_memory', 'sun_memory')
SIDE_FAR = ('spore_mark', 'empty_seat', 'crack_seen', 'depth_mark')

# ── S12-B: 일하는 사람은 일하는 쪽을 본다(사용자 지시 2026-10-03, PM 범위 추가) ─────
#   7~16행(방별 작업)을 **제자리에서 다시 그린다**(행 번호 그대로 — 개발의 room_work 가 그대로 먹는다).
#   설비가 셀 왼쪽에 있으므로 몸이 왼쪽을 본다. 반대쪽 설비면 개발이 셀 전체를 좌우 반전한다.
#   옆모습(왼쪽): 모루 망치·냄비 젓기·레버 당기기·독서대 읽기·공기통 두드리기 — 손과 눈이 한 줄에 있는 일
#   3/4(왼쪽):   담요 개기·상자 올리기·붕대 감기·밸브 돌리기·잎 따기 — 몸 앞에서 두 손이 움직이는 일
#   rest_lounge(17)는 뒷모습 그대로, 엘리베이터(18~20)는 문을 보는 게 자연스러워 그대로다.
TURN_PROFILE = ('work_workshop', 'work_pantry', 'work_generator', 'work_decoder', 'work_airlock')
TURN_Q34 = ('work_quarters', 'work_storage', 'work_infirmary', 'work_well', 'work_greenhouse')
S12B_CLIPS = [('work_34', 3), ('carry_34', 2), ('idle_glance', 3)]
S12B_IDS = [c for c, _n in S12B_CLIPS]
CLIPS = CLIPS + S12B_CLIPS
CLIP_SEC.update({'work_34': 1.4, 'carry_34': 1.0, 'idle_glance': 2.4})
S12B_KO = {
    'work_34': ('어디서나', '3/4 왼쪽을 보고 일한다 — 정면 work 와 같은 동작. 정면 work(2행)는 초상·UI 카드용으로 남는다', '오른손 도구'),
    'carry_34': ('어디서나', '3/4 왼쪽을 보고 상자를 든다 — 정면 carry(4행)는 그대로 남는다', '두 손'),
    'idle_glance': ('홀·대기', '정면 → 고개를 3/4 왼쪽으로 돌림 → 눈만 남기고 정면으로 돌아옴. idle 사이에 가끔 한 번', '오른손 도구'),
}
BASE_OF = {'work_34': 'work', 'carry_34': 'carry', 'idle_glance': 'idle'}   # 팔·다리는 이 행을 빌린다
WORK_VIEW = {c: 'profile_left' for c in TURN_PROFILE}
WORK_VIEW.update({c: 'q34_left' for c in TURN_Q34})
WORK_VIEW.update({'rest_lounge': 'back', 'work_34': 'q34_left', 'carry_34': 'q34_left',
                  'idle_glance': 'front > q34_left > front'})
# 옆모습 작업에서 오른쪽 몸 기준으로 그린 뒤 뒤집어 붙이는 각인(얼굴·가슴·허리 — 몸통 쪽)
# ── S15-D: 원정 — 잠수복 겹 · 바깥 동작 (사용자 승인 원정 작업, 2026-10-04) ──────────
#   성경(DECISIONS 2026-09-22 「주민은 헤엄치지 않고 무게추로 해저를 걷는다」 · EXPEDITION §3-6 「땅을 눌러 걷게 한다」)을
#   지킨다: swim_* 는 **헤엄이 아니라 무게추로 해저를 디디며 떠가는 걸음**이다(물속에서 한 걸음마다 잠깐 뜬다).
#   이름은 개발이 기다리는 것 그대로 둔다. 자유 유영이 필요하면 DECISIONS 를 먼저 고친다(요청함).
S15_CLIPS = [('swim_side', 3), ('swim_idle', 2), ('hatch_exit', 3), ('return_tired', 2), ('carry_box_swim', 2)]
S15_IDS = [c for c, _n in S15_CLIPS]
S15_SIDE = ('swim_side', 'hatch_exit', 'carry_box_swim')       # 오른쪽이 원본(좌우 반전으로 왼쪽)
S15_FRONT = ('swim_idle', 'return_tired')
CLIPS = CLIPS + S15_CLIPS
CLIP_SEC.update({'swim_side': 1.4, 'swim_idle': 2.6, 'hatch_exit': 1.5, 'return_tired': 2.6,
                 'carry_box_swim': 1.6})
S15_KO = {
    'swim_side': ('바깥(해저)', '무게추로 바닥을 디디며 오른쪽으로 떠간다 — 디딤 → 뜸(두 발이 바닥에서 3px) → 디딤. 팔은 앞으로 균형', '가까운 손에 역할 도구'),
    'swim_idle': ('바깥(해저)', '바닥에 서서 물살에 흔들린다(헤엄치지 않는다)', '오른손 도구'),
    'hatch_exit': ('문간 → 바깥', '문 아래 사다리를 내려와(높이 8 → 4 → 0) 바닥을 디딘다. 사다리는 셀 오른쪽에 함께 찍혀 있다', '두 손 사다리 · 도구는 허리 앞'),
    'return_tired': ('문간(돌아옴)', '돌아와서 어깨를 늘어뜨리고 반쯤 감은 눈 → 눈을 감고 웃으며 숨을 내쉰다(다친 게 아니라 지친 것)', '오른손 도구'),
    'carry_box_swim': ('바깥(해저)', '봉인 상자(갈래 무늬 + 끈)를 안고 떠가는 걸음 두 칸', '두 손 · 도구는 상자에'),
}
S15_STRIDE = {'swim_side': {'adult': 16, 'kid': 12}, 'carry_box_swim': {'adult': 12, 'kid': 8}}
MIRROR_IMPS = ('warden', 'knock_heard', 'water_memory', 'sun_memory', 'saved_breath', 'footprint',
               'empty_stomach')
PROFILE_HIDE = ('spore_mark', 'depth_mark', 'debt_paid')     # 먼 쪽 목덜미·관자놀이, 허리에 건 도구 쪽 손목
Q34_HIDE = ('depth_mark',)                                   # 돌린 얼굴의 먼 관자놀이

# ── 팔레트 ───────────────────────────────────────────────────────────────
# 흙 계열 따뜻한 색이 바탕. 차가운 색은 유리·물에만(고글 렌즈, 각인 '금을 본 자').
PAL = {
    'line':  (42, 29, 22),      # 외곽선 — 검정이 아니라 따뜻한 숯갈색
    'line2': (26, 18, 14),
    'suitD': (68, 42, 26),      # 잠수복 그늘
    'suitM': (108, 68, 38),     # 잠수복 중간
    'suitL': (144, 95, 52),     # 잠수복 밝은
    'suitH': (186, 134, 76),
    'cream': (232, 210, 168),   # 캔버스 천·끈
    'creamD': (198, 174, 132),
    'oliv':  (104, 100, 58),    # 허리띠
    'olivD': (70, 66, 38),
    'skin':  (240, 207, 174),
    'skinD': (206, 162, 128),
    'blush': (216, 134, 118),
    'ink':   (58, 36, 24),      # 눈·눈썹·입
    'white': (255, 246, 230),
    'hair':  (78, 48, 32),
    'hairD': (54, 33, 22),
    'ox':    (150, 62, 48),     # 적갈 — 수선 자국·십자
    'brassD': (110, 76, 30),
    'brassM': (158, 116, 42),
    'brass': (208, 162, 64),
    'brassH': (242, 216, 144),
    'bootM': (80, 56, 38),      # 무게추 장화 — 검정이면 어두운 방에서 발이 사라진다
    'bootL': (112, 82, 54),
    'tank':  (122, 106, 78),
    'tankL': (160, 142, 106),
    'flame': (255, 212, 130),   # 랜턴 심지 (틴트 제외)
    'flameR': (236, 160, 70),
    'glassD': (48, 96, 104),    # 유리 그늘   ← 차가운 색
    'glass': (126, 190, 194),   # 유리 반사   ← 차가운 색
    # 문어 (짐승은 사람보다 따뜻하다 — C5)
    'octM': (182, 96, 78),
    'octD': (124, 56, 46),
    'octL': (222, 142, 110),
    # 각인 전용
    'impGrn': (142, 188, 96),
    'impPlum': (142, 102, 138),
    'impDark': (38, 28, 24),
    'impCop': (204, 128, 66),
    'impPale': (236, 230, 214),
}

# 역할 겉옷 색 — 70px에서 여덟이 갈리는 첫 번째 축. 전부 흙 계열 안에서 색상(hue)을 벌렸다.
ROLE_COLS = {
    'scout':    ((96, 110, 72),  (60, 72, 44),  (132, 148, 100)),   # 올리브 초록
    'cook':     ((206, 122, 56), (138, 72, 28), (238, 166, 94)),    # 번트오렌지
    'medic':    ((228, 216, 188),(166, 150, 118),(250, 242, 220)),  # 크림 흰
    'engineer': ((88, 82, 72),   (52, 48, 42),  (126, 118, 102)),   # 숯회색
    'farmer':   ((152, 128, 66), (98, 80, 36),  (192, 168, 102)),   # 황토
    'scholar':  ((128, 102, 124),(82, 62, 80),  (164, 138, 158)),   # 탁한 자줏빛
    'trader':   ((160, 88, 66),  (104, 52, 36), (198, 126, 94)),    # 적갈
    'kid':      ((226, 183, 76), (156, 118, 38),(248, 216, 126)),   # 노란 황토
}
for _r, (_m, _d, _l) in ROLE_COLS.items():
    PAL['r_' + _r] = _m
    PAL['rD_' + _r] = _d
    PAL['rL_' + _r] = _l

ROLES = ['scout', 'cook', 'medic', 'engineer', 'farmer', 'scholar', 'trader', 'kid']
ROLE_KO = {'scout': '정찰병', 'cook': '요리사', 'medic': '의무병', 'engineer': '기술자',
           'farmer': '농부', 'scholar': '학자', 'trader': '교섭가', 'kid': '아이'}
ROLE_SIG = {   # ①머리 ②겉옷 ③손
    'scout':    ('뾰족 꼭지가 달린 올리브 후드 + 뒤 꼬리', '올리브 조끼', '짧은 망원경'),
    'cook':     ('키 큰 천 모자', '번트오렌지 앞치마', '국자'),
    'medic':    ('머릿수건 + 뒤 꼬리', '크림 가운 + 적갈 완장', '약 가방'),
    'engineer': ('이마 위로 올린 넓은 용접 고글(물빛 렌즈)', '숯회색 작업복', '렌치'),
    'farmer':   ('넓은 밀짚 챙', '황토 작업복', '물뿌리개'),
    'scholar':  ('각진 납작 모자 + 깨진 안경', '자줏빛 긴 외투', '책'),
    'trader':   ('둥근 챙모자 + 목도리', '적갈 코트', '손저울'),
    'kid':      ('작은 우비 후드', '노란 우비', '작은 등불'),
}

# ── 체형 (RESIDENT_STATS §6 — 스프린트 9-A) ──────────────────────────────
#   §6-1 원칙을 코드로 박아 둔다:
#     · 역할과 체형은 **완전히 독립**이다. 어느 역할에나 어느 체형이든 온다.
#     · 체형을 색으로 표시하지 않는다. 팔레트는 한 벌뿐이고 분홍은 없다.
#     · 잠수복 차림이므로 차이는 어깨 폭과 허리선에서 **1px 단위로만** 난다.
#       키·발 기준선·머리 크기·얼굴 위치는 체형과 무관하게 같다(규약 불변).
BODIES = {
    'a': dict(ko='체형 A', shoulder=0.0, waist=0.0,
              note='어깨가 넓고 허리선이 곧다 (S8에서 만든 것 그대로)'),
    'b': dict(ko='체형 B', shoulder=-1.0, waist=1.2,
              note='어깨가 1px 좁고 허리가 들어간다'),
}
BODY_IDS = ['a', 'b']

# ── 머리 6종 · 얼굴 3종 (본체와 분리된 레이어) ──────────────────────────
#   전부 **같은 정수리 띠**로 시작한다. 그래야 기본(short)으로 구워 낸 시트 위에
#   어느 머리를 얹어도 기본 머리가 완전히 가려진다(§자동 검사에서 증명).
HAIRS = [
    ('short',  '짧은머리',    '정수리 띠만'),
    ('tied',   '묶은머리',    '오른쪽 투구 테 아래 매듭 + 짧은 꽁지'),
    ('long',   '긴머리',      '양쪽 어깨 앞으로 내린 두 갈래'),
    ('braid',  '땋은머리',    '왼쪽 가슴 위로 내린 세 마디 땋음'),
    ('curly',  '곱슬',        '정수리 띠가 울퉁불퉁 + 관자놀이 곱슬 두 점'),
    ('scarf',  '민머리+두건', '정수리 띠 자리를 천이 대신하고 왼쪽에 매듭'),
]
FACES = [
    ('f0', '얼굴 ①', '둥근 눈 · 곧은 눈썹 · 넓은 미소'),
    ('f1', '얼굴 ②', '좁은 눈 · 올라간 눈썹 · 작은 입 · 주근깨'),
    ('f2', '얼굴 ③', '넓게 벌어진 눈 · 안쪽이 내려온 눈썹'),
]
# 머리 레이어 위에 얹히도록 설계된 각인(= 머리와 픽셀이 겹치는 것이 정상)
IMPRINT_ON_HAIR = {'water_memory'}

# 틴트를 받으면 안 되는 색(스스로 빛나거나, 가독성 앵커)
NO_TINT = {'flame', 'flameR', 'white', 'ink', 'line', 'line2', 'glass', 'glassD'}

# ── 실제 렌더 방 (2.5D 판정 기준) ────────────────────────────────────────
#   사람 없는 플레이트가 아직 없어서(배경 담당 요청 중) 기존 렌더에서
#   주민을 피한 칸만 잘라 쓴다. 보고서 §미완에 적는다.
SCENE_SRC = os.path.join(ROOT, 'static', 'art', 'deep', 'section_room_zoom.png')
SCENE_BOX = (1148, 330, 1364, 600)   # 216×270 — 좌우 주민을 피한 깨끗한 칸
SCENE_FLOOR = 248                    # 크롭 기준 바닥선 y (전체 좌표 578)
SCENE_LAMP = (100, 40)
_cache = {}


def scene_crop():
    if 'im' not in _cache:
        _cache['im'] = Image.open(SCENE_SRC).convert('RGB').crop(SCENE_BOX)
    return _cache['im'].copy()


def lamp_tint():
    if 'tint' not in _cache:
        lx, ly = SCENE_LAMP
        box = scene_crop().crop((max(0, lx - 45), ly + 14, lx + 45, ly + 64))
        c = box.resize((1, 1), Image.BOX).getpixel((0, 0))
        m = max(1.0, sum(c) / 3.0)
        _cache['tint'] = tuple(ci / m for ci in c)
    return _cache['tint']


def clamp8(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def harmonize(strength=0.20, contrast=1.26):
    """2.5D 조건 ④ — 팔레트를 배경 렌더에서 뽑아 20% 당기고, 방 평균색 기준으로
    대비를 1.26배 재확장한다(S7에서 찾은 값. 당기기만 하면 벽에 묻혀 형체가 사라진다)."""
    crop = scene_crop()
    q = crop.quantize(colors=16, method=Image.MEDIANCUT)
    raw = q.getpalette()[:48]
    cols = [tuple(raw[i * 3:i * 3 + 3]) for i in range(16)]
    base = crop.resize((1, 1), Image.BOX).getpixel((0, 0))

    def lum(c):
        return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

    for k, c in list(PAL.items()):
        if k in NO_TINT:
            continue
        near = min(cols, key=lambda b: abs(lum(b) - lum(c)))
        mixed = [c[i] * (1 - strength) + near[i] * strength for i in range(3)]
        PAL[k] = tuple(clamp8(base[i] + (mixed[i] - base[i]) * contrast) for i in range(3))


def room_light(spr, strength=1.0, t=None):
    """2.5D 조건 ② — 방의 등불색을 받는다. 이것이 HD-2D의 생명."""
    if t is None:
        t = lamp_tint()
    spr = spr.convert('RGBA')
    w, h = spr.size
    px = spr.load()
    for y in range(h):
        f = 1.0 + strength * (0.13 - 0.32 * (y / max(1, h - 1)))
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            fx = 1.0 + strength * 0.07 * (1 - 2 * x / max(1, w - 1))
            k = f * fx
            px[x, y] = (clamp8(r * k * (1 + 0.30 * strength * (t[0] - 1))),
                        clamp8(g * k * (1 + 0.30 * strength * (t[1] - 1))),
                        clamp8(b * k * (1 + 0.30 * strength * (t[2] - 1))), a)
    return spr


def ground_shadow(base, pos, spr, k=1.0):
    """2.5D 조건 ③ — 발밑 접지 그림자. 없으면 캐릭터가 공중에 뜬다."""
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    ww = int(spr.width * 0.70 * k)
    hh = max(5, int(spr.height * 0.075))
    cx = pos[0] + spr.width // 2
    cy = pos[1] + spr.height - hh // 3
    d.ellipse([cx - ww // 2, cy - hh // 2, cx + ww // 2, cy + hh // 2], fill=(10, 6, 4, 165))
    return Image.alpha_composite(base, sh.filter(ImageFilter.GaussianBlur(max(2, hh // 2))))


# ── 캔버스 ───────────────────────────────────────────────────────────────
class Cv:
    """원화 픽셀 캔버스. 칸 하나에 팔레트 키 문자열이 들어간다."""

    def __init__(self, w=CELL, h=CELL, stencil=None):
        self.w, self.h = w, h
        self.g = [[None] * w for _ in range(h)]
        # stencil = 「아래에 이미 깔린 판」. 레이어(머리·얼굴)가 only=('skin',) 같은
        # 조건을 쓸 때 자기 칸이 비어 있으면 아래 판을 읽는다 → 본체에 직접 그린 것과
        # 같은 픽셀이 나온다(= 레이어로 분리해도 결과가 변하지 않는다).
        self.stencil = stencil

    def set(self, x, y, t):
        if t is None:
            return
        x = int(round(x)); y = int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = t

    def clear(self, x, y):
        x = int(round(x)); y = int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = None

    def get(self, x, y):
        x = int(round(x)); y = int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            v = self.g[y][x]
            if v is None and self.stencil is not None:
                return self.stencil.get(x, y)
            return v
        return None

    def own(self, x, y):
        """스텐실을 보지 않고 자기 칸만."""
        x = int(round(x)); y = int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.g[y][x]
        return None

    def blit(self, other):
        for y in range(self.h):
            row = other.g[y]
            for x in range(self.w):
                if row[x] is not None:
                    self.g[y][x] = row[x]
        return self

    def pixels(self):
        return set((x, y) for y in range(self.h) for x in range(self.w)
                   if self.g[y][x] is not None)

    def rect(self, x0, y0, x1, y1, t):
        for y in range(int(round(y0)), int(round(y1)) + 1):
            for x in range(int(round(x0)), int(round(x1)) + 1):
                self.set(x, y, t)

    def ell(self, cx, cy, rx, ry, t):
        for y in range(int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1):
            for x in range(int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1):
                dx = (x - cx) / max(rx, .001); dy = (y - cy) / max(ry, .001)
                if dx * dx + dy * dy <= 1.0:
                    self.set(x, y, t)

    def ell_in(self, cx, cy, rx, ry, t, only=None):
        for y in range(int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1):
            for x in range(int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1):
                dx = (x - cx) / max(rx, .001); dy = (y - cy) / max(ry, .001)
                if dx * dx + dy * dy <= 1.0:
                    cur = self.get(x, y)
                    if cur is None:
                        continue
                    if only is not None and cur not in only:
                        continue
                    self.set(x, y, t)

    def outline(self, t='line'):
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.g[y][x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h and self.g[ny][nx] is not None:
                        add.append((x, y)); break
        for x, y in add:
            self.g[y][x] = t

    def bbox(self):
        xs = [x for y in range(self.h) for x in range(self.w) if self.g[y][x] is not None]
        ys = [y for y in range(self.h) for x in range(self.w) if self.g[y][x] is not None]
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def img(self):
        im = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        px = im.load()
        for y in range(self.h):
            for x in range(self.w):
                t = self.g[y][x]
                if t is not None:
                    px[x, y] = PAL[t] + (255,)
        return im

    def mask(self):
        """틴트 마스크 — 흰색일수록 방 등불색을 많이 받는다. 0 = 절대 틴트 금지."""
        im = Image.new('L', (self.w, self.h), 0)
        px = im.load()
        for y in range(self.h):
            for x in range(self.w):
                t = self.g[y][x]
                if t is None:
                    continue
                px[x, y] = 40 if t in ('line', 'line2') else (0 if t in NO_TINT else 255)
        return im


# ── 공통 부품 ────────────────────────────────────────────────────────────
def eye(c, x, y, w=3, h=3):
    c.rect(x, y, x + w - 1, y + h - 1, 'ink')
    c.set(x, y + h - 1, 'skin'); c.set(x + w - 1, y + h - 1, 'skin')
    c.set(x, y, 'white')


_eye_base = eye


def brow(c, x, y, w, side):
    for i in range(w):
        dy = 1 if ((side == 'l' and i == 0) or (side == 'r' and i == w - 1)) else 0
        c.set(x + i, y + dy, 'ink')


def smile(c, cx, y, w=2, sad=False):
    for i in range(-w, w + 1):
        dy = (1 if sad else -1) if abs(i) == w else 0
        c.set(cx + i, y + dy, 'ink')


def blush(c, x0, x1, y):
    for x in range(x0, x1 + 1):
        if c.get(x, y) in ('skin', 'skinD'):
            c.set(x, y, 'blush')


def wave(c, x0, x1, y, t, step=2):
    for x in range(int(round(x0)), int(round(x1)) + 1, step):
        c.set(x, y, t)


def mitten(c, cx, cy, t='cream'):
    c.ell(cx, cy, 2.4, 2.2, t)


def boot(c, x0, x1, y0, y1):
    c.rect(x0, y0, x1, y1 - 1, 'bootM')
    c.rect(x0, y0, x0 + 1, y1 - 1, 'bootL')
    c.rect(x0, y1, x1, y1, 'brassM')      # 무게추 밑창
    c.set(x0, y1, 'brass'); c.set(x1, y1 - 1, 'brassD')


def lantern(c, cx, cy):
    c.ell(cx, cy, 1.9, 2.4, 'flameR')
    c.rect(cx - 1, cy - 1, cx + 1, cy + 1, 'flame')
    c.set(cx, cy - 3, 'brassD')


def tank(c, cx, cy, ry=7.0):
    c.ell(cx, cy, 2.7, ry, 'tank')
    c.ell(cx - 1, cy, 1.1, ry - .5, 'tankL')
    c.ell(cx, cy - ry, 2.7, 1.6, 'tankL')
    c.rect(cx - 1, cy - ry - 3, cx + 1, cy - ry, 'brassD')


# ── 머리에 쓴 것 (①) ────────────────────────────────────────────────────
def headwear(c, role, hx, hy, hr, back=False, layer='over'):
    """머리에 쓴 것 (①) — 70px 판독의 첫 번째 축.
    layer='under' 는 얼굴 구멍보다 먼저(두개골을 감싸는 천),
    layer='over'  는 얼굴보다 나중에(챙·밴드·꼬리) 그린다."""
    top = hy - hr
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    if role == 'scout':
        # roles.json 의 hood:true 를 그대로 — 끐꼉한 꼬리가 달린 올리브 후드
        if layer == 'under':
            c.ell(hx, hy - .8, hr + .7, hr + .3, rM)
            c.ell_in(hx - 1.6, hy - 2.4, hr - .4, hr - 1.2, rL, only=(rM,))
            c.rect(hx - 2, hy - hr - 3, hx + 1, hy - hr - 2, rD)        # 꼬지
            c.set(hx - 1, hy - hr - 4, rM)
            c.rect(hx + hr - 2, top + 6, hx + hr + 3, top + 10, rD)     # 뒤로 넘긴 꼬리
            c.rect(hx + hr + 1, top + 9, hx + hr + 3, top + 14, rM)
        elif not back:
            c.rect(hx - hr + 2, top + 3, hx + hr - 2, top + 3, rD)      # 후드 알단
    elif role == 'cook':
        if layer == 'under':
            c.ell(hx, top - 2.2, hr - 1.4, 4.4, rL)                     # 키 큰 천 모자
            c.ell_in(hx + 2, top - 1.4, hr - 2.4, 3.4, rM, only=(rL,))
            c.rect(hx - hr + 1, top, hx + hr - 1, top + 2, rM)
            c.rect(hx - hr + 1, top + 2, hx + hr - 1, top + 2, rD)
            wave(c, hx - hr + 2, hx + hr - 2, top + 1, rL)
    elif role == 'medic':
        if layer == 'under':
            c.ell(hx, hy - 1.0, hr + .5, hr - .2, rL)                   # 머릿수건
            c.ell_in(hx + 2, hy + .5, hr - .5, hr - 1.5, rM, only=(rL,))
            c.rect(hx + hr - 2, top + 5, hx + hr + 2, top + 11, rL)     # 뒤 꼬리
            c.rect(hx + hr, top + 9, hx + hr + 2, top + 12, rM)
        elif not back:
            c.rect(hx - 1, top + 1, hx + 1, top + 1, 'ox')              # 이마 십자
            c.set(hx, top, 'ox'); c.set(hx, top + 2, 'ox')
    elif role == 'engineer':
        if layer == 'over':
            c.rect(hx - hr - 1, top - 2, hx + hr + 1, top + 2, rD)      # 이마 위로 올린 용접 고글
            c.rect(hx - hr - 1, top - 2, hx + hr + 1, top - 2, 'tankL')
            c.rect(hx - hr - 1, top - 1, hx - hr, top + 2, 'tankL')
            if not back:
                c.ell(hx - 3.6, top - .2, 2.4, 1.8, 'glassD')
                c.ell(hx + 3.6, top - .2, 2.4, 1.8, 'glassD')
                c.set(hx - 4, top - 1, 'glass'); c.set(hx + 3, top - 1, 'glass')
                c.rect(hx - 1, top - 1, hx + 1, top - 1, 'brassM')
            c.rect(hx + hr - 1, top + 2, hx + hr + 2, top + 5, 'tankL')  # 어깨 공구띄 끔
    elif role == 'farmer':
        if layer == 'over':
            c.rect(hx - hr - 5, top + 2, hx + hr + 5, top + 3, rM)      # 넓은 밀짚 챙
            c.rect(hx - hr - 5, top + 3, hx + hr + 5, top + 3, rD)
            wave(c, hx - hr - 4, hx + hr + 4, top + 2, rL)
        else:
            c.ell(hx, top + 1.0, hr - 1.5, 2.6, rL)                     # 낮은 밀짚 머리통
            c.ell_in(hx + 2, top + 1.5, hr - 2.5, 2.0, rM, only=(rL,))
    elif role == 'scholar':
        if layer == 'under':
            c.rect(hx - hr + 1, top - 2, hx + hr - 1, top + 2, rM)      # 각진 납작 모자
            c.rect(hx - hr + 1, top - 2, hx + hr - 1, top - 2, rL)
            c.rect(hx - hr + 1, top + 2, hx + hr - 1, top + 2, rD)
            c.rect(hx + hr - 1, top - 1, hx + hr + 1, top + 3, 'brass')  # 술
    elif role == 'trader':
        if layer == 'under':
            c.ell(hx, top + .2, hr - 2, 3.2, rM)                        # 둥근 챙모자 머리통
            c.ell(hx - 1, top - 1.4, hr - 3.5, 1.6, rL)
        else:
            # S8 보고서가 지적한 「의무병과 교섭가의 실루엣이 가장 비슷하다」의 해결 —
            # 챙 한쪽을 접어 올린다. 의무병의 뒤 꼬리는 **오른쪽**, 이 지느러미는 **왼쪽**이라
            # 70px 검은 실루엣에서 뻗는 방향이 반대가 된다.
            c.rect(hx - hr - 1, top + 3, hx + hr + 4, top + 4, rD)      # 오른쪽으로 더 긴 챙
            c.rect(hx - hr - 1, top + 3, hx + hr + 4, top + 3, rM)
            c.rect(hx - hr - 3, top - 3, hx - hr - 2, top + 4, rD)      # 접어 올린 왼쪽 챙
            c.rect(hx - hr - 3, top - 3, hx - hr - 3, top + 3, rM)
            c.set(hx - hr - 2, top - 4, rL)
    elif role == 'kid':
        if layer == 'under':
            c.ell(hx, hy - .6, hr + .8, hr + .4, rM)                    # 작은 우비 후드
            c.ell_in(hx - 1.5, hy - 2.2, hr - .5, hr - 1.2, rL, only=(rM,))
            c.set(hx, hy - hr - 2, rD); c.set(hx, hy - hr - 1, rM)      # 꼭지
            c.rect(hx - hr, hy + hr - 2, hx + hr, hy + hr, rD)          # 후드 아랫단


def hand_prop(c, role, x, y, flip=False):
    """손에 든 것 (③). x,y = 오른손 장갑 중심."""
    s = -1 if flip else 1
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    if role == 'scout':                      # 짧은 망원경
        c.rect(x + s * 2, y - 4, x + s * 3, y + 1, 'brassM')
        c.rect(x + s * 2, y - 5, x + s * 3, y - 5, 'brass')
        c.set(x + s * 2, y - 4, 'brassH')
    elif role == 'cook':                     # 국자
        c.rect(x + s * 2, y - 6, x + s * 2, y, 'brassM')
        c.ell(x + s * 2, y + 1.5, 2.2, 1.8, 'brass')
        c.set(x + s * 2, y + 1, 'brassH')
    elif role == 'medic':                    # 약 가방
        c.rect(x + s * 1, y + 1, x + s * 5, y + 5, 'cream')
        c.rect(x + s * 1, y + 1, x + s * 5, y + 1, 'creamD')
        c.rect(x + s * 3, y + 2, x + s * 3, y + 4, 'ox')
        c.rect(x + s * 2, y + 3, x + s * 4, y + 3, 'ox')
    elif role == 'engineer':                 # 렌치
        c.rect(x + s * 2, y - 5, x + s * 3, y + 1, 'tankL')
        c.rect(x + s * 1, y - 7, x + s * 4, y - 6, 'tankL')
        c.set(x + s * 2, y - 7, None); c.set(x + s * 3, y - 7, None)
        c.set(x + s * 1, y - 7, 'tankL'); c.set(x + s * 4, y - 7, 'tankL')
    elif role == 'farmer':                   # 물뿌리개
        c.rect(x + s * 1, y - 2, x + s * 5, y + 3, rM)
        c.rect(x + s * 1, y - 2, x + s * 5, y - 2, rL)
        c.rect(x + s * 5, y - 4, x + s * 7, y - 1, rD)
        c.set(x + s * 7, y - 4, rD)
    elif role == 'scholar':                  # 책
        c.rect(x + s * 1, y - 4, x + s * 5, y + 2, rD)
        c.rect(x + s * 2, y - 3, x + s * 5, y + 1, 'cream')
        c.rect(x + s * 3, y - 3, x + s * 3, y + 1, 'creamD')
    elif role == 'trader':                   # 손저울
        c.rect(x + s * 3, y - 6, x + s * 3, y, 'brassM')
        c.rect(x + s * 1, y - 6, x + s * 5, y - 6, 'brassM')
        c.rect(x + s * 1, y - 4, x + s * 2, y - 4, 'brass')
        c.rect(x + s * 4, y - 3, x + s * 5, y - 3, 'brass')
        c.set(x + s * 1, y - 5, 'brassD'); c.set(x + s * 5, y - 5, 'brassD')
    elif role == 'kid':                      # 작은 등불
        c.rect(x + s * 2, y - 1, x + s * 4, y + 2, 'flameR')
        c.rect(x + s * 3, y, x + s * 3, y + 1, 'flame')
        c.set(x + s * 3, y - 2, 'brassD')


# ── 몸 ───────────────────────────────────────────────────────────────────
def legs_walk(f):
    """3프레임 걷기: f0 디딤 / f1 왼발 앞 / f2 오른발 앞."""
    return [(0, 0), (-1, 1), (1, -1)][f]


POSE = {
    #            머리 내림  몸통 반지름  목→몸통중심  다리     다리를 몸통 앞에
    'idle':      dict(drop=0,  tr=7.2, tdy=9, legs='stand', front=False),
    'walk':      dict(drop=0,  tr=7.2, tdy=9, legs='walk',  front=False),
    'work':      dict(drop=1,  tr=7.2, tdy=9, legs='stand', front=False),
    'sit':       dict(drop=10, tr=5.9, tdy=7, legs='sit',   front=True),
    'carry':     dict(drop=0,  tr=7.2, tdy=9, legs='stand', front=False),
    'hurt':      dict(drop=12, tr=5.9, tdy=7, legs='kneel', front=True),
    'back_walk': dict(drop=0,  tr=7.2, tdy=9, legs='walk',  front=False),
}
for _c in S11_IDS:      # S11 — 전부 선 자세. 몸통·다리 규약은 idle 과 같다
    POSE[_c] = dict(drop=0, tr=7.2, tdy=9, legs='stand', front=False)
for _c in S12_IDS:      # S12 — 옆모습. 세로 좌표 규약(머리·목·몸통·허리)은 walk 와 같다
    POSE[_c] = dict(drop=0, tr=7.2, tdy=9, legs='side', front=False)
for _c in S12B_IDS:
    POSE[_c] = dict(POSE[BASE_OF[_c]])
for _c in S15_SIDE:
    POSE[_c] = dict(drop=0, tr=7.2, tdy=9, legs='side', front=False)
for _c in S15_FRONT:
    POSE[_c] = dict(POSE['idle'])
BASE_OF.update({'swim_idle': 'idle', 'return_tired': 'idle'})
S11_BOB = {'work_quarters': [0, -1, 0], 'work_storage': [1, 0, -1], 'work_well': [0, 1, 0],
           'work_greenhouse': [1, 1, 1], 'work_generator': [0, 0, 1], 'work_infirmary': [1, 1, 0],
           'work_workshop': [-1, 0, 1], 'work_decoder': [1, 1, 1], 'work_pantry': [0, 1, 0],
           'work_airlock': [0, 1, 0], 'rest_lounge': [0, 1],
           'elevator_wait': [0, 0], 'elevator_turn': [0], 'elevator_ride': [0, 1]}
S11_LEAN = {'work_quarters': [0, 0, 0], 'work_storage': [0, -1, -1], 'work_well': [-1, -1, 0],
            'work_greenhouse': [-1, -1, -1], 'work_generator': [-1, 0, 0],
            'work_infirmary': [-1, -1, 0], 'work_workshop': [-1, -1, -1],
            'work_decoder': [-1, -1, -1], 'work_pantry': [-1, -1, -1], 'work_airlock': [-1, -1, -1],
            'rest_lounge': [0, 0], 'elevator_wait': [-1, 0], 'elevator_turn': [0],
            'elevator_ride': [0, 0]}


def draw_legs(c, mode, cx, leg_y0, kid, f):
    """다리. sit/kneel 은 몸통보다 나중에 그려 앞으로 나온다."""
    if mode == 'sit':
        # 한쪽으로 모아 앉기 — 바닥에 닿는 면이 넓어 '쉰다'가 멀리서도 읽힌다
        c.rect(cx - 6, FOOT - 9, cx + 5, FOOT - 2, 'suitD')          # 엉덩이
        c.rect(cx - 12, FOOT - 7, cx + 3, FOOT - 2, 'suitM')         # 허벅지(가로)
        c.rect(cx - 12, FOOT - 7, cx + 3, FOOT - 7, 'suitL')
        c.rect(cx - 12, FOOT - 2, cx + 3, FOOT - 2, 'suitD')
        c.ell(cx - 11, FOOT - 5, 3.4, 3.0, 'suitL')                  # 무릎
        c.rect(cx - 14, FOOT - 4, cx - 9, FOOT - 1, 'suitM')         # 정강이
        boot(c, cx - 15, cx - 9, FOOT - 3, FOOT)
        c.rect(cx + 1, FOOT - 4, cx + 7, FOOT - 1, 'suitD')
        boot(c, cx + 3, cx + 9, FOOT - 3, FOOT)
        return
    if mode == 'kneel':
        # 한 무릎을 꿇고 주저앉음
        c.rect(cx - 9, FOOT - 4, cx - 1, FOOT - 1, 'suitM')   # 바닥에 닿은 무릎
        c.rect(cx - 9, FOOT - 4, cx - 1, FOOT - 4, 'suitL')
        c.rect(cx - 9, FOOT - 1, cx - 1, FOOT, 'suitD')
        c.rect(cx + 1, FOOT - 10, cx + 6, FOOT - 3, 'suitD')  # 세운 무릎
        c.rect(cx + 1, FOOT - 10, cx + 2, FOOT - 3, 'suitM')
        boot(c, cx, cx + 7, FOOT - 3, FOOT)
        return
    dxL, dxR = (legs_walk(f) if mode == 'walk' else (0, 0))
    lw = 5 if not kid else 4
    for sx, dxf in ((cx - 6 if not kid else cx - 5, dxL),
                    (cx + 2 if not kid else cx + 1, dxR)):
        c.rect(sx, leg_y0, sx + lw - 1, FOOT - 5, 'suitD')
        c.rect(sx, leg_y0, sx + 1, FOOT - 5, 'suitM')
        boot(c, sx + dxf - 1, sx + lw + dxf - 1, FOOT - 4, FOOT)


# ── S11: 방별 작업 · 엘리베이터 ─────────────────────────────────────────
def seg(c, p0, p1, t, w=3):
    """굵기 w 의 곧은 획(정사각 붓)."""
    x0, y0 = p0
    x1, y1 = p1
    n = int(math.ceil(max(abs(x1 - x0), abs(y1 - y0)))) or 1
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        y = y0 + (y1 - y0) * k / n
        xi = int(round(x - (w - 1) / 2.0))
        yi = int(round(y - (w - 1) / 2.0))
        c.rect(xi, yi, xi + w - 1, yi + w - 1, t)


def ring(c, cx, cy, r, w, t):
    for y in range(int(math.floor(cy - r)), int(math.ceil(cy + r)) + 1):
        for x in range(int(math.floor(cx - r)), int(math.ceil(cx + r)) + 1):
            d = math.hypot(x - cx, y - cy)
            if r - w <= d <= r:
                c.set(x, y, t)


def elbow_of(sh, hand, a, b, out):
    """두 마디 팔의 팔꿈치. 닿지 않으면 곧게 편다. 팔꿈치는 아래·바깥으로 꺾인다."""
    dx, dy = hand[0] - sh[0], hand[1] - sh[1]
    d = math.hypot(dx, dy)
    if d >= a + b - 0.2 or d < 0.5:
        return ((sh[0] + hand[0]) / 2.0, (sh[1] + hand[1]) / 2.0)
    x = (d * d + a * a - b * b) / (2 * d)
    h = math.sqrt(max(0.0, a * a - x * x))
    ux, uy = dx / d, dy / d
    px_, py_ = sh[0] + ux * x, sh[1] + uy * x
    e1 = (px_ - uy * h, py_ + ux * h)
    e2 = (px_ + uy * h, py_ - ux * h)
    sc = lambda e: e[1] + 0.3 * out * e[0]
    return e1 if sc(e1) >= sc(e2) else e2


def arm_to(c, sh, hand, R, side):
    t = 'suitM' if side == 'l' else 'suitD'
    a = b = R * 0.56 + 0.3
    e = elbow_of(sh, hand, a, b, -1 if side == 'l' else 1)
    seg(c, sh, e, t, 3)
    seg(c, e, hand, t, 3)
    if side == 'l':
        seg(c, (sh[0] - 1, sh[1]), (e[0] - 1, e[1]), 'suitL', 1)
    return e


def quilt(c, x0, y0, x1, y1, folded=False):
    """거주실 담요 — 적갈·크림 체크. 흙색 팔레트 안에서 가장 '이불'로 읽히는 무늬."""
    x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if folded:
                t = 'ox' if ((y - y0) % 3 == 1) else 'cream'
            else:
                t = 'ox' if (((x - x0) // 2 + (y - y0) // 2) % 2) else 'creamD'
            c.set(x, y, t)
    c.rect(x0, y0, x1, y0, 'cream')
    if not folded:
        c.rect(x0, y0, x0, y1, 'cream'); c.rect(x1, y0, x1, y1, 'cream')
        c.rect(x0, y1, x1, y1, 'cream')
    else:
        c.rect(x0, y1, x1, y1, 'creamD')


def s11_pose(c, ov, clip, f, g, objc, mitc, anc, hide):
    """S11 행의 팔·방 설비·손에 든 물건. 왼손이 방의 일을 하고 오른손 도구가 역할을 말한다.
    설비(fx)는 몸 옆·뒤 → 본판(c), 몸 앞에 든 물건(hh)은 머리카락보다 위 → ov.
    돌려주는 것: (왼손, 오른손) 장갑 중심."""
    kid, role = g['kid'], g['role']
    cx, neck_y, torso_cy, belt_y = g['cx'], g['neck_y'], g['torso_cy'], g['belt_y']
    ax_l, ax_r, arm_y0, arm_y1, tk = g['ax_l'], g['ax_r'], g['arm_y0'], g['arm_y1'], g['tk']
    SL = (ax_l + 1.5, arm_y0 + 2.0)
    SR = (ax_r + 1.5, arm_y0 + 2.0)
    R = float(arm_y1 - arm_y0)           # 어른 13 · 아이 8 — 팔 길이
    s = R / 13.0
    z = 0.75 if kid else 1.0             # 설비 크기
    F = FOOT
    fx, hh = Cv(), Cv()

    def P(dx, dy):
        return (SL[0] + dx * s, SL[1] + dy * s)

    def ir(v):
        return int(round(v))

    lhand = rhand = None
    hip = False             # 두 손을 쓰는 일 — 도구는 허리에 건다
    prop_front = False      # 도구를 몸 앞에서 두 손으로 든다(엘리베이터 안)
    no_prop = False

    if clip == 'work_well':
        W = P(-14, 6)
        rw = 4.5 * z
        px0 = ir(W[0])
        top = ir(W[1] - rw - 5 * z)
        fx.rect(px0 - 1, top, px0 + 1, F, 'tank'); fx.rect(px0 - 1, top, px0 - 1, F, 'tankL')
        pe = max(1, px0 - ir(6 * z))
        fx.rect(pe, top - 1, px0 + 1, top + 1, 'tank'); fx.rect(pe, top - 1, px0, top - 1, 'tankL')
        fx.rect(pe - 1, top - 2, pe, top + 2, 'brassD')              # 벽으로 들어가는 이음쇠
        fx.rect(px0 - 2, F - 1, px0 + 2, F, 'brassD')
        ys = ir(F - 9 * z)
        fx.rect(px0 - 4, ys, px0 - 2, ys + 1, 'tankL'); fx.set(px0 - 4, ys + 2, 'tankL')
        bx0, bx1 = px0 - 8, px0 - 2
        fx.rect(bx0, F - 4, bx1, F, 'suitM'); fx.rect(bx0, F - 4, bx1, F - 4, 'suitL')
        fx.rect(bx0 + 1, F - 3, bx1 - 1, F - 3, 'glass'); fx.rect(bx0, F - 1, bx1, F - 1, 'brassD')
        dxp = px0 - 4
        if f == 0:
            fx.set(dxp, ys + 3, 'glass')
        elif f == 1:
            fx.set(dxp, ys + 4, 'glass'); fx.set(dxp, ys + 5, 'glassD')
        else:
            fx.set(dxp - 1, F - 5, 'white'); fx.set(dxp + 1, F - 5, 'white'); fx.set(dxp, F - 6, 'glass')
        ring(fx, W[0], W[1], rw, 1.7, 'ox')
        for k in range(3):
            ang = math.radians(f * 40 + k * 120)
            seg(fx, W, (W[0] + (rw - 1) * math.cos(ang), W[1] + (rw - 1) * math.sin(ang)), 'brassM', 1)
        fx.set(W[0], W[1], 'brass')
        a = math.radians([-60, -15, 30][f])
        lhand = (W[0] + rw * math.cos(a), W[1] + rw * math.sin(a))

    elif clip == 'work_generator':
        x0 = max(1, ir(P(-19, 0)[0])); x1 = ir(P(-7, 0)[0]); top = ir(F - 13 * z)
        fx.rect(x0, top, x1, F, 'tank'); fx.rect(x0, top, x1, top, 'tankL'); fx.rect(x0, top, x0, F, 'tankL')
        fx.rect(x0, F - 1, x1, F, 'suitD')
        fx.set(x0 + 1, F - 3, 'brassM'); fx.set(x1 - 1, F - 3, 'brassM')
        gc = (x0 + 3.5 * z + .5, top + 4.5 * z)
        fx.ell(gc[0], gc[1], 2.3 * z, 2.3 * z, 'cream')
        na = math.radians([-150, -90, -30][f])
        seg(fx, gc, (gc[0] + 2.2 * z * math.cos(na), gc[1] + 2.2 * z * math.sin(na)), 'ox', 1)
        lx, ly = x1 - 2, ir(top + 3 + 5 * z)
        if f == 2:                                             # 전기가 들어왔다
            fx.rect(lx - 1, ly, lx, ly + 1, 'flame'); fx.set(lx, ly, 'white')
        else:
            fx.rect(lx - 1, ly, lx, ly + 1, 'olivD')
        piv = (x1 - 2 * z, top)
        fx.rect(ir(piv[0]) - 1, top - 1, ir(piv[0]) + 1, top, 'brassD')
        la = math.radians([-125, -95, -65][f])
        end = (piv[0] + 10 * z * math.cos(la), piv[1] + 10 * z * math.sin(la))
        seg(fx, piv, end, 'brassM', 1)
        fx.ell(end[0], end[1], 1.4, 1.4, 'ox')
        lhand = end

    elif clip == 'work_workshop':
        yt = belt_y + 1
        a0 = max(3, ir(P(-17, 0)[0])); a1 = ir(P(-6, 0)[0])
        fx.rect(a0, yt, a1, yt + 1, 'tankL'); fx.rect(a0, yt + 1, a1, yt + 1, 'tank')
        fx.rect(a0 - 2, yt, a0 - 1, yt, 'tankL'); fx.set(a0 - 3, yt, 'tank')
        mid = (a0 + a1) // 2
        fx.rect(mid - 2, yt + 2, mid + 2, yt + 3, 'tank'); fx.rect(mid - 3, yt + 4, mid + 3, yt + 4, 'tank')
        fx.rect(mid - 4, yt + 5, mid + 4, F, 'suitM'); fx.rect(mid - 4, yt + 5, mid - 3, F, 'suitL')
        fx.rect(mid - 4, F, mid + 4, F, 'suitD'); fx.rect(mid - 3, yt + 8, mid + 3, yt + 8, 'suitD')
        hp = mid + 1
        fx.rect(hp - 2, yt - 1, hp + 2, yt - 1, 'flameR'); fx.set(hp, yt - 1, 'flame')
        if f == 0:
            lhand, d = ((P(-12, -6), (-0.3, -0.95)) if g.get('profile') else (P(-5, -11), (-0.45, -0.9)))   # 옆모습: 얼굴 앞을 피해 앞으로 든다
        elif f == 1:
            lhand, d = P(-9, -2), (-1.0, 0.15)
        else:
            lhand = (hp + 3, yt - 4)
            d = (hp - lhand[0], yt - 2 - lhand[1])
        n = math.hypot(*d); d = (d[0] / n, d[1] / n)
        L = 4.5 * z
        seg(hh, lhand, (lhand[0] + d[0] * L, lhand[1] + d[1] * L), 'suitL', 1)
        hc = (lhand[0] + d[0] * (L + 1), lhand[1] + d[1] * (L + 1))
        pp = (-d[1], d[0])
        for tt in (-2, -1, 0, 1, 2):
            for kk in (0, 1):
                hh.set(hc[0] + pp[0] * tt + d[0] * kk, hc[1] + pp[1] * tt + d[1] * kk,
                       'tankL' if kk == 0 else 'tank')
        if f == 2:                                             # 칠 때 불똥
            for ox_, oy_, t in ((-3, -2, 'flame'), (3, -3, 'flame'), (-4, 0, 'brassH'),
                                (4, -1, 'brassH'), (-1, -4, 'flame'), (2, -5, 'white')):
                hh.set(hp + ox_, yt - 2 + oy_, t)

    elif clip == 'work_storage':
        hip = True
        shy = ir(SL[1] - 8 * s); sx1 = ir(P(-5, 0)[0])
        sx0 = max(1, sx1 - ir(16 * z))
        fx.rect(sx0, shy, sx1, shy, 'suitL'); fx.rect(sx0, shy + 1, sx1, shy + 1, 'suitM')
        fx.rect(sx1 - 2, shy + 2, sx1 - 1, shy + 4, 'suitD'); fx.rect(sx0 + 1, shy + 2, sx0 + 2, shy + 4, 'suitD')
        fx.rect(sx0 + 1, shy - 3, sx0 + 3, shy - 1, 'brassM'); fx.set(sx0 + 1, shy - 3, 'brassH')   # 선반의 단지
        bw, bh = ir(10 * z), ir(7 * z)
        if f == 0:
            bx0, by0 = cx - 2 - bw // 2, belt_y + 2
        elif f == 1:
            bc = P(-4, 0)
            bx0, by0 = ir(bc[0] - bw / 2.0), ir(bc[1] - bh / 2.0)
        else:
            bx0, by0 = sx1 - 1 - bw, shy - bh
        bx1, by1 = bx0 + bw, by0 + bh - 1
        tgt = fx if f == 2 else hh                              # 선반 위에 놓이면 설비가 된다
        tgt.rect(bx0, by0, bx1, by1, 'suitL'); tgt.rect(bx0, by0, bx1, by0, 'suitH')
        tgt.rect(bx0, by0, bx0, by1, 'suitH'); tgt.rect(bx0, by1, bx1, by1, 'suitD')
        wave(tgt, bx0 + 1, bx1 - 1, by0 + 2, 'cream')
        if f == 2:
            lhand = (bx1 + 1, by0 + bh // 2)
        else:
            lhand = (bx0, by0 + bh // 2 + 1)
            rhand = (bx1, by0 + bh // 2 + 1)

    elif clip == 'work_quarters':
        hip = True
        ky = [5, 4, 3][f] if kid else 0                      # 아이는 어깨 = 머리 갈래 자리라 손을 내린다
        if f == 0:
            sp = 11 if kid else 13 * s
            lhand = (cx - sp, torso_cy - 4 + ky); rhand = (cx + sp, torso_cy - 4 + ky)
            quilt(hh, lhand[0], lhand[1] - 1, rhand[0], F - 6 * z)
        elif f == 1:
            lhand = (cx - 9 * s, torso_cy - 2 + ky); rhand = (cx + 9 * s, torso_cy - 2 + ky)
            yb = (torso_cy - 3 + F - 6 * z) / 2.0 + 1
            quilt(hh, lhand[0], lhand[1] - 1, rhand[0], yb)
            hh.rect(ir(lhand[0]), ir(lhand[1]) - 1, ir(rhand[0]), ir(lhand[1]) - 1, 'creamD')
        else:
            lhand = (cx - 6 * s, torso_cy + 1 + ky); rhand = (cx + 6 * s, torso_cy + 1 + ky)
            quilt(hh, lhand[0], lhand[1] - 1, rhand[0], lhand[1] + 4 * z, folded=True)

    elif clip == 'work_infirmary':
        bx0 = max(1, ir(P(-17, 0)[0])); bx1 = ir(P(-7, 0)[0]); by0 = ir(F - 6 * z)
        fx.rect(bx0, by0, bx1, F, 'cream'); fx.rect(bx1, by0, bx1, F, 'creamD')
        fx.rect(bx0, F, bx1, F, 'creamD')
        mx, my = (bx0 + bx1) // 2, (by0 + F) // 2 + 1
        fx.rect(mx - 2, my, mx + 2, my, 'ox'); fx.rect(mx, my - 2, mx, my + 2, 'ox')
        lhand = [P(-6, 2), P(-8, -1), P(-5, -3)][f]
        r = [2.2, 2.6, 3.0][f] * z                             # 감을수록 굵어지는 두루마리
        rc = (lhand[0] - 2.2 * z, lhand[1] - 1.0)
        A = (rc[0] - .5, rc[1] + r)
        sag = [3.0, 4.0, 2.5][f] * z
        n = 14
        pts = [(A[0] + (mx - A[0]) * t / n - sag * math.sin(math.pi * t / n),
                A[1] + (by0 - A[1]) * t / n) for t in range(n + 1)]
        for i in range(n):                                    # 늘어진 천 띠 — 막대가 아니라 처진 곡선
            seg(hh, pts[i], pts[i + 1], 'white', 2)
        for i in range(n):
            seg(hh, (pts[i][0] - 1, pts[i][1]), (pts[i + 1][0] - 1, pts[i + 1][1]), 'cream', 1)
        hh.ell(rc[0], rc[1], r, r, 'white')
        hh.ell_in(rc[0] + .6, rc[1] + .6, r - .8, r - .8, 'cream', only=('white',))
        hh.set(rc[0], rc[1], 'creamD'); hh.set(rc[0] + 1, rc[1], 'creamD')

    elif clip == 'work_greenhouse':
        p0 = max(2, ir(P(-18, 0)[0])); p1 = ir(P(-8, 0)[0]); yp = ir(F - 7 * z)
        for y in range(yp, F + 1):
            ins = (y - yp) // 3
            fx.rect(p0 + ins, y, p1 - ins, y, 'ox')
        fx.rect(p0 - 1, yp, p1 + 1, yp + 1, 'suitL'); fx.rect(p0, yp - 1, p1, yp - 1, 'suitD')
        pm = (p0 + p1) / 2.0
        ptop = SL[1] - 8 * s
        fx.rect(ir(pm), ir(ptop + 2), ir(pm), yp - 1, 'olivD')
        for dx, dy, rx, ry, t in ((0, 1, 2.4, 2.4, 'impGrn'), (-4, 3, 3.2, 2.2, 'impGrn'),
                                  (4, 4, 3.2, 2.2, 'oliv'), (-3, 8, 3.0, 2.0, 'oliv'),
                                  (3, 10, 3.0, 2.0, 'impGrn'), (-4, 13, 3.0, 2.0, 'impGrn'),
                                  (4, 15, 2.6, 1.8, 'oliv')):
            fx.ell(pm + dx * z, ptop + dy * z, rx * z, ry * z, t)
        dead = 'brassM'                                            # 시든 잎 하나
        if f == 0:
            lhand = (pm + 7 * z, ptop + 6 * z)
            fx.ell(lhand[0] - 1.5, lhand[1] + 1, 1.8, 1.2, dead)
        elif f == 1:
            lhand = P(-4, 1)
            hh.ell(lhand[0] - 2, lhand[1] - 1.5, 1.8, 1.2, dead)
        else:
            lhand = (pm + 6 * z, ptop + 9 * z)
            fx.ell(pm + 5 * z, yp - 3, 1.6, 1.0, dead)

    elif clip == 'work_decoder':
        lx0 = max(2, ir(P(-16, 0)[0])); lx1 = ir(P(-3, 0)[0]); yt = belt_y - 3
        mid = (lx0 + lx1) // 2
        fx.rect(mid - 1, yt + 2, mid + 1, F, 'suitD'); fx.rect(mid - 1, yt + 2, mid - 1, F, 'suitM')
        fx.rect(mid - 4, F - 1, mid + 4, F, 'suitD')
        fx.rect(lx0, yt + 1, lx1, yt + 2, 'suitM'); fx.rect(lx0, yt + 1, lx1, yt + 1, 'suitL')
        fx.rect(lx0 + 1, yt - 2, mid - 1, yt, 'cream'); fx.rect(mid + 1, yt - 2, lx1 - 1, yt, 'cream')
        fx.rect(lx0 + 1, yt - 2, mid - 1, yt - 2, 'white'); fx.rect(mid + 1, yt - 2, lx1 - 1, yt - 2, 'white')
        fx.rect(mid, yt - 3, mid, yt, 'creamD')
        for xx in range(lx0 + 2, lx1 - 1, 2):                      # 글줄
            if xx != mid:
                fx.set(xx, yt - 1, 'creamD')
        fx.rect(lx0, yt - 4, lx0, yt, 'cream'); fx.set(lx0, yt - 5, 'flame'); fx.set(lx0, yt - 6, 'flameR')
        if f == 0:
            lhand = (lx1 - 2, yt - 3)
        elif f == 1:
            ph = ir(9 * z)
            hh.rect(mid, yt - ph, mid + 1, yt - 2, 'white'); hh.rect(mid + 1, yt - ph, mid + 1, yt - 2, 'cream')
            lhand = (mid + 1, yt - ph)
        else:
            hh.rect(lx0 + 2, yt - 4, mid - 1, yt - 3, 'white'); hh.rect(lx0 + 2, yt - 3, mid - 1, yt - 3, 'cream')
            lhand = (lx0 + 3, yt - 4)

    elif clip == 'work_pantry':
        sx0 = ir(P(-15, 0)[0]); sx1 = ir(P(-4, 0)[0]); st = ir(F - 5 * z)
        fx.rect(sx0, st, sx1, F, 'tank'); fx.rect(sx0, st, sx1, st, 'tankL')
        fx.rect(sx0 + 2, F - 3, sx1 - 2, F - 2, 'flameR')
        for k in range(sx0 + 2 + (f % 2), sx1 - 1, 2):
            fx.set(k, F - 3, 'flame')
        py0 = ir(st - 6 * z)
        fx.rect(sx0 + 1, py0, sx1 - 1, st - 1, 'tank'); fx.rect(sx0 + 1, py0, sx0 + 2, st - 1, 'tankL')
        fx.rect(sx0, py0, sx1, py0, 'tankL'); fx.set(sx0 - 1, py0 + 1, 'tank'); fx.set(sx1 + 1, py0 + 1, 'tank')
        mid = (sx0 + sx1) // 2
        for bx_, hgt in ((sx0 + 2, 4), (mid, 6), (sx1 - 2, 3)):     # 김
            for k in range(hgt):
                xx = bx_ + (1 if ((k + f + bx_) % 3 == 0) else (-1 if ((k + f + bx_) % 3 == 1) else 0))
                fx.ell(xx, py0 - 2 - k * 2, 1.0, 0.8, 'white' if k < 2 else 'cream')
        lhand = [(sx1 - 1, py0 - 4), (mid, py0 - 5), (sx0 + 3, py0 - 4)][f]
        sp_end = (lhand[0] + [-1, 0, 1][f], py0 + 1)
        seg(hh, lhand, sp_end, 'suitL', 1)

    elif clip == 'work_airlock':
        tx0 = max(2, ir(P(-16, 0)[0])); tx1 = tx0 + ir(6 * z); top = ir(F - 17 * z)
        mid = (tx0 + tx1) // 2
        fx.rect(tx0, top + 2, tx1, F, 'tank'); fx.rect(tx0 + 1, top + 2, tx0 + 1, F, 'tankL')
        fx.rect(tx0 + 1, top + 1, tx1 - 1, top + 1, 'tank'); fx.rect(tx0 + 2, top, tx1 - 2, top, 'tankL')
        fx.rect(mid - 1, top - 2, mid + 1, top - 1, 'brassD')
        fx.rect(tx0, top + 6, tx1, top + 6, 'brassM'); fx.rect(tx0, F - 4, tx1, F - 4, 'brassM')
        hx0 = max(1, tx0 - ir(4 * z))                                    # 호스 — 바닥에 사려 둔다
        seg(fx, (mid - 1, top - 2), (tx0 - 1, top - 4), 'suitD', 2)
        seg(fx, (tx0 - 1, top - 4), (hx0, top + 4), 'suitD', 2)
        seg(fx, (hx0, top + 4), (hx0, F - 2), 'suitD', 2)
        fx.ell(hx0 + 1, F - 1, 2.6 * z, 1.2, 'suitD')
        gc = (tx1 + 2.5 * z, top - 1)
        fx.rect(mid + 2, top - 1, tx1, top - 1, 'brassD')
        fx.ell(gc[0], gc[1], 2.3 * z, 2.3 * z, 'cream')
        na = math.radians([-130, -50, -100][f])
        seg(fx, gc, (gc[0] + 2.0 * z * math.cos(na), gc[1] + 2.0 * z * math.sin(na)), 'ox', 1)
        lhand = [(gc[0] + 1, gc[1] - 4.5 * z), (gc[0] + 1, gc[1] - 2.2 * z),
                 (gc[0] + 3, gc[1] - 5.5 * z)][f]
        if f == 1:                                              # 톡 — 두드림
            hh.set(gc[0] - 3, gc[1] - 3, 'white'); hh.set(gc[0] + 4, gc[1] - 3, 'white')

    elif clip == 'rest_lounge':
        no_prop = True
        lhand = P(-5, -10)                                      # 유리에 댄 손

    elif clip == 'elevator_ride':
        prop_front = True
        lhand = (cx - 3, belt_y + 4 + (0 if not kid else 1))
        rhand = (cx + 3, belt_y + 4 + (0 if not kid else 1))
    # elevator_wait · elevator_turn — 두 팔 내림, 오른손 도구 (idle 과 같은 팔)

    # ── 조립 ──
    c.blit(fx)
    if lhand is not None:            # 장갑 중심은 정수 — 각인(손등 금)이 장갑 안에 떨어지게
        lhand = (ir(lhand[0]), ir(lhand[1]))
    if rhand is not None:
        rhand = (ir(rhand[0]), ir(rhand[1]))
    am = Cv()                        # 팔만 따로 — 머리 뒤 베일 각인을 가리는 판정에 쓴다
    mid_ = belt_y - 4
    prof = g.get('profile', False)   # S12 옆모습 작업 — 먼 팔은 몸통 뒤라 그리지 않고 도구는 허리에 건다
    am.rect(ax_l, arm_y0 + 1, ax_l + 3, arm_y0 + 3, 'suitM')      # 어깨 뿌리
    if not prof:
        am.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y0 + 3, 'suitD')
    if lhand is not None:
        e = arm_to(am, SL, lhand, R, 'l')
        wl = (lhand[0], lhand[1])
    else:
        am.rect(ax_l, arm_y0 + 1, ax_l + 3, mid_, 'suitM'); am.rect(ax_l + tk, mid_, ax_l + 3 + tk, arm_y1, 'suitM')
        am.rect(ax_l, arm_y0 + 1, ax_l + 1, mid_, 'suitL'); am.rect(ax_l + tk, mid_, ax_l + 1 + tk, arm_y1, 'suitL')
        wl = (ax_l + 1 + tk, arm_y1 + 2)
        e = (SL[0], SL[1] + R * 0.55)
    if rhand is not None:
        arm_to(am, SR, rhand, R, 'r')
        wr = (rhand[0], rhand[1])
    elif prof:
        wr = g['hip_xy']
    else:
        am.rect(ax_r, arm_y0 + 1, ax_r + 3, mid_, 'suitD'); am.rect(ax_r - tk, mid_, ax_r + 3 - tk, arm_y1, 'suitD')
        wr = (ax_r + 2 - tk, arm_y1 + 2)
    c.blit(am)
    anc['_arm'] = am
    anc['_fx'] = fx
    if prop_front:
        hand_prop(hh, role, wr[0], wr[1])
    ov.blit(hh)
    mitten(mitc, wl[0], wl[1])
    if rhand is not None:
        mitten(mitc, wr[0], wr[1], 'creamD')
    elif prof:
        hand_prop(c, role, wr[0], wr[1])
    else:
        mitten(c, wr[0], wr[1], 'creamD')
        if not g['back'] and not hip and not no_prop:
            hand_prop(c, role, wr[0], wr[1])
    if hip and not g['back'] and not prof:
        hand_prop(c, role, ax_r - 1, belt_y + 3)
    ov.blit(mitc)
    objc.blit(fx); objc.blit(hh)
    anc['_front'] = hh
    anc['mitten_l'] = (int(wl[0]), int(wl[1]))
    anc['wrist_r'] = (int(wr[0]), int(wr[1] - 2))
    if lhand is not None:            # 팔이 내려가 있으면 기존 앵커(ax_l, neck_y+5) 그대로
        anc['arm_l'] = (int(round(SL[0] - 1.5 + (e[0] - SL[0]) * 0.35)),
                        int(round(SL[1] + 2.0 + (e[1] - SL[1] - 2.0) * 0.35)))
    return wl, wr


# ── S12: 옆모습 (오른쪽을 본다) ─────────────────────────────────────────
def _mirror_into(dst, src, ax):
    """src 를 세로축 x=ax 기준으로 뒤집어 dst 에 얹는다(뒤 꼬리를 뒤통수 쪽으로 돌릴 때)."""
    for y in range(src.h):
        for x in range(src.w):
            t = src.g[y][x]
            if t is not None:
                dst.set(2 * ax - x, y, t)


def headwear_side(c, role, hx, hy, hr, layer, f=0):
    """머리에 쓴 것 — 옆에서 본 꼴. 대부분 앞모습 그대로(돌려 봐도 같은 모양)이고,
    **뒤로 늘어지는 것**(정찰병 후드 꼬리·의무병 머릿수건 꼬리·학자 모자 술)만 뒤통수 쪽(왼쪽)으로 돌린다.
    기술자 고글은 렌즈 하나가 이마 앞으로 튀어나온다."""
    top = hy - hr
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    if role in ('scout', 'medic', 'scholar') and layer == 'under':
        tmp = Cv()
        headwear(tmp, role, hx, hy, hr, False, 'under')
        _mirror_into(c, tmp, int(round(hx)))
        return
    if role == 'medic' and layer == 'over':                  # 이마 십자 — 이마가 앞(오른쪽)에 있다
        x0 = int(round(hx + hr - 4))
        c.rect(x0 - 1, top + 1, x0 + 1, top + 1, 'ox'); c.set(x0, top, 'ox'); c.set(x0, top + 2, 'ox')
        return
    if role == 'engineer' and layer == 'over':
        c.rect(hx - hr - 1, top - 2, hx + hr, top + 2, rD)                     # 고글 끈
        c.rect(hx - hr - 1, top - 2, hx + hr, top - 2, 'tankL')
        c.rect(hx - hr - 1, top - 1, hx - hr, top + 2, 'tankL')                 # 뒤 버클
        c.ell(hx + hr - 1.2, top - .2, 2.4, 1.9, 'glassD')                      # 앞으로 나온 렌즈 하나
        c.set(int(round(hx + hr - 2)), int(round(top - 1)), 'glass')
        c.rect(hx - hr - 3, top + 2, hx - hr, top + 5, 'tankL')                 # 공구띠 끝(뒤)
        return
    headwear(c, role, hx, hy, hr, False, layer)


def side_boot(c, x0, x1, y0, y1, far):
    """옆에서 본 무게추 장화 — 발끝이 오른쪽."""
    c.rect(x0, y0, x1, y1 - 1, 'suitD' if far else 'bootM')
    if not far:
        c.rect(x0, y0, x0 + 1, y1 - 1, 'bootL')
        c.set(x1, y0, 'bootL')
    c.rect(x0, y1, x1, y1, 'brassD' if far else 'brassM')                     # 무게추 밑창
    if not far:
        c.set(x1, y1, 'brass')


def s15_pose(clip, f, kid):
    """S15 옆모습 원정 동작의 자세값. build_side(pose=...) 가 쓴다(기존 호출은 pose 없음 = 그대로)."""
    st = 3 if kid else 4
    if clip == 'swim_side':
        return [dict(bob=0, legs=(st, -st, 0, 0), deg=(34, 8)),
                dict(bob=-3, legs=(2, -2, 3, 3), deg=(40, 30)),
                dict(bob=0, legs=(-st, st, 0, 0), deg=(18, 30))][f]
    if clip == 'carry_box_swim':
        return [dict(bob=0, legs=(3, -3, 0, 0), carry=True, sealed=True),
                dict(bob=-2, legs=(1, -1, 2, 2), carry=True, sealed=True)][f]
    if clip == 'hatch_exit':
        step = 3 if kid else 4
        dy = [2 * step, step, 0][f]
        xn = 7 if kid else 9                               # 사다리 기둥(몸 중심에서)
        legs = [(5, 4, dy + step, dy), (5, 4, dy, dy + step), (2, -2, 0, 0)][f]
        nh = [(xn - 1, -3), (xn - 1, 1), (xn - 1, 3)][f]   # 가까운 손(목 기준)
        fh = [(xn - 1, 3), (xn - 1, -3), None][f]
        return dict(bob=-dy, legs=legs, ladder=dict(xn=xn, step=step), near_hand=nh, far_hand=fh,
                    deg=(0, -10), tool='belt')
    return None


def build_side(role, clip, f, body, stand=False, pose=None):
    """옆모습 본체(오른쪽을 본다). build_raw 와 같은 (base, ov, 앵커) 를 돌려준다.
    세로 좌표(맨머리 44/33px · 목 · 몸통 · 허리 · 발 기준선)는 앞모습과 같은 식이다."""
    c = Cv()
    ov = Cv(stencil=c)
    kid = (role == 'kid')
    H = H_KID if kid else H_ADULT
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    B = BODIES[body]
    carry = (clip == 'carry_side') or bool(pose and pose.get('carry'))
    if stand:                                       # 옆모습 작업(S12-B) — 선 몸통만. 팔·설비는 s11_pose 가 붙인다
        bob = S11_BOB.get(clip, [0, 0, 0])[f]
    elif pose:                                      # S15 원정 동작
        bob = pose['bob']
    else:
        bob = ([0, 1] if carry else [0, -1, 0])[f]

    hr = 8.5 if not kid else 7.4
    head_top = FOOT - (H - 1) + bob
    hy = head_top + hr
    cx = 31
    hx = cx + 1
    neck_y = head_top + (17 if not kid else 15)
    torso_ry = 7.2 if not kid else 5.0
    torso_rx = 6.0 if not kid else 4.8              # 옆에서 본 가슴 두께
    torso_cy = neck_y + (9 if not kid else 6)
    belt_y = int(round(torso_cy + torso_ry * .45))
    leg_y0 = int(round(torso_cy + torso_ry - 1))
    arm_y0 = neck_y + 1
    arm_y1 = belt_y + (2 if not kid else 1)
    R = float(arm_y1 - arm_y0)

    # ── 걸음 — 가까운 다리(오른) / 먼 다리. 팔은 다리와 반대 ──
    st = (3 if kid else 4) if not carry else (2 if kid else 3)
    if stand:
        near_dx, far_dx, near_lift, far_lift = 1, -2, 0, 0
        swing = 0
    elif carry:
        near_dx, far_dx, near_lift, far_lift = [st, -st][f], [-st, st][f], 0, 0
        swing = 0
    else:
        near_dx = [st, 0, -st][f]
        far_dx = [-st, -1, st][f]
        near_lift, far_lift = 0, [0, 2, 0][f]
        swing = [-1, 0, 1][f]                       # 가까운 팔: 가까운 다리가 앞이면 뒤로
    # 팔 흔들기 각도(도, +가 앞). 가까운 팔은 앞쪽으로 치우쳐 흔든다 — 뒤로 크게 빼면 도구가 몸통에 묻힌다
    near_deg = [2, 12, 26][f] if not (carry or stand) else 0
    far_deg = [20, 6, -10][f] if not (carry or stand) else 0
    if pose:
        near_dx, far_dx, near_lift, far_lift = pose['legs']
        near_deg, far_deg = pose.get('deg', (near_deg, far_deg))

    tool_cv, obj = Cv(), Cv()
    anc = {}

    # ── S15 문간 사다리 — 옆에서 보면 기둥 하나 + 사람 쪽으로 난 가로대 끝 ──
    if pose and pose.get('ladder'):
        lx = cx + pose['ladder']['xn']
        c.rect(lx, 1, lx + 1, FOOT, 'tank'); c.rect(lx, 1, lx, FOOT, 'tankL')
        for ry in range(FOOT + 1 - pose['ladder']['step'], 0, -pose['ladder']['step']):
            c.rect(lx - 2, ry, lx - 1, ry, 'tankL')

    # ── 등 뒤 공기통 (옆에서 보면 등 뒤로 튀어나온다 — 옆모습의 가장 큰 실루엣 단서) ──
    if not kid:
        tank(c, cx - torso_rx - 1, torso_cy - 1, torso_ry - 1.2)
        c.rect(cx - torso_rx, neck_y - 1, cx - torso_rx + 2, neck_y + 1, 'suitD')   # 호스 이음

    # ── 먼 팔 (몸통 뒤) ──
    SF = (cx - 0.5, arm_y0 + 2.0)
    SN = (cx + 0.5, arm_y0 + 2.0)
    if not carry and not stand:
        a = math.radians(far_deg)
        hf = (SF[0] + R * 0.9 * math.sin(a), SF[1] + R * 0.9 * math.cos(a))
        hf = (int(round(hf[0])), int(round(hf[1])))
        if pose and pose.get('far_hand'):
            hf = (int(cx + pose['far_hand'][0]), int(neck_y + pose['far_hand'][1]))
        arm_to(c, SF, hf, R, 'r')
        mitten(c, hf[0], hf[1], 'creamD')

    # ── 다리: 먼 다리 → 가까운 다리 ──
    lw = 4 if not kid else 3
    for dx, lift, far in ((far_dx, far_lift, True), (near_dx, near_lift, False)):
        hip = (cx - (1 if far else 0), leg_y0)
        ank = (cx + dx, FOOT - 4 - lift)
        seg(c, hip, ank, 'suitD' if far else 'suitM', lw)
        if not far:
            seg(c, (hip[0] + 1, hip[1]), (ank[0] + 1, ank[1]), 'suitL', 1)
        fxp = int(round(cx + dx))
        side_boot(c, fxp - 2, fxp + (3 if not kid else 2), FOOT - 4 - lift, FOOT - lift, far)

    # ── 몸통 ──
    c.ell(cx, torso_cy, torso_rx, torso_ry, rM)
    c.ell_in(cx - 2, torso_cy - 2.2, torso_rx - 2, torso_ry - 1.2, rL, only=(rM,))
    c.ell_in(cx, torso_cy + torso_ry - 1, torso_rx, 3.2, rD, only=(rM, rL))
    if B['waist']:                                  # 체형 B — 옆에서는 허리 앞뒤가 1px 들어간다
        coat = (rM, rD, rL)
        for yy in range(belt_y - 2, belt_y + 2):
            dy = (yy - torso_cy) / max(torso_ry, .001)
            if abs(dy) >= 1.0:
                continue
            rr = torso_rx * math.sqrt(1.0 - dy * dy)
            cut = B['waist'] * (1.0 - abs(yy - belt_y + 0.5) / 2.6)
            if cut <= 0:
                continue
            for xx in range(cx - 12, cx + 13):
                if abs(xx - cx) > rr - cut and c.own(xx, yy) in coat:
                    c.clear(xx, yy)
    c.rect(cx - 4, torso_cy - 2, cx - 3, torso_cy, 'ox')                   # 기운 자국
    c.rect(cx - torso_rx + 1, belt_y, cx + torso_rx - 1, belt_y + 1, 'oliv')
    c.rect(int(cx + torso_rx - 1), belt_y, int(cx + torso_rx - 1), belt_y + 1, 'brassM')   # 버클(앞)

    # ── 허리 랜턴 — 등 쪽 허리에 건다 ──
    if not kid:
        lantern(c, int(cx - torso_rx), belt_y + 3)

    # ── 목 실링 + 어깨 링 ──
    c.ell(cx, neck_y - 1, torso_rx - .2, 2.6, 'cream')
    c.ell(cx, neck_y - 2, torso_rx - .8, 1.9, 'creamD')
    wave(c, cx - torso_rx + 2, cx + torso_rx - 2, neck_y - 3, 'suitD')
    c.rect(cx - torso_rx + 1, neck_y, cx + torso_rx - 1, neck_y, 'brassD')

    # ── 머리: 놋쇠 돔 + 옆으로 난 얼굴 창 ──
    c.ell(hx, hy, hr, hr, 'brassD')
    c.ell(hx, hy - .5, hr - .9, hr - .9, 'brassM')
    c.ell(hx, hy - 1.1, hr - 1.9, hr - 1.9, 'brass')
    c.ell(hx - hr * .42, hy - hr * .58, hr * .36, hr * .24, 'brassH')
    headwear_side(c, role, hx, hy, hr, 'under', f)
    c.set(int(round(hx - hr + 1.6)), int(round(hy - 1)), 'brassH')            # 뒤 볼트 하나
    fy = hy + 1.5
    fr = hr - 2.2
    wrx, wry = fr - 2.0, fr
    wx = hx + hr - wrx - 1.2                       # 얼굴 창은 투구 앞쪽에 붙는다
    c.ell(wx, fy, wrx + .9, wry + .9, 'brassD')
    c.ell(wx, fy, wrx, wry, 'skin')
    c.ell_in(wx + 1.4, fy + 1.6, wrx - .6, wry - .8, 'skinD', only=('skin',))
    win = {}
    for yy in range(int(fy - wry) - 1, int(fy + wry) + 2):
        xs = [xx for xx in range(64) if c.own(xx, yy) in ('skin', 'skinD')]
        if xs:
            win[yy] = (min(xs), max(xs))
    ey = ey_of(fy)
    nose = (win[ey + 2][1] + 1, ey + 2)                                      # 코 — 창 테를 1px 넘는다
    c.set(nose[0], nose[1], 'skin'); c.set(nose[0], nose[1] + 1, 'skinD')

    if role == 'scholar':                          # 깨진 안경 — 앞 렌즈 테 + 귀로 가는 다리
        xf = win[ey][1]
        ov.rect(xf - 3, ey - 1, xf + 1, ey - 1, 'brassM')
        ov.set(xf + 1, ey, 'brassM'); ov.set(xf + 1, ey + 1, 'brassM')
        ov.set(xf - 1, ey - 1, 'brassH')
    if role == 'trader':                           # 목도리 — 꼬리가 뒤로 날린다
        ov.rect(hx - hr + 3, hy + hr - 1, hx + hr - 1, hy + hr + 1, rL)
        tx = int(round(hx - hr + 3)) - [0, 1, 0][f] if not (carry or stand) else int(round(hx - hr + 3))
        ov.rect(tx - 2, hy + hr, tx, hy + hr + 1, rM)
        ov.rect(tx - 3, hy + hr + 2, tx - 1, hy + hr + 3, rM)
    headwear_side(ov, role, hx, hy, hr, 'over', f)

    # ── 가까운 팔 · 도구 / 상자 ──
    am, mit = Cv(), Cv()
    if stand:
        wr = (cx, belt_y)
    elif not carry:
        a = math.radians(near_deg)
        hn = (SN[0] + R * 0.9 * math.sin(a), SN[1] + R * 0.9 * math.cos(a))
        hn = (int(round(hn[0])), int(round(hn[1])))
        if pose and pose.get('near_hand'):
            hn = (int(cx + pose['near_hand'][0]), int(neck_y + pose['near_hand'][1]))
        if pose and pose.get('tool') == 'belt':          # S15 사다리 — 두 손이 비어야 한다. 도구는 허리 앞에 꽂는다
            hand_prop(tool_cv, role, cx + 2, belt_y + 2)
            c.blit(tool_cv)
        arm_to(am, SN, hn, R, 'l')
        c.blit(am)
        mitten(mit, hn[0], hn[1], 'cream')
        c.blit(mit)
        if not (pose and pose.get('tool') == 'belt'):
            hand_prop(tool_cv, role, hn[0], hn[1])
            c.blit(tool_cv)
        wr = hn
    else:
        bw, bh = (10, 8) if not kid else (8, 6)
        bx0 = cx + (2 if not kid else 1)
        by0 = int(round(torso_cy - (3 if not kid else 2)))
        bx1, by1 = bx0 + bw - 1, by0 + bh - 1
        top_rel = {'scout': -5, 'cook': -6, 'medic': 1, 'engineer': -7, 'farmer': -4,
                   'scholar': -4, 'trader': -6, 'kid': -2}[role]
        hand_prop(tool_cv, role, bx0 + 2, by0 - (3 if not kid else 2) - top_rel)   # 상자에 꽂힌 도구
        box = Cv()
        box.rect(bx0, by0, bx1, by1, 'suitL'); box.rect(bx0, by0, bx1, by0, 'suitH')
        box.rect(bx0, by0, bx0, by1, 'suitH'); box.rect(bx0, by1, bx1, by1, 'suitD')
        box.rect(bx1, by0 + 1, bx1, by1, 'suitM')
        lx0, ly0 = bx0 + 2, by0 + 2                                          # 바코드 표 — 유물을 읽는 행위
        if pose and pose.get('sealed'):              # S15 봉인 상자 — 끈 두 줄 + 갈래 무늬(빈 원)
            box.rect(bx0 + 2, by0, bx0 + 2, by1, 'olivD'); box.rect(bx1 - 2, by0, bx1 - 2, by1, 'olivD')
            mx_, my_ = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
            ring(box, mx_, my_, 2.6 if not kid else 2.0, 1.0, 'brassM')
        else:
            box.rect(lx0, ly0, lx0 + (5 if not kid else 4), ly0 + (2 if not kid else 1), 'cream')
            for k_, xx in enumerate(range(lx0, lx0 + (5 if not kid else 4) + 1)):
                if k_ in ((0, 1, 3, 5) if not kid else (0, 2, 3)):      # 굵기가 다른 세로줄 — 바코드
                    box.rect(xx, ly0, xx, ly0 + (2 if not kid else 1), 'ink')
        c.blit(tool_cv)
        for (xx, yy) in box.pixels():                                         # 상자가 도구 아랫부분을 가린다
            tool_cv.clear(xx, yy)
        c.blit(box)
        obj.blit(box)
        hn = (bx0 + 2, by1 - 1)
        arm_to(am, SN, hn, R, 'l')
        c.blit(am)
        mitten(mit, hn[0], hn[1], 'cream')
        c.blit(mit)
        wr = hn
    obj.blit(tool_cv)

    xf = win[ey][1]
    aL = {
        'role': role, 'body': body, 'kid': kid, 'clip': clip, 'f': f,
        'hx': hx, 'hy': hy, 'hr': hr, 'fy': fy, 'fr': fr,
        'cx': cx, 'neck_y': neck_y, 'torso_rx': torso_rx, 'belt_y': belt_y,
        'torso_cy': torso_cy, 'torso_ry': torso_ry, 'arm_y0': arm_y0, 'arm_y1': arm_y1, 'head_top_y': head_top,
        'ax_l': int(cx - torso_rx), 'ax_r': int(cx + torso_rx),
        'sad': False, 'side': True,
        'wx': wx, 'wrx': wrx, 'wry': wry, 'win': win, 'ey': ey, 'nose': nose,
        'rim': int(round(hy + hr)),
        'head_top': (int(hx), int(head_top)),
        'forehead': ((win[min(win) + 1][0] + win[min(win) + 1][1]) // 2 + 1, min(win) + 1),
        'temple_l': (0, 0), 'neck_l': (0, 0), 'arm_l': (0, 0), 'mitten_l': (0, 0),
        'temple_r': (int(win[ey][0] - 1), int(ey)),                       # 귀 자리 = 창 뒤 테
        # 「지킨 자」 흉터 — 어른은 볼, 아이는 얼굴 창이 좁아(입 높이에서 3~5px) 턱으로 내린다
        'cheek_r': ((int(win[ey + 3][0] + 2), int(ey + 3)) if not kid else (int(win[ey + 5][0]), int(ey + 5))),
        'collar_r': (int(cx + 2), int(neck_y + 1)),
        'chest': (int(cx + torso_rx - 2), int(neck_y + 3)),
        'wrist_r': (int(wr[0]), int(wr[1] - 2)),
        'belt_c': (int(cx - 4), int(belt_y + 1)),          # 허리 옆 매듭 — 흔드는 팔 뒤쪽(팔에 안 가린다)
        'face_shown': True,
        'hide': set(SIDE_FAR),
    }
    # 몸 앞으로 온 것(가까운 팔·장갑·도구·상자)이 가린 각인 픽셀은 잘라 낸다.
    # 손목 팔찌(debt_paid)는 팔 **위**에 있으므로 팔에는 잘리지 않고, 든 물건에만 잘린다.
    front_all = am.pixels() | mit.pixels() | obj.pixels()
    aL['side_cut'] = {'*': front_all, 'debt_paid': obj.pixels()}
    if pose and pose.get('ladder'):              # S15 사다리 — 손을 얼굴 높이로 올린다: 손목 팔찌는 얼굴에 비키고, 흉터는 팔찌에 비킨다
        hs_ = hair_layer_side('short', aL, c)
        fpx = set()
        for _fid, _k, _n in FACES:
            fpx |= face_layer(_fid, aL, c, hs_).pixels()
        aL['side_cut']['debt_paid'] = obj.pixels() | fpx
        aL['side_cut']['warden'] = front_all | _imprint_raw('debt_paid', aL).pixels()
    aL['obj_cv'] = obj
    aL['mit_px'] = mit.pixels()
    aL['front_px'] = set(obj.pixels())
    return c, ov, aL


MX = 61          # 옆모습 작업: 오른쪽 몸을 x' = 61 - x 로 뒤집는다(몸 중심 31 -> 30)


def mirror_cv(cv):
    out = Cv()
    for y in range(cv.h):
        row = cv.g[y]
        for x in range(cv.w):
            if row[x] is not None:
                out.set(MX - x, y, row[x])
    return out


def build_profile_work(role, clip, f, body):
    """
    S12-B 옆모습 작업(왼쪽을 본다). 몸·머리는 build_side(선 자세)를 뒤집어 쓰고,
    팔·설비·든 물건은 S11 의 s11_pose 를 그대로 쓴다(어깨만 옆모습 어깨로 옮겼다 -> 설비가 7px 오른쪽으로 온다).
    머리·얼굴·몸통 각인은 오른쪽 몸 기준(aL['_r'])으로 그린 뒤 뒤집는다.
    """
    cR, ovR, aR = build_side(role, clip, f, body, stand=True)
    c = mirror_cv(cR)
    ov = Cv(stencil=c)
    ov.blit(mirror_cv(ovR))
    kid = (role == 'kid')
    cxL = MX - aR['cx']
    shL = MX - (aR['cx'] + 0.5)
    g = dict(role=role, kid=kid, cx=cxL, neck_y=aR['neck_y'], torso_cy=aR['torso_cy'],
             torso_ry=aR['torso_ry'], torso_rx=aR['torso_rx'], belt_y=aR['belt_y'],
             head_top=aR['head_top_y'], ax_l=shL - 1.5, ax_r=shL - 1.5,
             arm_y0=aR['arm_y0'], arm_y1=aR['arm_y1'], tk=0, back=False,
             profile=True, hip_xy=(cxL + 2, aR['belt_y'] + 3))
    s11_anc, s11_hide = {}, set()
    s11_obj, s11_mit = Cv(), Cv()
    s11_pose(c, ov, clip, f, g, s11_obj, s11_mit, s11_anc, s11_hide)
    hx = MX - aR['hx']
    aL = {
        'role': role, 'body': body, 'kid': kid, 'clip': clip, 'f': f,
        'hx': hx, 'hy': aR['hy'], 'hr': aR['hr'], 'fy': aR['fy'], 'fr': aR['fr'],
        'cx': cxL, 'neck_y': aR['neck_y'], 'torso_rx': aR['torso_rx'], 'belt_y': aR['belt_y'],
        'ax_l': int(shL - 1.5), 'ax_r': int(shL - 1.5), 'sad': False, 'face_shown': True,
        'view': 'profile_left', '_r': aR,
        'head_top': (int(hx), int(aR['head_top_y'])),
        'neck_l': (0, 0), 'temple_l': (0, 0), 'temple_r': (0, 0), 'cheek_r': (0, 0),
        'forehead': (0, 0), 'collar_r': (0, 0), 'chest': (0, 0), 'belt_c': (0, 0),
    }
    front = s11_anc.pop('_front')
    armc = s11_anc.pop('_arm')
    fxc = s11_anc.pop('_fx')
    fixvis = set(p_ for p_ in fxc.pixels() if c.own(*p_) == fxc.own(*p_) and ov.own(*p_) is None)
    armvis = set(p_ for p_ in armc.pixels() if c.own(*p_) == armc.own(*p_) and ov.own(*p_) is None)
    aL['clip_px'] = fixvis
    aL['behind_px'] = armvis | s11_mit.pixels() | fixvis
    aL.update(s11_anc)
    # 옆모습: 일하는 팔은 몸 앞 — 몸통 각인을 가린다. 팔 위의 각인(왼 위팔 띠·왼 장갑 금)은 제외.
    # 가슴 목걸이는 팔 띠에도 비킨다(팔이 앞).
    es_raw = _imprint_raw('empty_seat', aL).pixels()
    front_arm = armvis | s11_mit.pixels()
    hs_ = hair_layer('short', aL, c)
    face_px = set()
    for _fid, _k, _n in FACES:                       # 장갑이 얼굴 앞을 지날 때 금은 얼굴에 비킨다
        face_px |= face_layer(_fid, aL, c, hs_).pixels()
    aL['side_cut'] = {'*': front_arm, 'empty_seat': set(), 'crack_seen': face_px,
                      'footprint': front_arm | es_raw}
    fp = front.pixels() - s11_mit.pixels()
    aL['front_px'] = fp
    aL['hide'] = set()
    s11_hide.update(PROFILE_HIDE)
    for _iid, _k, _p, _c in IMPRINTS:
        if imprint_layer(_iid, aL).pixels() & fp:
            s11_hide.add(_iid)
    aL['hide'] = set(s11_hide)
    aL['obj_cv'] = s11_obj
    aL['mit_px'] = s11_mit.pixels()
    return c, ov, aL


def build_raw(role, clip='idle', f=0, body='a'):
    """본체를 **두 장**으로 돌려준다 (스프린트 9-A에서 레이어로 쪼갰다).
         base : 머리에 쓴 것(under) · 몸 · 얼굴 구멍의 맨살까지
         ov   : 얼굴보다 **나중에** 와야 하는 것 (안경 · 목도리 · 챙 · 일하는 티)
    머리카락과 얼굴은 여기서 그리지 않는다. 사이에 레이어로 끼운다:
         base → 머리 레이어 → 얼굴 레이어 → ov → 외곽선
    이 순서가 S8의 그리기 순서와 **한 칸도 다르지 않다**(기본 조합 short+f0 기준).
    """
    if clip in SIDE_IDS:                     # S12 옆모습 — 따로 그린다(기존 행 경로는 손대지 않음)
        return build_side(role, clip, f, body)
    if clip in S15_SIDE:                     # S15 원정 옆모습
        return build_side(role, clip, f, body, pose=s15_pose(clip, f, role == 'kid'))
    if clip in TURN_PROFILE:                 # S12-B 옆모습 작업(왼쪽)
        return build_profile_work(role, clip, f, body)
    c = Cv()
    ov = Cv(stencil=c)
    kid = (role == 'kid')
    H = H_KID if kid else H_ADULT
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    back = (clip in BACK_CLIPS)
    turn = (clip == 'elevator_turn')
    s11 = clip in S11_IDS
    P = POSE[clip]
    B = BODIES[body]
    pc = BASE_OF.get(clip, clip)            # S12-B 새 행은 팔·다리를 이 행에서 빌린다(기존 행은 pc == clip)
    q34 = (clip in TURN_Q34 or clip in ('work_34', 'carry_34') or (clip == 'idle_glance' and f == 1))

    if s11:
        bob, lean = S11_BOB[clip][f], S11_LEAN[clip][f]
    elif clip in S12B_IDS:
        bob = {'work_34': [0, -1, 0], 'carry_34': [0, 1], 'idle_glance': [0, 0, 0]}[clip][f]
        lean = -1 if clip == 'work_34' else 0
    elif clip in S15_FRONT:                  # S15 — 물살에 흔들림 / 돌아와 어깨를 늘어뜨림
        bob = {'swim_idle': [0, -1], 'return_tired': [1, 2]}[clip][f]
        lean = {'swim_idle': [-1, 1], 'return_tired': [0, 0]}[clip][f]
    else:
        bob = {'walk': [0, -1, -1], 'back_walk': [0, -1, -1], 'idle': [0, 1],
               'sit': [0, 1], 'work': [0, -1, 0], 'carry': [0, 1],
               'hurt': [0, 1]}[clip][f]
        lean = 1 if clip == 'work' else (2 if clip == 'hurt' else 0)
    s11_anc, s11_hide = {}, set()
    s11_obj, s11_mit = Cv(), Cv()

    # ── 기준 좌표 (원화) ── 체형이 바뀌어도 세로 좌표는 **전부 그대로**다.
    #    키 44px(아이 33px)·발 기준선 59·머리 크기·얼굴 위치는 규약이라 불변.
    hr = 8.5 if not kid else 7.4
    head_top = FOOT - (H - 1) + P['drop'] + bob      # 맨머리 꼭대기
    hy = head_top + hr
    hx = 32 + lean
    neck_y = head_top + (17 if not kid else 15)
    torso_ry = P['tr'] if not kid else P['tr'] - 2.2
    torso_rx = (8.6 if not kid else 6.9) + B['shoulder'] * (0.7 if kid else 1.0)
    torso_cy = neck_y + (P['tdy'] if not kid else P['tdy'] - 3)
    belt_y = int(round(torso_cy + torso_ry * .45))
    leg_y0 = int(round(torso_cy + torso_ry - 1))
    cx = 32

    # ── 뒤쪽: 공기통 ──
    if not kid:
        if back:
            pass                 # 뒤에서 보면 공기통이 앞에 온다 — 몸통 뒤에 그린다
        else:
            tank(c, cx + 11, torso_cy - 1, torso_ry - 1.2)
            c.rect(cx + 7, neck_y + 1, cx + 10, neck_y + 2, 'suitD')

    # ── 다리 (뒤) ──
    if not P['front']:
        draw_legs(c, P['legs'], cx, leg_y0, kid, f)

    # ── 몸통 — 역할 겉옷이 가장 큰 색 면이다 (70px 판독의 두 번째 축) ──
    c.ell(cx, torso_cy, torso_rx, torso_ry, rM)
    c.ell_in(cx - 2, torso_cy - 2.2, torso_rx - 2, torso_ry - 1.2, rL, only=(rM,))
    c.ell_in(cx, torso_cy + torso_ry - 1, torso_rx, 3.2, rD, only=(rM, rL))
    c.rect(cx - torso_rx, neck_y + 1, cx - torso_rx + 1, torso_cy + 1, 'suitM')
    c.rect(cx + torso_rx - 1, neck_y + 1, cx + torso_rx, torso_cy + 1, 'suitD')

    # ── 허리선 (체형 B) ── 겉옷을 좌우 1px씩만 깎는다. 과장 금지(§6-3).
    if B['waist'] and P['legs'] not in ('sit', 'kneel'):
        coat = (rM, rD, rL, 'suitM', 'suitD')
        for yy in range(belt_y - 2, belt_y + 2):
            dy = (yy - torso_cy) / max(torso_ry, .001)
            if abs(dy) >= 1.0:
                continue
            rr = torso_rx * math.sqrt(1.0 - dy * dy)
            cut = B['waist'] * (1.0 - abs(yy - belt_y + 0.5) / 2.6)
            if cut <= 0:
                continue
            for xx in range(cx - 14, cx + 15):
                if abs(xx - cx) > rr - cut and c.own(xx, yy) in coat:
                    c.clear(xx, yy)

    if not back:
        c.rect(cx - 4, neck_y + 1, cx - 3, belt_y - 1, 'cream')
        c.rect(cx + 3, neck_y + 1, cx + 4, belt_y - 1, 'cream')
        c.rect(cx - 7, torso_cy - 2, cx - 6, torso_cy, 'ox')      # 기운 자국
    else:
        c.rect(cx - 5, neck_y + 2, cx + 5, neck_y + 3, 'cream')
    c.rect(cx - torso_rx + 1, belt_y, cx + torso_rx - 1, belt_y + 1, 'oliv')
    if not back:
        c.rect(cx - 1, belt_y - 1, cx + 1, belt_y + 2, 'brassM')
        c.set(cx, belt_y, 'brassH')

    # ── 뒷모습의 공기통 — 등에 메므로 앞으로 나온다 ──
    if back and not kid:
        tank(c, cx - 5, torso_cy - 1, torso_ry - .6)
        tank(c, cx + 5, torso_cy - 1, torso_ry - .6)
        c.rect(cx - 1, int(torso_cy - torso_ry), cx + 1, int(torso_cy + torso_ry - 2), 'cream')

    # ── 팔 ──
    arm_y0 = neck_y + 1
    arm_y1 = belt_y + (2 if not kid else 1)
    ax_l, ax_r = int(cx - torso_rx - 2), int(cx + torso_rx - 1)
    if pc == 'carry':
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, arm_y1 - 1, 'suitM')
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y1 - 1, 'suitD')
        bx0, bx1 = cx - 7, cx + 7
        by0, by1 = int(torso_cy - 1), int(torso_cy + 6)
        c.rect(bx0, by0, bx1, by1, 'suitL')
        c.rect(bx0, by0, bx1, by0, 'suitH')
        c.rect(bx0, by0, bx0, by1, 'suitH')
        c.rect(bx0, by1, bx1, by1, 'suitD')
        wave(c, bx0 + 1, bx1 - 1, by0 + 3, 'cream')
        wl, wr = (cx - 9, by0 + 2), (cx + 9, by0 + 2)
        mitten(c, wl[0], wl[1]); mitten(c, wr[0], wr[1], 'creamD')
    elif clip == 'hurt':
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, FOOT - 5, 'suitM')
        wl = (ax_l + 1, FOOT - 3)
        mitten(c, wl[0], wl[1])                                   # 바닥을 짚은 손
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y1, 'suitD')
        wr = (ax_r + 2, arm_y1 + 2)
        mitten(c, wr[0], wr[1], 'creamD')
    elif clip == 'sit':
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, arm_y1, 'suitM')
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y1, 'suitD')
        wl, wr = (ax_l + 1, arm_y1 + 2), (ax_r + 2, arm_y1 + 2)
        mitten(c, wl[0], wl[1]); mitten(c, wr[0], wr[1], 'creamD')
    elif s11:
        g = dict(role=role, kid=kid, cx=cx, neck_y=neck_y, torso_cy=torso_cy,
                 torso_ry=torso_ry, torso_rx=torso_rx, belt_y=belt_y, head_top=head_top,
                 ax_l=ax_l, ax_r=ax_r, arm_y0=arm_y0, arm_y1=arm_y1,
                 tk=int(round(BODIES[body]['waist'] and 1 or 0)), back=back)
        wl, wr = s11_pose(c, ov, clip, f, g, s11_obj, s11_mit, s11_anc, s11_hide)
    else:
        sw = [0, 1, -1][f] if clip in ('walk', 'back_walk') else 0
        lift = [0, -4, -2][f] if pc == 'work' else 0
        # 허리선은 **팔이 만든다**. 몸통을 깎아도 팔이 그 자리를 덮어 버려서
        # 바깥선이 바뀌지 않는다(S9에서 폭을 재 보고 알았다). 체형 B는 팔꿈치
        # 아래를 1px 안으로 붙여 어깨→허리로 좁아지는 바깥선을 만든다.
        tk = int(round(BODIES[body]['waist'] and 1 or 0))
        mid = belt_y - 4
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, mid, 'suitM')
        c.rect(ax_l + tk, mid, ax_l + 3 + tk, arm_y1 + sw, 'suitM')
        c.rect(ax_l, arm_y0 + 1, ax_l + 1, mid, 'suitL')
        c.rect(ax_l + tk, mid, ax_l + 1 + tk, arm_y1 + sw, 'suitL')
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, mid, 'suitD')
        c.rect(ax_r - tk, mid, ax_r + 3 - tk, arm_y1 - sw + lift, 'suitD')
        wl = (ax_l + 1 + tk, arm_y1 + sw + 2)
        wr = (ax_r + 2 - tk, arm_y1 - sw + lift + 2)
        mitten(c, wl[0], wl[1]); mitten(c, wr[0], wr[1], 'creamD')

    # ── 허리 랜턴 (장갑과 겹치지 않게 허리띠 바로 아래 앞쪽) ──
    if not kid:
        lantern(c, int(cx - torso_rx + 1), belt_y + 3)

    # ── 다리 (앞) ──
    if P['front']:
        draw_legs(c, P['legs'], cx, leg_y0, kid, f)

    # ── 손에 든 것 (③) ──
    if not back and pc in ('idle', 'walk', 'work'):
        hand_prop(c, role, wr[0], wr[1])

    # ── 목 실링 + 어깨 링 ──
    c.ell(cx, neck_y - 1, torso_rx - .4, 2.8, 'cream')
    c.ell(cx, neck_y - 2, torso_rx - 1, 2.0, 'creamD')
    wave(c, cx - torso_rx + 2, cx + torso_rx - 2, neck_y - 3, 'suitD')
    c.rect(cx - torso_rx + 1, neck_y, cx + torso_rx - 1, neck_y, 'brassD')
    c.set(cx - torso_rx + 2, neck_y, 'brassM'); c.set(cx + torso_rx - 2, neck_y, 'brassM')

    # ── 머리: 놋쇠 돔 + 완전히 노출된 얼굴 (면갑을 올린 상태) ──
    c.ell(hx, hy, hr, hr, 'brassD')
    c.ell(hx, hy - .5, hr - .9, hr - .9, 'brassM')
    c.ell(hx, hy - 1.1, hr - 1.9, hr - 1.9, 'brass')
    c.ell(hx - hr * .42, hy - hr * .58, hr * .36, hr * .24, 'brassH')
    headwear(c, role, hx, hy, hr, back, 'under')
    for bx in (-1, 1):                                   # 볼트 두 개
        c.set(int(round(hx + bx * (hr - 1.2))), int(round(hy - 1)), 'brassH')
    fy = hy + 1.5
    fr = hr - 2.2
    c.ell(hx, fy, fr + .9, fr + .9, 'brassD')            # 얼굴 구멍 테
    if back:
        c.ell(hx, fy, fr, fr, 'hair')
        c.ell_in(hx - 1.6, fy - 1.8, fr - 1.0, fr - 1.4, 'suitH', only=('hair',))
        c.rect(int(hx), int(fy - fr), int(hx), int(fy + fr - 3), 'hairD')   # 가르마
        c.rect(int(hx - 3), int(fy + fr - 2), int(hx + 3), int(fy + fr), 'hairD')  # 목덜미
    elif turn:
        # S11 엘리베이터에 들어서며 몸을 돌리는 한 프레임 — 얼굴 구멍의 왼쪽은 뒷머리,
        # 오른쪽 절반에만 맨살과 눈 하나. 얼굴 레이어(3종)는 이 프레임에 얹지 않는다.
        c.ell(hx, fy, fr, fr, 'hair')
        c.ell_in(hx - 1.6, fy - 1.8, fr - 1.0, fr - 1.4, 'suitH', only=('hair',))
        c.ell_in(hx + 2.4, fy + .6, fr - 1.9, fr - .4, 'skin', only=('hair', 'suitH'))
        c.ell_in(hx + 3.4, fy + 2.0, fr - 2.8, fr - 1.6, 'skinD', only=('skin',))
        ey = ey_of(fy)
        c.rect(int(round(hx + 2)), int(round(fy - fr + 1)), int(round(hx + fr - 1)),
               int(round(fy - fr + 2)), 'hair')                     # 앞머리 띠(돌아선 쪽)
        eye(c, int(round(hx + 2)), ey, 2, 3)
        c.set(int(round(hx + 2)), ey - 2, 'ink')                    # 눈썹 한 획
        c.set(int(round(hx + 3)), ey - 3, 'ink')
        c.set(int(round(hx + 4)), ey + 4, 'ink')                    # 입 한 점
        blush(c, int(round(hx + 5)), int(round(hx + 5)), ey + 2)
        if role == 'scholar':
            ov.rect(int(round(hx + 1)), ey - 1, int(round(hx + 5)), ey - 1, 'brassM')
            ov.set(int(round(hx + 5)), ey, 'brassM')
        if role == 'trader':
            ov.rect(hx - hr + 1, hy + hr - 1, hx + hr - 1, hy + hr + 1, rL)
            ov.rect(hx + hr - 3, hy + hr + 1, hx + hr - 1, hy + hr + 4, rM)
    elif q34:
        # S12-B 3/4 왼쪽 — 얼굴 창이 왼쪽(보는 쪽)으로 1.6px 옮겨 가고 폭이 좁아진다. 오른쪽은 투구 옆면(놋쇠)
        wx = hx - 1.6
        wrx = fr - .7
        c.ell(wx, fy, wrx + .9, fr + .9, 'brassD')
        c.ell(wx, fy, wrx, fr, 'skin')
        c.ell_in(wx + 1.6, fy + 1.6, wrx - .6, fr - .6, 'skinD', only=('skin',))
        q_win = {}
        for yy in range(int(fy - fr) - 1, int(fy + fr) + 2):
            xs = [xx for xx in range(64) if c.own(xx, yy) in ('skin', 'skinD')]
            if xs:
                q_win[yy] = (min(xs), max(xs))
        q_ey = ey_of(fy)
        lo_ = q_win[q_ey][0]
        if role == 'scholar':                            # 깨진 안경 — 가까운 알은 크게, 먼 알은 테 두 칸
            ov.rect(lo_ + 3, q_ey - 1, lo_ + 7, q_ey - 1, 'brassM')
            ov.set(lo_ + 3, q_ey, 'brassM'); ov.set(lo_ + 7, q_ey, 'brassM')
            ov.rect(lo_, q_ey - 1, lo_ + 1, q_ey - 1, 'brassM')
            ov.set(lo_ + 6, q_ey - 1, 'brassH')
        if role == 'trader':
            ov.rect(hx - hr + 1, hy + hr - 1, hx + hr - 1, hy + hr + 1, rL)
            ov.rect(hx + hr - 3, hy + hr + 1, hx + hr - 1, hy + hr + 4, rM)
    else:
        c.ell(hx, fy, fr, fr, 'skin')
        c.ell_in(hx + 1.6, fy + 1.6, fr - .6, fr - .6, 'skinD', only=('skin',))
        # ↓ 머리카락과 얼굴은 레이어로 빠졌다 (hair_layer / face_layer)
        if role == 'scholar':                            # 깨진 안경 (얼굴보다 위)
            ov.rect(hx - 6, ey_of(fy) - 1, hx - 1, ey_of(fy) - 1, 'brassM')
            ov.rect(hx + 1, ey_of(fy) - 1, hx + 6, ey_of(fy) - 1, 'brassM')
            ov.set(hx - 6, ey_of(fy), 'brassM'); ov.set(hx + 6, ey_of(fy), 'brassM')
            ov.set(hx - 3, ey_of(fy) + 1, 'brassH')
        if role == 'trader':                             # 목도리
            ov.rect(hx - hr + 1, hy + hr - 1, hx + hr - 1, hy + hr + 1, rL)
            ov.rect(hx + hr - 3, hy + hr + 1, hx + hr - 1, hy + hr + 4, rM)

    headwear(ov, role, hx, hy, hr, back, 'over')

    if clip == 'return_tired' and f == 1:                 # S15 — 후 하고 내쉬는 숨(투구 밖)
        ov.set(int(round(hx + hr + 1)), int(round(fy + 2)), 'cream')
        ov.set(int(round(hx + hr + 2)), int(round(fy + 1)), 'creamD')
    if pc == 'work' and f == 1 and not back:             # 일하는 티 (C7)
        ov.set(wr[0] + 4, wr[1] - 8, 'cream')
        ov.set(wr[0] + 5, wr[1] - 10, 'creamD')

    aL = {
        'role': role, 'body': body, 'kid': kid, 'clip': clip, 'f': f,
        'hx': hx, 'hy': hy, 'hr': hr, 'fy': fy, 'fr': fr,
        'cx': cx, 'neck_y': neck_y, 'torso_rx': torso_rx, 'belt_y': belt_y,
        'ax_l': int(ax_l), 'ax_r': int(ax_r),
        'sad': (clip == 'hurt'),
        'head_top': (int(hx), int(head_top)),
        'forehead': (int(hx), int(round(fy - fr + 1.2))),
        'temple_l': (int(round(hx - fr - .4)), int(round(fy - 1))),
        'temple_r': (int(round(hx + fr - .6)), int(round(fy - 1))),
        # 「지킨 자」 흉터 — S9에서 1px 아래·안쪽으로 내렸다. 광대 높이(홍조 줄)에
        # 있으면 얼굴 레이어 3종과 픽셀을 다툰다(자동 검사에서 잡혔다).
        'cheek_r': (int(round(hx + fr - 2.2)), int(round(fy + 3))),
        'neck_l': (int(round(cx - torso_rx + 2)), int(neck_y - 2)),
        'collar_r': (int(round(cx + torso_rx - 4)), int(neck_y + 1)),
        'chest': (int(cx), int(neck_y + 3)),
        'arm_l': (int(ax_l), int(neck_y + 5)),
        'wrist_r': (int(wr[0]), int(wr[1] - 2)),
        'mitten_l': (int(wl[0]), int(wl[1])),
        'belt_c': (int(cx + (4 if not kid else 0)), int(belt_y + 1)),
        'face_shown': (not back),
    }
    if q34:                              # S12-B 3/4 왼쪽 — 얼굴 쪽 앵커를 돌린 얼굴에 맞춘다
        t0_ = min(q_win)
        lo1, hi1 = q_win[t0_ + 1]
        aL.update({'q34': True, 'view': 'q34_left', 'win': q_win, 'ey': q_ey,
                   'rim': int(round(hy + hr)),
                   'temple_r': (q_win[q_ey][1] + 1, q_ey),            # 가까운 관자놀이 = 창 뒤 테
                   'cheek_r': ((q_win[q_ey + 3][1] - 1, q_ey + 3) if not kid
                               else (q_win[q_ey + 4][1], q_ey + 4)),
                   'forehead': ((lo1 + hi1) // 2, t0_ + 1)})
        # 베일은 정면 식(머리 왼쪽)에 둔다 — 뒤통수(오른쪽)는 묶은 머리 매듭·두건 꼬리 자리라 부딪친다
        if kid:                          # 아이: 목덜미 자국을 목 실링 줄로 내리고 1px 비킨다(돌린 얼굴 창이 턱까지 내려온다)
            aL['neck_l'] = (aL['neck_l'][0] - 2, int(neck_y) + 1)
        # 머리 뒤 베일은 맨 뒤(IMPRINT_FRONT 1) — 목덜미 자국과 겹치면 베일이 비킨다
        aL['side_cut'] = {'*': set(), 'sun_memory': _imprint_raw('spore_mark', aL).pixels()}
        s11_hide.update(Q34_HIDE)
        aL['hide'] = set(Q34_HIDE)
    if clip == 'idle_glance' and f == 2:  # 고개는 돌아왔고 눈만 아직 왼쪽
        aL['eye_dx'] = -1
    if clip == 'return_tired':            # S15 — 반쯤 감은 눈 → 웃으며 감은 눈
        aL['tired'] = f + 1
    if s11:
        front = s11_anc.pop('_front')
        armc = s11_anc.pop('_arm')
        fxc = s11_anc.pop('_fx')
        # 각인은 몸에 붙은 것이다 — 몸 옆·뒤 설비 위 허공에 그려질 수 없다 → 보이는 설비 픽셀에서 잘라 낸다.
        fixvis = set(p_ for p_ in fxc.pixels() if c.own(*p_) == fxc.own(*p_) and ov.own(*p_) is None)
        armvis = set(p_ for p_ in armc.pixels() if c.own(*p_) == armc.own(*p_) and ov.own(*p_) is None)
        aL['clip_px'] = fixvis
        # 「햇빛의 기억」 베일은 머리 **뒤**로 늘어진다 — 일하는 팔·장갑 뒤로 숨는다.
        aL['behind_px'] = armvis | s11_mit.pixels() | fixvis
        aL.update(s11_anc)
        aL['face_shown'] = not (back or turn)
        # 몸 **앞에** 든 물건(담요·상자·붕대…)이 가린 부위의 각인은 그 프레임에서 끈다.
        # 옆·뒤의 설비(fixture)와 겹치는 각인은 끄지 않는다 — 그건 설계 오류로 검사에서 잡는다.
        fp = front.pixels() - s11_mit.pixels()
        aL['front_px'] = fp
        if back:                     # 관자놀이 각인은 얼굴 쪽 — 등 돌린 프레임에서는 안 보인다
            s11_hide.update({'knock_heard', 'depth_mark'})
        aL['hide'] = set()
        for _iid, _k, _p, _c in IMPRINTS:
            if imprint_layer(_iid, aL).pixels() & fp:
                s11_hide.add(_iid)
        aL['hide'] = set(s11_hide)
        aL['obj_cv'] = s11_obj          # 방 설비·손에 든 물건(장갑 제외) — 검사용
        aL['mit_px'] = s11_mit.pixels()
    return c, ov, aL


def ey_of(fy):
    """눈 윗줄 — 얼굴 레이어와 안경이 같은 수를 써야 하므로 함수 하나로 묶었다."""
    return int(round(fy + .4))


# ── 머리 레이어 6종 (본체와 분리 — 어느 체형·어느 역할에도 얹힌다) ──────
def hair_layer(hid, a, base):
    """머리카락 한 벌을 투명 레이어로. 6종 전부 **같은 정수리 띠**로 시작하므로
    기본(short)으로 구워 낸 시트 위에 얹으면 기본 머리가 완전히 덮인다."""
    if a.get('_r') is not None:          # S12-B 옆모습 작업 — 오른쪽 몸 기준으로 그려 뒤집는다
        return mirror_cv(hair_layer(hid, a['_r'], mirror_cv(base)))
    if a.get('side'):                    # S12 옆모습 — 옆에서 본 머리 6종
        return hair_layer_side(hid, a, base)
    if a.get('q34'):                     # S12-B 3/4 왼쪽
        return hair_layer_q34(hid, a, base)
    c = Cv(stencil=base)
    hx, hy, hr = a['hx'], a['hy'], a['hr']
    fy, fr = a['fy'], a['fr']
    cx, neck_y, trx = a['cx'], a['neck_y'], a['torso_rx']
    face = a['face_shown']
    cr = 'cream' if hid == 'scarf' else 'hair'
    crD = 'creamD' if hid == 'scarf' else 'hairD'

    # ① 정수리 띠 — 여섯 종 공통. S8이 본체에 직접 그리던 두 줄과 같은 식이다.
    if face:
        c.ell_in(hx, fy - fr + 1.2, fr - .4, 2.1, cr, only=('skin', 'skinD'))
        c.ell_in(hx - 1.8, fy - fr + .6, fr - 2.2, 1.4, crD, only=(cr,))
        if hid == 'curly':                                  # 울퉁불퉁한 윗선
            for dx in (-4, -1, 2, 5):
                c.ell_in(hx + dx, fy - fr + 2.6, 1.3, 1.3, cr, only=('skin', 'skinD'))
            c.set(hx - 5, fy - fr + 3, crD); c.set(hx + 4, fy - fr + 3, crD)
    elif hid == 'scarf':                                    # 뒷모습도 천으로 덮는다
        c.ell_in(hx, fy - 1.0, fr + .6, fr - 1.0, cr, only=('hair', 'hairD', 'suitH'))
        c.ell_in(hx - 1.6, fy - 2.4, fr - 1.0, 1.6, crD, only=(cr,))

    # ② 갈래 — **투구 테 아래**에서만 나온다.
    #    투구 위(= 역할이 사는 자리)는 절대 건드리지 않는다. 그래서 머리가 바뀌어도
    #    「머리에 쓴 것」으로 역할을 읽는 규칙(C1)이 흐려지지 않는다.
    rim = int(round(hy + hr))          # 투구 아랫단 = 목 실링 바로 위
    # 몸 위로 내려오는 갈래는 **어두운 쪽을 속심**으로 쓴다. 겉옷 색이 역할마다
    # 다르므로(올리브·크림·숯·황토…) 밝은 머리색이면 어떤 겉옷에서는 묻힌다.
    core, hi = (cr, crD) if hid == 'scarf' else (crD, cr)
    if hid == 'tied':
        c.ell(hx + hr - 1, rim - 2, 2.4, 2.2, core)         # 오른쪽 매듭
        c.ell_in(hx + hr - 2, rim - 3, 1.6, 1.3, hi, only=(core,))
        c.rect(hx + hr, rim, hx + hr + 1, rim + 3, core)    # 짧은 꽁지
        c.set(hx + hr + 1, rim + 4, hi)
    elif hid == 'long':
        for sx in (a['ax_l'] + 5, a['ax_r'] - 3):
            c.rect(sx, neck_y + 3, sx + 1, neck_y + 7, core)  # 어깨 앞으로 내린 두 갈래
            c.rect(sx, neck_y + 3, sx, neck_y + 6, hi)
            c.set(sx + 1, neck_y + 7, core)
    elif hid == 'braid':
        # 팔 **안쪽**에 둔다. 어깨 바깥에 두면 체형 B의 팔이 덮어 사라진다(눈으로 보고 고쳤다).
        bx = a['ax_l'] + 5
        for k in range(3):                                  # 왼쪽 어깨 위 세 마디 땋음
            yy = neck_y + 1 + k * 2
            c.rect(bx, yy, bx + 1, yy + 1, core)
            c.set(bx + (k % 2), yy, hi)
        c.set(bx, neck_y + 7, core)                         # 끝은 carry 상자 윗단(+8) 위에서 멈춘다
    elif hid == 'curly':
        for sx in (hx - fr + 2.0, hx + fr - 2.0):           # 이마 양끝 곱슬 두 점
            c.ell_in(sx, fy - fr + 3.4, 1.5, 1.4, cr, only=('skin', 'skinD'))
            c.set(sx, fy - fr + 4, crD)
    elif hid == 'scarf':
        # 왼쪽으로 비껴 내려 묶은 두건 — 베일 각인(머리 왼쪽 바깥)과 자리를 다투지
        # 않도록 **얼굴 구멍 안쪽**에만 머문다.
        for yy in range(int(round(fy - fr + 3)), int(round(fy - fr + 6))):
            for xx in range(int(round(hx - fr)), int(round(hx - fr + 4))):
                if c.get(xx, yy) in ('skin', 'skinD'):
                    c.set(xx, yy, cr if (xx + yy) % 3 else crD)
    return c


# ── 얼굴 레이어 3종 (성별과 무관하다. 누구에게나 아무거나 붙는다) ────────
def face_layer(fid, a, base, hair=None):
    """눈·눈썹·입·홍조. 본체와 분리되어 있어 머리 6종과 자유 조합된다."""
    c = Cv(stencil=base)
    if hair is not None:                 # 홍조 판정이 머리카락 아래를 보면 안 된다
        st = Cv(stencil=base); st.blit(hair); c.stencil = st
    if a.get('_r') is not None:          # S12-B 옆모습 작업
        st = Cv()
        st.blit(base)
        if hair is not None:
            st.blit(hair)
        return mirror_cv(face_layer(fid, a['_r'], mirror_cv(st)))
    if not a['face_shown']:
        return c
    if a.get('side'):                    # S12 옆모습 — 눈 하나·눈썹·입·코·홍조
        return face_layer_side(fid, a, c)
    if a.get('q34'):                     # S12-B 3/4 왼쪽 — 먼 눈은 한 줄, 가까운 눈은 크게
        return face_layer_q34(fid, a, c)
    hx, fy, fr = a['hx'], a['fy'], a['fr']
    sad = a['sad']
    ey = ey_of(fy)

    edx = a.get('eye_dx', 0)             # S12-B idle_glance f2 — 눈만 왼쪽(기존 행은 0)
    tired = a.get('tired', 0)            # S15 return_tired — 0 이면 기존과 같다

    def eye(c_, x_, y_, w_=3, h_=3):
        if tired == 1:                   # 반쯤 감은 눈 — 윗줄이 눈꺼풀로 내려온다
            return _eye_base(c_, x_, y_ + 1, w_, 2)
        if tired == 2:                   # 웃으며 감은 눈 — 가운데가 올라간 한 획
            for i_ in range(w_):
                mid = (0 < i_ < w_ - 1) or (w_ == 2 and i_ == 1)
                c_.set(x_ + i_, y_ + (1 if mid else 2), 'ink')
            return None
        return _eye_base(c_, x_, y_, w_, h_)
    if fid == 'f0':                      # S8의 얼굴 그대로 (기본값)
        ew = 3
        exl = int(round(hx - 4.5)) + edx; exr = int(round(hx + 1.5)) + edx
        brow(c, exl, ey - 3 + (1 if sad else 0), ew, 'l')
        brow(c, exr, ey - 3 + (1 if sad else 0), ew, 'r')
        eye(c, exl, ey, ew, 2 if sad else 3)
        eye(c, exr, ey, ew, 2 if sad else 3)
        c.set(hx, ey + 3, 'skinD')
        smile(c, hx, ey + 4, 2, sad=sad)
        blush(c, int(hx - 6), int(hx - 5), ey + 2)
        blush(c, int(hx + 5), int(hx + 6), ey + 2)
    elif fid == 'f1':                    # 좁고 긴 눈 · 바깥이 올라간 눈썹 · 작은 입
        exl = int(round(hx - 4)) + edx; exr = int(round(hx + 2)) + edx
        for i in range(3):               # 바깥이 올라간 눈썹
            c.set(exl - 1 + i, ey - 3 + (1 if sad else 0) + (1 if i == 2 else 0), 'ink')
            c.set(exr + i, ey - 3 + (1 if sad else 0) + (1 if i == 0 else 0), 'ink')
        eye(c, exl, ey, 2, 2 if sad else 3)
        eye(c, exr + 1, ey, 2, 2 if sad else 3)
        c.set(hx, ey + 3, 'skinD')
        smile(c, hx, ey + 4, 1, sad=sad)
        for fx, fyy in ((-3, 2), (-1, 3), (3, 2)):          # 주근깨
            if c.get(hx + fx, ey + fyy) in ('skin', 'skinD'):
                c.set(hx + fx, ey + fyy, 'skinD')
        blush(c, int(hx - 6), int(hx - 5), ey + 2)
        blush(c, int(hx + 5), int(hx + 6), ey + 2)
    else:                                # f2 — 넓게 벌어진 눈 · 안쪽이 내려온 눈썹
        ew = 3
        # 아이는 얼굴이 작다. 고정 간격으로 벌리면 관자놀이 각인과 부딪친다
        # (자동 검사에서 잡혔다) → 얼굴 반지름에 비례해 벌린다.
        exl = int(round(hx - (fr - 0.3))) + edx; exr = int(round(hx + (fr - 3.3))) + edx
        for i in range(ew):
            c.set(exl + i, ey - 3 + (1 if sad else 0) + (1 if i == 0 else 0), 'ink')
            c.set(exr + i, ey - 3 + (1 if sad else 0) + (1 if i == ew - 1 else 0), 'ink')
        eye(c, exl, ey, ew, 2 if sad else 3)
        eye(c, exr, ey, ew, 2 if sad else 3)
        c.set(hx, ey + 3, 'skinD')
        smile(c, hx, ey + 4, 1, sad=sad)             # 작고 넓게 번지는 입
        c.set(hx - 2, ey + 3 + (1 if sad else 0), 'ink')
        c.set(hx + 2, ey + 3 + (1 if sad else 0), 'ink')
        blush(c, int(hx - 5), int(hx - 5), ey + 3)
        blush(c, int(hx + 5), int(hx + 5), ey + 3)
    return c


# ── S12: 옆모습의 머리 6종 · 얼굴 3종 ─────────────────────────────────────
#   규칙은 앞모습과 같다: ①여섯 종 모두 **같은 앞머리 띠 + 귀밑머리**로 시작한다(기본 short 가 완전히 덮인다)
#   ②갈래는 투구 테 아래(뒤통수 밑)에서만 나온다 ③얼굴 픽셀과 머리 픽셀은 한 칸도 겹치지 않는다
#   — 그래야 머리 패치와 얼굴 패치를 **함께** 얹어도 그 조합이 그대로 나온다(생성기가 18조합 전수 검사).
def hair_layer_side(hid, a, base):
    c = Cv(stencil=base)
    win, ey = a['win'], a['ey']
    hx, hr, rim = a['hx'], a['hr'], a['rim']
    kid = a['kid']
    cr = 'cream' if hid == 'scarf' else 'hair'
    crD = 'creamD' if hid == 'scarf' else 'hairD'
    core, hi = (cr, crD) if hid == 'scarf' else (crD, cr)
    SK = ('skin', 'skinD')
    t0 = min(win)
    # ① 공통: 앞머리 띠(창 윗줄 ~ 눈썹 위) + 귀밑머리(창 뒤 두 칸, 눈썹 줄 ~ 눈 아래)
    band = list(range(t0, min(ey - 3, t0 + 2)))      # 두 줄 — 창이 작아 얼굴 자리를 남긴다
    for yy in band:
        lo, hi_ = win[yy]
        for xx in range(lo, hi_ + 1):
            if c.get(xx, yy) in SK:
                c.set(xx, yy, crD if (yy == band[-1] and xx <= lo + 1) else cr)
    for yy in range(band[-1] + 1, ey + 1):
        lo = win[yy][0]
        pts = ((lo, crD), (lo + 1, cr)) if yy <= ey - 2 else ((lo, crD),)
        for xx, t in pts:
            if c.get(xx, yy) in SK:
                c.set(xx, yy, t)
    bx = int(round(hx - hr))                         # 뒤통수 바깥선
    if hid == 'tied':                                # 뒤통수 밑 매듭 + 짧은 꽁지
        kx = bx + 3
        c.ell(kx + .5, rim - .5, 2.2, 2.0, core)
        c.ell_in(kx, rim - 1.2, 1.3, 1.0, hi, only=(core,))
        c.rect(kx - 1, rim + 1, kx, rim + 3, core)
        c.set(kx - 1, rim + 4, hi)
    elif hid == 'long':                              # 등으로 곧게 내린 머리
        L = 7 if not kid else 5
        c.rect(bx + 2, rim - 2, bx + 4, rim + L, core)
        c.rect(bx + 2, rim - 2, bx + 2, rim + L - 1, hi)
        c.set(bx + 4, rim + L, hi)
    elif hid == 'braid':                             # 등으로 내린 세 마디 땋음 + 붉은 끈
        for k in range(3 if not kid else 2):
            yy = rim - 1 + k * 3
            c.rect(bx + 3, yy, bx + 4, yy + 2, core)
            c.set(bx + 3 + (k % 2), yy, hi)
        yy = rim - 1 + (3 if not kid else 2) * 3
        c.set(bx + 3, yy, 'ox'); c.set(bx + 4, yy, 'ox')
        c.set(bx + 4, yy + 1, core)
    elif hid == 'curly':                             # 앞머리 끝이 창 테를 넘고, 귀밑머리에 곱슬 한 덩이
        lo0, hi0 = win[t0 + 1]
        c.set(hi0 + 1, t0 + 1, cr); c.set(hi0 + 1, t0, crD)
        lo1 = win[ey - 3][0]
        c.set(lo1 + 2, ey - 3, cr); c.set(lo1 + 2, ey - 2, crD)
        c.set(win[t0][0] - 1, t0, cr)
    elif hid == 'scarf':                             # 두건 매듭 꼬리 — 뒤통수 밑으로
        kx = bx + 2
        c.rect(kx, rim - 2, kx + 2, rim - 1, cr)
        c.rect(kx - 1, rim, kx, rim + 2, crD)
        c.set(kx + 1, rim, cr)
    return c


def face_layer_side(fid, a, c):
    """옆얼굴 — 눈 하나(크다: 2×3), 눈썹 한 획, 입, 홍조. 코는 본체(창 테를 1px 넘는 살)."""
    win, ey = a['win'], a['ey']
    kid = a['kid']
    xf = win[ey][1]
    xm = win[ey + 4][1]
    ym = ey + 4

    def eye_side(ex, y0, h):
        c.rect(ex, y0, ex + 1, y0 + h - 1, 'ink')
        c.set(ex + 1, y0, 'white')                   # 앞쪽 위 반짝임
    if fid == 'f0':                                  # 둥근 눈 · 곧은 눈썹 · 웃는 입
        ex = xf - 2
        eye_side(ex, ey, 3)
        c.set(ex, ey - 3, 'ink'); c.set(ex + 1, ey - 3, 'ink')
        c.set(xm - 1, ym, 'ink'); c.set(xm, ym, 'ink'); c.set(xm - 2, ym - 1, 'ink')
        blush(c, xm - 3, xm - 3, ey + 2); blush(c, xm - 3, xm - 3, ey + 3)
    elif fid == 'f1':                                # 좁은 눈 · 올라간 눈썹 · 작은 입 · 주근깨
        ex = xf - 2
        eye_side(ex, ey + 1, 2)
        c.set(ex - 1, ey - 2, 'ink'); c.set(ex, ey - 3, 'ink'); c.set(ex + 1, ey - 3, 'ink')
        c.set(xm, ym, 'ink'); c.set(xm - 1, ym, 'ink')
        blush(c, xm - 3, xm - 3, ey + 2)
        for fx_, fy_ in ((xm - 2, ey + 3), (win[ey + 1][0] + 2, ey + 1)):
            if c.get(fx_, fy_) in ('skin', 'skinD'):
                c.set(fx_, fy_, 'skinD' if c.get(fx_, fy_) == 'skin' else 'blush')
    else:                                            # f2 — 뒤로 물러난 눈 · 앞이 내려온 눈썹 · 넓은 입
        ex = xf - 3
        eye_side(ex, ey, 3)
        c.set(ex - 1, ey - 3, 'ink'); c.set(ex, ey - 3, 'ink'); c.set(ex + 1, ey - 2, 'ink')
        c.set(xm - 2, ym, 'ink'); c.set(xm - 1, ym, 'ink'); c.set(xm, ym, 'ink')
        blush(c, xm - 3, xm - 3, ey + 3)
    return c


# ── S12-B: 3/4 왼쪽의 머리 6종 · 얼굴 3종 ────────────────────────────────
#   옆모습과 같은 규칙: 공통 앞머리 띠 + 귀밑머리(뒤 = 오른쪽)로 시작, 얼굴과 머리 픽셀은 겹치지 않는다.
#   묶은·긴·땋은 머리의 갈래는 몸에 붙은 것이라 정면 식을 그대로 쓴다(투구 테 아래).
def hair_layer_q34(hid, a, base):
    c = Cv(stencil=base)
    win, ey = a['win'], a['ey']
    hx, hr, rim = a['hx'], a['hr'], a['rim']
    neck_y = a['neck_y']
    cr = 'cream' if hid == 'scarf' else 'hair'
    crD = 'creamD' if hid == 'scarf' else 'hairD'
    core, hi = (cr, crD) if hid == 'scarf' else (crD, cr)
    SK = ('skin', 'skinD')
    t0 = min(win)
    band = list(range(t0, min(ey - 3, t0 + 2)))
    for yy in band:
        lo, hi_ = win[yy]
        for xx in range(lo, hi_ + 1):
            if c.get(xx, yy) in SK:
                c.set(xx, yy, crD if (yy == band[-1] and xx >= hi_ - 1) else cr)
    for yy in range(band[-1] + 1, ey + 1):
        hi_ = win[yy][1]
        pts = ((hi_, crD), (hi_ - 1, cr)) if yy <= ey - 2 else ((hi_, crD),)
        for xx, t in pts:
            if c.get(xx, yy) in SK:
                c.set(xx, yy, t)
    rim_ = int(round(a['hy'] + hr))
    if hid == 'tied':                                # 정면과 같은 오른쪽 매듭(= 뒤통수 쪽)
        c.ell(hx + hr - 1, rim_ - 2, 2.4, 2.2, core)
        c.ell_in(hx + hr - 2, rim_ - 3, 1.6, 1.3, hi, only=(core,))
        c.rect(hx + hr, rim_, hx + hr + 1, rim_ + 3, core)
        c.set(hx + hr + 1, rim_ + 4, hi)
    elif hid == 'long':
        for sx in (a['ax_l'] + 5, a['ax_r'] - 3):
            c.rect(sx, neck_y + 3, sx + 1, neck_y + 7, core)
            c.rect(sx, neck_y + 3, sx, neck_y + 6, hi)
            c.set(sx + 1, neck_y + 7, core)
    elif hid == 'braid':
        bx = a['ax_l'] + 5
        for k in range(3):
            yy = neck_y + 1 + k * 2
            c.rect(bx, yy, bx + 1, yy + 1, core)
            c.set(bx + (k % 2), yy, hi)
        c.set(bx, neck_y + 7, core)
    elif hid == 'curly':
        lo0 = win[t0 + 1][0]
        c.set(lo0 - 1, t0 + 1, cr); c.set(lo0 - 1, t0, crD)
        hi1 = win[ey - 3][1]
        c.set(hi1 - 2, ey - 3, cr); c.set(hi1 - 2, ey - 2, crD)
    elif hid == 'scarf':                             # 두건 매듭 꼬리 — 뒤통수 밑(오른쪽)
        kx = int(round(hx + hr - 1))                 # 옷깃(아낀 숨 고리) 위에서 멈춘다
        c.rect(kx - 1, rim_ - 3, kx + 1, rim_ - 2, cr)
        c.rect(kx + 1, rim_ - 1, kx + 2, rim_, crD)
    return c


def face_layer_q34(fid, a, c):
    win, ey = a['win'], a['ey']
    kid = a['kid']
    lo = win[ey][0]
    nx = lo + (5 if (fid == 'f2' and not kid) else 4)        # 가까운 눈
    c.set(lo + 2, ey + 3, 'skinD')                           # 코끝(먼 볼 쪽)
    if fid == 'f0':
        c.rect(lo + 1, ey, lo + 1, ey + 2, 'ink')            # 먼 눈 — 한 줄
        eye(c, nx, ey, 3, 3)
        c.set(lo + 1, ey - 3, 'ink')
        for i in range(3):
            c.set(nx + i, ey - 3, 'ink')
        smile(c, lo + 3, ey + 4, 1)
        blush(c, nx + 3, nx + 4, ey + 2)
    elif fid == 'f1':
        c.rect(lo + 1, ey + 1, lo + 1, ey + 2, 'ink')
        eye(c, nx, ey, 2, 3)
        c.set(lo + 1, ey - 3, 'ink')
        c.set(nx, ey - 3, 'ink'); c.set(nx + 1, ey - 3, 'ink'); c.set(nx + 2, ey - (3 if kid else 4), 'ink')   # 아이는 ey-4 가 앞머리 띠
        c.set(lo + 3, ey + 4, 'ink'); c.set(lo + 4, ey + 4, 'ink')
        blush(c, nx + 3, nx + 4, ey + 2)
        for fx_, fy_ in ((nx + 1, ey + 3), (nx + 3, ey + 3)):
            if c.get(fx_, fy_) == 'skin':
                c.set(fx_, fy_, 'skinD')
    else:
        c.rect(lo + 1, ey, lo + 1, ey + 2, 'ink')
        eye(c, nx, ey, 3, 3)
        c.set(lo + 1, ey - 3, 'ink')
        c.set(nx, ey - 2, 'ink'); c.set(nx + 1, ey - 3, 'ink'); c.set(nx + 2, ey - 3, 'ink')
        for xx in (lo + 2, lo + 3, lo + 4):
            c.set(xx, ey + 4, 'ink')
        c.set(lo + 1, ey + 3, 'ink'); c.set(lo + 5, ey + 3, 'ink')
        blush(c, nx + 3, nx + 3, ey + 3)
    return c


# ── S15-D: 잠수복 겹(suit) — 원정 나갈 때 얹는다 ─────────────────────────
#   주민은 이미 잠수복 + 놋쇠 투구(면갑을 올린 상태)를 입고 있다. 바깥으로 나갈 때 달라지는 것만 겹으로 낸다:
#     ① 면갑 유리 — 얼굴 창 테 안쪽 가장자리가 유리빛으로 + 반짝임 한 점(유리를 내렸다)
#     ② 투구 등불 — 어둠 속 랜턴 하나(스스로 빛남, 틴트 금지 색)
#     ③ 발목 납 띠 — 무게추로 해저를 걷는다(DECISIONS 2026-09-22)
#     ④ 거품 — 투구 앞에서 오른다(프레임마다 높이가 다르다)
#   규칙: 이 겹의 픽셀은 **머리 6종 · 얼굴 3종(18조합) · 각인 12종 어느 픽셀과도 겹치지 않는다**(생성기가 전수 검사).
#   그래서 얼굴(눈·눈썹·입)은 유리 너머로 그대로 보이고, 머리·얼굴 조합 규칙도 그대로 성립한다.
SUIT_WIN = ('skin', 'skinD', 'hair', 'hairD', 'suitH')
_SUIT = {}


def suit_forbid(role, clip, f, body):
    base, ov, a = raw_of(role, clip, f, body)
    fb = set()
    for hid, _k, _n in HAIRS:
        hl = hair_layer(hid, a, base)
        fb |= hl.pixels()
        for fid, _k2, _n2 in FACES:
            fb |= face_layer(fid, a, base, hl).pixels()
    srole = 'kid' if role == 'kid' else 'scout'
    _b, _o, ai = raw_of(srole, clip, f, body)
    for iid, _k, _p, _c in IMPRINTS:
        fb |= imprint_layer(iid, ai).pixels()
    # 머리 변형이 실루엣을 넓히면 외곽선도 따라 바뀐다 — 18조합이 기본에서 바꾸는 칸 전부를 비켜야 한다
    d0 = img_of(role, clip, f, body, 'short', 'f0').img().load()
    for hid, _k, _n in HAIRS:
        for fid, _k2, _n2 in FACES:
            if hid == 'short' and fid == 'f0':
                continue
            v = img_of(role, clip, f, body, hid, fid).img().load()
            for y in range(CELL):
                for x in range(CELL):
                    if v[x, y] != d0[x, y]:
                        fb.add((x, y))
    return fb


def suit_layer(role, clip, f, body):
    k = (role, clip, f, body)
    if k in _SUIT:
        return _SUIT[k]
    base, ov, a = raw_of(role, clip, f, body)
    comp = build(role, clip, f, body)[0]
    fb = suit_forbid(role, clip, f, body)
    hx, hy, hr = a['hx'], a['hy'], a['hr']
    view = ('right' if (clip in SIDE_IDS or clip in S15_SIDE) else
            ('left' if clip in TURN_PROFILE else 'front'))
    sc = Cv()
    # ① 면갑 유리 — 창 가장자리(테에 닿은 칸) 중 머리·얼굴·각인이 한 번도 오지 않는 칸
    ring = []
    for (x, y) in base.pixels():
        if base.own(x, y) in SUIT_WIN and ov.own(x, y) is None and math.hypot(x - hx, y - hy) <= hr - 0.5:
            if any(base.own(x + dx, y + dy) == 'brassD' for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                if (x, y) not in fb:
                    ring.append((x, y))
    for (x, y) in ring:
        sc.set(x, y, 'glass')
    if ring:
        g = max(ring, key=(lambda q: -q[0] - q[1]) if view == 'left' else (lambda q: q[0] - q[1]))
        sc.set(g[0], g[1], 'white')
    # ② 투구 등불(2×2 + 놋쇠 테)
    #    자리 후보를 차례로 시험해 머리·얼굴·각인과 겹치지 않는 첫 자리에 단다(없으면 그 칸은 등불 없음)
    if view == 'front':
        cands = [(hx - hr, hy - 2), (hx - hr, hy - 4), (hx - hr + 1, hy + 2), (hx + hr - 2, hy - 4)]
    elif view == 'right':
        cands = [(hx - 3, hy + 3), (hx - 5, hy + 1), (hx - 4, hy - 2), (hx - 1, hy - 4)]
    else:
        cands = [(hx + 2, hy + 3), (hx + 4, hy + 1), (hx + 3, hy - 2), (hx, hy - 4)]
    for (cx_, cy_) in cands:
        lx, ly = int(round(cx_)), int(round(cy_))
        lamp = ((lx, ly, 'flame'), (lx + 1, ly, 'flame'), (lx, ly + 1, 'flameR'), (lx + 1, ly + 1, 'flameR'),
                (lx - 1, ly, 'brassD'), (lx - 1, ly + 1, 'brassD'))
        if not any((x, y) in fb for x, y, _t in lamp):
            for (x, y, t) in lamp:
                sc.set(x, y, t)
            break
    # ③ 발목 납 띠 — 장화 바로 위 한 줄(가까운 장화만 — 먼 장화는 그늘색이라 잡히지 않는다)
    for (x, y) in base.pixels():
        if base.own(x, y) in ('bootM', 'bootL') and base.own(x, y - 1) in ('suitD', 'suitM', 'suitL') \
                and (x, y - 1) not in fb:
            sc.set(x, y - 1, 'tank')
    # ④ 거품 — 빈 칸에만(모자·도구 실루엣을 가리지 않는다)
    x0 = int(round(hx + hr + 2)) if view != 'left' else int(round(hx - hr - 3))
    ph = (f * 3) % 7
    y0 = int(a['head_top'][1]) + 4 - ph
    for (x, y, t) in ((x0, y0, 'white'), (x0 + 1, y0, 'glass'), (x0 + (1 if view != 'left' else -1), y0 - 5, 'glass')):
        if 0 <= x < CELL and 0 <= y < CELL and comp.own(x, y) is None and (x, y) not in fb:
            sc.set(x, y, t)
    _SUIT[k] = sc
    return sc


# ── 조립 ─────────────────────────────────────────────────────────────────
_RAW = {}


def raw_of(role, clip, f, body):
    k = (role, clip, f, body)
    if k not in _RAW:
        _RAW[k] = build_raw(role, clip, f, body)
    return _RAW[k]


def build(role, clip='idle', f=0, body='a', hair='short', face='f0'):
    """한 프레임을 조립한다. (캔버스, 앵커)를 돌려준다.
    기본 인자(body='a', hair='short', face='f0')는 **S8 결과와 픽셀이 같다**."""
    base, ov, a = raw_of(role, clip, f, body)
    hl = hair_layer(hair, a, base)
    fl = face_layer(face, a, base, hl)
    c = Cv()
    c.blit(base).blit(hl).blit(fl).blit(ov)
    c.outline('line')
    return c, a


# ── 각인 12종 (C4 — 부위를 나눠 3개 동시에도 안 겹친다) ────────────────
IMPRINTS = [
    ('spore_mark',  '포자의 표식', '목덜미 왼쪽', '녹색'),
    ('empty_stomach', '빈 위장', '허리띠 오른쪽 매듭', '올리브·놋쇠'),
    ('warden',      '지킨 자', '오른 광대', '적갈'),
    ('sun_memory',  '햇빛의 기억', '머리 뒤로 늘어진 베일', '바랜 크림'),
    ('empty_seat',  '빈 자리', '왼 위팔', '숯검정'),
    ('footprint',   '발자국', '가슴 중앙 목걸이', '흰 이빨'),
    ('debt_paid',   '갚은 자', '오른 손목', '놋쇠'),
    ('water_memory', '물의 기억', '이마 앞머리', '젖은 머리 + 반짝임'),
    ('saved_breath', '아낀 숨', '오른 옷깃 호스 고리', '구릿빛'),
    ('crack_seen',  '금을 본 자', '왼 장갑 끝', '유리빛'),
    ('depth_mark',  '깊이의 자국', '왼 관자놀이', '자줏빛'),
    ('knock_heard', '두드림을 들은 자', '오른 관자놀이 울림쇠', '놋쇠 + 흰 점'),
]


def imprint_layer(iid, a):
    """각인 하나를 투명 레이어로. 본체와 같은 64×64 셀, 같은 자리에 겹치면 된다."""
    c = _imprint_raw(iid, a)
    cut = set()
    if 'clip_px' in a:                       # S11 행만 — 기존 7행은 이 키가 없어 그대로
        cut |= a['clip_px']
    if iid == 'sun_memory' and 'behind_px' in a:
        cut |= a['behind_px']
    if 'side_cut' in a:                       # S12 옆모습 — 몸 앞으로 온 팔·장갑·도구·상자가 가린 칸
        cut |= a['side_cut'].get(iid, a['side_cut']['*'])
    if a.get('clip') not in S11_IDS and a.get('clip') not in SIDE_IDS and a.get('clip') not in S15_SIDE:   # PM 2026-10-03: 기존 7행 충돌 39건 수리
        cut |= _old_row_cut(iid, a)
    mine = c.pixels()
    for (x, y) in cut:
        if c.own(x, y) is not None:
            c.clear(x, y)
    if 'side_cut' in a and mine and len(c.pixels()) <= 1 and len(mine) > 1:
        c = Cv()                              # 한 점만 남으면 그 프레임에서 끈다(S11 규칙과 같다)
    return c


# 앞에 있는 것이 이긴다(높을수록 앞). 겹친 칸은 뒤에 있는 각인에서 잘라 낸다.
#  손목·장갑(손이 앞) > 목덜미 > … > 팔띠 > 허리 매듭 > 머리 뒤 베일(맨 뒤)
IMPRINT_FRONT = {'crack_seen': 9, 'debt_paid': 8, 'spore_mark': 7, 'footprint': 6,
                 'saved_breath': 6, 'warden': 6, 'water_memory': 6, 'depth_mark': 6,
                 'knock_heard': 5, 'empty_seat': 3, 'empty_stomach': 2, 'sun_memory': 1}
_OLDCUT = {}


def _old_row_cut(iid, a):
    """기존 7행 전용. 각인은 머리카락(6종 어느 것이든)·얼굴 레이어 **아래**로 숨고,
    다른 각인과 겹치면 뒤에 있는 쪽이 비킨다. 본체·머리·얼굴 픽셀은 건드리지 않는다.
    충돌이 없는 프레임(idle f0 포함)은 잘라 낼 것이 없어 결과가 같다."""
    key = (a['role'], a['clip'], a['f'], a['body'], iid)
    if key in _OLDCUT:
        return _OLDCUT[key]
    base, _o, a0 = raw_of(a['role'], a['clip'], a['f'], a['body'])
    mine = _imprint_raw(iid, a0).pixels()
    cut = set()
    if mine:
        if iid not in IMPRINT_ON_HAIR:
            for hid, _k, _n in HAIRS:
                cut |= mine & hair_layer(hid, a0, base).pixels()
        hs = hair_layer('short', a0, base)
        for fid, _k, _n in FACES:
            cut |= mine & face_layer(fid, a0, base, hs).pixels()
        for oid, _k, _p, _c in IMPRINTS:
            if oid != iid and IMPRINT_FRONT.get(oid, 5) > IMPRINT_FRONT.get(iid, 5):
                cut |= mine & _imprint_raw(oid, a0).pixels()
        if cut and len(mine - cut) <= 1:      # 한 점만 남으면 그 프레임에서 통째로 끈다(S11 규칙)
            cut = set(mine)
    _OLDCUT[key] = cut
    return cut


def _imprint_raw(iid, a):
    c = Cv()
    face = a['face_shown']
    if iid in a.get('hide', ()):      # S11: 그 프레임에 물건에 가려진 부위
        return c
    if a.get('_r') is not None and iid in MIRROR_IMPS:     # S12-B 옆모습 작업 — 몸통 쪽 각인은 오른쪽 몸에서 뒤집는다
        return mirror_cv(_imprint_raw(iid, a['_r']))
    if iid == 'spore_mark':
        x, y = a['neck_l']
        c.rect(x, y, x + 1, y, 'impGrn'); c.set(x + 1, y + 1, 'impGrn')
    elif iid == 'empty_stomach':
        x, y = a['belt_c']
        c.rect(x, y, x + 2, y, 'olivD'); c.set(x + 1, y + 1, 'brassM')
    elif iid == 'warden':
        if not face:
            return c
        x, y = a['cheek_r']
        c.set(x, y, 'ox'); c.set(x, y + 1, 'ox'); c.set(x + 1, y + 2, 'ox')
    elif iid == 'sun_memory' and a.get('veil_back'):        # S12-B 3/4 왼쪽 — 베일은 뒤통수(오른쪽)로
        x, y = a['head_top']
        hr = int(a['hr'])
        c.rect(x + hr, y + 10, x + hr + 2, y + 16, 'impPale')
        c.rect(x + hr + 2, y + 13, x + hr + 3, y + 17, 'impPale')
        c.set(x + hr, y + 9, 'impPale')
    elif iid == 'sun_memory':
        x, y = a['head_top']
        hr = int(a['hr'])
        c.rect(x - hr - 2, y + 10, x - hr, y + 16, 'impPale')     # 왼쪽으로 늘어진 베일
        c.rect(x - hr - 3, y + 13, x - hr - 2, y + 17, 'impPale')
        c.set(x - hr, y + 9, 'impPale')
    elif iid == 'empty_seat':
        x, y = a['arm_l']
        c.rect(x, y, x + 2, y + 1, 'impDark')
    elif iid == 'footprint':
        x, y = a['chest']
        c.set(x, y, 'impPale'); c.set(x, y + 1, 'white'); c.set(x, y + 2, 'impPale')
    elif iid == 'debt_paid':
        x, y = a['wrist_r']
        c.rect(x - 1, y, x + 1, y, 'brass'); c.set(x, y + 1, 'brassH')
    elif iid == 'water_memory':
        if not face:
            return c
        x, y = a['forehead']
        c.rect(x - 2, y, x + 2, y, 'hairD'); c.set(x - 1, y - 1, 'white')
    elif iid == 'saved_breath':
        x, y = a['collar_r']
        c.rect(x, y, x + 2, y, 'impCop'); c.set(x + 2, y + 1, 'impCop')
    elif iid == 'crack_seen':
        x, y = a['mitten_l']
        c.set(x - 1, y - 1, 'glass'); c.set(x, y - 2, 'glass'); c.set(x - 2, y, 'glassD')
    elif iid == 'depth_mark':
        # S9: 꼬리를 **바깥쪽**으로 돌렸다. 안쪽으로 뻗으면 아이의 작은 얼굴에서
        # 얼굴 레이어(눈)와 픽셀을 다툰다(자동 검사에서 잡혔다).
        x, y = a['temple_l']
        c.rect(x, y, x, y + 2, 'impPlum')
    elif iid == 'knock_heard':
        x, y = a['temple_r']
        c.rect(x, y, x, y + 1, 'brass'); c.set(x + 1, y + 2, 'white')
    return c


# ── 문어 (식구. 어떤 매체에서도 발화하지 않는다 — DECISIONS 2026-09-27) ──
def build_octopus(pose='idle', f=0):
    """문어 — 식구다. 짐승은 사람보다 가깝고 따뜻하다(C5).
    어떤 매체에서도 발화하지 않는다(DECISIONS 2026-09-27)."""
    c = Cv()
    bob = [0, 1, 0][f % 3]
    body, bodyD, bodyL = 'octM', 'octD', 'octL'
    cx = 30
    cy = FOOT - 13 + bob

    def arm(x0, y0, ang, length, thick, curl, t=None):
        px_, py_ = float(x0), float(y0)
        a = math.radians(ang)
        for k in range(length):
            w = max(0.6, thick * (1.0 - k / float(length)) + .4)
            c.ell(px_, py_, w, w * .85, t or (bodyD if k % 4 == 3 else body))
            if k % 3 == 1 and w > 1.2:                  # 빨판
                c.set(px_, py_ + w * .6, bodyL)
            a += math.radians(curl)
            px_ += math.cos(a); py_ += math.sin(a)

    # 여덟 팔 — 아래로 늘어지고 끝이 말린다
    specs = [(-9, 148, 14, 2.4, 6), (-7, 124, 15, 2.7, 4), (-4, 106, 13, 2.6, 3),
             (-1, 95, 10, 2.2, 2), (1, 85, 10, 2.2, -2), (4, 74, 13, 2.6, -3),
             (7, 56, 15, 2.7, -4), (9, 32, 14, 2.4, -6)]
    for dx, ang, ln, th, cu in specs:
        arm(cx + dx, cy + 6.5, ang + math.sin(f * 1.1 + dx) * 5, ln, th, cu)

    # 외투막(머리처럼 보이는 몸통)
    c.ell(cx, cy, 9.2, 8.4, body)
    c.ell(cx, cy - 5.5, 6.0, 4.4, body)                  # 위로 솟은 부분
    c.ell_in(cx - 2.6, cy - 3.6, 6.4, 5.4, bodyL, only=(body,))
    c.ell_in(cx, cy + 5.6, 9.2, 3.4, bodyD, only=(body, bodyL))
    for dx in (-5, 0, 5, -2, 3):                         # 사마귀 무늬 (반복 무늬)
        c.set(cx + dx, cy + 2 + (dx % 3), bodyD)
    c.rect(cx - 7, cy + 7, cx + 7, cy + 8, bodyD)        # 외투막 아랫단
    c.ell(cx + 7.5, cy - 1.5, 2.2, 2.6, bodyL)           # 숨구멍(사이펀)
    c.set(cx + 8, cy - 2, bodyD)

    # 눈 — 크고 둥글고 사람보다 밝다 (C5). 신뢰의 역전을 눈으로 말한다
    for ex in (cx - 4, cx + 4):
        c.ell(ex, cy + .2, 2.8, 2.6, 'white')
        c.ell(ex, cy + .6, 1.5, 1.5, 'ink')
        c.set(ex - 1, cy - 1, 'white')
    c.ell_in(cx, cy - 2.8, 8.0, 1.4, bodyD, only=(body, bodyL))   # 눈두덩

    if pose == 'wrap':
        # 손목 감기 (J7) — 사람의 손목 하나와, 그 둘레를 세 바퀴 감은 팔
        wx, wy = cx + 20, cy + 1
        c.rect(wx - 2, wy - 9, wx + 4, wy + 4, 'suitM')            # 잠수복 소매
        c.rect(wx - 2, wy - 9, wx, wy + 4, 'suitL')
        mitten(c, wx + 1, wy + 7)                                   # 벙어리 장갑
        for k in range(22):                                         # 뻗어 나간 팔
            t = k / 21.0
            x = cx + 8 + t * 10
            y = cy + 5 - math.sin(t * 2.0) * 5.5
            w = 2.5 - t * 1.1
            c.ell(x, y, w, w * .85, body if k % 4 else bodyD)
        bands = ((wy - 6, 5.2, 0), (wy - 2, 4.6, -1), (wy + 2, 3.8, 1))
        for yy, rw, ox in bands:                                    # 세 바퀴
            c.ell(wx + 1 + ox, yy, rw, 1.5, body)
            c.ell_in(wx + 1 + ox, yy - .6, rw - .6, .9, bodyL, only=(body,))
            c.set(wx + 1 + ox - int(rw), yy + 1, bodyD)
            c.set(wx + 1 + ox + int(rw), yy + 1, bodyD)
        c.set(wx + 6, wy + 3, body); c.set(wx + 7, wy + 2, bodyD)   # 말린 끝
    c.outline('line')
    return c


# ── 출력 ─────────────────────────────────────────────────────────────────
def up(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def to_h(im, hh):
    k = hh / im.height
    return im.resize((max(1, int(round(im.width * k))), hh), Image.NEAREST)


def font(sz=12):
    for name in ('malgun.ttf', 'malgunsl.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(name, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def room_bg(w, h, floor=0.86, light=True):
    im = Image.new('RGB', (w, h), (18, 12, 9))
    px = im.load()
    cx, cy = w * 0.5, h * 0.36
    mr = math.hypot(w, h) * 0.62
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / mr
            k = max(0.0, 1.0 - d) ** 1.7
            if light:
                px[x, y] = (int(96 + 86 * k), int(72 + 70 * k), int(50 + 48 * k))
            else:
                px[x, y] = (int(16 + 44 * k), int(11 + 28 * k), int(9 + 18 * k))
    d = ImageDraw.Draw(im)
    fy = int(h * floor)
    d.rectangle([0, fy, w, h], fill=(142, 108, 70) if light else (27, 18, 13))
    d.line([0, fy, w, fy], fill=(96, 70, 44) if light else (74, 50, 32))
    return im


def sheet_of(cells, k):
    """3열 × 7행 시트. 셀 = CELL*k, 발 기준선 = BASE_Y*k."""
    w, h = CELL * k * MAXF, CELL * k * len(CLIPS)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for (clip, n), row in zip(CLIPS, range(len(CLIPS))):
        for i in range(n):
            one = cells[(clip, i)]
            im.paste(up(one, k) if k > 1 else one, (CELL * k * i, CELL * k * row))
    return im


def mask_sheet_of(cells, k):
    w, h = CELL * k * MAXF, CELL * k * len(CLIPS)
    im = Image.new('L', (w, h), 0)
    for (clip, n), row in zip(CLIPS, range(len(CLIPS))):
        for i in range(n):
            one = cells[(clip, i)]
            im.paste(one.resize((one.width * k, one.height * k), Image.NEAREST) if k > 1 else one,
                     (CELL * k * i, CELL * k * row))
    return im


def trim_sprite(c):
    """외곽 여백을 잘라 낸 실제 스프라이트와 발·머리 좌표."""
    bb = c.bbox()
    im = c.img()
    return im.crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), bb


# ── 체형·머리·얼굴 조합 유틸 (스프린트 9-A) ─────────────────────────────
SHAPES = [('a', 'scout', 'a'), ('b', 'scout', 'b'),
          ('kid', 'kid', 'a'), ('kid_b', 'kid', 'b')]
SHAPE_KO = {'a': '어른 체형 A', 'b': '어른 체형 B',
            'kid': '아이 체형 A', 'kid_b': '아이 체형 B'}
IMP_SUB = {'a': ('imprints',), 'b': ('imprints', 'b'),
           'kid': ('imprints', 'kid'), 'kid_b': ('imprints', 'kid_b')}


def shape_of(role, body):
    return (('kid_b' if body == 'b' else 'kid') if role == 'kid'
            else ('b' if body == 'b' else 'a'))


def sheet_name(role, body):
    """체형 A는 **S8 경로 그대로**(개발이 이미 붙이고 있다). B만 접미사 _b."""
    return role if body == 'a' else role + '_b'


def pick_look(role, body, salt=0):
    """머리·얼굴을 역할과 **무관하게** 고른다. 결정적(같은 입력 → 같은 사람, D6).
    게임에서는 role 대신 uid+주민 id 를 넣는다(RESIDENT_STATS §3 생성 규칙과 같은 꼴)."""
    h = 2166136261
    for ch in (role + '|' + body + '|' + str(salt)):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return HAIRS[h % len(HAIRS)][0], FACES[(h >> 11) % len(FACES)][0]


_IMG = {}


def img_of(role, clip, f, body, hair, face):
    k = (role, clip, f, body, hair, face)
    if k not in _IMG:
        _IMG[k] = build(role, clip, f, body, hair, face)[0]
    return _IMG[k]


def diff_img(d, v):
    """기본 시트(d)와 변형(v)의 차이만 남긴 투명 패치.
    클라이언트가 기본 시트 위에 그대로 알파 합성하면 변형이 된다 — 아래에서 전수 검사한다."""
    out = Image.new('RGBA', d.size, (0, 0, 0, 0))
    dp, vp, op = d.load(), v.load(), out.load()
    for y in range(d.height):
        for x in range(d.width):
            if dp[x, y] != vp[x, y]:
                op[x, y] = vp[x, y]
    return out


def apply_patch(d, p):
    o = d.copy()
    o.alpha_composite(p)
    return o


def main():
    os.makedirs(OUT, exist_ok=True)
    for sub in ('src', 'masks', 'imprints', 'check', 'hair', 'faces'):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    harmonize()
    f12, f14, f16 = font(12), font(15), font(18)

    meta_roles = {'a': {}, 'b': {}}
    standing = {}        # (role, body) → idle f0 (기본 조합)
    looked = {}          # (role, body) → idle f0 (조합을 입힌 것)
    LOOK = {}

    # ── 1. 16종 시트 (8역할 × 체형 2) ──────────────────────────────────
    for body in BODY_IDS:
        for role in ROLES:
            cells, mcells = {}, {}
            for clip, n in CLIPS:
                for i in range(n):
                    c, a = build(role, clip, i, body)
                    cells[(clip, i)] = c.img()
                    mcells[(clip, i)] = c.mask()
                    if clip == 'idle' and i == 0:
                        anchors0, base_cv = a, c
            nm = sheet_name(role, body)
            sheet_of(cells, 1).save(os.path.join(OUT, 'src', nm + '.png'))
            sheet_of(cells, SHEET_K).save(os.path.join(OUT, nm + '.png'))
            mask_sheet_of(mcells, 1).save(os.path.join(OUT, 'masks', nm + '.png'))

            head_top = anchors0['head_top'][1]
            px_h = FOOT - head_top + 1
            bb = base_cv.bbox()
            meta_roles[body][role] = {
                'ko': ROLE_KO[role],
                'sig_head': ROLE_SIG[role][0], 'sig_coat': ROLE_SIG[role][1],
                'sig_hand': ROLE_SIG[role][2],
                'color': '#%02X%02X%02X' % ROLE_COLS[role][0],
                'bare_head_px': px_h, 'bare_head_m': round(px_h / PPM, 4),
                'head_top_y': head_top, 'foot_y': FOOT,
                'with_hat_top_y': bb[1], 'with_hat_px': FOOT - bb[1] + 1,
                'shoulder_w_px': int(round(anchors0['torso_rx'] * 2)),
                'sheet': nm + '.png',
            }
            standing[(role, body)] = cells[('idle', 0)]
            hair, face = pick_look(role, body)
            LOOK[(role, body)] = (hair, face)
            looked[(role, body)] = build(role, 'idle', 0, body, hair, face)[0].img()
            print('[ok] %-9s %s  맨머리 %2dpx = %.3fm  어깨 %2dpx  (%s/%s)'
                  % (role, body, px_h, px_h / PPM,
                     meta_roles[body][role]['shoulder_w_px'], hair, face))

    # ── 2. 머리 6종 · 얼굴 3종 패치 (역할 × 체형마다 한 벌) ─────────────
    npatch, bad = 0, 0
    PATCH_SHEETS = {}
    for body in BODY_IDS:
        for role in ROLES:
            dcells = {}
            for clip, n in CLIPS:
                for i in range(n):
                    dcells[(clip, i)] = img_of(role, clip, i, body, 'short', 'f0').img()
            dsheet = sheet_of(dcells, 1)
            for kind, items, dflt in (('hair', HAIRS, 'short'), ('faces', FACES, 'f0')):
                d0 = os.path.join(OUT, kind, '%s_%s' % (role, body))
                os.makedirs(d0, exist_ok=True)
                for vid, ko, note in items:
                    pcells, vcells = {}, {}
                    for clip, n in CLIPS:
                        for i in range(n):
                            v = img_of(role, clip, i, body,
                                       vid if kind == 'hair' else 'short',
                                       vid if kind == 'faces' else 'f0').img()
                            vcells[(clip, i)] = v
                            pcells[(clip, i)] = diff_img(dcells[(clip, i)], v)
                    psheet = sheet_of(pcells, 1)
                    psheet.save(os.path.join(d0, vid + '.png'))
                    npatch += 1
                    PATCH_SHEETS[(role, body, kind, vid)] = psheet
                    # 전수 검사: 기본 시트 + 패치 == 변형 시트 (한 픽셀도 틀리면 안 된다)
                    if list(apply_patch(dsheet, psheet).getdata()) != \
                       list(sheet_of(vcells, 1).getdata()):
                        bad += 1
                        print('   [!!] 패치 복원 실패: %s %s %s' % (role, body, vid))
    print('[검사] 머리·얼굴 패치 %d장, 기본시트+패치==변형시트 불일치 %d건' % (npatch, bad))

    # ── 2-b. 조합 얼굴 패치 (PM 2026-10-03 결정 (가)) ─────────────────────
    #   정면 0~6행에서 얼굴②·③ 눈썹이 곱슬·두건 머리 픽셀과 같은 자리라, 머리 패치 위에 얼굴 패치를
    #   그냥 얹으면 머리를 덮어쓴다(840칸). 0~6행 픽셀은 그대로 두고, **머리가 얹힌 시트 기준의 얼굴 패치**를
    #   새 파일로 낸다: faces/<role>_<body>/<hair>_<face>.png = (기본 + 머리 패치) → (그 머리 + 그 얼굴) 의 차이.
    #   규칙: 머리 ≠ short 이고 얼굴 ≠ f0 이면 <face>.png 대신 <hair>_<face>.png 를 얹는다.
    #   검사: 18조합 × 26행 전부, 기본 + 머리 패치 + (규칙대로 고른 얼굴 패치) == 그 조합을 직접 그린 것.
    ncombo, combo_bad_all, naive_bad_cells = 0, 0, 0
    for body in BODY_IDS:
        for role in ROLES:
            cellsets = [(clip, i) for clip, n in CLIPS for i in range(n)]
            dsheet = sheet_of({k: img_of(role, k[0], k[1], body, 'short', 'f0').img() for k in cellsets}, 1)
            d0 = os.path.join(OUT, 'faces', '%s_%s' % (role, body))
            for hid, _k, _n in HAIRS:
                hsheet = apply_patch(dsheet, PATCH_SHEETS[(role, body, 'hair', hid)])
                for fid, _k2, _n2 in FACES:
                    want = sheet_of({k: img_of(role, k[0], k[1], body, hid, fid).img() for k in cellsets}, 1)
                    plain = PATCH_SHEETS[(role, body, 'faces', fid)]
                    # 참고: 규칙 없이 단순히 겹쳤을 때 틀리는 칸 수(셀 단위)
                    naive = apply_patch(hsheet, plain)
                    if naive.tobytes() != want.tobytes():
                        for r_, (clip, n) in enumerate(CLIPS):
                            for i in range(n):
                                box = (CELL * i, CELL * r_, CELL * (i + 1), CELL * (r_ + 1))
                                if naive.crop(box).tobytes() != want.crop(box).tobytes():
                                    naive_bad_cells += 1
                    if hid != 'short' and fid != 'f0':
                        cp = diff_img(hsheet, want)
                        cp.save(os.path.join(d0, '%s_%s.png' % (hid, fid)))
                        ncombo += 1
                        use = cp
                    else:
                        use = plain
                    if apply_patch(hsheet, use).tobytes() != want.tobytes():
                        combo_bad_all += 1
                        print('   [!!] 조합 패치 복원 실패: %s %s %s+%s' % (role, body, hid, fid))
    COMBO_CHECK = {'combo_face_patches': ncombo, 'combos_tested': len(BODY_IDS) * len(ROLES) * 18,
                   'cells_per_combo': sum(n for c_, n in CLIPS), 'mismatch_with_rule': combo_bad_all,
                   'mismatch_cells_without_rule_ref': naive_bad_cells}
    print('[검사] 조합 얼굴 패치 %d장 · 18조합 × 16시트 × 전 %d행: 규칙대로 얹었을 때 불일치 %d건 '
          '(규칙 없이 단순 겹침이면 %d칸 틀림 — 참고)' % (ncombo, len(CLIPS), combo_bad_all, naive_bad_cells))

    # ── 2-c. S15 잠수복 겹 — 역할 × 체형마다 한 장(전 행) ─────────────────
    #   검사: ①겹 × (머리 6 ∪ 얼굴 18조합 ∪ 각인 12) 픽셀 = 0
    #         ②18조합마다, 그 조합이 기본 시트에서 바꾼 칸(머리·얼굴 변화)을 겹이 한 칸도 덮지 않는다
    #           → 기본 + 머리 + 얼굴(조합 규칙) + 겹 == 그 조합 그대로 + 겹. 얼굴이 유리 너머로 보인다.
    os.makedirs(os.path.join(OUT, 'suit'), exist_ok=True)
    suit_clash, suit_cover, suit_cells = 0, 0, 0
    for body in BODY_IDS:
        for role in ROLES:
            cellsets = [(clip, i) for clip, n in CLIPS for i in range(n)]
            scells = {}
            for (clip, i) in cellsets:
                sc_ = suit_layer(role, clip, i, body)
                scells[(clip, i)] = sc_.img()
                n_ = len(sc_.pixels() & suit_forbid(role, clip, i, body))
                suit_clash += n_
                suit_cells += 1
                if n_:
                    print('   [!!] 잠수복 겹 충돌 %s_%s %s f%d: %d칸' % (role, body, clip, i, n_))
            ssheet = sheet_of(scells, 1)
            nm = '%s_%s' % (role, body)
            ssheet.save(os.path.join(OUT, 'suit', nm + '.png'))
            sheet_of(scells, SHEET_K).save(os.path.join(OUT, 'suit', nm + '_x4.png'))
            dsheet = sheet_of({k: img_of(role, k[0], k[1], body, 'short', 'f0').img() for k in cellsets}, 1)
            salpha = ssheet.getchannel('A').load()
            dpx = dsheet.load()
            for hid, _k, _n in HAIRS:
                for fid, _k2, _n2 in FACES:
                    want = sheet_of({k: img_of(role, k[0], k[1], body, hid, fid).img() for k in cellsets}, 1)
                    wpx = want.load()
                    for y in range(want.height):
                        for x in range(want.width):
                            if salpha[x, y] and wpx[x, y] != dpx[x, y]:
                                suit_cover += 1
    SUIT_CHECK = {'suit_sheets': len(BODY_IDS) * len(ROLES), 'cells': suit_cells,
                  'suit_x_hair_face_imprint_px': suit_clash, 'suit_covers_combo_change_px': suit_cover}
    print('[검사 S15] 잠수복 겹 %d장 · %d칸: 겹×(머리·얼굴·각인) %d칸 · 18조합 변화를 덮은 칸 %d'
          % (len(BODY_IDS) * len(ROLES), suit_cells, suit_clash, suit_cover))

    # ── 3. 각인 레이어 — 네 체형(어른 A·B, 아이 A·B)마다 한 벌 ──────────
    for sid, arole, abody in SHAPES:
        d0 = os.path.join(OUT, *IMP_SUB[sid])
        os.makedirs(d0, exist_ok=True)
        for iid, ko, part, col in IMPRINTS:
            cells = {}
            for clip, n in CLIPS:
                for i in range(n):
                    _b, _o, a = raw_of(arole, clip, i, abody)
                    cells[(clip, i)] = imprint_layer(iid, a).img()
            sheet_of(cells, 1).save(os.path.join(d0, iid + '.png'))
            sheet_of(cells, SHEET_K).save(os.path.join(d0, iid + '_x4.png'))
    print('[ok] 각인 %d종 × 4벌(어른 A·B, 아이 A·B)' % len(IMPRINTS))

    # ── 4. 자동 검사 — 각인 × 각인 / × 얼굴 / × 머리 ────────────────────
    #     S8은 각인끼리만 봤다. S9에서 머리·얼굴 레이어까지 넓혔다(지시).
    total_clash = 0
    for sid, arole, abody in SHAPES:
        base, _ov, a0 = raw_of(arole, 'idle', 0, abody)
        imp = {iid: imprint_layer(iid, a0).pixels() for iid, _k, _p, _c in IMPRINTS}
        hrs = {hid: hair_layer(hid, a0, base).pixels() for hid, _k, _n in HAIRS}
        fcs = {fid: face_layer(fid, a0, base, hair_layer('short', a0, base)).pixels()
               for fid, _k, _n in FACES}
        c_ii = c_if = c_ih = 0
        det = []
        ids = [t[0] for t in IMPRINTS]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                n = len(imp[ids[i]] & imp[ids[j]])
                if n:
                    c_ii += n; det.append('각인%s×각인%s' % (ids[i], ids[j]))
        for iid in ids:
            for fid in fcs:
                n = len(imp[iid] & fcs[fid])
                if n:
                    c_if += n; det.append('각인%s×얼굴%s' % (iid, fid))
            if iid in IMPRINT_ON_HAIR:
                continue
            for hid in hrs:
                n = len(imp[iid] & hrs[hid])
                if n:
                    c_ih += n; det.append('각인%s×머리%s' % (iid, hid))
        # 기본 머리(short)가 다른 다섯에 **완전히 덮이는가** — 패치 방식의 전제
        uncovered = [hid for hid in hrs if hid != 'short' and (hrs['short'] - hrs[hid])]
        total_clash += c_ii + c_if + c_ih + len(uncovered)
        print('[검사] %-6s 각인×각인 %d · 각인×얼굴 %d · 각인×머리 %d · 기본머리 미덮임 %s %s'
              % (sid, c_ii, c_if, c_ih, uncovered or '없음', det[:3]))
    print('[검사] 레이어 충돌 합계: %d건' % total_clash)
    # 머리 위에 얹히도록 **설계된** 각인은 머리 안에 들어 있는지 거꾸로 검사한다
    for sid, arole, abody in SHAPES:
        base, _o, a0 = raw_of(arole, 'idle', 0, abody)
        for iid in sorted(IMPRINT_ON_HAIR):
            p = imprint_layer(iid, a0).pixels()
            inside = all(len(p & hair_layer(h, a0, base).pixels()) > 0 for h, _k, _n in HAIRS)
            print('[검사] %-6s %s 는 머리 6종 모두에 얹히는가: %s' % (sid, iid, inside))

    # ── 5. 문어 ──
    oct_sheet = Image.new('RGBA', (CELL * 4, CELL), (0, 0, 0, 0))
    for i in range(3):
        oct_sheet.paste(build_octopus('idle', i).img(), (CELL * i, 0))
    oct_sheet.paste(build_octopus('wrap', 0).img(), (CELL * 3, 0))
    oct_sheet.save(os.path.join(OUT, 'src', 'octopus.png'))
    up(oct_sheet, SHEET_K).save(os.path.join(OUT, 'octopus.png'))
    print('[ok] 문어 idle 3 + wrap 1')

    # ── 검증 1: 70px 8역할 한 줄 (밝은 벽 / 어두운 방) — 체형 A 기준, S8과 같은 컷 ──
    for name, light in (('check/row70_light.png', True), ('check/row70_dark.png', False)):
        W, Hh = 980, 220
        im = room_bg(W, Hh, 0.80, light)
        d = ImageDraw.Draw(im)
        step = W // 8
        for i, role in enumerate(ROLES):
            sp = standing[(role, 'a')]
            s = to_h(sp.crop(sp.getbbox()), 70)
            xc = step * i + step // 2
            im.paste(s, (xc - s.width // 2, int(Hh * 0.80) - s.height), s)
            d.text((step * i + 6, int(Hh * 0.80) + 8), ROLE_KO[role], font=f14,
                   fill=(40, 28, 18) if light else (226, 198, 150))
        d.text((8, 6), '70px 판독 — %s' % ('밝은 벽' if light else '어두운 방'), font=f16,
               fill=(40, 28, 18) if light else (236, 206, 150))
        im.save(os.path.join(OUT, name))

    # ── 검증 1-b: 검은 실루엣 70px (자가 검수 1번) ──
    W, Hh = 980, 150
    im = room_bg(W, Hh, 0.84, True)
    d = ImageDraw.Draw(im)
    step = W // 8
    for i, role in enumerate(ROLES):
        sp = standing[(role, 'a')].crop(standing[(role, 'a')].getbbox())
        s = to_h(sp, 70)
        sil = Image.new('RGBA', s.size, (0, 0, 0, 0))
        px, qx = s.load(), sil.load()
        for y in range(s.height):
            for x in range(s.width):
                if px[x, y][3] > 0:
                    qx[x, y] = (22, 14, 10, 255)
        xc = step * i + step // 2
        im.paste(sil, (xc - sil.width // 2, int(Hh * 0.84) - sil.height), sil)
        d.text((step * i + 6, int(Hh * 0.84) + 6), ROLE_KO[role], font=f14, fill=(40, 28, 18))
    d.text((8, 6), '검은 실루엣 70px — 머리에 쓴 것과 손에 든 것만으로 갈리는가', font=f16, fill=(40, 28, 18))
    im.save(os.path.join(OUT, 'check', 'silhouette70.png'))

    # ── 검증 7 (S9): 70px × 16명 — 8역할 × 체형 2 ───────────────────────
    order = [(r, b) for r in ROLES for b in BODY_IDS]
    for name, light, sil_mode in (('check/row70_16_light.png', True, False),
                                  ('check/row70_16_dark.png', False, False),
                                  ('check/silhouette70_16.png', True, True)):
        W, Hh = 1600, 250
        im = room_bg(W, Hh, 0.66, light)
        d = ImageDraw.Draw(im)
        step = W // 16
        for i, (role, body) in enumerate(order):
            sp = looked[(role, body)]
            s = to_h(sp.crop(sp.getbbox()), 70)
            if sil_mode:
                sl = Image.new('RGBA', s.size, (0, 0, 0, 0))
                px, qx = s.load(), sl.load()
                for y in range(s.height):
                    for x in range(s.width):
                        if px[x, y][3] > 0:
                            qx[x, y] = (22, 14, 10, 255)
                s = sl
            xc = step * i + step // 2
            im.paste(s, (xc - s.width // 2, int(Hh * 0.66) - s.height), s)
            col = (40, 28, 18) if light else (226, 198, 150)
            d.text((step * i + 4, int(Hh * 0.66) + 6), ROLE_KO[role], font=f14, fill=col)
            d.text((step * i + 4, int(Hh * 0.66) + 24), BODIES[body]['ko'], font=f12, fill=col)
            hair, face = LOOK[(role, body)]
            d.text((step * i + 4, int(Hh * 0.66) + 42), hair + ' / ' + face, font=f12,
                   fill=(110, 84, 58) if light else (160, 132, 100))
        ttl = ('검은 실루엣 70px × 16명 — 체형이 바뀌어도 역할은 **투구 위**로 갈린다' if sil_mode
               else '70px × 16명 (8역할 × 체형 2) — %s' % ('밝은 벽' if light else '어두운 방'))
        d.text((8, 6), ttl, font=f16, fill=(40, 28, 18) if light else (236, 206, 150))
        im.save(os.path.join(OUT, name))

    # ── 검증 8 (S9): 체형 A/B 나란히 + 겹쳐 보기 ────────────────────────
    W, Hh = 1180, 440
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    for i, role in enumerate(['scout', 'engineer', 'kid']):
        x0 = 24 + i * 390
        cells = {}
        for j, body in enumerate(BODY_IDS):
            c, a = build(role, 'idle', 0, body)
            cells[body] = c
            fig = up(c.img(), 4)
            im.paste(fig, (x0 + j * 112 - 36, 66 - 4 * 8), fig)
            d.text((x0 + j * 112, 46), BODIES[body]['ko'], font=f14, fill=(236, 206, 150))
            d.text((x0 + j * 112 - 6, 342), '어깨 %dpx' % int(round(a['torso_rx'] * 2)),
                   font=f12, fill=(196, 168, 128))
        # 겹쳐 보기 — 같은 셀이라 좌표가 그대로 맞는다
        ov = Image.new('RGBA', (CELL, CELL), (0, 0, 0, 0))
        op = ov.load()
        A, Bc = cells['a'], cells['b']
        for y in range(CELL):
            for x in range(CELL):
                av, bv = A.g[y][x] is not None, Bc.g[y][x] is not None
                if av and bv:
                    op[x, y] = (96, 76, 56, 255)
                elif av:
                    op[x, y] = (214, 96, 72, 255)       # A만 있는 칸 = A가 넓다
                elif bv:
                    op[x, y] = (118, 186, 196, 255)     # B만 있는 칸
        z = up(ov, 4)
        im.paste(z, (x0 + 232 - 36, 66 - 4 * 8), z)
        d.text((x0 + 232, 46), '겹쳐 보기', font=f14, fill=(236, 206, 150))
        d.text((x0, 364), ROLE_KO[role], font=f16, fill=(240, 212, 150))
    d.text((8, 6), '체형 A / B — 어깨 1px, 팔꿈치 아래가 1px 더 안으로(허리선). '
                   '색·키·머리 크기·얼굴 자리는 전부 같다 (×4 확대)',
           font=f16, fill=(236, 206, 150))
    d.text((8, 26), '성별을 색으로 표시하지 않는다(분홍 없음). 역할과 체형은 독립이다 — '
                    '어느 역할에나 어느 체형이든 온다.', font=f14, fill=(198, 170, 130))
    d.text((8, Hh - 38), '겹쳐 보기: 붉은 칸 = 체형 A에만 있는 픽셀(어깨·팔꿈치 아래), '
                         '푸른 칸 = 체형 B에만 있는 픽셀. 차이는 좌우 1~2px뿐이다.',
           font=f12, fill=(188, 160, 124))
    d.text((8, Hh - 20), '※ 몸통만 깎으면 팔이 그 자리를 덮어 바깥선이 안 바뀐다. 그래서 '
                         '팔꿈치 아래를 1px 당겼다 — 어깨에서 허리로 좁아지는 선이 생긴다.',
           font=f12, fill=(170, 144, 110))
    im.save(os.path.join(OUT, 'check', 'bodyAB.png'))

    # ── 검증 9 (S9): 머리 6종 × 얼굴 3종 ────────────────────────────────
    W, Hh = 1180, 716
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    demo = 'engineer'
    for i, (hid, ko, note) in enumerate(HAIRS):
        x0 = 20 + (i % 3) * 390
        y0 = 58 + (i // 3) * 206
        for j, body in enumerate(BODY_IDS):
            c, a = build(demo, 'idle', 0, body, hid, 'f0')
            cut = c.img().crop((int(a['hx'] - 14), int(a['head_top'][1] - 4),
                                int(a['hx'] + 15), int(a['neck_y'] + 12)))
            z = up(cut, 5)
            im.paste(z, (x0 + j * 150, y0 + 22), z)

        d.text((x0, y0), '%s  (%s)' % (ko, hid), font=f14, fill=(240, 212, 150))
        d.text((x0, y0 + 46 + 145), note, font=f12, fill=(192, 164, 126))
    # 얼굴 3종 — 얼굴 구멍만 ×8
    y0 = 58 + 2 * 206
    d.text((20, y0), '얼굴 3종 (×8, 얼굴 구멍만) — 눈 크기·눈썹 각도·입·주근깨만 다르다',
           font=f14, fill=(240, 212, 150))
    for j, (fid, fko, fnote) in enumerate(FACES):
        c, a = build(demo, 'idle', 0, 'a', 'short', fid)
        hx, fy, fr = a['hx'], a['fy'], a['fr']
        cut = c.img().crop((int(hx - fr - 1), int(fy - fr - 1), int(hx + fr + 2), int(fy + fr + 2)))
        z = up(cut, 8)
        im.paste(z, (24 + j * 260, y0 + 24), z)
        d.text((24 + j * 260, y0 + 28 + z.height), '%s  %s' % (fko, fid), font=f14,
               fill=(232, 202, 150))
        d.text((24 + j * 260, y0 + 46 + z.height), fnote, font=f12, fill=(188, 160, 124))
    d.text((8, 6), '머리 6종 × 얼굴 3종 — 본체와 분리된 레이어. 역할·체형과 무관하게 조합된다 '
                   '(칸마다 왼쪽 = 체형 A · 오른쪽 = 체형 B)', font=f16, fill=(236, 206, 150))
    d.text((8, 24), '머리 갈래는 「투구 테 아래」에서만 나온다 — 투구 위는 역할이 사는 자리라 건드리지 않는다.',
           font=f12, fill=(188, 160, 124))
    im.save(os.path.join(OUT, 'check', 'hair6_face3.png'))

    # ── 검증 10 (S9): 한 방주에 같이 사는 열여섯 ────────────────────────
    plate = scene_crop()
    tileW = plate.width
    cols = 1600 // tileW + 2
    bgw = tileW * cols
    bg = Image.new('RGB', (bgw, plate.height))
    for i in range(cols):
        bg.paste(plate if i % 2 == 0 else plate.transpose(Image.FLIP_LEFT_RIGHT),
                 (i * tileW, 0))
    bg = bg.crop((0, 0, 1600, plate.height)).convert('RGBA')
    crew = Image.new('RGBA', (1600, plate.height + 40), (14, 10, 8, 255))
    crew.alpha_composite(bg, (0, 0))
    floor = SCENE_FLOOR
    for i, (role, body) in enumerate(order):
        hair, face = LOOK[(role, body)]
        clip, fi = [('idle', 0), ('walk', 1), ('work', 0), ('carry', 0),
                    ('idle', 1), ('sit', 0)][i % 6]
        c, _a = build(role, clip, fi, body, hair, face)
        bb = c.bbox()
        spr = room_light(up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), 2))
        px0 = 14 + i * 99 - spr.width // 2 + 30
        py0 = floor - (FOOT - bb[1] + 1) * 2 + (0 if i % 2 == 0 else 6)
        crew = ground_shadow(crew, (px0, py0), spr)
        crew.alpha_composite(spr, (px0, py0))
    d = ImageDraw.Draw(crew)
    d.rectangle([0, 0, 1599, 24], fill=(16, 11, 9))
    d.text((8, 4), '한 방주에 같이 사는 열여섯 — 8역할 × 체형 2, 머리·얼굴은 역할과 무관하게 섞었다 (×2, 방 빛 적용)',
           font=f16, fill=(236, 206, 150))
    for i, (role, body) in enumerate(order):
        d.text((14 + i * 99 + 10, crew.height - 34), ROLE_KO[role], font=f12, fill=(206, 178, 138))
        d.text((14 + i * 99 + 10, crew.height - 18), body.upper() + ' ' + LOOK[(role, body)][0],
               font=f12, fill=(150, 124, 96))
    crew.convert('RGB').save(os.path.join(OUT, 'check', 'crew16.png'))

    # ── 검증 2: 실제 렌더 방 합성 (×3) — 체형 A·B를 섞는다 ──────────────
    wide = Image.open(SCENE_SRC).convert('RGB').crop((1000, 320, 1480, 600)).convert('RGBA')
    comp = wide.copy()
    picks = [('scout', 'a', 150, 'idle', 0), ('medic', 'b', 222, 'work', 1),
             ('trader', 'a', 296, 'idle', 0), ('kid', 'b', 360, 'idle', 0)]
    for role, body, px_x, clip, fi in picks:
        hair, face = LOOK[(role, body)]
        c, _a = build(role, clip, fi, body, hair, face)
        bb = c.bbox()
        spr = room_light(up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), ROOM_K))
        px0 = px_x - spr.width // 2
        py0 = (578 - 320) - (FOOT - bb[1] + 1) * ROOM_K
        comp = ground_shadow(comp, (px0, py0), spr)
        comp.alpha_composite(spr, (px0, py0))
    big = up(comp.convert('RGB'), 2)
    d = ImageDraw.Draw(big)
    fl = (578 - 320) * 2
    for m, lab in ((1.6, '1.6m = 132px'), (1.2, '1.2m = 99px')):
        yy = fl - int(m * PPM * ROOM_K) * 2
        d.line([24, yy, big.width - 24, yy], fill=(255, 196, 96))
        d.text((28, yy - 16), lab, font=f12, fill=(255, 212, 130))
    d.line([24, fl, big.width - 24, fl], fill=(255, 196, 96))
    d.rectangle([2, 2, big.width - 3, 26], fill=(16, 11, 9))
    d.text((8, 5), '실제 렌더 방 × P2 도트 — 정수 배율 ×3 · 체형 A/B 섞음 · 맨머리 1.6m = 132px',
           font=f16, fill=(236, 206, 150))
    d.text((8, big.height - 24), '※ 좌우 끝의 인물은 배경 렌더에 이미 그려진 옛 화풍 주민이다'
           ' (사람 없는 플레이트를 배경 담당에게 요청해 둠). 키 비교용으로 남겼다.',
           font=f12, fill=(200, 168, 128))
    big.save(os.path.join(OUT, 'check', 'room_composite.png'))
    scene_crop().save(os.path.join(OUT, 'room_plate.png'))

    def zoom_panel(role, ids, k_fig=4, k_zoom=9, body='a'):
        """본체 + 각인 위치 상자 + 확대 조각."""
        c, a = build(role, 'idle', 0, body)
        base = c.img()
        boxes = []
        for iid in ids:
            lay = imprint_layer(iid, a)
            bbl = lay.bbox()
            if bbl:
                boxes.append((iid, bbl))
            base.alpha_composite(lay.img())
        bb = c.bbox()
        fig = up(base.crop((bb[0] - 1, bb[1] - 1, bb[2] + 2, bb[3] + 2)), k_fig)
        df = ImageDraw.Draw(fig)
        for iid, bl in boxes:
            x0 = (bl[0] - (bb[0] - 1)) * k_fig - 2
            y0 = (bl[1] - (bb[1] - 1)) * k_fig - 2
            x1 = (bl[2] + 1 - (bb[0] - 1)) * k_fig + 1
            y1 = (bl[3] + 1 - (bb[1] - 1)) * k_fig + 1
            df.rectangle([x0, y0, x1, y1], outline=(255, 214, 120))
        zooms = []
        for iid, bl in boxes:
            pad = 3
            cut = base.crop((bl[0] - pad, bl[1] - pad, bl[2] + 1 + pad, bl[3] + 1 + pad))
            zooms.append((iid, up(cut, k_zoom)))
        return fig, zooms

    # ── 검증 3: 각인 3개 동시 착용 ──
    sets = [('scout', ['warden', 'empty_seat', 'debt_paid']),
            ('medic', ['spore_mark', 'water_memory', 'footprint']),
            ('engineer', ['crack_seen', 'depth_mark', 'knock_heard']),
            ('farmer', ['sun_memory', 'empty_stomach', 'saved_breath'])]
    PW, W, Hh = 262, 1048, 330
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    for i, (role, ids) in enumerate(sets):
        fig, zooms = zoom_panel(role, ids, 4, 5, 'b' if i % 2 else 'a')
        x0 = i * PW + 10
        im.paste(fig, (x0, 36), fig)
        d.text((x0, 36 + fig.height + 4), ROLE_KO[role] + (' · 체형 B' if i % 2 else ' · 체형 A'),
               font=f14, fill=(236, 206, 150))
        zx = x0 + fig.width + 8
        for j, (iid, z) in enumerate(zooms):
            zy = 40 + j * 92
            im.paste(z, (zx, zy), z)
            nm = [t[1] for t in IMPRINTS if t[0] == iid][0]
            pt = [t[2] for t in IMPRINTS if t[0] == iid][0]
            d.text((zx, zy + z.height + 2), nm, font=f12, fill=(242, 214, 152))
            d.text((zx, zy + z.height + 18), pt, font=f12, fill=(184, 156, 120))
    d.text((8, 6), '각인 3개 동시 착용 — 12종이 서로·머리·얼굴과 한 픽셀도 겹치지 않는다(자동 검사)',
           font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'imprint3.png'))

    # ── 검증 3-b: 각인 12종 ──
    W, Hh = 1180, 620
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    for i, (iid, ko, part, col) in enumerate(IMPRINTS):
        fig, zooms = zoom_panel('scout', [iid], 3, 8)
        cx0 = (i % 4) * (W // 4) + 10
        cy0 = (i // 4) * 200 + 30
        im.paste(fig, (cx0, cy0), fig)
        if zooms:
            im.paste(zooms[0][1], (cx0 + fig.width + 4, cy0 + 10), zooms[0][1])
        d.text((cx0 + fig.width + 4, cy0 + 100), ko, font=f14, fill=(240, 212, 150))
        d.text((cx0 + fig.width + 4, cy0 + 118), part, font=f12, fill=(190, 162, 124))
        d.text((cx0 + fig.width + 4, cy0 + 134), col, font=f12, fill=(158, 134, 102))
    d.text((8, 6), '각인 12종 — 머리·목·가슴·팔·손목·허리로 부위를 나눴다 (오른쪽은 ×8 확대)',
           font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'imprints12.png'))

    # ── 검증 4: 자세 여섯 + 뒷모습 (체형 B로 — 허리선이 자세마다 깨지지 않는지) ──
    rowspec = [[('idle', 2, '느린 호흡'), ('walk', 3, '걷기'), ('work', 3, '일하기'),
                ('carry', 2, '물건 들기')],
               [('sit', 2, '앉기'), ('hurt', 2, '부상·주저앉음'), ('back_walk', 3, '뒷모습 걷기')]]
    W, Hh = 1060, 540
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    for r, row in enumerate(rowspec):
        base_y = 160 + r * 250
        x = 12
        for clip, n, ko in row:
            x_start = x
            for i in range(n):
                c, _ = build('scout', clip, i, 'b', 'braid', 'f1')
                bb = c.bbox()
                s2 = up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), 3)
                im.paste(s2, (x, base_y - (FOOT - bb[1] + 1) * 3), s2)
                x += s2.width + 3
            d.line([x_start - 4, base_y + 1, x - 6, base_y + 1], fill=(120, 92, 58))
            d.text((x_start, base_y + 6), '%s (%d)' % (ko, n), font=f14, fill=(230, 200, 150))
            d.text((x_start, base_y + 24), clip, font=f12, fill=(170, 144, 110))
            x += 26
    d.text((8, 6), '자세 7종 — 체형 B · 땋은머리 · 얼굴 ②. 발 기준선(가로 선)은 전부 같다',
           font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'poses.png'))

    # ── 검증 5: 걷기 애니메이션 시트 (방 빛을 받은 판) ──
    W = 8 * 150
    im = room_bg(W, 210, 0.81, False)
    d = ImageDraw.Draw(im)
    for i, role in enumerate(ROLES):
        for fidx in range(3):
            c, _ = build(role, 'walk', fidx)
            bb = c.bbox()
            s = room_light(up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), 2))
            im.paste(s, (i * 150 + 8 + fidx * 46, 170 - s.height), s)
        d.text((i * 150 + 8, 178), ROLE_KO[role] + ' walk f0~2', font=f12, fill=(214, 186, 150))
    d.text((8, 6), '걷기 3프레임 × 8역할 (×2, 방 빛 적용)', font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'walk_all.png'))

    # 걷기 시트(방 빛) — 비교 페이지가 CSS steps(3)로 돌린다
    for body in BODY_IDS:
        for role in ROLES:
            hair, face = LOOK[(role, body)]
            lit = Image.new('RGBA', (CELL * ROOM_K * 3, CELL * ROOM_K), (0, 0, 0, 0))
            for i in range(3):
                c, _ = build(role, 'walk', i, body, hair, face)
                lit.paste(room_light(up(c.img(), ROOM_K)), (CELL * ROOM_K * i, 0))
            lit.save(os.path.join(OUT, 'check', 'walklit_%s.png' % sheet_name(role, body)))

    # ── 검증 6: 문어 ──
    W, Hh = 620, 240
    im = room_bg(W, Hh, 0.84, False)
    d = ImageDraw.Draw(im)
    for i, (pose, fi, lab) in enumerate((('idle', 0, 'idle f0'), ('idle', 1, 'idle f1'),
                                         ('wrap', 0, '손목 감기 (J7)'))):
        c = build_octopus(pose, fi)
        bb = c.bbox()
        s = up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), 3)
        im.paste(s, (20 + i * 200, int(Hh * 0.84) - s.height), s)
        d.text((20 + i * 200, int(Hh * 0.84) + 8), lab, font=f14, fill=(226, 198, 150))
    d.text((8, 6), '문어 — 식구다. 말하지 않는다 (DECISIONS 2026-09-27)', font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'octopus.png'))

    # ── 검증 11 (S9): 배경이 낸 **사람 없는 플레이트** 위 진짜 합성 ───────
    #   S8 미완 ①(사람 없는 플레이트가 없다)이 배경 S8-C 에서 해결됐다.
    #   plates_meta.json 의 floor_y·char_scale 을 그대로 읽어 발바닥을 맞춘다.
    PLDIR = os.path.join(ROOT, 'static', 'art', 'plates')
    pmeta = None
    try:
        pmeta = json.load(io.open(os.path.join(PLDIR, 'plates_meta.json'), encoding='utf-8'))
    except Exception as e:
        print('[!] plates_meta.json 못 읽음:', e)
    if pmeta:
        flY = pmeta['floor_y']
        kk = pmeta['grid']['char_scale']
        rooms = [('quarters', '거주', [('kid', 'a', 'idle', 0), ('cook', 'b', 'sit', 0),
                                      ('scout', 'a', 'idle', 1)]),
                 ('workshop', '공방', [('engineer', 'a', 'work', 1), ('engineer', 'b', 'work', 0),
                                      ('trader', 'a', 'carry', 0)]),
                 ('infirmary', '의무실', [('medic', 'b', 'work', 1), ('scholar', 'a', 'hurt', 0),
                                        ('farmer', 'b', 'idle', 0)]),
                 ('greenhouse', '온실', [('farmer', 'a', 'work', 1), ('kid', 'b', 'walk', 1),
                                       ('medic', 'a', 'idle', 0)])]
        cw, ch = pmeta['canvas']
        sheetimg = Image.new('RGBA', (cw * 2, ch * 2 + 64), (14, 10, 8, 255))
        for ri, (rid, rko, people) in enumerate(rooms):
            fp = os.path.join(PLDIR, 'room_plate_%s_lit.png' % rid)
            if not os.path.exists(fp):
                continue
            pl = Image.open(fp).convert('RGBA')
            rinfo = [r for r in pmeta['rooms'] if r.get('id') == rid]
            lamp = (rinfo[0].get('lamp') if rinfo else None) or [cw // 2, 110]
            sx0, sx1 = (rinfo[0].get('stand_x') if rinfo else None) or [138, 534]
            box = pl.convert('RGB').crop((max(0, lamp[0] - 60), lamp[1] + 20,
                                          min(cw, lamp[0] + 60), lamp[1] + 90))
            cc = box.resize((1, 1), Image.BOX).getpixel((0, 0))
            mm = max(1.0, sum(cc) / 3.0)
            tint = tuple(ci / mm for ci in cc)
            step = (sx1 - sx0) // (len(people) + 1)
            for pi, (role, body, clip, fi) in enumerate(people):
                hair, face = LOOK[(role, body)]
                c, _a = build(role, clip, fi, body, hair, face)
                bb = c.bbox()
                spr = room_light(up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), kk),
                                 1.0, tint)
                px0 = sx0 + step * (pi + 1) - spr.width // 2
                py0 = flY - (FOOT - bb[1] + 1) * kk
                pl = ground_shadow(pl, (px0, py0), spr)
                pl.alpha_composite(spr, (px0, py0))
            dd = ImageDraw.Draw(pl)
            dd.text((12, 10), '%s (%s_lit) · 발바닥 = floor_y %d · ×%d = 82.5px/m'
                    % (rko, rid, flY, kk), font=f14, fill=(244, 216, 160))
            sheetimg.alpha_composite(pl, ((ri % 2) * cw, 56 + (ri // 2) * ch))
        dd = ImageDraw.Draw(sheetimg)
        dd.text((10, 8), '배경이 낸 사람 없는 방 플레이트 위 — plates_meta.json 의 floor_y·char_scale 을 '
                         '그대로 읽어 붙였다 (좌표 보정 0)', font=f16, fill=(236, 206, 150))
        dd.text((10, 32), '등불색 틴트는 각 플레이트의 등불 아래를 직접 샘플링했다. '
                          '앉기·일하기·부상·들기·걷기를 섞었다.', font=f14, fill=(188, 160, 124))
        sheetimg.convert('RGB').save(os.path.join(OUT, 'check', 'plate_rooms.png'))
        print('[ok] check/plate_rooms.png — 사람 없는 플레이트 4칸 합성')


    # ── S11 검사 — 자세 전 행 × 전 프레임으로 넓혔다 ──────────────────────
    #   ①각인×각인 ②각인×얼굴 3종 ③각인×머리 6종(water_memory 제외) — 기존 검사와 같은 식
    #   ④각인×방 설비/든 물건(보이는 픽셀) ⑤얼굴×설비/물건 ⑥머리×옆 설비
    #   기존 7행은 **참고로만** 센다(손대지 않기로 했으므로). 새 14행은 전부 0이어야 한다.
    s11_tot, old_tot, s11_hidden = 0, 0, {}
    s12_tot, s12_det = 0, []
    s15_tot = 0
    for sid, arole, abody in SHAPES:
        for clip, n in CLIPS:
            for i in range(n):
                base, _ov, a0 = raw_of(arole, clip, i, abody)
                imp = {iid: imprint_layer(iid, a0).pixels() for iid, _k, _p, _c in IMPRINTS}
                hrs = {hid: hair_layer(hid, a0, base).pixels() for hid, _k, _n in HAIRS}
                hs = hair_layer('short', a0, base)
                fcs = {fid: face_layer(fid, a0, base, hs).pixels() for fid, _k, _n in FACES}
                ids = [t[0] for t in IMPRINTS]
                cnt, det = 0, []
                for x in range(len(ids)):
                    for y in range(x + 1, len(ids)):
                        if imp[ids[x]] & imp[ids[y]]:
                            cnt += 1; det.append('%s×%s' % (ids[x], ids[y]))
                for iid in ids:
                    for fid in fcs:
                        if imp[iid] & fcs[fid]:
                            cnt += 1; det.append('%s×얼굴%s' % (iid, fid))
                    if iid not in IMPRINT_ON_HAIR:
                        for hid in hrs:
                            if imp[iid] & hrs[hid]:
                                cnt += 1; det.append('%s×머리%s' % (iid, hid))
                if clip in S11_IDS or clip in SIDE_IDS or clip in S15_SIDE:
                    comp, _ = build(arole, clip, i, abody)
                    oc = a0['obj_cv']
                    vis = set(p_ for p_ in oc.pixels() if comp.own(*p_) == oc.own(*p_)) - a0['mit_px']
                    fixv = vis - a0['front_px']
                    for iid in ids:
                        if imp[iid] & vis:
                            cnt += 1; det.append('%s×설비' % iid)
                    for fid in fcs:
                        if fcs[fid] & vis:
                            cnt += 1; det.append('얼굴%s×물건' % fid)
                    for hid in hrs:
                        if hrs[hid] & fixv:
                            cnt += 1; det.append('머리%s×설비' % hid)
                    if clip in S15_SIDE:                  # S15 — 따로 센다
                        s15_tot += cnt
                        if cnt:
                            print('   [!!] S15 %s %s f%d: %s' % (sid, clip, i, det[:4]))
                        continue
                    if clip in SIDE_IDS:                  # S12 — 따로 센다(S11 기록값은 그대로 둔다)
                        s12_tot += cnt
                        if cnt:
                            s12_det.append('%s %s f%d: %s' % (sid, clip, i, det[:4]))
                            print('   [!!] S12 %s %s f%d: %s' % (sid, clip, i, det[:4]))
                        continue
                    for h_ in sorted(a0['hide']):
                        s11_hidden.setdefault((sid, clip, i), []).append(h_)
                    s11_tot += cnt
                    if cnt:
                        print('   [!!] %s %s f%d: %s' % (sid, clip, i, det[:4]))
                elif clip in S15_FRONT:                   # S15 정면 새 행
                    s15_tot += cnt
                    if cnt:
                        print('   [!!] S15 %s %s f%d: %s' % (sid, clip, i, det[:4]))
                elif clip in S12B_IDS:                    # S12-B 새 행(work_34·carry_34·idle_glance)
                    s12_tot += cnt
                    if cnt:
                        s12_det.append('%s %s f%d: %s' % (sid, clip, i, det[:4]))
                        print('   [!!] S12B %s %s f%d: %s' % (sid, clip, i, det[:4]))
                else:
                    old_tot += cnt
    print('[검사 S11] 새 14행 × 4체형 레이어 충돌: %d건 (기존 7행 참고: %d건)' % (s11_tot, old_tot))
    print('[검사 S11] 몸 앞 물건에 가려 그 프레임에서 꺼지는 각인: %d프레임' % len(s11_hidden))
    S11_CHECK = {'s11_clash': s11_tot, 'old_rows_clash_ref': old_tot,
                 'old_rows_fix': '2026-10-03 PM 결정: 기존 7행 충돌 39건(S8·S9 전 프레임) 수리. 각인 레이어만 프레임별로 '
                                 '잘라 냈다 — 머리 6종·얼굴 3종 아래로 숨고, 각인끼리는 뒤의 것이 비킨다(IMPRINT_FRONT). '
                                 '한 점만 남으면 그 프레임에서 끈다. 본체·머리·얼굴 픽셀과 S11 행은 불변',
                 'hidden': {'%s/%s/f%d' % k: v for k, v in sorted(s11_hidden.items())}}

    # ── S11 검증 그림 ──────────────────────────────────────────────────
    PLDIR11 = os.path.join(ROOT, 'static', 'art', 'plates')
    try:
        pm11 = json.load(io.open(os.path.join(PLDIR11, 'plates_meta.json'), encoding='utf-8'))
    except Exception:
        pm11 = None
    PLATE_OF = {'generator': 'power'}

    def plate_and_tint(rid):
        pid = PLATE_OF.get(rid, rid)
        fp_ = os.path.join(PLDIR11, 'room_plate_%s_lit.png' % pid)
        if not (pm11 and os.path.exists(fp_)):
            return None, lamp_tint(), pid
        pl_ = Image.open(fp_).convert('RGBA')
        info = [r for r in pm11['rooms'] if r.get('id') == pid]
        lamp = (info[0].get('lamp') if info else None) or [pm11['canvas'][0] // 2, 110]
        box = pl_.convert('RGB').crop((max(0, lamp[0] - 60), lamp[1] + 20,
                                       min(pm11['canvas'][0], lamp[0] + 60), lamp[1] + 90))
        cc = box.resize((1, 1), Image.BOX).getpixel((0, 0))
        mm = max(1.0, sum(cc) / 3.0)
        return pl_, tuple(ci / mm for ci in cc), pid

    WORK_CAST = {   # 방마다 두 사람 — 같은 동작, 다른 도구(= 다른 역할)
        'quarters': [('kid', 'b'), ('trader', 'a')], 'storage': [('scout', 'a'), ('cook', 'b')],
        'well': [('engineer', 'b'), ('farmer', 'a')], 'greenhouse': [('farmer', 'b'), ('medic', 'a')],
        'generator': [('engineer', 'a'), ('scout', 'b')], 'infirmary': [('medic', 'b'), ('kid', 'a')],
        'workshop': [('engineer', 'a'), ('trader', 'b')], 'decoder': [('scholar', 'a'), ('kid', 'b')],
        'pantry': [('cook', 'a'), ('farmer', 'b')], 'airlock': [('scout', 'a'), ('engineer', 'b')],
        'lounge': [('scholar', 'b'), ('kid', 'a')],
    }
    ROOM_KO11 = {'quarters': '거주실', 'storage': '창고', 'well': '정수실', 'greenhouse': '온실',
                 'generator': '발전실', 'infirmary': '의무실', 'workshop': '공방',
                 'decoder': '해독실·서고', 'pantry': '식량창고', 'airlock': '에어락', 'lounge': '전망 라운지'}
    flY = pm11['floor_y'] if pm11 else 315
    kk = pm11['grid']['char_scale'] if pm11 else ROOM_K
    cw, ch = (pm11['canvas'] if pm11 else (672, 378))
    sx0_, sx1_ = 138, 534
    lit_index = {}
    panels = []
    for rid, cast in WORK_CAST.items():
        clip = ROOM_WORK[rid]
        nfr = dict(CLIPS)[clip]
        pl, tint, pid = plate_and_tint(rid)
        if pl is None:
            bgp = room_bg(cw, ch, flY / float(ch), True).convert('RGBA')
        else:
            bgp = pl.copy()
        # 방 빛 받은 셀 띠(×3, 프레임 가로) — 비교 페이지가 CSS steps 로 돌린다
        for role, body in cast:
            hair, face = LOOK[(role, body)]
            strip = Image.new('RGBA', (CELL * kk * nfr, CELL * kk), (0, 0, 0, 0))
            for i in range(nfr):
                cc_, _ = build(role, clip, i, body, hair, face)
                strip.paste(room_light(up(cc_.img(), kk), 1.0, tint), (CELL * kk * i, 0))
            nm = 'worklit_%s_%s.png' % (rid, sheet_name(role, body))
            strip.save(os.path.join(OUT, 'check', nm))
            lit_index.setdefault(rid, []).append({'file': 'check/' + nm, 'role': role, 'body': body,
                                                  'frames': nfr})
        # 정지 합성 — 셀 단위로 붙인다(셀 발 기준선 60 × kk = floor_y)
        step = (sx1_ - sx0_) // (len(cast) + 1)
        for pi, (role, body) in enumerate(cast):
            hair, face = LOOK[(role, body)]
            fi = min(1, nfr - 1) if pi == 0 else 0
            cc_, _ = build(role, clip, fi, body, hair, face)
            spr = room_light(up(cc_.img(), kk), 1.0, tint)
            px0 = int(sx0_ + (sx1_ - sx0_) * (0.28 if pi == 0 else 0.80)) - CELL * kk // 2
            py0 = flY - BASE_Y * kk
            bb = cc_.bbox()
            sh_ = up(cc_.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), kk)
            bgp = ground_shadow(bgp, (px0 + bb[0] * kk, py0 + bb[1] * kk), sh_)
            bgp.alpha_composite(spr, (px0, py0))
        dd = ImageDraw.Draw(bgp)
        dd.rectangle([0, 0, cw, 30], fill=(16, 11, 9, 230))
        dd.text((10, 6), '%s — %s%s' % (ROOM_KO11[rid], clip,
                                        '' if pl is not None else '  (플레이트 없음: 임시 바탕)'),
                font=f14, fill=(244, 216, 160))
        panels.append(bgp)
    colsN = 3
    rowsN = (len(panels) + colsN - 1) // colsN
    big = Image.new('RGBA', (cw * colsN, ch * rowsN + 44), (14, 10, 8, 255))
    for i, pn in enumerate(panels):
        big.alpha_composite(pn, ((i % colsN) * cw, 44 + (i // colsN) * ch))
    dd = ImageDraw.Draw(big)
    dd.text((10, 10), '방별 작업 동작 × 방 플레이트 — plates_meta 의 floor_y·char_scale(×%d) 그대로, '
                      '셀 발 기준선 60 = floor_y %d. 왼쪽 사람은 f1, 오른쪽은 f0' % (kk, flY),
            font=f16, fill=(236, 206, 150))
    big.convert('RGB').save(os.path.join(OUT, 'check', 'work_rooms.png'))

    # 70px 판독 — 행 = 방, 열 = 8역할(f1). "모자 포함 키 49px → 70px" 배율(기존 70px 컷과 같은 크기)
    rows70 = [c for c in S11_IDS if c.startswith('work_')] + ['rest_lounge']
    W70 = 140 + 8 * 104
    H70 = 34 + len(rows70) * 104
    im = room_bg(W70, H70, 0.99, True)
    d = ImageDraw.Draw(im)
    sc70 = 70.0 / 49.0
    for r, clip in enumerate(rows70):
        y0 = 34 + r * 104
        rid = [k for k, v in ROOM_WORK.items() if v == clip][0]
        d.text((8, y0 + 40), ROOM_KO11.get(rid, rid), font=f14, fill=(40, 28, 18))
        d.text((8, y0 + 60), clip, font=f12, fill=(96, 72, 50))
        for j, role in enumerate(ROLES):
            nfr = dict(CLIPS)[clip]
            cc_, _ = build(role, clip, min(1, nfr - 1), 'a')
            one = cc_.img()
            z70 = one.resize((int(round(CELL * sc70)), int(round(CELL * sc70))), Image.NEAREST)
            im.paste(z70, (140 + j * 104 + 52 - z70.width // 2, y0 + 100 - int(BASE_Y * sc70)), z70)
    for j, role in enumerate(ROLES):
        d.text((140 + j * 104 + 30, 8), ROLE_KO[role], font=f14, fill=(40, 28, 18))
    im.save(os.path.join(OUT, 'check', 'work70.png'))

    # 엘리베이터 — 기다림(2) → (뒷걸음: 기존 행) → 돌아섬(1) → 탐(2)
    seq = [('elevator_wait', 0), ('elevator_wait', 1), ('back_walk', 1), ('elevator_turn', 0),
           ('elevator_ride', 0), ('elevator_ride', 1)]
    labels = ['기다림 f0', '기다림 f1', '들어감(back_walk)', '돌아섬', '탐 f0', '탐 f1']
    castE = [('scout', 'a'), ('medic', 'b'), ('kid', 'a'), ('trader', 'b')]
    WE, HE = 40 + len(seq) * 170, 50 + len(castE) * 210
    im = room_bg(WE, HE, 0.99, False)
    d = ImageDraw.Draw(im)
    for r, (role, body) in enumerate(castE):
        hair, face = LOOK[(role, body)]
        y0 = 50 + r * 210
        for j, (clip, fi) in enumerate(seq):
            cc_, _ = build(role, clip, fi, body, hair, face)
            spr = room_light(up(cc_.img(), 3))
            x0 = 20 + j * 170
            if clip == 'elevator_ride':          # 칸 자리(개발이 칸 전체를 움직인다)
                d.rectangle([x0 + 22, y0 + 4, x0 + 170, y0 + 192], outline=(150, 112, 62), width=3)
            im.paste(spr, (x0, y0 + 186 - BASE_Y * 3), spr)
            if r == 0:
                d.text((x0 + 20, 26), labels[j], font=f14, fill=(236, 206, 150))
    d.text((8, 4), '엘리베이터 자세 — 내려가는 느낌은 칸 전체를 움직여 낸다(개발). 사람은 거의 정지',
           font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'elevator.png'))
    for role, body in castE:
        hair, face = LOOK[(role, body)]
        strip = Image.new('RGBA', (CELL * 3 * 5, CELL * 3), (0, 0, 0, 0))
        for j, (clip, fi) in enumerate([('elevator_wait', 0), ('elevator_wait', 1), ('elevator_turn', 0),
                                        ('elevator_ride', 0), ('elevator_ride', 1)]):
            cc_, _ = build(role, clip, fi, body, hair, face)
            strip.paste(room_light(up(cc_.img(), 3)), (CELL * 3 * j, 0))
        strip.save(os.path.join(OUT, 'check', 'elevlit_%s.png' % sheet_name(role, body)))
    print('[ok] S11 check/work_rooms.png · work70.png · elevator.png · worklit_* · elevlit_*')

    # ── S12 검사 — 옆모습: 각인 보임/끔 · 머리+얼굴 패치 18조합 · 변형이 옆에서도 보이는가 ──
    all_tot = s11_tot + old_tot + s12_tot + s15_tot
    print('[검사 S15] 원정 새 5행 × 4체형 레이어 충돌: %d건' % s15_tot)
    print('[검사 S12] 옆모습 2행 + 새 3행 × 4체형 레이어 충돌: %d건 · 전 %d행 합계: %d건' % (s12_tot, len(CLIPS), all_tot))
    TURNED = list(TURN_Q34) + list(TURN_PROFILE) + S12_IDS + S12B_IDS   # 돌아선 얼굴이 있는 모든 행
    combo_bad, empty_var, same_var, side_frames = 0, [], [], 0
    imp_seen = {}
    for body in BODY_IDS:
        for role in ROLES:
            for clip in TURNED:
                for i in range(dict(CLIPS)[clip]):
                    if clip == 'idle_glance' and i != 1:
                        continue                     # 정면 머리(f0·f2)는 0~6행과 같은 정면 레이어 — 아래 참고 검사로 따로 센다
                    side_frames += 1
                    di = img_of(role, clip, i, body, 'short', 'f0').img()
                    hp = {h: diff_img(di, img_of(role, clip, i, body, h, 'f0').img()) for h, _k, _n in HAIRS}
                    fp_ = {fc: diff_img(di, img_of(role, clip, i, body, 'short', fc).img()) for fc, _k, _n in FACES}
                    for h, _k, _n in HAIRS:          # 변형이 옆모습에서 사라지면 안 된다
                        if h != 'short' and hp[h].getbbox() is None:
                            empty_var.append('%s_%s %s f%d %s' % (role, body, clip, i, h))
                    for fc, _k, _n in FACES:
                        if fc != 'f0' and fp_[fc].getbbox() is None:
                            empty_var.append('%s_%s %s f%d %s' % (role, body, clip, i, fc))
                    hl = [h for h, _k, _n in HAIRS]
                    for x_ in range(len(hl)):
                        for y_ in range(x_ + 1, len(hl)):
                            if list(hp[hl[x_]].getdata()) == list(hp[hl[y_]].getdata()):
                                same_var.append('%s_%s %s f%d %s=%s' % (role, body, clip, i, hl[x_], hl[y_]))
                    for h, _k, _n in HAIRS:          # 머리 패치 + 얼굴 패치를 **함께** 얹어도 그 조합이 나오는가
                        for fc, _k2, _n2 in FACES:
                            got = apply_patch(apply_patch(di, hp[h]), fp_[fc])
                            want = img_of(role, clip, i, body, h, fc).img()
                            if list(got.getdata()) != list(want.getdata()):
                                combo_bad += 1
                                print('   [!!] 조합 실패 %s_%s %s f%d %s+%s' % (role, body, clip, i, h, fc))
    for sid, arole, abody in SHAPES:
        for clip in S12_IDS:
            for i in range(dict(CLIPS)[clip]):
                _b, _o, a0 = raw_of(arole, clip, i, abody)
                for iid, _k, _p, _c in IMPRINTS:
                    if imprint_layer(iid, a0).pixels():
                        imp_seen.setdefault(iid, set()).add('%s/%s/f%d' % (sid, clip, i))
    n_side_cells = len(SHAPES) * sum(n for c_, n in S12_CLIPS)
    imp_vis = {iid: '%d/%d' % (len(imp_seen.get(iid, ())), n_side_cells) for iid, _k, _p, _c in IMPRINTS}
    print('[검사 S12] 머리+얼굴 패치 18조합 × 돌아선 행 %d칸: 불일치 %d건 · 사라진 변형 %d · 같아진 머리 %d'
          % (side_frames, combo_bad, len(empty_var), len(same_var)))
    print('[검사 S12] 각인이 보이는 칸(4체형 × 5칸 중):', imp_vis)
    S12_CHECK = {'side_clash': s12_tot, 'all_rows_clash': all_tot, 'detail': s12_det,
                 'patch_combo_mismatch': combo_bad, 'patch_combo_tested': side_frames * 18,
                 'variant_vanished': empty_var, 'hair_variants_identical': same_var,
                 'imprint_visible_cells': imp_vis}

    # ── S12 검증 그림 ──
    # ① 걷기 순서(×3) — 8역할, 체형 A·B 번갈아, 각자 머리·얼굴
    seqS = [('walk_side', 0), ('walk_side', 1), ('walk_side', 2), ('carry_side', 0), ('carry_side', 1)]
    WS, HS = 150 + len(seqS) * 150, 40 + 8 * 170
    im = room_bg(WS, HS, 0.99, False)
    d = ImageDraw.Draw(im)
    for r, role in enumerate(ROLES):
        body = BODY_IDS[r % 2]
        hair, face = LOOK[(role, body)]
        y0 = 40 + r * 170
        d.text((8, y0 + 70), ROLE_KO[role], font=f14, fill=(236, 206, 150))
        d.text((8, y0 + 90), '%s · %s/%s' % (BODIES[body]['ko'], hair, face), font=f12, fill=(170, 144, 110))
        for j, (clip, fi) in enumerate(seqS):
            cc_, _ = build(role, clip, fi, body, hair, face)
            spr = room_light(up(cc_.img(), 3))
            im.paste(spr, (150 + j * 150 - 20, y0 + 160 - BASE_Y * 3), spr)
    for j, (clip, fi) in enumerate(seqS):
        d.text((150 + j * 150 + 10, 20), '%s f%d' % (clip, fi), font=f12, fill=(236, 206, 150))
    d.text((8, 2), '옆모습 — 오른쪽이 원본, 왼쪽은 좌우 반전(×3, 방 빛)', font=f14, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'walk_side.png'))

    # ② 70px 판독 — 색 / 검은 실루엣, 8역할 × 체형 A·B
    sc70 = 70.0 / 49.0
    W7, H7 = 140 + 16 * 70, 34 + 3 * 110
    im = room_bg(W7, H7, 0.99, True)
    d = ImageDraw.Draw(im)
    for rr, (lab, clip, fi, sil) in enumerate((('색 · 걷기 f2', 'walk_side', 2, False),
                                               ('실루엣 · 걷기 f0', 'walk_side', 0, True),
                                               ('색 · 들고 걷기', 'carry_side', 0, False))):
        y0 = 34 + rr * 110
        d.text((8, y0 + 40), lab, font=f12, fill=(40, 28, 18))
        for j, (role, body) in enumerate(order):
            hair, face = LOOK[(role, body)]
            one = build(role, clip, fi, body, hair, face)[0].img()
            if sil:
                px_ = one.load()
                for yy in range(one.height):
                    for xx in range(one.width):
                        if px_[xx, yy][3] > 0:
                            px_[xx, yy] = (22, 14, 10, 255)
            z70 = one.resize((int(round(CELL * sc70)), int(round(CELL * sc70))), Image.NEAREST)
            im.paste(z70, (140 + j * 70 + 35 - z70.width // 2, y0 + 104 - int(BASE_Y * sc70)), z70)
    for j, (role, body) in enumerate(order):
        d.text((140 + j * 70 + 6, 6), ROLE_KO[role][:2] + body.upper(), font=f12, fill=(40, 28, 18))
    im.save(os.path.join(OUT, 'check', 'side70.png'))

    # ③ 옆얼굴 — 머리 6종 · 얼굴 3종 (×7), 어른과 아이
    W8, H8 = 20 + 8 * 230, 60 + 2 * 300
    im = room_bg(W8, H8, 0.99, False)
    d = ImageDraw.Draw(im)
    looks8 = [(h, 'f0') for h, _k, _n in HAIRS] + [('short', 'f1'), ('short', 'f2')]
    for rr, (role, body) in enumerate((('engineer', 'a'), ('kid', 'b'))):
        for j, (h, fc) in enumerate(looks8):
            cc_, a_ = build(role, 'walk_side', 0, body, h, fc)
            ht = int(a_['head_top'][1])
            cut = cc_.img().crop((16, ht - 6, 44, ht + 28))
            z = up(cut, 7)
            im.paste(z, (20 + j * 230, 50 + rr * 300), z)
            if rr == 0:
                d.text((20 + j * 230, 30), '%s · %s' % (h, fc), font=f14, fill=(236, 206, 150))
    d.text((8, 4), '옆얼굴 — 눈(2×3)·눈썹·코·입·홍조. 머리 갈래는 뒤통수 밑에서만 나온다(위: 어른, 아래: 아이)',
           font=f14, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'side_hair_face.png'))

    # ④ 방 빛 받은 옆모습 띠(×3, 5칸: walk_side f0~2 + carry_side f0~1) — 비교 페이지가 쓴다
    side_lit = {}
    for body in BODY_IDS:
        for role in ROLES:
            hair, face = LOOK[(role, body)]
            strip = Image.new('RGBA', (CELL * 3 * 5, CELL * 3), (0, 0, 0, 0))
            for j, (clip, fi) in enumerate(seqS):
                cc_, _ = build(role, clip, fi, body, hair, face)
                strip.paste(room_light(up(cc_.img(), 3)), (CELL * 3 * j, 0))
            nm = 'sidelit_%s.png' % sheet_name(role, body)
            strip.save(os.path.join(OUT, 'check', nm))
            side_lit[sheet_name(role, body)] = {'file': 'check/' + nm, 'role': role, 'body': body,
                                               'hair': hair, 'face': face}
    # ⑤ S12-B 새 행 — work_34 · carry_34 · idle_glance (×3, 방 빛), 8역할
    seqB = [(c_, i_) for c_, n_ in S12B_CLIPS for i_ in range(n_)]
    WB, HB = 150 + len(seqB) * 130, 40 + 8 * 170
    im = room_bg(WB, HB, 0.99, False)
    d = ImageDraw.Draw(im)
    for r, role in enumerate(ROLES):
        body = BODY_IDS[r % 2]
        hair, face = LOOK[(role, body)]
        y0 = 40 + r * 170
        d.text((8, y0 + 70), ROLE_KO[role], font=f14, fill=(236, 206, 150))
        for j, (clip, fi) in enumerate(seqB):
            cc_, _ = build(role, clip, fi, body, hair, face)
            spr = room_light(up(cc_.img(), 3))
            im.paste(spr, (150 + j * 130 - 40, y0 + 160 - BASE_Y * 3), spr)
    for j, (clip, fi) in enumerate(seqB):
        d.text((150 + j * 130 + 4, 20), '%s f%d' % (clip, fi), font=f12, fill=(236, 206, 150))
    d.text((8, 2), 'S12-B 새 행 — 3/4 일하기 · 3/4 들기 · 정면→3/4→정면 둘러보기 (×3)', font=f14, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'turn_new.png'))
    glance_lit = {}
    for body in BODY_IDS:
        for role in ROLES:
            hair, face = LOOK[(role, body)]
            strip = Image.new('RGBA', (CELL * 3 * len(seqB), CELL * 3), (0, 0, 0, 0))
            for j, (clip, fi) in enumerate(seqB):
                cc_, _ = build(role, clip, fi, body, hair, face)
                strip.paste(room_light(up(cc_.img(), 3)), (CELL * 3 * j, 0))
            nm = 'turnlit_%s.png' % sheet_name(role, body)
            strip.save(os.path.join(OUT, 'check', nm))
            glance_lit[sheet_name(role, body)] = 'check/' + nm
    print('[ok] S12 check/walk_side.png · side70.png · side_hair_face.png · turn_new.png · sidelit_* · turnlit_*')

    # ── S15 검증 그림 — 원정(잠수복 겹을 얹은 판) ──
    def suited(role, clip, fi, body, hair, face):
        im_ = build(role, clip, fi, body, hair, face)[0].img()
        im_.alpha_composite(suit_layer(role, clip, fi, body).img())
        return im_
    seq15 = [(c_, i_) for c_, n_ in S15_CLIPS for i_ in range(n_)]
    W15, H15 = 150 + len(seq15) * 112, 40 + 8 * 170
    im = Image.new('RGB', (W15, H15), (10, 30, 38))
    d = ImageDraw.Draw(im)
    d.rectangle([0, H15 - 30, W15, H15], fill=(40, 46, 40))
    for r, role in enumerate(ROLES):
        body = BODY_IDS[r % 2]
        hair, face = LOOK[(role, body)]
        y0 = 40 + r * 170
        d.text((8, y0 + 70), ROLE_KO[role], font=f14, fill=(200, 226, 220))
        for j, (clip, fi) in enumerate(seq15):
            spr = up(suited(role, clip, fi, body, hair, face), 3)
            im.paste(spr, (150 + j * 112 - 60, y0 + 160 - BASE_Y * 3), spr)
    for j, (clip, fi) in enumerate(seq15):
        d.text((150 + j * 112 - 6, 20), '%s %d' % (clip, fi), font=f12, fill=(200, 226, 220))
    d.text((8, 2), 'S15 원정 — 잠수복 겹(면갑 유리·투구 등불·발목 납 띠·거품)을 얹은 판 (×3)', font=f14, fill=(220, 236, 230))
    im.save(os.path.join(OUT, 'check', 'expedition.png'))
    # 70px — 잠수복을 입어도 역할이 갈리는가(색 / 실루엣)
    W7, H7 = 140 + 16 * 70, 34 + 2 * 110
    im = Image.new('RGB', (W7, H7), (16, 40, 48))
    d = ImageDraw.Draw(im)
    for rr, (lab, clip, fi, sil) in enumerate((('잠수복 · 걸음', 'swim_side', 0, False), ('실루엣', 'swim_side', 0, True))):
        y0 = 34 + rr * 110
        d.text((8, y0 + 40), lab, font=f12, fill=(210, 230, 224))
        for j, (role, body) in enumerate(order):
            hair, face = LOOK[(role, body)]
            one = suited(role, clip, fi, body, hair, face)
            if sil:
                px_ = one.load()
                for yy in range(one.height):
                    for xx in range(one.width):
                        if px_[xx, yy][3] > 0:
                            px_[xx, yy] = (6, 14, 18, 255)
            z70 = one.resize((int(round(CELL * sc70)), int(round(CELL * sc70))), Image.NEAREST)
            im.paste(z70, (140 + j * 70 + 35 - z70.width // 2, y0 + 104 - int(BASE_Y * sc70)), z70)
    for j, (role, body) in enumerate(order):
        d.text((140 + j * 70 + 6, 6), ROLE_KO[role][:2] + body.upper(), font=f12, fill=(210, 230, 224))
    im.save(os.path.join(OUT, 'check', 'suit70.png'))
    # 얼굴이 유리 너머로 보이는가 — 확대
    im = Image.new('RGB', (20 + 6 * 250, 290), (10, 30, 38))
    d = ImageDraw.Draw(im)
    for j, (role, body, clip, fi, h, fc) in enumerate((('engineer', 'a', 'swim_idle', 0, 'short', 'f0'),
                                                       ('medic', 'b', 'swim_idle', 0, 'curly', 'f2'),
                                                       ('scout', 'a', 'swim_side', 0, 'tied', 'f1'),
                                                       ('kid', 'b', 'swim_side', 1, 'scarf', 'f0'),
                                                       ('trader', 'b', 'return_tired', 0, 'long', 'f1'),
                                                       ('farmer', 'a', 'return_tired', 1, 'braid', 'f2'))):
        one = suited(role, clip, fi, body, h, fc)
        _b, _o, a_ = raw_of(role, clip, fi, body)
        ht = int(a_['head_top'][1])
        cut = one.crop((14, max(0, ht - 8), 50, max(0, ht - 8) + 34))
        z = up(cut, 7)
        im.paste(z, (20 + j * 250, 30), z)
        d.text((20 + j * 250, 8), '%s %s %s+%s' % (ROLE_KO[role], clip, h, fc), font=f12, fill=(210, 230, 224))
    im.save(os.path.join(OUT, 'check', 'suit_faces.png'))
    # 비교 페이지용 — 잠수복을 얹은 원정 띠(×3, 12칸)
    exp_lit = {}
    for body in BODY_IDS:
        for role in ROLES:
            hair, face = LOOK[(role, body)]
            strip = Image.new('RGBA', (CELL * 3 * len(seq15), CELL * 3), (0, 0, 0, 0))
            for j, (clip, fi) in enumerate(seq15):
                strip.paste(up(suited(role, clip, fi, body, hair, face), 3), (CELL * 3 * j, 0))
            nm = 'explit_%s.png' % sheet_name(role, body)
            strip.save(os.path.join(OUT, 'check', nm))
            exp_lit[sheet_name(role, body)] = 'check/' + nm
    print('[ok] S15 check/expedition.png · suit70.png · suit_faces.png · explit_*')

    # ── 메타 ──
    meta = {
        '_comment': 'P2 48px 생활형 도트 — 확정 화풍. 정수 배율 + image-rendering:pixelated 필수.',
        'style': 'p2', 'authored': 'hand-plotted pixels, no generative AI',
        'src_cell': CELL, 'src_baseline': BASE_Y, 'src_ppm': PPM,
        'sheet_scale': SHEET_K, 'cell': CELL * SHEET_K, 'baseline': BASE_Y * SHEET_K,
        'ppm': PPM * SHEET_K,
        'room_scale': ROOM_K, 'room_cell': CELL * ROOM_K, 'room_baseline': BASE_Y * ROOM_K,
        'room_h_1m6': int(H_ADULT * ROOM_K),
        'cols': MAXF,
        'clips': [c for c, _ in CLIPS],
        'frames': {c: n for c, n in CLIPS},
        'rows': {c: i for i, (c, _) in enumerate(CLIPS)},
        'anim_seconds': CLIP_SEC,
        'sheet': 'static/art/chars/front/p2/<role>.png  (체형 A, x4, 셀 256, 발 기준선 240)',
        'sheet_b': 'static/art/chars/front/p2/<role>_b.png  (체형 B, 같은 규약)',
        'source': 'static/art/chars/front/p2/src/<role>[_b].png  (x1, 셀 64, 발 기준선 60)',
        'tint_mask': 'static/art/chars/front/p2/masks/<role>[_b].png  (x1, L8)',
        'imprint_layer': 'static/art/chars/front/p2/imprints/<id>.png (어른 체형 A) · '
                         'imprints/b/ (어른 체형 B) · imprints/kid/ (아이 A) · imprints/kid_b/ (아이 B). '
                         '같은 셀·같은 자리에 알파 합성. 기본은 전부 꺼짐',
        'octopus': 'static/art/chars/front/p2/octopus.png  (x4, 4칸: idle f0~2 + wrap)',
        'bodies': {bid: {'ko': BODIES[bid]['ko'], 'note': BODIES[bid]['note'],
                         'sheet_suffix': ('' if bid == 'a' else '_b')} for bid in BODY_IDS},
        'body_rule': '역할과 체형은 독립이다(어느 역할에나 어느 체형이든). 체형을 색으로 '
                     '표시하지 않는다. 키·발 기준선·머리 크기·얼굴 자리는 체형과 무관하게 같다.',
        'hair': [{'id': i, 'ko': k, 'note': n,
                  'layer': 'hair/<role>_<body>/%s.png' % i} for i, k, n in HAIRS],
        'faces': [{'id': i, 'ko': k, 'note': n,
                   'layer': 'faces/<role>_<body>/%s.png' % i} for i, k, n in FACES],
        'layer_rule': '머리·얼굴 레이어는 **기본 시트(short + f0)와의 차이만 담은 투명 패치**다. '
                      'src/<role>[_b].png 위에 같은 자리로 알파 합성하면 그 조합이 된다(생성기가 전수 검증). '
                      'x1만 낸다 — x4가 필요하면 NEAREST로 정수 확대한다. '
                      '머리는 투구 테 아래에서만 바뀌므로 「머리에 쓴 것 = 역할」 규칙을 흐리지 않는다.',
        'variation_recipe': '머리·얼굴·체형은 역할과 무관하게 뽑는다. 시드는 uid + 주민 id '
                            '(같은 입력이면 같은 사람 — D6). 생성기의 pick_look()이 같은 꼴의 FNV 해시를 쓴다.',
        'roles': meta_roles['a'],
        'roles_b': meta_roles['b'],
        'imprints': [{'id': i, 'ko': k, 'part': p, 'color': c,
                      'on_hair': (i in IMPRINT_ON_HAIR)} for i, k, p, c in IMPRINTS],
        'layer_checks': '생성기가 매 실행마다: ①각인×각인 ②각인×얼굴 3종 ③각인×머리 6종 '
                        '(머리 위에 얹히도록 설계된 water_memory 제외) ④기본머리 덮임 '
                        '⑤기본시트+패치==변형시트 를 전수 검사한다.',
        # ── S11 (스프린트 11-B) — 아래 키는 전부 **새로 더한 것**이다. 위의 값은 그대로 ──
        's11_rows': {c: {'row': i, 'frames': n, 'room': S11_KO[c][0], 'what': S11_KO[c][1],
                         'hands': S11_KO[c][2], 'seconds': CLIP_SEC[c]}
                     for i, (c, n) in enumerate(CLIPS) if c in S11_IDS},
        'room_work': ROOM_WORK,
        'room_work_rule': '방에 배치된 사람은 room_work[방 id] 행을 돈다. 플레이트 파일명 power = 방 id generator. '
                          '설비(밸브·레버·모루·독서대·화로·공기통·화분·선반·십자 상자)는 **사람 셀 안에 같이 찍혀 있다** — '
                          '그래서 방 플레이트의 어느 stand_x 에 세워도 동작이 방을 말한다. 설비는 몸 왼쪽에 있다 — '
                          '3/4 다섯 방(거주·창고·정수·온실·의무)은 셀 x 0~20, 옆모습 다섯 방(발전·공방·해독·식량·에어락)은 '
                          '셀 x 7~27(S12: 옆모습 어깨가 몸 가운데라 팔 길이 안으로 당겼다). 사람은 설비 쪽(왼쪽)을 본다. '
                          '설비가 사람 오른쪽에 와야 하면 셀 전체를 좌우 반전한다(외곽선·틴트 규칙 동일). '
                          'bath(물 끓이는 방)는 sit, hall 은 idle.',
        'combo_patch_rule': '머리·얼굴을 함께 바꿀 때: 기본 시트 + hair/<role>_<body>/<hair>.png 를 먼저 얹고, '
                            '머리가 short 가 아니고 얼굴이 f0 가 아니면 faces/<role>_<body>/<hair>_<face>.png 를, '
                            '아니면 faces/<role>_<body>/<face>.png 를 얹는다(PM 2026-10-03 결정 (가)). '
                            '정면 0~6행에서 곱슬·두건 × 얼굴②·③ 은 단순 겹침이면 틀린다 — 조합 파일이 그 답이다. '
                            '조합 파일은 모든 행(26)을 담고, 생성기가 18조합 × 16시트 × 전 행을 픽셀까지 검사한다.',
        'combo_check_result': COMBO_CHECK,
        'elevator': {'sequence': ['elevator_wait', 'back_walk(칸으로 들어감)', 'elevator_turn', 'elevator_ride',
                                  'walk(내림)'],
                     'note': 'ride 는 거의 정지 — 내려가는 느낌은 칸 전체를 세로로 움직여 낸다. '
                             'turn 은 1프레임(0.25초)만 보여 준다. 얼굴 패치·얼굴 각인은 turn 에서 꺼진다(뒷모습과 같은 규칙)'},
        'imprint_hide_rule': '몸 앞에 든 물건(담요·상자·붕대)이 각인 부위를 가리는 프레임에서는 그 각인을 그리지 않는다 — '
                             '각인 시트(imprints/*.png)의 그 칸이 이미 비어 있으므로 클라이언트는 아무 것도 할 필요가 없다.',
        'layer_checks_s11': '생성기가 새 14행 × 4체형 × 전 프레임에서 ①각인×각인 ②각인×얼굴 ③각인×머리 '
                            '④각인×설비·든 물건 ⑤얼굴×설비·든 물건 ⑥머리×옆 설비 를 전수 검사한다.',
        's11_check_result': S11_CHECK,
        's11_lit_strips': lit_index,
        # ── S12 (스프린트 12-C) — 아래 키는 전부 **새로 더한 것**이다. 위의 값은 그대로 ──
        's12_rows': {c: {'row': i, 'frames': n, 'where': S12_KO[c][0], 'what': S12_KO[c][1],
                         'hands': S12_KO[c][2], 'seconds': CLIP_SEC[c],
                         'stride_src_px_per_loop': S12_STRIDE[c]}
                     for i, (c, n) in enumerate(CLIPS) if c in SIDE_IDS},
        'facing': {'walk_side': 'right', 'carry_side': 'right',
                   'note': '옆모습 행은 **오른쪽을 보는 것이 원본**이다. 왼쪽으로 걸을 때는 셀을 좌우 반전한다'
                           '(CSS scaleX(-1) / drawImage 음수 폭). 반전 축은 셀 가운데(원화 x 32, ×4 시트는 128)다. '
                           '발 기준선은 그대로라 세로 보정은 0이다. 머리·얼굴·각인 패치도 같은 반전을 함께 건다(같은 셀이므로). '
                           '반전하면 보이는 쪽 각인이 그대로 따라온다 — 왼쪽으로 걸어도 「오른」 각인이 보인다(도트 게임의 관례적 생략).',
                   'other_rows': '0~20행은 정면·뒷모습이라 반전하지 않는다(기존 그대로)'},
        'side_speed': '바닥 이동 = stride_src_px_per_loop × 배율 / seconds. 예: walk_side 어른 ×3 → 16×3/0.8 = 60px/초. '
                      '이 값으로 밀면 발이 미끄러지지 않는다. 아이는 보폭이 작다.',
        'side_imprints': {'near_shown': list(SIDE_NEAR), 'center_shown': list(SIDE_CENTER),
                          'far_hidden': list(SIDE_FAR),
                          'rule': '오른쪽을 보면 몸의 오른쪽이 보는 사람을 향한다 → 이름에 「오른」이 든 각인은 보이고 「왼」 각인 넷은 '
                                  '먼 쪽이라 끈다. 가슴 목걸이·이마·머리 뒤 베일은 옆에서도 보인다. 앞으로 흔든 팔·장갑·도구·상자가 '
                                  '가린 칸은 잘라 내고, 한 점만 남으면 그 프레임에서 끈다. 각인 시트의 그 칸이 이미 비어 있으므로 '
                                  '클라이언트가 할 일은 없다.'},
        'side_layers': '머리 6종·얼굴 3종은 옆모습에서도 같은 패치 방식이다(hair/·faces/ 시트의 21~22행). '
                       '여섯 머리가 모두 같은 앞머리 띠 + 귀밑머리로 시작하고, 갈래(매듭·긴머리·땋음·두건 꼬리)는 뒤통수 밑에서만 나온다. '
                       '얼굴 픽셀과 머리 픽셀이 겹치지 않아 머리 패치 + 얼굴 패치를 함께 얹어도 그 조합과 픽셀이 같다(18조합 전수 검사).',
        'side_check_result': S12_CHECK,
        's12_lit_strips': {'cells': ['%s f%d' % (c_, i_) for c_, i_ in seqS], 'scale': 3, 'strips': side_lit},
        # ── S12-B (PM 범위 추가: 일하는 사람은 일하는 쪽을 본다) ──
        's12b_rows': {c: {'row': i, 'frames': n, 'where': S12B_KO[c][0], 'what': S12B_KO[c][1],
                          'hands': S12B_KO[c][2], 'seconds': CLIP_SEC[c], 'view': WORK_VIEW[c]}
                      for i, (c, n) in enumerate(CLIPS) if c in S12B_IDS},
        'work_view': WORK_VIEW,
        'work_view_rule': '7~16행은 S12-B 에서 제자리에 다시 그렸다(행 번호·프레임 수·초 그대로). 설비가 셀 왼쪽에 있으므로 '
                          '**왼쪽을 보는 것이 원본**이다. 설비가 사람 오른쪽에 와야 하는 자리면 셀 전체를 좌우 반전한다(설비·사람·패치·각인 함께). '
                          'profile_left = 옆모습(먼 팔은 몸 뒤, 역할 도구는 허리 뒤에 건다), q34_left = 3/4(왼손이 일하고 오른손 도구는 그대로). '
                          '17행 rest_lounge 는 뒷모습, 18~20행 엘리베이터와 0~6행은 정면 그대로다. 정면 work(2)·carry(4)는 초상·UI 카드용으로 남고, '
                          '방 밖에서 일하거나 드는 장면에는 work_34·carry_34 를 쓴다.',
        'turn_imprints': {'profile_left_hidden': list(PROFILE_HIDE), 'q34_left_hidden': list(Q34_HIDE),
                          'rule': '옆모습 작업: 먼 쪽 목덜미·관자놀이와 허리에 건 도구 쪽 손목을 끈다. 일하는 팔의 각인(왼 위팔·왼 장갑)은 보인다. '
                                  '3/4: 돌린 얼굴의 먼 관자놀이만 끄고, 베일은 뒤통수(오른쪽)로 늘어진다. 가려진 칸은 시트에서 이미 비어 있다.'},
        's12b_lit_strips': {'cells': ['%s f%d' % (c_, i_) for c_, i_ in seqB], 'scale': 3, 'strips': glance_lit},
        # ── S15-D 원정 ──
        's15_rows': {c: {'row': i, 'frames': n, 'where': S15_KO[c][0], 'what': S15_KO[c][1],
                         'hands': S15_KO[c][2], 'seconds': CLIP_SEC[c],
                         'facing': ('right' if c in S15_SIDE else 'front'),
                         'stride_src_px_per_loop': S15_STRIDE.get(c)}
                     for i, (c, n) in enumerate(CLIPS) if c in S15_IDS},
        's15_bible_note': '이 행들은 헤엄이 아니다 — DECISIONS 2026-09-22 「주민은 헤엄치지 않고 무게추로 해저를 걷는다」에 따라 '
                          'swim_side 는 무게추로 바닥을 디디며 한 걸음마다 잠깐 뜨는 걸음, swim_idle 은 바닥에 서서 물살에 흔들리는 것이다. '
                          '자유 유영이 필요하면 결정 로그를 먼저 고친다(요청함).',
        'suit_layer': 'static/art/chars/front/p2/suit/<role>_<body>.png (x1) · <role>_<body>_x4.png — 전 행. 원정 나갈 때만 얹는다.',
        'suit_rule': '겹치는 순서: 기본 시트 → hair/<hair>.png → 얼굴(combo_patch_rule 대로 <face>.png 또는 <hair>_<face>.png) '
                     '→ **suit** → 각인. 잠수복 겹은 머리 6종·얼굴 18조합·각인 12종의 어느 픽셀과도 겹치지 않는다(생성기 전수 검사) — '
                     '그래서 얼굴(눈·눈썹·입)은 면갑 유리 너머로 그대로 보이고 조합 규칙도 그대로다. 겹은 ①면갑 유리 가장자리 + 반짝임 '
                     '②투구 등불(스스로 빛남 — 틴트 금지) ③발목 납 띠 ④거품(빈 칸에만). 옆모습 행을 좌우 반전할 때 겹도 같이 반전한다.',
        'suit_check_result': SUIT_CHECK,
        'combo_check_result_s15': {'all_rows_including_s15': True, 'mismatch_with_rule': combo_bad_all},
        'billboard_3d': {
            'note': '원정 3D 화면(아이소 45°, EXPEDITION §3-6)에서 빌보드로 쓸 때: 걷는 방향을 화면 좌표로 바꿔 넷 중 하나를 고른다. '
                    '화면 아래로 = 정면(walk 1 / 물속 swim_idle 23+ 서기), 화면 위로 = 뒷모습(back_walk 6), '
                    '화면 오른쪽 = 옆(walk_side 21 / 물속 swim_side), 왼쪽 = 옆 좌우 반전. 대각선은 가로 성분이 크면 옆, 아니면 정면·뒤. '
                    '물속은 옆모습만으로도 충분하다(정면 걸음 대신 swim_side + 반전, 멈추면 swim_idle). '
                    '빌보드 발 원점 = 셀 발 기준선(원화 y 60, ×4 시트 240) · 셀 가운데 x. 1.6m = 44 원화 px.',
            'dirs': {'down': ['walk', 'swim_idle'], 'up': ['back_walk'], 'right': ['walk_side', 'swim_side'],
                     'left': ['walk_side(반전)', 'swim_side(반전)']},
            'camera': '아이소 45°/45° 가정(DECISIONS 2026-09-23). 실제 카메라 각을 요청함으로 물었다'},
        's15_lit_strips': {'cells': ['%s f%d' % (c_, i_) for c_, i_ in seq15], 'scale': 3, 'strips': exp_lit,
                           'note': '잠수복 겹을 얹은 판'},
        'rules_2_5d': {
            '1_integer_scale': '정수 배율 + NEAREST(image-rendering: pixelated). 소수 배율 금지',
            '2_lamp_tint': 'masks/<role>.png 가 흰 곳만 방 등불색을 곱한다. 0인 곳(눈·외곽선·랜턴 불꽃·유리)은 건드리지 않는다. 권장식: rgb *= (1 + 0.30*(tint-1)) * (1.13 - 0.32*(y/h))',
            '3_contact_shadow': '발 기준선에 폭 = 스프라이트 70%, 높이 = 7.5%의 흐린 타원 (알파 165)',
            '4_palette': '배경 렌더 16색에서 명도가 가까운 색으로 20% 당기고, 방 평균색 기준 대비를 1.26배 재확장 (이 파일 harmonize()에 구현)',
            '5_depth': '방 깊이 1.7m — 벽 가까이 세우고 앞뒤로 겹치는 소품을 두지 않는다',
        },
    }
    with io.open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1))
    print('[ok] meta.json / check/*.png')


if __name__ == '__main__':
    main()
