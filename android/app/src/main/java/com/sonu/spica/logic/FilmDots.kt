package com.sonu.spica.logic

import androidx.compose.ui.graphics.Color
import com.sonu.spica.ui.common.MARK_CORE
import com.sonu.spica.ui.common.MARK_RING
import com.sonu.spica.ui.common.MarkDot
import com.sonu.spica.ui.theme.C
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * The door's film, as data and one pure function. spec/done/onboarding-goals.md
 * § 1 · The door; the frozen contract is `spec/reference/onboarding-film.dc.html`.
 *
 * The approved prototype had no clock: a 500 ms tick set new targets and CSS
 * transitions did every frame in between. This is that, written down. A
 * per-beat target table says where everything should be on each beat, and
 * `frame(ms)` applies the browser's transition rules to it explicitly — each
 * channel eases from its *current* value whenever its target changes, keeps
 * running when it does not, and a fade reversed part-way takes only as long
 * as it had run (CSS Transitions § 3). Colours blend in sRGB, channel by
 * channel, as the browser blends them — not in Oklab, as Compose's `lerp`
 * would. So the film can be frozen at any millisecond and set beside the web's.
 *
 * The twin of `frontend/src/door/filmDots.ts`, kept the way `Tokens.kt` is
 * kept with `theme.ts`: the same names in the same order, the same
 * arithmetic, and colours as token names, never hex.
 *
 * Nothing here is random. The scatter is arithmetic on the dot's index and the
 * jitter a keyframe with a per-dot delay, so it is ported as it was.
 */
object FilmDots {

    /** Dots on screen. */
    const val N = 28

    /** One beat. */
    const val BEAT_MS = 500

    /** Beats in a loop: 22 s. */
    const val LOOP = 44
    const val LOOP_MS = LOOP * BEAT_MS

    /** The acts, by their first beat: mess 0–9, order 10–14, outcome 15–34, close 35–43. */
    const val ORDER_FROM = 10
    const val OUTCOME_FROM = 15
    const val CLOSE_FROM = 35

    /** Beats in one outcome scene; its figure shows from the scene's second beat. */
    const val SCENE_BEATS = 5

    /** The stage, in units: one unit is one dp at full size, and never more. */
    object STAGE {
        const val w = 390f
        const val h = 560f
    }

    /**
     * The mess: dot `i` takes `MESS[i % 8]`. Red was the sixth in the prototype;
     * red means *over* everywhere in the app, so it is `dietSoft` here.
     */
    val MESS: List<Color> = listOf(C.paisa, C.diet, C.work, C.dietInk, C.grey, C.dietSoft, C.paisaSoft, C.workSoft)

    /** The order: one colour per row of the month. */
    val ROWS: List<Color> = listOf(C.paisa, C.dietInk, C.diet, C.work)

    /** A missed day in an outcome scene: an empty track, not a judgement. */
    val MISSED: Color = C.ringIdle

    /** The mark, small and built. */
    val MARK_INK: Color = C.brand

    /**
     * The four outcomes, one person's month — the dots are days, the figure what
     * they added up to. Marketing, told as such; never written anywhere.
     */
    data class Win(val figure: String, val line: String, val hue: Color, val ink: Color, val missed: List<Int>)

    val WINS: List<Win> = listOf(
        Win("₹15,000", "saved this month.", C.paisa, C.paisaInk, listOf(4, 13, 22)),
        Win("−2 kg", "this month, and counting.", C.diet, C.dietInk, listOf(5, 6, 17, 26)),
        Win("6 hours", "a week, back for you.", C.work, C.workInk, listOf(9, 23)),
        Win("4 weeks", "at the gym. Started, and stuck.", C.dietInk, C.dietInk, emptyList()),
    )

    val WEEKDAYS: List<String> = listOf("M", "T", "W", "T", "F", "S", "S")

    /** The three captions, each a list of lines. */
    val CAPTIONS: List<List<String>> = listOf(
        listOf("Money slipping. Time slipping.", "Health slipping."),
        listOf("Spica puts it in order."),
        listOf("Time for what matters."),
    )

