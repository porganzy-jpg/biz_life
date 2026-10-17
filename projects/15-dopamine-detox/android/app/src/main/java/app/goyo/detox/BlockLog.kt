package app.goyo.detox

import android.content.Context
import java.io.File

/**
 * 차단 기록(기기 안에만). 나중에 '충동 지도'(C)의 원자료가 된다.
 * 형식: epochMs,package,surfaceId,action
 */
object BlockLog {
    private const val FILE = "blocks.csv"

    fun append(ctx: Context, pkg: String, surfaceId: String, action: BlockAction) {
        File(ctx.filesDir, FILE).appendText("${System.currentTimeMillis()},$pkg,$surfaceId,$action\n")
    }

    fun tail(ctx: Context, n: Int): List<String> {
        val f = File(ctx.filesDir, FILE)
        return if (f.exists()) f.readLines().takeLast(n) else emptyList()
    }

    fun countSince(ctx: Context, sinceMs: Long): Int {
        val f = File(ctx.filesDir, FILE)
        if (!f.exists()) return 0
        return f.readLines().count { line ->
            val parts = line.split(',')
            parts.size >= 4 && parts[3] != BlockAction.NONE.name &&
                (parts[0].toLongOrNull() ?: 0) >= sinceMs
        }
    }
}
