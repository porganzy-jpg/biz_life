package app.goyo.detox

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import java.util.Calendar

/** P0 화면: 고지 → 접근성 켜기 → 덤프 모드 → 오늘 기록. 디자인은 P1에서. */
class MainActivity : Activity() {

    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pad = (16 * resources.displayMetrics.density).toInt()
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }

        col.addView(TextView(this).apply {
            text = "고요 — 숏폼은 지우고, 사람은 남긴다"
            textSize = 20f
        })
        // Play 정책의 '눈에 띄는 고지': 앱 안에서, 권한 요청 전에, 무엇을 읽고 어디로 가는지.
        col.addView(TextView(this).apply {
            text = "\n이 앱은 접근성 권한으로 유튜브·인스타·카카오톡·네이버·틱톡의 화면 구조를 읽어 " +
                "숏폼 화면이면 자동으로 닫습니다.\n\n• 화면 정보는 이 기기 안에서만 처리됩니다.\n" +
                "• 이 앱에는 인터넷 권한이 없어 어떤 데이터도 전송할 수 없습니다.\n" +
                "• 아래 버튼을 눌러 직접 '고요 숏폼 차단'을 켜야 동작합니다.\n"
        })
        col.addView(Button(this).apply {
            text = "동의하고 접근성 설정 열기"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })
        col.addView(Switch(this).apply {
            text = "덤프 모드 (새 화면 규칙 찾기용)"
            isChecked = Prefs.dumpMode(this@MainActivity)
            setOnCheckedChangeListener { _, on -> Prefs.setDumpMode(this@MainActivity, on) }
        })
        status = TextView(this).apply { setPadding(0, pad, 0, 0) }
        col.addView(status)

        setContentView(ScrollView(this).apply { addView(col, MATCH_PARENT, WRAP_CONTENT) })
    }

    override fun onResume() {
        super.onResume()
        val midnight = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0)
        }.timeInMillis
        val rules = Rules.load(this).values
        val unverified = rules.flatMap { r -> r.surfaces.filter { !it.verified }.map { "${r.name} ${it.label}" } }
        status.text = buildString {
            append("오늘 닫은 숏폼: ${BlockLog.countSince(this@MainActivity, midnight)}번\n\n")
            append("미검증 규칙: ${unverified.joinToString()}\n\n최근 기록\n")
            BlockLog.tail(this@MainActivity, 10).reversed().forEach { append(it).append('\n') }
        }
    }
}
