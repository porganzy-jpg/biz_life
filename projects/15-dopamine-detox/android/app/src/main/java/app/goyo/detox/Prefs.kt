package app.goyo.detox

import android.content.Context

object Prefs {
    private const val NAME = "goyo"
    private const val DUMP = "dump_mode"

    fun dumpMode(ctx: Context): Boolean =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).getBoolean(DUMP, false)

    fun setDumpMode(ctx: Context, on: Boolean) {
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit().putBoolean(DUMP, on).apply()
    }
}
