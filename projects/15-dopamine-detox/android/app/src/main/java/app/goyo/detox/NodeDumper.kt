package app.goyo.detox

import android.content.Context
import android.view.accessibility.AccessibilityNodeInfo
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 덤프 모드: 지금 화면의 노드 트리를 텍스트로 저장한다.
 * 카톡 숏폼 탭처럼 아직 아무도 공개하지 않은 화면의 view id 를 찾는 용도.
 * 저장 위치: /sdcard/Android/data/app.goyo.detox/files/dumps/  (adb pull 로 가져온다)
 */
object NodeDumper {
    private val stamp = SimpleDateFormat("MMdd_HHmmss", Locale.US)

    fun dump(ctx: Context, pkg: String, root: AccessibilityNodeInfo): File {
        val dir = File(ctx.getExternalFilesDir(null), "dumps").apply { mkdirs() }
        val f = File(dir, "${pkg}_${stamp.format(Date())}.txt")
        val sb = StringBuilder()
        walk(root, 0, sb)
        f.writeText(sb.toString())
        return f
    }

    private fun walk(n: AccessibilityNodeInfo?, depth: Int, sb: StringBuilder) {
        if (n == null || depth > 60) return
        sb.append("  ".repeat(depth))
            .append(n.className?.toString()?.substringAfterLast('.'))
            .append(" id=").append(n.viewIdResourceName ?: "-")
        n.text?.let { sb.append(" text=\"").append(it.take(40)).append('"') }
        n.contentDescription?.let { sb.append(" desc=\"").append(it.take(40)).append('"') }
        if (n.isSelected) sb.append(" [SELECTED]")
        if (!n.isVisibleToUser) sb.append(" [hidden]")
        sb.append('\n')
        for (i in 0 until n.childCount) walk(n.getChild(i), depth + 1, sb)
    }
}