    /** What a screen reader hears, once. The captions are not read out as they change. */
    const val LABEL = "A short film in dots: a life slipping out of hand is put in order, and becomes results."

    class MarkBox(val x: Float, val y: Float, val size: Float)
    class Days(val top: Float, val cell: Float, val size: Float, val lineHeight: Float)
    class Figure(
        val top: Float, val size: Float, val lineHeight: Float, val tracking: Float,
        val lineTop: Float, val lineSize: Float, val lineLineHeight: Float,
    )
    class Caption(val top: Float, val size: Float, val lineHeight: Float, val weight: Int)

    /**
     * Where the text sits, in stage units, as the prototype laid it out: a block's
     * top and its line height (each line is centred in its own line box).
     */
    object LAYOUT {
        /** The small mark: a 34-unit square, scaled about its centre. */
        val mark = MarkBox(178f, 22f, 34f)

        /** The weekday row: seven 34-unit cells centred on the stage, 12-unit text. */
        val days = Days(112f, 34f, 12f, 16f)

        /** The figure (46 on 50, −1 tracking) and its serif line (18 on 25, 2 below). */
        val figure = Figure(300f, 46f, 50f, -1f, 352f, 18f, 25f)

        /** The captions: mess, order, close. */
        val captions = listOf(Caption(474f, 20f, 27f, 400), Caption(316f, 20f, 27f, 400), Caption(352f, 28f, 34f, 500))
    }

    /**
     * The mark the close builds, in the prototype's order: the centre, the four
     * mid dots (top, right, bottom, left), then the diagonals (top-right,
     * bottom-right, bottom-left, top-left). Dot `i` flies to `MARK[i]`; dots 9–27
     * fly to the centre and fade. `MARK_RING` runs clockwise from the top.
     */
    val MARK: List<MarkDot> = listOf(
        MARK_CORE, MARK_RING[0], MARK_RING[2], MARK_RING[4], MARK_RING[6], MARK_RING[1], MARK_RING[3], MARK_RING[5], MARK_RING[7],
    )

    /** The close's mark: centred here, at twice the 96-unit grid. */
    object CLOSE {
        const val cx = 195.0
        const val cy = 236.0
        const val scale = 2.0
    }

    /** Reduced motion holds these beats, each until the next: every act's settled frame, one per outcome scene. */
    val HOLDS: List<Int> = listOf(9, 14, 19, 24, 29, 34, 43)

    /* ── timing ───────────────────────────────────────────────────────── */

    /** CSS's cubic-bezier: Newton's method, then bisection — the way browsers solve it. */
    class Bezier(x1: Double, y1: Double, x2: Double, y2: Double) {
        private val cx = 3 * x1
        private val bx = 3 * (x2 - x1) - cx
        private val ax = 1 - cx - bx
        private val cy = 3 * y1
        private val by = 3 * (y2 - y1) - cy
        private val ay = 1 - cy - by

        private fun sampleX(t: Double) = ((ax * t + bx) * t + cx) * t
        private fun sampleY(t: Double) = ((ay * t + by) * t + cy) * t
        private fun slopeX(t: Double) = (3 * ax * t + 2 * bx) * t + cx

        private fun solve(x: Double): Double {
            var t = x
            for (i in 0 until 8) {
                val err = sampleX(t) - x
                if (abs(err) < 1e-7) return t
                val d = slopeX(t)
                if (abs(d) < 1e-6) break
                t -= err / d
            }
            var lo = 0.0
            var hi = 1.0
            t = x
            while (hi - lo > 1e-7) {
                val v = sampleX(t)
                if (abs(v - x) < 1e-7) return t
                if (x > v) lo = t else hi = t
                t = (lo + hi) / 2
            }
            return t
        }

        fun at(p: Double): Double = if (p <= 0) 0.0 else if (p >= 1) 1.0 else sampleY(solve(p))
    }

    /** CSS's curves: `settle` is the prototype's cubic-bezier(.2,.75,.2,1). */
    object CURVES {
        val settle = Bezier(0.2, 0.75, 0.2, 1.0)
        val ease = Bezier(0.25, 0.1, 0.25, 1.0)
        val easeInOut = Bezier(0.42, 0.0, 0.58, 1.0)
    }

