package app.goyo.detox

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** 앱 안의 숏폼 구간 하나(예: 유튜브 쇼츠). */
data class Surface(
    val id: String,
    val label: String,
    val viewIds: List<String>,
    val selectedTabs: List<String>,
    val verified: Boolean,
)

data class AppRule(
    val pkg: String,
    val name: String,
    val blockWholeApp: Boolean,
    val surfaces: List<Surface>,
)

/**
 * 규칙은 코드가 아니라 assets/shortform_rules.json 에 있다.
 * 이후 원격 갱신(P2)도 같은 형식의 파일을 filesDir 에 덮어쓰는 방식으로 붙인다.
 */
object Rules {
    private const val ASSET = "shortform_rules.json"
    private const val OVERRIDE = "shortform_rules.override.json"

    fun load(ctx: Context): Map<String, AppRule> {
        val override = ctx.getFileStreamPath(OVERRIDE)
        val text = if (override.exists()) override.readText()
        else ctx.assets.open(ASSET).bufferedReader().use { it.readText() }
        return parse(text).associateBy { it.pkg }
    }

    fun parse(text: String): List<AppRule> {
        val apps = JSONObject(text).getJSONArray("apps")
        return (0 until apps.length()).map { i ->
            val a = apps.getJSONObject(i)
            val surfaces = a.optJSONArray("surfaces") ?: JSONArray()
            AppRule(
                pkg = a.getString("package"),
                name = a.optString("name"),
                blockWholeApp = a.optBoolean("blockWholeApp", false),
                surfaces = (0 until surfaces.length()).map { j ->
                    val s = surfaces.getJSONObject(j)
                    Surface(
                        id = s.getString("id"),
                        label = s.optString("label"),
                        viewIds = s.optJSONArray("viewIds").strings(),
                        selectedTabs = s.optJSONArray("selectedTabs").strings(),
                        verified = s.optBoolean("verified", false),
                    )
                },
            )
        }
    }

    private fun JSONArray?.strings(): List<String> =
        if (this == null) emptyList() else (0 until length()).map { getString(it) }
}
