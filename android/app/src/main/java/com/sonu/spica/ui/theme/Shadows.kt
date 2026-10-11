package com.sonu.spica.ui.theme

import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.shadow.Shadow
import androidx.compose.ui.draw.dropShadow
import androidx.compose.ui.unit.DpOffset
import androidx.compose.ui.unit.dp

/**
 * The prototype's `shadow` tokens, as CSS box-shadows: a y-offset, a blur and
 * ink at an alpha. `dropShadow` takes the same three numbers, so these read
 * one-for-one against `theme.ts`.
 */
object S {
    /** `0 1px 3px rgba(25,30,25,0.07)` */
    fun card(shape: Shape) = Modifier.dropShadow(shape, Shadow(radius = 3.dp, color = C.shadow, offset = DpOffset(0.dp, 1.dp), alpha = 0.07f))

    /** `0 1px 3px rgba(25,30,25,0.06)` */
    fun bubble(shape: Shape) = Modifier.dropShadow(shape, Shadow(radius = 3.dp, color = C.shadow, offset = DpOffset(0.dp, 1.dp), alpha = 0.06f))

    /** `0 6px 20px rgba(25,30,25,0.12)` */
    fun input(shape: Shape) = Modifier.dropShadow(shape, Shadow(radius = 20.dp, color = C.shadow, offset = DpOffset(0.dp, 6.dp), alpha = 0.12f))

    /** `0 12px 30px rgba(25,30,25,0.18)` */
    fun popover(shape: Shape) = Modifier.dropShadow(shape, Shadow(radius = 30.dp, color = C.shadow, offset = DpOffset(0.dp, 12.dp), alpha = 0.18f))

    /**
     * `0 4px 18px rgba(27,23,26,0.06)` — Home's widgets, floating on the tinted
     * ground. The thread's cards sit in the page with a hairline; Home's lift
     * off it, because a glance is read as objects, not as text.
     */
    fun widget(shape: Shape) = Modifier.dropShadow(shape, Shadow(radius = 18.dp, color = C.shadow, offset = DpOffset(0.dp, 4.dp), alpha = 0.06f))

    /** `0 3px 10px rgba(22,96,74,0.3)` */
    fun mic(shape: Shape) = Modifier.dropShadow(shape, Shadow(radius = 10.dp, color = C.brand, offset = DpOffset(0.dp, 3.dp), alpha = 0.3f))
}