    /** One property's transition: how long, on which curve. */
    class Transition(val ms: Double, val ease: Bezier)

    /** Each channel's transition, as the prototype's stylesheet set it. */
    object TIMING {
        /** A dot's left and top. */
        val position = Transition(1000.0, CURVES.settle)

        /** A dot's width and height. */
        val size = Transition(700.0, CURVES.ease)

        /** A dot's colour. */
        val colour = Transition(700.0, CURVES.ease)

        /** A dot's opacity. */
        val opacity = Transition(600.0, CURVES.ease)

        /** The small mark's opacity, and its scale about its centre (0.6 hidden, 1 shown). */
        val markOpacity = Transition(700.0, CURVES.ease)
        val markScale = Transition(900.0, CURVES.settle)

        /** The weekday row, the figure and the captions: opacity, and the figure's lift. */
        val fade = Transition(650.0, CURVES.ease)
        val lift = Transition(750.0, CURVES.settle)
    }

    /**
     * The mess's shake: a 700 ms keyframe, eased in and out between keys, offset
     * per dot by `(i × 113) mod 700` ms. It runs only in the mess and stops dead
     * at the order, as the prototype's class swap did.
     */
    object JITTER {
        const val ms = 700
        const val stagger = 113
        val ease = CURVES.easeInOut
        val keys = doubleArrayOf(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        val offsets = listOf(0.0 to 0.0, 3.0 to -2.0, -2.0 to 3.0, 2.0 to 2.0, -3.0 to -1.0, 0.0 to 0.0)
    }

    /* ── the table ────────────────────────────────────────────────────── */

    /** Where one dot should be on a beat. `x`, `y` are its box's top-left corner. */
    class DotTarget(val x: Double, val y: Double, val size: Double, val opacity: Double, val fill: Color, /** Shaking: the mess only. */ val jitter: Boolean)

    class Targets(
        val dots: List<DotTarget>,
        val markOpacity: Double,
        val markScale: Double,
        val daysOpacity: Double,
        val figureOpacity: Double,
        /** The figure block's drop below its place while hidden. */
        val figureDrop: Double,
        val captions: List<Double>,
    )

    private fun sceneOf(beat: Int) = min(3, floor((beat - OUTCOME_FROM).toDouble() / SCENE_BEATS).toInt())

    /** JavaScript's `Math.round`: halves go up. */
    private fun jsRound(v: Double) = floor(v + 0.5)

    /** Every target on one beat (0–43). The prototype's `renderVals`, as data. */
    fun targets(beat: Int): Targets {
        val t = ((beat % LOOP) + LOOP) % LOOP
        val mess = t < ORDER_FROM
        val order = t >= ORDER_FROM && t < OUTCOME_FROM
        val outcome = t >= OUTCOME_FROM && t < CLOSE_FROM
        val close = t >= CLOSE_FROM
        val win = WINS[if (outcome) sceneOf(t) else 0]

        val dots = List(N) { i ->
            val x: Double
            val y: Double
            val size: Double
            var opacity = 1.0
            val fill: Color
            if (mess) {
                // Scattered, shaking and sliding down: the month slipping away.
                x = 18.0 + ((i * 97 + 31) % 340)
                y = 40.0 + ((i * 131 + 17) % 300) + t * (6 + (i % 5) * 3)
                size = 9.0 + (i % 4) * 3
                fill = MESS[i % MESS.size]
                opacity = if (y > 470) 0.0 else 1.0
            } else if (close) {
                val m = MARK[if (i < MARK.size) i else 0]
                size = m.r * 4.0
                x = CLOSE.cx + (m.x - 48) * CLOSE.scale - size / 2
                y = CLOSE.cy + (m.y - 48) * CLOSE.scale - size / 2
                opacity = if (i < MARK.size) 1.0 else 0.0
                fill = MARK_INK
            } else {
                val col = i % 7
                val row = i / 7
                size = 16.0
                x = 93.0 + col * 34 - size / 2
                y = 150.0 + row * 34 - size / 2
                fill = if (order) ROWS[row] else if (i in win.missed) MISSED else win.hue
            }
            DotTarget(jsRound(x), jsRound(y), size, opacity, fill, mess)
        }

        val shown = shownOn(t)
        return Targets(
            dots,
            markOpacity = if (order || outcome) 1.0 else 0.0,
            markScale = if (order || outcome) 1.0 else 0.6,
            daysOpacity = if (outcome) 1.0 else 0.0,
            figureOpacity = if (shown) 1.0 else 0.0,
            figureDrop = if (shown) 0.0 else 10.0,
            captions = listOf(if (mess && t >= 2) 1.0 else 0.0, if (order && t >= 11) 1.0 else 0.0, if (close && t >= 36) 1.0 else 0.0),
        )
    }

