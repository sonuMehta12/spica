import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

/**
 * Per-machine settings, never committed: `sdk.dir`, where the API lives, and
 * the Google web client id the sign-in token is minted for.
 */
val local = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

/** A string as Java source, for a BuildConfig field. */
fun quoted(s: String) = "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

/**
 * The laptop's address on the local network (Wi-Fi first), read fresh on every
 * build: a ValueSource is an input to the configuration cache, so a new DHCP
 * lease rebuilds with the new address instead of shipping a stale one.
 */
abstract class LanAddress : ValueSource<String, ValueSourceParameters.None> {
    override fun obtain(): String? = NetworkInterface.getNetworkInterfaces().toList()
        .filter { it.isUp && !it.isLoopback && !it.isVirtual && !it.isPointToPoint }
        .sortedBy { if (it.name.startsWith("en")) 0 else 1 }
        .flatMap { it.inetAddresses.toList() }
        .filterIsInstance<Inet4Address>()
        .firstOrNull { it.isSiteLocalAddress }
        ?.hostAddress
}

/**
 * Where a debug build finds the API. `lan` (the default) is the laptop on the
 * Wi-Fi — reachable from a phone on the same network and from the emulator
 * alike, so one APK serves both. Any other value is used as written.
 */
val apiBaseDebug: String = local.getProperty("spica.apiBase", "lan").let { v ->
    if (v != "lan") v
    else providers.of(LanAddress::class) {}.orNull?.let { "http://$it:8001" } ?: "http://10.0.2.2:8001"
}

android {
    namespace = "com.sonu.spica"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.sonu.spica"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"

        buildConfigField("String", "GOOGLE_CLIENT_ID", quoted(local.getProperty("spica.googleClientId", "")))
    }

    buildTypes {
        debug {
            // The laptop's LAN address unless local.properties names one; with no
            // network at all, the emulator's alias for the laptop.
            buildConfigField("String", "API_BASE", quoted(apiBaseDebug))
        }
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            buildConfigField("String", "API_BASE", quoted(local.getProperty("spica.apiBaseRelease", "")))
            // Signed with the debug key until there is a release key — this build
            // is for one person's phone, not the store.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.foundation)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)

    implementation(libs.credentials)
    implementation(libs.credentials.play)
    implementation(libs.googleid)

    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.coil.compose)
    implementation(libs.coil.network)
    implementation(libs.osmdroid)
    implementation(libs.health.connect)
}
