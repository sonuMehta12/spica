package com.sonu.spica.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.sonu.spica.R

/**
 * Jamun — the design tokens. `THEME.md` at the root says how to use them.
 *
 * Every colour is an OKLCH decision, checked against WCAG contrast on white;
 * the ratio sits beside each so the next colour added has a rule to follow.
 * Nothing hardcodes a hex anywhere else. A CSS px on the prototype is a dp (or
 * sp) here: both are the phone's own density-independent unit.
 */
object C {
    /* Neutrals — lean 0.5% toward jamun (C 0.005, H 335), so the greys and the
       brand read as one material rather than grey beside plum. */

    /** Text. 17.7 : 1. */
    val ink = Color(0xFF1B171A)
    /** The page. */
    val paper = Color(0xFFFFFFFF)
    /** A card or field that sits on the page. */
    val white = Color(0xFFFFFFFF)
    /** The deck card: a pale panel instead of a shadow. */
    val surface = Color(0xFFF8F4F7)

    /** Supporting text. 6.8 : 1. */
    val muted = Color(0xFF5D5A5C)
    /** Labels and metadata — passes AA on the page (5.0) and on the surface panel (4.6). */
    val faint = Color(0xFF726F71)
    /** Decorative only — a future day, an idle mark. Never text you must read. 2.7 : 1. */
    val grey = Color(0xFFA09DA0)

    /** Hairlines: small card borders, dividers. */
    val line = Color(0xFFEDEAEC)
    val lineSoft = Color(0xFFF2EFF1)
    /** Fields, the composer, a rule inside the deck card. */
    val border = Color(0xFFDEDBDE)
    /** A ring's empty track. */
    val ringIdle = Color(0xFFE8E5E7)

    /* Jamun — the one brand colour: the mic and send, the agent's mark, the
       current selection, links. At least 80° of hue from every mode, so an
       action never reads as a number. White on it 9.0 : 1. */
    val brand = Color(0xFF732F67)
    val brandHover = Color(0xFF611D55)
    /** Your messages: a tint of the brand, ink on it (15.3 : 1). */
    val brandTint = Color(0xFFF7EBF4)
    /** The mascot's arc. */
    val brandSoft = Color(0xFFCA8EBD)

    /** Chips are yours, not the brand's: white with a border, a brand wash when pressed. */
    val chip = Color(0xFFFFFFFF)
    val chipBorder = Color(0xFFDEDBDE)
    val chipHover = Color(0xFFF5E6F1)

    /* One colour per mode at equal lightness and chroma (L 0.62, C 0.13; hues
       160 · 55 · 250). The hue says which mode; equal lightness means none
       reads more urgent than another. Data only — never chrome. A mode's rings
       step in lightness: base, then ink, then soft. */
    val paisa = Color(0xFF239D6A)
    val paisaSoft = Color(0xFF9DD3B5)
    val paisaInk = Color(0xFF00613A)
    val paisaTint = Color(0xFFE6F9EE)

    val diet = Color(0xFFC16E2D)
    val dietSoft = Color(0xFFE9B999)
    val dietInk = Color(0xFF7C3C00)
    val dietTint = Color(0xFFFFF0E4)

    val work = Color(0xFF418AD1)
    val workSoft = Color(0xFFA2C8F0)
    val workInk = Color(0xFF125289)
    val workTint = Color(0xFFE7F5FF)

    /* The day look — Home's day rail and glance panel only, on trial
       (THEME.md § The day look). The three modes deepened together in OKLCH:
       base L 0.52 C 0.117, ink L 0.38 C 0.086, soft L 0.80 C 0.075, mist
       L 0.89 C 0.045, tint L 0.966 C 0.016 — one lightness and chroma, hue
       says which (160 · 55 · 250), all in gamut. A solid node carries a white
       glyph: white on base 5.2 · 5.7 · 5.5 : 1. Ink on tint 8.7 · 9.3 · 9.1. */
    val deepPaisa = Color(0xFF027D51)
    val deepPaisaInk = Color(0xFF005032)
    val deepPaisaSoft = Color(0xFF93CDAD)
    val deepPaisaMist = Color(0xFFC2E4D1)
    val deepPaisaTint = Color(0xFFEBF7F0)

    val deepDiet = Color(0xFF9B5418)
    val deepDietInk = Color(0xFF64340B)
    val deepDietSoft = Color(0xFFE4B290)
    val deepDietMist = Color(0xFFF3D4BF)
    val deepDietTint = Color(0xFFFDF1EA)

    val deepWork = Color(0xFF2B6CA9)
    val deepWorkInk = Color(0xFF18446E)
    val deepWorkSoft = Color(0xFF99C2ED)
    val deepWorkMist = Color(0xFFC5DEF8)
    val deepWorkTint = Color(0xFFECF5FF)

    /** Habits are counted in ink, never judged: the neutral, leaning to Jamun. White on it 9.3 : 1. */
    val deepHabit = Color(0xFF4B4649)
    val deepHabitMist = Color(0xFFE4E1E3)