    /** An outcome scene's figure is showing on this beat: from the scene's second beat. */
    private fun shownOn(t: Int) = t >= OUTCOME_FROM && t < CLOSE_FROM && (t - OUTCOME_FROM) % SCENE_BEATS >= 1

    /* ── the transition rules ─────────────────────────────────────────── */

    /** A token → [r, g, b] in 0–255. Colours blend in sRGB, channel by channel, as a browser does. */
    private fun rgb(token: Color) = doubleArrayOf(
        (token.red * 255).roundToInt().toDouble(), (token.green * 255).roundToInt().toDouble(), (token.blue * 255).roundToInt().toDouble(),
    )

    /**
     * One channel's transition: running from `from` at `start` to `to` over `ms`,
     * or finished and holding `to`. `back` is CSS's reversing-adjusted start value
     * and `shorten` its reversing shortening factor.
     */
    private class Seg(
        val from: DoubleArray,
        val to: DoubleArray,
        val start: Double,
        val ms: Double,
        val ease: Bezier,
        val back: DoubleArray,
        val shorten: Double,
    )

    private fun progress(seg: Seg, ms: Double): Double =
        if (seg.ms <= 0) 1.0 else seg.ease.at(min(1.0, max(0.0, (ms - seg.start) / seg.ms)))

    private fun at(seg: Seg, ms: Double): DoubleArray {
        val p = progress(seg, ms)
        return DoubleArray(seg.from.size) { k -> seg.from[k] + (seg.to[k] - seg.from[k]) * p }
    }

    private fun same(a: DoubleArray, b: DoubleArray) = a.contentEquals(b)

    private fun held(v: DoubleArray, timing: Transition) = Seg(v, v, Double.NEGATIVE_INFINITY, 0.0, timing.ease, v, 1.0)

    /** A style change at `ms`, for one channel: CSS Transitions § 3, as the browser runs it. */
    private fun retarget(seg: Seg, to: DoubleArray, ms: Double, timing: Transition): Seg {
        // The same end: a running transition carries on, a finished one holds.
        if (same(seg.to, to)) return seg
        // Nothing running: from where it rests, the full length.
        if (ms >= seg.start + seg.ms) return Seg(seg.to, to, ms, timing.ms, timing.ease, seg.to, 1.0)
        val now = at(seg, ms)
        // Already there: the running one is cancelled and nothing starts.
        if (same(now, to)) return held(to, timing)
        // Back where the running one came from: shortened by how far it got.
        if (same(seg.back, to)) {
            val shorten = min(1.0, max(0.0, abs(progress(seg, ms) * seg.shorten + 1 - seg.shorten)))
            return Seg(now, to, ms, timing.ms * shorten, timing.ease, seg.to, shorten)
        }
        return Seg(now, to, ms, timing.ms, timing.ease, now, 1.0)
    }

    /** A channel: what it reads from a beat's targets, and how it moves. */
    private class Channel(val read: (Targets) -> DoubleArray, val timing: Transition)

