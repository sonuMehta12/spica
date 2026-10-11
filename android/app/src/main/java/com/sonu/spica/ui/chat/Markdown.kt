package com.sonu.spica.ui.chat

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.sonu.spica.ui.theme.C
import com.sonu.spica.ui.theme.F
import com.sonu.spica.ui.theme.T

/**
 * The agent's prose, rendered — the web's `MarkdownBody`.
 *
 * The voice rules still hold: sans + ink, 12.5sp, no heading sizes. A `#`
 * renders as a bold line, not a title, because the card is a sentence, not a
 * document. Code is mono and muted — numbers and names the model quotes back
 * are data. Raw HTML is never rendered.
 */
private sealed interface Block {
    data class Para(val text: String) : Block
    data class Heading(val text: String) : Block
    data class Bullets(val items: List<String>, val ordered: Boolean) : Block
    data class Table(val head: List<String>, val rows: List<List<String>>) : Block
    data class Code(val text: String) : Block
}

private val bullet = Regex("^\\s*[-*+]\\s+(.*)$")
private val ordered = Regex("^\\s*\\d+[.)]\\s+(.*)$")
private val heading = Regex("^\\s{0,3}#{1,6}\\s+(.*)$")
private val tableSep = Regex("^\\s*\\|?\\s*:?-{2,}:?\\s*(\\|\\s*:?-{2,}:?\\s*)*\\|?\\s*$")

private fun cells(line: String) = line.trim().trim('|').split('|').map { it.trim() }

private fun parse(src: String): List<Block> {
    val lines = src.replace("\r\n", "\n").split('\n')
    val out = mutableListOf<Block>()
    val para = mutableListOf<String>()
    fun flush() {
        if (para.isNotEmpty()) out += Block.Para(para.joinToString(" "))
        para.clear()
    }
    var i = 0
    while (i < lines.size) {
        val line = lines[i]
        when {
            line.trim().startsWith("```") -> {
                flush()
                val code = mutableListOf<String>()
                i++
                while (i < lines.size && !lines[i].trim().startsWith("```")) code += lines[i++]
                out += Block.Code(code.joinToString("\n"))
            }
            line.isBlank() -> flush()
            heading.matches(line) -> {
                flush()
                out += Block.Heading(heading.find(line)!!.groupValues[1])
            }
            line.contains('|') && i + 1 < lines.size && tableSep.matches(lines[i + 1]) -> {
                flush()
                val head = cells(line)
                i += 2
                val rows = mutableListOf<List<String>>()
                while (i < lines.size && lines[i].contains('|') && lines[i].isNotBlank()) rows += cells(lines[i++])
                out += Block.Table(head, rows)
                continue
            }
            bullet.matches(line) || ordered.matches(line) -> {
                flush()
                val isOrdered = ordered.matches(line)
                val items = mutableListOf<String>()
                while (i < lines.size && (bullet.matches(lines[i]) || ordered.matches(lines[i]) || (lines[i].startsWith("  ") && lines[i].isNotBlank() && items.isNotEmpty()))) {
                    val l = lines[i]
                    val m = bullet.find(l) ?: ordered.find(l)
                    if (m != null) items += m.groupValues[1] else items[items.size - 1] = items.last() + " " + l.trim()
                    i++
                }
                out += Block.Bullets(items, isOrdered)
                continue
            }
            else -> para += line.trim()
        }
        i++
    }
    flush()
    return out
}

private val inline = Regex("\\*\\*(.+?)\\*\\*|__(.+?)__|`([^`]+)`|\\[([^\\]]+)]\\(([^)\\s]+)\\)|(?<![*\\w])\\*(?!\\s)(.+?)(?<!\\s)\\*(?!\\*)|(?<![_\\w])_(?!\\s)(.+?)(?<!\\s)_(?!\\w)")

/** `**bold**`, `*italic*`, `` `code` `` and `[links](url)` into one styled string. */
fun inlineMarkdown(src: String): AnnotatedString = buildAnnotatedString {
    var last = 0
    for (m in inline.findAll(src)) {
        append(src.substring(last, m.range.first))
        val g = m.groupValues
        when {
            g[1].isNotEmpty() || g[2].isNotEmpty() -> withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(inlineMarkdown(g[1].ifEmpty { g[2] })) }
            g[3].isNotEmpty() -> withStyle(SpanStyle(fontFamily = F.mono, fontSize = 11.sp, color = C.muted)) { append(g[3]) }
            g[4].isNotEmpty() -> withLink(LinkAnnotation.Url(g[5], TextLinkStyles(SpanStyle(color = C.brand)))) { append(g[4]) }
            g[6].isNotEmpty() || g[7].isNotEmpty() -> withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(g[6].ifEmpty { g[7] }) }
        }
        last = m.range.last + 1
    }
    append(src.substring(last))
}

@Composable
fun MarkdownBody(text: String, modifier: Modifier = Modifier) {
    val blocks = remember(text) { parse(text) }
    Column(modifier) {
        blocks.forEachIndexed { bi, b ->
            val bottom = if (bi == blocks.lastIndex) 0.dp else 6.dp
            when (b) {
                is Block.Para -> Text(inlineMarkdown(b.text), style = T.agentVoice, modifier = Modifier.padding(bottom = bottom))
                is Block.Heading -> Text(inlineMarkdown(b.text), style = T.agentVoice.copy(fontWeight = FontWeight.Bold), modifier = Modifier.padding(bottom = 4.dp))
                is Block.Code -> Text(b.text, style = T.mono.copy(fontSize = 11.sp, lineHeight = 16.sp), modifier = Modifier.padding(bottom = bottom))
                is Block.Bullets -> Column(Modifier.padding(top = 2.dp, bottom = bottom)) {
                    b.items.forEachIndexed { n, item ->
                        Row(Modifier.padding(vertical = 1.dp)) {
                            Text(if (b.ordered) "${n + 1}." else "•", style = T.agentVoice, modifier = Modifier.widthIn(min = 18.dp))
                            Text(inlineMarkdown(item), style = T.agentVoice)
                        }
                    }
                }
                is Block.Table -> Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 4.dp, bottom = bottom)) {
                    // Columns, so each one is as wide as its widest cell.
                    val cols = b.head.size
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (c in 0 until cols) {
                            Column {
                                Text(
                                    b.head[c],
                                    style = T.cardHeading,
                                    modifier = Modifier.padding(vertical = 2.dp),
                                )
                                b.rows.forEach { r ->
                                    Text(inlineMarkdown(r.getOrElse(c) { "" }), style = T.agentVoice.copy(fontSize = 14.sp), modifier = Modifier.padding(vertical = 2.dp))
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
