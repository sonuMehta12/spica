package com.sonu.spica.ui.data

import com.sonu.spica.ui.common.ActionPill
import com.sonu.spica.ui.common.AddRow
import com.sonu.spica.ui.common.BackStep
import com.sonu.spica.ui.common.FilterPill
import com.sonu.spica.ui.common.PillKind
import com.sonu.spica.ui.common.divider
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Paint
import android.graphics.drawable.BitmapDrawable
import android.graphics.drawable.Drawable
import android.view.MotionEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.sonu.spica.data.Api
import com.sonu.spica.data.Found
import com.sonu.spica.data.PersonRow
import com.sonu.spica.data.PlaceRow
import com.sonu.spica.data.body
import com.sonu.spica.lib.Day
import com.sonu.spica.lib.Fmt
import com.sonu.spica.state.AppState
import com.sonu.spica.state.SpicaViewModel
import com.sonu.spica.ui.common.Dot
import com.sonu.spica.ui.common.InlineField
import com.sonu.spica.ui.common.fadeUp
import com.sonu.spica.ui.common.tap
import com.sonu.spica.ui.home.topRule
import com.sonu.spica.ui.profile.SelectPill
import com.sonu.spica.ui.report.Card
import com.sonu.spica.ui.report.reportCard
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T
import java.util.Locale
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.osmdroid.config.Configuration
import org.osmdroid.events.MapEventsReceiver
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.CopyrightOverlay
import org.osmdroid.views.overlay.FolderOverlay
import org.osmdroid.views.overlay.MapEventsOverlay
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polygon

private val KINDS = listOf("home", "office", "shop", "eat", "hangout", "pickup", "gym", "other")

/** Delhi. The map has to start somewhere, and this is where the payments are. */
private fun home() = GeoPoint(28.6139, 77.209)

private const val NOBODY = "nobody in particular"

/** Tiny mono caps over a field. */
private val LabelStyle = T.mono.copy(fontSize = 12.5.sp, color = C.muted)

/** The web's `input` text: sans 12. */
private val FieldText = T.sans.copy(fontSize = 14.sp)

/** Where a new pin is going, before it has a name. */
private data class PendingPin(val lat: Double, val lng: Double, val name: String, val address: String?)

/**
 * Your data → Places. spec/done/places.md. Port of `PlacesSection.tsx`.
 *
 * Where the money was spent — not a list of places to visit. A pin appears
 * because you dropped it, or (once capture exists) because payments kept
 * landing in the same small circle three separate days running.
 *
 * Every number on a pin is counted server-side over the transactions pointing
 * at it, or at the counterparty it belongs to. That second path is what lets
 * Mohan Lal's shop show its spend with nothing tagged by hand.
 *
 * The web drew this with Leaflet; here it is osmdroid over the same
 * OpenStreetMap tiles, and search is the same Nominatim. The schema did not
 * change — that was the point of proving it on the web first.
 */
