# -*- coding: utf-8 -*-
"""클립명 -> AI 생성 테이크 매핑.

docs/AI_PROMPTS.md 의 테이크 구성과 1:1로 대응한다.
5초짜리 테이크 하나를 뽑아 여러 컷이 @초로 나눠 쓴다.
"""

TAKE_LEN = 5.0                      # 서비스에서 뽑는 클립 길이(초)
SLOTS = (0.2, 1.0, 1.8, 2.6, 3.4)    # 테이크 안에서 쓸 시작 지점 후보

# 테이크 -> 그 테이크가 커버하는 클립명들
TAKES = {
    "kkamu_front_take": [           # K1 정면 대사
        "kkamu_stare", "kkamu_deadpan", "kkamu_closeup", "kkamu_firm",
        "kkamu_done", "kkamu_calm", "kkamu_alert", "kkamu_witness",
        "kkamu_shout", "kkamu_arms", "kkamu_confident", "kkamu_innocent",
        "kkamu_smug", "kkamu_point", "kkamu_whisper",
    ],
    "kkamu_tilt_take": [            # K2 갸웃 / 시선 회피
        "kkamu_tilt", "kkamu_lookaway", "kkamu_freeze", "kkamu_defensive",
        "kkamu_think", "kkamu_sigh", "kkamu_stop", "kkamu_panic",
        "kkamu_casual", "kkamu_phone",
    ],
    "kkamu_bowl_take": [            # K3 물그릇 발 (시그니처 #1)
        "kkamu_paw_bowl", "kkamu_bowl_calm", "kkamu_slow_lift",
    ],
    "kkamu_blanket_take": [         # K4 이불 / 숨기
        "kkamu_blanket", "kkamu_in_blanket", "kkamu_hide",
    ],
    "kkamu_run_take": [             # K5 도망 (난이도 높음)
        "kkamu_run", "kkamu_walkaway", "kkamu_to_sofa",
    ],
    "kkamu_props_take": [           # K6 소품 다루는 까뮈
        "kkamu_food_bag", "kkamu_treat",
    ],
    "bawi_front_take": [            # B1 정면 대사
        "bawi_deadpan", "bawi_serious", "bawi_proud", "bawi_eyes",
        "bawi_blink", "bawi_calm", "bawi_freeze", "bawi_turn",
        "bawi_lookaway", "bawi_tilt", "bawi_point",
    ],
    "bawi_sit_take": [              # B2 앉아서 응시 / 기다림
        "bawi_sit_stare", "bawi_sit_door", "bawi_same_pose",
        "bawi_still_there", "bawi_at_door", "bawi_watching",
        "bawi_stare_long", "bawi_ears", "bawi_door_wide",
    ],
    "bawi_sofa_take": [             # B3 소파 뒤 (시그니처 #2)
        "sofa_back_butt", "bawi_behind_sofa", "bawi_pulled_out",
        "bawi_scolded",
    ],
    "bawi_sleep_take": [            # B4 자는 얼굴 / 드러눕기
        "bawi_sleep_face", "bawi_still", "bawi_collapse", "bawi_despair",
        "bawi_burrow", "bawi_blanket",
    ],
    "bawi_react_take": [            # B5 벌떡 / 꼬리 / 반응
        "bawi_jump", "bawi_tail", "bawi_smile", "bawi_look_back",
        "bawi_follow", "bawi_own_bowl",
    ],
    "bawi_paw_bowl": [              # B6 바위도 발 담그기 (EP04 반전, 단독 생성)
        "bawi_paw_bowl",
    ],
}

# 테이크로 안 묶는 것 - 사물/배경/2마리. 개별 생성하거나 정지 이미지로 처리.
STANDALONE = {
    "phone_buzz", "two_blankets", "empty_room", "scale_paws", "empty_bag",
    "sofa_back_two", "leash_closeup", "window_sunny", "window_sunset",
    "night_walk", "wet_floor", "broken_pot", "door_lock", "door_open",
    "owner_pov_sofa", "owner_sees_paw", "wet_pawprints",
}

CLIP_TO_TAKE = {c: t for t, clips in TAKES.items() for c in clips}


def slot_for(duration: float, recent: list[float]) -> float:
    """컷 길이에 맞는 시작 지점을 고른다.

    긴 컷은 테이크 뒤쪽 슬롯을 못 쓰기 때문에 단순 로테이션은 어긋난다.
    유효한 슬롯 중 '가장 오래전에 쓴 것'을 고르면 같은 구간이 연속으로 반복되지 않는다.
    recent: 이 테이크에서 이미 쓴 슬롯들(오래된 것부터)
    """
    valid = [s for s in SLOTS if s + duration <= TAKE_LEN]
    if not valid:
        return round(max(0.0, TAKE_LEN - duration), 1)
    unused = [s for s in valid if s not in recent]
    if unused:
        return unused[0]
    return min(valid, key=lambda s: len(recent) - 1 - recent[::-1].index(s))
