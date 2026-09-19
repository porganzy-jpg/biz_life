from manim import *
import random
class BarcodeScan(Scene):
    def construct(self):
        random.seed(8801)
        self.camera.background_color = "#0B0710"
        # EAN-13 스타일 바코드 (세로 화면 중앙)
        bars = VGroup(); x = -3.2
        for i in range(48):
            w = random.choice([0.06,0.06,0.12,0.18]); gap = random.choice([0.06,0.1])
            bars.add(Rectangle(width=w, height=3.6, fill_color=WHITE, fill_opacity=1, stroke_width=0).move_to([x+w/2,0,0])); x += w+gap
        bars.move_to(ORIGIN)
        digits = Text("8 801234 567890", font_size=40, color=GREY_B).next_to(bars, DOWN, buff=0.35)
        self.play(FadeIn(bars, shift=UP*0.3), FadeIn(digits), run_time=0.5)
        # 스캔 라인 두 번
        line = Line(bars.get_left()+UP*2.2, bars.get_left()+DOWN*2.2, color="#FF2D2D", stroke_width=6)
        glow = line.copy().set_stroke(color="#FF2D2D", width=26, opacity=0.35)
        scan = VGroup(glow, line)
        self.add(scan)
        self.play(scan.animate.move_to(bars.get_right()), run_time=0.55, rate_func=linear)
        self.play(scan.animate.move_to(bars.get_left()), run_time=0.45, rate_func=linear)
        self.remove(scan)
        # 바코드가 붉게 물들고 마법진처럼 흔들림
        self.play(bars.animate.set_fill("#FF3B3B"), digits.animate.set_color("#FF7A7A"), run_time=0.25)
        ring = Circle(radius=2.6, color="#B14CFF", stroke_width=5).set_opacity(0)
        self.play(Create(ring.set_opacity(1)), bars.animate.set_fill("#C33BFF"), run_time=0.4)
        self.play(ring.animate.scale(2.4).set_opacity(0), bars.animate.scale(1.25).set_fill("#FF3B3B"), run_time=0.45)
        self.wait(0.15)
config.frame_rate = 30