@Composable
fun PlacesSection(vm: SpicaViewModel, s: AppState) {
    val places = s.places
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val keyboard = LocalSoftwareKeyboardController.current

    var q by remember { mutableStateOf("") }
    var hits by remember { mutableStateOf<List<Found>?>(null) }
    var searching by remember { mutableStateOf(false) }
    var dropped by remember { mutableStateOf<PendingPin?>(null) }
    var kind by remember { mutableStateOf("shop") }
    var open by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    // Back closes what is open before it leaves the section — a dropped pin,
    // then an open place, then the search's hits. The last one listed goes first.
    BackStep(hits != null) { hits = null }
    BackStep(open != null && places.any { it.id == open }) { open = null }
    BackStep(dropped != null) { dropped = null }

    // The pins live in one folder, so a redraw clears exactly them and never
    // the tap receiver or the attribution.
    val layer = remember { FolderOverlay() }

    // The map owns its own view, so it is created once and told about state
    // afterwards — never re-created on a recomposition.
    val map = remember {
        Configuration.getInstance().load(ctx, ctx.getSharedPreferences("osmdroid", Context.MODE_PRIVATE))
        // OSM's tile policy wants every client named; osmdroid sends this as the User-Agent.
        Configuration.getInstance().userAgentValue = "com.sonu.spica"
        MapView(ctx).apply {
            // osmdroid draws with canvas.setMatrix, which replaces the offset
            // Compose drew it at — the map painted over the search row above
            // it. Its own layer gives that matrix the view's own coordinates.
            setLayerType(android.view.View.LAYER_TYPE_HARDWARE, null)
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)
            // 256 tile pixels are 256dp, as they were 256 CSS px — otherwise a
            // dense screen shows the city at a third of the size.
            setTilesScaledToDpi(true)
            setMaxZoomLevel(19.0)
            // This composable calls onDetach itself; a detach from the window
            // must not tear the map down under it.
            setDestroyMode(false)
            overlayManager.tilesOverlay.setLoadingBackgroundColor(C.lineSoft.toArgb())
            overlayManager.tilesOverlay.setLoadingLineColor(C.lineSoft.toArgb())
            controller.setZoom(12.0)
            controller.setCenter(home())
            // First, so it sits under the pins: a tap on a pin opens it, anywhere else drops one.
            overlays.add(
                MapEventsOverlay(object : MapEventsReceiver {
                    override fun singleTapConfirmedHelper(p: GeoPoint): Boolean {
                        dropped = PendingPin(p.latitude, p.longitude, "", null)
                        return true
                    }

                    override fun longPressHelper(p: GeoPoint): Boolean = false
                }),
            )
            overlays.add(layer)
            overlays.add(CopyrightOverlay(ctx).apply { setAlignRight(true); setTextColor(C.muted.toArgb()) })
            // The page scrolls, and without this the Column takes every vertical
            // drag — the map could only be panned sideways. Returning false
            // leaves the gesture itself to the map.
            setOnTouchListener { v, e ->
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> v.parent?.requestDisallowInterceptTouchEvent(true)
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> v.parent?.requestDisallowInterceptTouchEvent(false)
                }
                false
            }
        }
    }
    DisposableEffect(map) { onDispose { map.onDetach() } }

    // Redraw the pins whenever the rows or the pending drop move. Keyed on the
    // drop's position, not the drop: typing its name moves nothing.
    LaunchedEffect(places, dropped?.lat, dropped?.lng) {
        val density = ctx.resources.displayMetrics.density
        layer.items.clear()
        // Circles first: osmdroid draws in the order added, and Leaflet kept
        // its markers in a pane above the shapes.
        for (p in places) {
            // The radius is a real thing a payment gets matched against, so it
            // is drawn rather than left as a number in a form.
            layer.add(
                Polygon(map).apply {
                    setPoints(Polygon.pointsAsCircle(GeoPoint(p.lat, p.lng), p.radiusM.toDouble()))
                    outlinePaint.color = C.brand.copy(alpha = 0.35f).toArgb()
                    outlinePaint.strokeWidth = 1f * density
                    fillPaint.color = C.brand.copy(alpha = 0.06f).toArgb()
                    // Not a tap target: a tap inside the circle still drops a
                    // pin, as a click passes through Leaflet's circle to the map.
                    setOnClickListener { _, _, _ -> false }
                },
            )
        }
        for (p in places) {
            layer.add(
                Marker(map).apply {
                    position = GeoPoint(p.lat, p.lng)
                    icon = dotIcon(ctx, if (p.confirmed) C.paisa else C.amber)
                    setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
                    // A tap opens the pin's row; the web's hover tooltip has no touch equivalent.
                    setOnMarkerClickListener { _, _ ->
                        open = p.id
                        true
                    }
                },
            )
        }
        dropped?.let { d ->
            layer.add(
                Marker(map).apply {
                    position = GeoPoint(d.lat, d.lng)
                    icon = dotIcon(ctx, C.red)
                    setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
                    setOnMarkerClickListener { _, _ -> true }
                },
            )
        }
        map.invalidate()
    }

    fun focusOn(lat: Double, lng: Double) {
        map.controller.setZoom(16.0)
        map.controller.setCenter(GeoPoint(lat, lng))
    }

    fun search() {
        val clean = q.trim()
        if (clean.isEmpty() || searching) return
        searching = true
        keyboard?.hide()
        scope.launch {
            hits = try {
                Api.searchPlaces(clean)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                emptyList<Found>()
            }
            searching = false
        }
    }

    fun jumpTo(f: Found) {
        focusOn(f.lat, f.lng)
        dropped = PendingPin(f.lat, f.lng, f.name, f.address)
        hits = null
    }

    fun save() {
        val d = dropped ?: return
        val name = d.name.trim()
        if (name.isEmpty() || busy) return
        busy = true
        scope.launch {
            val ok = vm.addPlace(
                body(
                    "name" to name,
                    "lat" to d.lat,
                    "lng" to d.lng,
                    "kind" to kind,
                    "address" to d.address,
                    // Searched or tapped — both are yours, and neither is a guess.
                    "source" to if (!d.address.isNullOrEmpty()) "search" else "manual",
                ),
            )
            busy = false
            if (ok) {
                dropped = null
                q = ""
            }
        }
    }

    val byKind = remember(places) { places.groupBy { it.kind ?: "other" }.toList() }

    Column(Modifier.fillMaxWidth().padding(bottom = 8.dp).reportCard().clip(Card)) {
        Row(
            Modifier.fillMaxWidth().height(IntrinsicSize.Min).padding(horizontal = 18.dp, vertical = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            InlineField(
                q, { q = it }, Modifier.weight(1f),
                placeholder = "Search a place, or tap the map", mono = false, style = FieldText, onDone = ::search,
            )
            val canFind = q.isNotBlank() && !searching
            PinButton(
                if (searching) "…" else "Find",
                bg = if (canFind) C.brand else C.line, fg = if (canFind) C.white else C.faint,
                modifier = Modifier.fillMaxHeight(), enabled = canFind, onClick = ::search,
            )
        }

        hits?.let { list ->
            Column(Modifier.fillMaxWidth().topRule()) {
                if (list.isEmpty()) {
                    Text(
                        "Nothing found. Tap the map instead.",
                        style = T.sans.copy(fontSize = 14.sp, color = C.muted),
                        modifier = Modifier.padding(horizontal = 18.dp, vertical = 10.dp),
                    )
                } else {
                    list.forEachIndexed { i, f ->
                        Column(
                            Modifier.fillMaxWidth().then(if (i > 0) Modifier.divider(18.dp, 18.dp) else Modifier)
                                .tap { jumpTo(f) }.padding(horizontal = 18.dp, vertical = 9.dp),
                        ) {
                            Text(f.name, style = T.sans.copy(fontSize = 15.sp))
                            Text(f.address, style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 2.dp))
                        }
                    }
                }
            }
        }

        AndroidView(factory = { map }, modifier = Modifier.fillMaxWidth().height(260.dp).background(C.lineSoft))

        dropped?.let { d ->
            Column(Modifier.fillMaxWidth().fadeUp(180).topRule().padding(start = 18.dp, end = 18.dp, top = 11.dp, bottom = 13.dp)) {
                PinLabel("Name")
                InlineField(
                    d.name, { dropped = dropped?.copy(name = it) }, Modifier.fillMaxWidth(),
                    placeholder = "Mohan Lal, Ghar, chai tapri…", autoFocus = true, mono = false, style = FieldText,
                    onDone = ::save,
                )
                Column(Modifier.padding(top = 10.dp)) {
                    PinLabel("What is it")
                    SelectPill(kind, KINDS) { kind = it }
                }
                Text(
                    "%.5f, %.5f".format(Locale.US, d.lat, d.lng),
                    style = T.mono.copy(fontSize = 12.5.sp, color = C.faint),
                    modifier = Modifier.padding(top = 8.dp),
                )
                Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    val canSave = d.name.isNotBlank() && !busy
                    PinButton(
                        "Drop pin", bg = if (canSave) C.brand else C.line, fg = if (canSave) C.white else C.faint,
                        padH = 14.dp, enabled = canSave, onClick = ::save,
                    )
                    PinButton("Cancel", bg = C.paper, fg = C.muted, border = C.border, padH = 12.dp) { dropped = null }
                }
            }
        }
    }

    Column(Modifier.fillMaxWidth().reportCard().clip(Card)) {
        if (places.isEmpty()) {
            Text(
                "No places yet. Search for one, or tap the map where you pay.",
                style = T.sans.copy(fontSize = 15.sp, color = C.muted),
                modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp),
            )
        }
        byKind.forEach { (k, rows) ->
            key(k) {
                Column(Modifier.fillMaxWidth().padding(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 4.dp)) {
                    PinLabel(k)
                    rows.forEach { p ->
                        key(p.id) {
                            PinRow(
                                p, s.people, isOpen = open == p.id, vm = vm, scope = scope,
                                onToggle = {
                                    open = if (open == p.id) null else p.id
                                    focusOn(p.lat, p.lng)
                                },
                            )
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

/** One pin: name, what the ledger counted, and what was spent. Tapping it opens the pin and flies the map there. */
@Composable
private fun PinRow(
    p: PlaceRow,
    people: List<PersonRow>,
    isOpen: Boolean,
    vm: SpicaViewModel,
    scope: CoroutineScope,
    onToggle: () -> Unit,
) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
        Column(Modifier.weight(1f).alignByBaseline().tap(onClick = onToggle)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // A detected pin is a guess until you say so — the dot stands
                // where the web wrote `· andaaza`.
                if (!p.confirmed) Dot()
                Text(
                    buildAnnotatedString {
                        append(p.name)
                        p.counterpartyName?.takeIf { it.isNotEmpty() }?.let {
                            withStyle(SpanStyle(fontFamily = F.mono, fontSize = 12.5.sp, color = C.faint)) { append(" $it") }
                        }
                    },
                    style = T.sans.copy(fontSize = 15.sp),
                )
            }
            val counted = if (p.payments > 0) {
                "${p.payments} payment${if (p.payments > 1) "s" else ""}" +
                    (p.lastSeen?.takeIf { it.isNotEmpty() }?.let { " · ${Day.shortDay(it)}" } ?: "")
            } else {
                "nothing spent here yet"
            }
            Text("$counted · ${p.radiusM}m", style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(top = 3.dp))
        }
        Text(
            if (p.spent > 0) Fmt.rupees(p.spent / 100.0) else "—",
            style = T.mono.copy(
                fontSize = 13.sp,
                fontWeight = if (p.spent > 0) FontWeight.SemiBold else FontWeight.Normal,
                color = if (p.spent > 0) C.ink else C.faint,
            ),
            softWrap = false,
            modifier = Modifier.alignByBaseline(),
        )
    }
    if (isOpen) PinDetail(p, people, vm, scope)
}

/** The opened pin: whose it is, how big it is, and the way to remove it. */
@Composable
private fun PinDetail(p: PlaceRow, people: List<PersonRow>, vm: SpicaViewModel, scope: CoroutineScope) {
    val focus = LocalFocusManager.current
    var radius by remember(p.id, p.radiusM) { mutableStateOf(p.radiusM.toString()) }
    var editing by remember { mutableStateOf(false) }

    // Saved on blur, as the web's field was; an unreadable or unchanged value sends nothing.
    fun commitRadius() {
        val n = radius.trim().toIntOrNull() ?: return
        if (n > 0 && n != p.radiusM) scope.launch { vm.editPlace(p.id, body("radius_m" to n)) }
    }

    Column(Modifier.fillMaxWidth().fadeUp(200).padding(top = 2.dp, bottom = 10.dp)) {
        p.address?.takeIf { it.isNotEmpty() }?.let {
            Text(it, style = T.mono.copy(fontSize = 12.5.sp, color = C.faint), modifier = Modifier.padding(bottom = 7.dp))
        }

        // The link is what makes a pin show its spend without a single payment
        // being tagged by hand.
        PinLabel("Whose place")
        val current = people.firstOrNull { it.id == p.counterpartyId }?.name ?: p.counterpartyName ?: NOBODY
        SelectPill(current, listOf(NOBODY) + people.map { it.name }) { picked ->
            val id = if (picked == NOBODY) null else people.firstOrNull { it.name == picked }?.id ?: return@SelectPill
            if (id != p.counterpartyId) scope.launch { vm.editPlace(p.id, body("counterparty_id" to id)) }
        }

        Column(Modifier.padding(top = 10.dp)) {
            Text(
                buildAnnotatedString {
                    append("How big")
                    withStyle(SpanStyle(color = C.faint)) { append("  a paan shop is 20m, a mall 200m") }
                },
                style = LabelStyle,
                modifier = Modifier.padding(bottom = 4.dp),
            )
            InlineField(
                radius, { radius = it },
                Modifier.fillMaxWidth().onFocusChanged { st ->
                    if (editing && !st.hasFocus) commitRadius()
                    editing = st.hasFocus
                },
                numeric = true, mono = false, style = FieldText,
                // Done only lets go of the field; the blur is what saves, so it saves once.
                onDone = { focus.clearFocus() },
            )
        }

        PinButton(
            "Remove pin", bg = C.redSurface, fg = C.red, modifier = Modifier.padding(top = 10.dp),
            border = C.redBorder, padH = 12.dp, padV = 5.dp,
        ) { vm.removePlace(p.id) }
    }
}

@Composable
private fun PinLabel(text: String) {
    Text(text, style = LabelStyle, modifier = Modifier.padding(bottom = 4.dp))
}

/** The web's small mono buttons: 10sp on a 12dp-radius pill. One that cannot act yet is greyed and ignores taps. */
@Composable
private fun PinButton(
    label: String,
    bg: Color,
    fg: Color,
    modifier: Modifier = Modifier,
    border: Color? = null,
    padH: Dp = 13.dp,
    padV: Dp = 6.dp,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    // A pill, as the kit draws them: no drawn edge — paper becomes the surface tint.
    val shape = RoundedCornerShape(50)
    Box(
        modifier.clip(shape).background(if (bg == C.paper) C.surface else bg)
            .tap(enabled = enabled, onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 9.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = T.sans.copy(fontSize = 16.sp, lineHeight = 20.4.sp, fontWeight = androidx.compose.ui.text.font.FontWeight.Medium, color = fg), maxLines = 1, softWrap = false)
    }
}

/**
 * A dot, not osmdroid's default marker — a circle reads better at this size,
 * as it did on the web: 13dp across, a 2dp white ring, a soft ink shadow.
 * One bitmap per marker, never shared: osmdroid recycles a marker's icon when
 * the marker detaches, and a shared one would die with the first.
 */
private fun dotIcon(ctx: Context, fill: Color): Drawable {
    val d = ctx.resources.displayMetrics.density
    val r = 6.5f * d
    // Room for the shadow's 3dp blur and its 1dp drop.
    val pad = 5f * d
    val side = kotlin.math.ceil((r + pad) * 2).toInt()
    val bmp = Bitmap.createBitmap(side, side, Bitmap.Config.ARGB_8888)
    val canvas = android.graphics.Canvas(bmp)
    val c = side / 2f
    val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    paint.color = C.white.toArgb()
    paint.setShadowLayer(3f * d, 0f, 1f * d, C.shadow.copy(alpha = 0.35f).toArgb())
    canvas.drawCircle(c, c, r, paint)
    paint.clearShadowLayer()
    paint.color = fill.toArgb()
    canvas.drawCircle(c, c, r - 2f * d, paint)
    return BitmapDrawable(ctx.resources, bmp)
}
