package app.goyo.detox

enum class BlockAction {
    /** 아무것도 안 함(직전 차단의 여파로 들어온 중복 이벤트 등). */
    NONE,
    /** 뒤로가기: 앱은 유지하고 숏폼 화면만 빠져나온다. 카톡처럼 꼭 필요한 앱에 적합. */
    BACK,
    /** 홈으로: 앱 자체를 떠난다. 뒤로가기가 숏폼에서 못 빠져나올 때의 최후 수단. */
    HOME,
}

object BlockPolicy {

    /**
     * 숏폼 화면이 감지됐을 때 무엇을 할지 정한다.
     *
     * @param surface      감지된 구간(예: 카톡 숏폼 탭). surface.id 로 앱별 분기 가능.
     * @param recentBlocks 같은 구간에서 최근 차단한 시각들(ms, 오래된 순). 이번 건은 포함 안 됨.
     * @param now          지금 시각(ms)
     *
     * 고려할 점:
     *  - 화면 전환 한 번에 이벤트가 여러 개 들어온다. 방금(예: 1초 안에) BACK 을 눌렀다면
     *    또 누르면 앱 밖으로 튕겨 나간다 → 짧은 쿨다운 동안은 NONE.
     *  - 뒤로가기 후에도 다시 숏폼이 뜨는 경우(유튜브가 쇼츠를 복원, 사용자가 계속 재진입)
     *    → 짧은 시간에 여러 번이면 HOME 으로 승격.
     *  - 카톡은 꼭 필요한 앱이라 HOME 으로 쫓아내면 불편이 크다. 카톡만 다르게 할지?
     */
    fun decide(surface: Surface, recentBlocks: List<Long>, now: Long): BlockAction {
        // TODO(사용자): 쿨다운·승격 규칙 구현 (5~10줄)
        return BlockAction.BACK
    }
}
