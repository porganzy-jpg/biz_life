package app.goyo.detox

import android.view.accessibility.AccessibilityNodeInfo

/** 현재 화면 트리에서 숏폼 구간을 찾는다. 찾으면 그 Surface 를, 없으면 null. */
object Matcher {

    fun find(rule: AppRule, root: AccessibilityNodeInfo): Surface? {
        for (s in rule.surfaces) {
            if (s.viewIds.any { id -> hasVisibleViewId(root, "${rule.pkg}:id/$id") }) return s
            if (s.selectedTabs.isNotEmpty() && hasSelectedTab(root, s.selectedTabs)) return s
        }
        return null
    }

    private fun hasVisibleViewId(root: AccessibilityNodeInfo, fullId: String): Boolean =
        root.findAccessibilityNodeInfosByViewId(fullId).any { it.isVisibleToUser }

    /**
     * 하단 탭 라벨("숏폼", "Shorts")은 다른 탭에 있을 때도 화면에 보이므로
     * 글자만 맞추면 오탐이 난다. 반드시 isSelected 인 노드만 인정한다.
     */
    private fun hasSelectedTab(root: AccessibilityNodeInfo, labels: List<String>): Boolean {
        for (label in labels) {
            val hits = root.findAccessibilityNodeInfosByText(label)
            for (n in hits) {
                if (!n.isVisibleToUser) continue
                val t = n.text?.toString()?.trim()
                val d = n.contentDescription?.toString()?.trim()
                val exact = t == label || d == label
                if (exact && (n.isSelected || n.parent?.isSelected == true)) return true
            }
        }
        return false
    }
}
