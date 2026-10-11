package com.sonu.spica.data

import com.sonu.spica.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.decodeFromJsonElement
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/** An error that reached us from the server, carrying what it answered. */
class HttpError(val status: Int, message: String) : Exception(message)

/** The status an error carries, or null when it never reached the server. */
fun Throwable.status(): Int? = (this as? HttpError)?.status

/**
 * Every request to our API goes through here.
 *
 * The only place that knows about the bearer header, and the only place that
 * can tell a 401 from a 500: a 401 drops the token and the door comes back.
 * Port of `call()` in `frontend/src/data/api.ts`.
 */
object Http {
    val base: String = BuildConfig.API_BASE.trimEnd('/')

    val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        // A chat turn is a model call with tools behind it; a clear folds the
        // thread through the summariser. Both can take a while.
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val JSON = "application/json".toMediaType()

    suspend fun raw(path: String, method: String = "GET", body: JsonElement? = null, label: String = path): JsonElement? =
        withContext(Dispatchers.IO) {
            val b = Request.Builder().url(base + path)
            Session.token.value?.let { b.header("Authorization", "Bearer $it") }
            // Only a request that carries one describes its body.
            val rb = body?.toString()?.toRequestBody(JSON)
            b.method(method, rb ?: if (method == "POST" || method == "PUT" || method == "PATCH") ByteArray(0).toRequestBody(null) else null)
            client.newCall(b.build()).execute().use { res ->
                if (!res.isSuccessful) {
                    // The token is dead whatever the caller decides to do about it.
                    if (res.code == 401) Session.signedOut()
                    throw HttpError(res.code, "$label: ${res.code}")
                }
                if (res.code == 204) return@withContext null
                val text = res.body.string()
                if (text.isBlank()) null else WireJson.parseToJsonElement(text)
            }
        }

    suspend inline fun <reified T> get(path: String, label: String = path): T =
        WireJson.decodeFromJsonElement(raw(path, "GET", null, label) ?: JsonNull)

    suspend inline fun <reified T> send(method: String, path: String, body: JsonElement? = null): T =
        WireJson.decodeFromJsonElement(raw(path, method, body, "$method $path") ?: JsonNull)

    /** A write whose answer the caller does not read. */
    suspend fun fire(method: String, path: String, body: JsonElement? = null) {
        raw(path, method, body, "$method $path")
    }
}

/**
 * A JSON body from pairs. A `null` value is sent as JSON null — "clear this
 * field" — so a field meant to be left alone is simply not listed.
 */
fun body(vararg pairs: Pair<String, Any?>): JsonObject = JsonObject(pairs.associate { (k, v) -> k to toJson(v) })

fun toJson(v: Any?): JsonElement = when (v) {
    null -> JsonNull
    is JsonElement -> v
    is String -> JsonPrimitive(v)
    is Number -> JsonPrimitive(v)
    is Boolean -> JsonPrimitive(v)
    is List<*> -> JsonArray(v.map(::toJson))
    is Map<*, *> -> JsonObject(v.entries.associate { (k, x) -> k.toString() to toJson(x) })
    else -> JsonPrimitive(v.toString())
}
