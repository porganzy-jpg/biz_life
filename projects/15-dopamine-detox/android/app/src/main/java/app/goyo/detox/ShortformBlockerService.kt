package app.goyo.detox

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.widget.Toast

class ShortformBlockerService : AccessibilityService() {

    private var rules: Map<String, AppRule> = emptyMap()
    private val lastCheck = HashMap<String, Long>()
    private val lastDump = HashMap<String, Long>()
    private val history = HashMap<String, ArrayDeque<Long>>()

    override fun onServiceConnected() {
        rules = Rules.load(this)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        val pkg = event.packageName?.toString() ?: return
        val rule = rules[pkg] ?: return
        val now = System.currentTimeMillis()

        // 스크롤·내용 변경 이벤트는 매우 잦다. 창 전환은 항상, 나머지는 300ms 에 한 번만 검사.
        val isWindowChange = event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
        if (!isWindowChange && now - (lastCheck[pkg] ?: 0) < 300) return
        lastCheck[pkg] = now

        val root = rootInActiveWindow ?: return

        if (Prefs.dumpMode(this) && now - (lastDump[pkg] ?: 0) > 3000) {
            lastDump[pkg] = now
            NodeDumper.dump(this, pkg, root)
        }

        val surface = if (rule.blockWholeApp) {
            Surface("${pkg}_app", rule.name, emptyList(), emptyList(), verified = true)
        } else {
            Matcher.find(rule, root) ?: return
        }

        val past = history.getOrPut(surface.id) { ArrayDeque() }
        while (past.isNotEmpty() && now - past.first() > 60_000) past.removeFirst()

        val action = if (rule.blockWholeApp) BlockAction.HOME
        else BlockPolicy.decide(surface, past.toList(), now)

        when (action) {
            BlockAction.NONE -> return
            BlockAction.BACK -> performGlobalAction(GLOBAL_ACTION_BACK)
            BlockAction.HOME -> performGlobalAction(GLOBAL_ACTION_HOME)
        }
        past.addLast(now)
        BlockLog.append(this, pkg, surface.id, action)
        Toast.makeText(this, "${rule.name} ${surface.label}을(를) 닫았어요", Toast.LENGTH_SHORT).show()
    }

    override fun onInterrupt() {}
}