    private val CHANNELS: List<Channel> = (0 until N).flatMap { i ->
        listOf(
            Channel({ tg -> doubleArrayOf(tg.dots[i].x) }, TIMING.position),
            Channel({ tg -> doubleArrayOf(tg.dots[i].y) }, TIMING.position),
            Channel({ tg -> doubleArrayOf(tg.dots[i].size) }, TIMING.size),
            Channel({ tg -> doubleArrayOf(tg.dots[i].opacity) }, TIMING.opacity),
            Channel({ tg -> rgb(tg.dots[i].fill) }, TIMING.colour),
        )
    } + listOf(
        Channel({ tg -> doubleArrayOf(tg.markOpacity) }, TIMING.markOpacity),
        Channel({ tg -> doubleArrayOf(tg.markScale) }, TIMING.markScale),
        Channel({ tg -> doubleArrayOf(tg.daysOpacity) }, TIMING.fade),
        Channel({ tg -> doubleArrayOf(tg.figureOpacity) }, TIMING.fade),
        Channel({ tg -> doubleArrayOf(tg.figureDrop) }, TIMING.lift),
        Channel({ tg -> doubleArrayOf(tg.captions[0]) }, TIMING.fade),
        Channel({ tg -> doubleArrayOf(tg.captions[1]) }, TIMING.fade),
        Channel({ tg -> doubleArrayOf(tg.captions[2]) }, TIMING.fade),
    )

    /** Where the shared channels start, after five per dot. */
    private const val MARK_CH = N * 5

    private val BEATS: List<Targets> = List(LOOP) { targets(it) }

    /**
     * One loop: each beat's transition per channel, and whose figure is on
     * screen. The prototype swapped the words the moment a scene changed, while
     * the old figure was still fading out; here they change as the next one
     * fades in. The timing does not move, and the ink goes with the words.
     */
    private class Table(val segs: List<List<Seg>>, val figure: List<Int>)

    /**
     * Each beat's running transitions, for one loop, from the state it starts
     * in. The very first loop starts still on beat 0, as the prototype did on
     * mount; every later one starts where the first ended — nothing still moves
     * by beat 43 — so each repeats exactly.
     */
    private fun build(entering: List<Seg>, figureFrom: Int): Table {
        var now = entering
        var shown = figureFrom
        val segs = mutableListOf<List<Seg>>()
        val figure = mutableListOf<Int>()
        for (beat in 0 until LOOP) {
            val ms = beat.toDouble() * BEAT_MS
            now = now.mapIndexed { c, seg -> retarget(seg, CHANNELS[c].read(BEATS[beat]), ms, CHANNELS[c].timing) }
            if (shownOn(beat)) shown = sceneOf(beat)
            segs.add(now)
            figure.add(shown)
        }
        return Table(segs, figure)
    }

    private val FIRST: Table = build(CHANNELS.map { ch -> held(ch.read(BEATS[0]), ch.timing) }, 0)
    private val LATER: Table = build(
        FIRST.segs[LOOP - 1].map { seg -> Seg(seg.from, seg.to, seg.start - LOOP_MS, seg.ms, seg.ease, seg.back, seg.shorten) },
        FIRST.figure[LOOP - 1],
    )

    /* ── a frame ──────────────────────────────────────────────────────── */

    class DotFrame(
        /** The dot's box, top-left, and its side: the prototype's `left`, `top`, `width`. */
        val x: Float,
        val y: Float,
        val size: Float,
        /** The shake, applied to the drawn dot only. */
        val jx: Float,
        val jy: Float,
        /** Already blended, each channel rounded as a browser paints it. */
        val fill: Color,
        val opacity: Float,
    )

    class MarkFrame(val opacity: Float, val scale: Float)
    class DaysFrame(val opacity: Float)

    /** `win` is which outcome's words and ink are on screen. */
    class FigureFrame(val opacity: Float, val drop: Float, val text: String, val line: String, val ink: Color, val win: Int)

    class Frame(val dots: List<DotFrame>, val mark: MarkFrame, val days: DaysFrame, val figure: FigureFrame, val captions: List<Float>)

    private class Place(val first: Boolean, val local: Double, val beat: Int)