    /* The estimate dot, and nothing else — gold, dark enough to count as a
       mark. 3.1 : 1. */
    val amber = Color(0xFFC58500)
    val amberDeep = Color(0xFF734D00)
    val amberTint = Color(0xFFFEF2D9)

    /* Over — money out, over a limit, late. 5.5 : 1. */
    val red = Color(0xFFBD3933)
    val redTint = Color(0xFFFFEEEC)
    val redSurface = Color(0xFFFFF6F5)
    val redBorder = Color(0xFFFAC6BF)

    /** The shadow tint for what floats — ink, never black. Nothing in the page casts one. */
    val shadow = Color(0xFF1B171A)

    /** `#16604A` from the server → a Color. Anything unreadable is grey. */
    fun hex(s: String?): Color {
        if (s == null) return grey
        val h = s.removePrefix("#")
        return try {
            when (h.length) {
                6 -> Color(("FF$h").toLong(16))
                8 -> Color(h.substring(6, 8).toLong(16).toInt() shl 24 or h.substring(0, 6).toLong(16).toInt())
                else -> grey
            }
        } catch (_: NumberFormatException) {
            grey
        }
    }
}

/**
 * Two faces, bundled in `res/font` as variable fonts (OFL; licences in
 * `assets/licenses`). Downloadable fonts were tried first: a phone serves
 * only the families its Play services directory knows, and the emulator's
 * knew neither — the design fell back to Roboto without a word.
 *
 * A variable file draws every weight; each entry pins its own.
 */
private fun weights(res: Int, style: FontStyle, vararg ws: FontWeight, extra: List<FontVariation.Setting> = emptyList()) =
    ws.map { w -> Font(res, w, style, variationSettings = FontVariation.Settings(FontVariation.weight(w.weight), *extra.toTypedArray())) }

object F {
    /**
     * Newsreader — the agent's words and the page's date. Serif is Spica
     * speaking. Optical size 16: set for reading, not for posters.
     */
    val display = FontFamily(
        weights(R.font.newsreader, FontStyle.Normal, FontWeight.Normal, FontWeight.Medium, FontWeight.SemiBold, extra = listOf(FontVariation.Setting("opsz", 16f))) +
            weights(R.font.newsreader_italic, FontStyle.Italic, FontWeight.Normal, FontWeight.Medium, extra = listOf(FontVariation.Setting("opsz", 16f))),
    )

    /** Anek Latin (Ek Type, Mumbai) — everything you tap, and every number. */
    val sans = FontFamily(
        weights(R.font.anek_latin, FontStyle.Normal, FontWeight.Normal, FontWeight.Medium, FontWeight.SemiBold, FontWeight.Bold, extra = listOf(FontVariation.width(100f))),
    )

    /** Data is the same face in grey — no mono. The name stays so every call site moved at once. */
    val mono = sans

    /**
     * Figtree (Erik Kennedy, OFL) — the day look, on Home's day rail and
     * glance panel only, on trial. Friendly and geometric, heavy for titles
     * and numbers; it draws ₹, the true minus and tabular figures (checked in
     * the file).
     */
    val day = FontFamily(
        weights(R.font.figtree, FontStyle.Normal, FontWeight.Medium, FontWeight.SemiBold, FontWeight.Bold, FontWeight.ExtraBold),
    )
}

/** Every number lines up: ₹1,100 and ₹8,880 are the same width. */
private const val TNUM = "tnum"

/** The styles that recur — each one a rule, not a taste. */
object T {
    /**
     * The agent's own words, wherever they appear: the serif, at reading size.
     * Typography says who is speaking — the agent has no bubble and no face.
     */
    val agentVoice = TextStyle(fontFamily = F.display, fontSize = 15.5.sp, lineHeight = 23.sp, color = C.ink, fontFeatureSettings = TNUM)

    /** A card's heading: sentence case, a quiet second rank. No tracked caps. */
    val cardHeading = TextStyle(fontFamily = F.sans, fontSize = 12.5.sp, fontWeight = FontWeight.Medium, color = C.muted, fontFeatureSettings = TNUM)

    /** A figure: the interface face at medium weight, tabular. Numbers are data, not the agent's voice. */
    val figure = TextStyle(fontFamily = F.sans, fontWeight = FontWeight.Medium, color = C.ink, fontFeatureSettings = TNUM)

    /** Data: the interface face in grey, figures tabular. */
    val mono = TextStyle(fontFamily = F.mono, color = C.muted, fontFeatureSettings = TNUM)
    val sans = TextStyle(fontFamily = F.sans, color = C.ink, fontFeatureSettings = TNUM)
    val display = TextStyle(fontFamily = F.display, fontWeight = FontWeight.Medium, color = C.ink, fontFeatureSettings = TNUM)

    /** The day look's face, figures tabular. Weight and size set where used: heavy for titles and numbers, medium for the grey lines. */
    val day = TextStyle(fontFamily = F.day, color = C.ink, fontFeatureSettings = TNUM)
}