    /** The beat a moment falls on, and its milliseconds into the loop. */
    private fun place(ms: Double): Place {
        val t = max(0.0, ms)
        val first = t < LOOP_MS
        val local = if (first) t else (t - LOOP_MS) % LOOP_MS
        return Place(first, local, min(LOOP - 1, floor(local / BEAT_MS).toInt()))
    }

    /** The shake of dot `i`, `local` ms into a loop. */
    private fun jitter(i: Int, local: Double): Pair<Double, Double> {
        val phase = ((local + ((i * JITTER.stagger) % JITTER.ms)) % JITTER.ms) / JITTER.ms
        var k = 0
        while (k < JITTER.keys.size - 2 && phase >= JITTER.keys[k + 1]) k++
        val span = JITTER.keys[k + 1] - JITTER.keys[k]
        val p = JITTER.ease.at((phase - JITTER.keys[k]) / span)
        val (ax, ay) = JITTER.offsets[k]
        val (bx, by) = JITTER.offsets[k + 1]
        return (ax + (bx - ax) * p) to (ay + (by - ay) * p)
    }

    /** sRGB channels in 0–255 → a colour, each channel rounded as the web's `rgb()` string is. */
    private fun paint(c: DoubleArray) = Color(c[0].roundToInt().coerceIn(0, 255), c[1].roundToInt().coerceIn(0, 255), c[2].roundToInt().coerceIn(0, 255))

    /** A beat's targets with nothing moving: a held frame. */
    private fun still(beat: Int): Frame {
        val tg = BEATS[beat]
        val w = if (beat >= OUTCOME_FROM && beat < CLOSE_FROM) sceneOf(beat) else 0
        val win = WINS[w]
        return Frame(
            dots = tg.dots.map { d -> DotFrame(d.x.toFloat(), d.y.toFloat(), d.size.toFloat(), 0f, 0f, paint(rgb(d.fill)), d.opacity.toFloat()) },
            mark = MarkFrame(tg.markOpacity.toFloat(), tg.markScale.toFloat()),
            days = DaysFrame(tg.daysOpacity.toFloat()),
            figure = FigureFrame(tg.figureOpacity.toFloat(), tg.figureDrop.toFloat(), win.figure, win.line, win.ink, w),
            captions = tg.captions.map { it.toFloat() },
        )
    }

    /**
     * Everything on screen `ms` into the film, on the film's own clock.
     *
     * `reduced` is reduced motion: seven held frames — the mess settled, the
     * order, each outcome scene's last beat, the close — each for its own stretch
     * of the same clock, cut hard, no shake.
     */
    fun frame(ms: Double, reduced: Boolean = false): Frame {
        val where = place(ms)
        val local = where.local
        val beat = where.beat
        if (reduced) return still(HOLDS.firstOrNull { it >= beat } ?: (LOOP - 1))

        val table = if (where.first) FIRST else LATER
        val segs = table.segs[beat]
        fun value(c: Int) = at(segs[c], local)
        val w = table.figure[beat]
        val win = WINS[w]
        val dots = List(N) { i ->
            val c = i * 5
            val (jx, jy) = if (BEATS[beat].dots[i].jitter) jitter(i, local) else (0.0 to 0.0)
            DotFrame(
                x = value(c)[0].toFloat(),
                y = value(c + 1)[0].toFloat(),
                size = value(c + 2)[0].toFloat(),
                jx = jx.toFloat(),
                jy = jy.toFloat(),
                fill = paint(value(c + 4)),
                opacity = value(c + 3)[0].toFloat(),
            )
        }
        return Frame(
            dots,
            mark = MarkFrame(value(MARK_CH)[0].toFloat(), value(MARK_CH + 1)[0].toFloat()),
            days = DaysFrame(value(MARK_CH + 2)[0].toFloat()),
            figure = FigureFrame(value(MARK_CH + 3)[0].toFloat(), value(MARK_CH + 4)[0].toFloat(), win.figure, win.line, win.ink, w),
            captions = listOf(value(MARK_CH + 5)[0].toFloat(), value(MARK_CH + 6)[0].toFloat(), value(MARK_CH + 7)[0].toFloat()),
        )
    }
}
