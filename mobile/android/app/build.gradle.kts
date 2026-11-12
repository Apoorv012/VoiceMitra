plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.roborazzi)
}

// Firebase config is per developer and gitignored (README.md). Without it the app still builds and
// runs; it just can't be rung by push (the patient socket still rings it while open).
val hasFirebaseConfig = file("google-services.json").exists()
if (hasFirebaseConfig) apply(plugin = libs.plugins.google.services.get().pluginId)

android {
    // `in.voicemitra.patient` is the id registered with Firebase; Kotlin can't use `in` (a keyword)
    // as a package name, so the code lives under com.voicemitra.patient.
    namespace = "com.voicemitra.patient"
    compileSdk = 37

    defaultConfig {
        applicationId = "in.voicemitra.patient"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
        // Where the app talks to the backend unless changed in its settings (Me -> Advanced). Set by
        // `voicemitra.serverUrl` in gradle.properties, or per build: `./gradlew assembleRelease
        // -Pvoicemitra.serverUrl=https://...`. Default: the home PC's tunnel.
        val serverUrl = providers.gradleProperty("voicemitra.serverUrl").orNull ?: "https://test-voicemitra.apoorvm.com"
        buildConfigField("String", "DEFAULT_SERVER_URL", "\"$serverUrl\"")
        buildConfigField("boolean", "HAS_FIREBASE", hasFirebaseConfig.toString())
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // Real phones only (no emulator is used): drops the x86 WebRTC libraries, roughly halving the APK
        // so it can be sent over WhatsApp.
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Sideloaded pilot builds: signed with the debug key so `assembleRelease` gives an installable APK.
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
    testOptions {
        unitTests.isIncludeAndroidResources = true  // Robolectric renders the app's real resources
        // ApiContractTest talks to a running backend when given one: -PvmServer=http://127.0.0.1:8100
        unitTests.all {
            it.systemProperty("vm.server", providers.gradleProperty("vmServer").getOrElse(""))
            it.systemProperty("vm.staff", providers.gradleProperty("vmStaff").getOrElse(""))
            // Robolectric reaches into JDK internals that JDK 25 no longer opens by default.
            it.jvmArgs(
                "--add-exports=java.base/jdk.internal.access=ALL-UNNAMED",
                "--add-opens=java.base/java.io=ALL-UNNAMED",
                "--add-opens=java.base/java.lang=ALL-UNNAMED",
                "--add-opens=java.base/java.util=ALL-UNNAMED",
            )
            it.maxHeapSize = "3g"
        }
    }
    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    // Pulled in old by Firebase; the ActivityResult permission prompts need 1.3+.
    implementation(libs.androidx.fragment)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.process)
    implementation(libs.androidx.datastore.preferences)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.livekit.android)
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.messaging)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.roborazzi)
    testImplementation(libs.roborazzi.compose)
    testImplementation(libs.androidx.test.junit)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.compose.ui.test.junit4)
    debugImplementation(libs.compose.ui.test.manifest)
}

// `./gradlew.bat screenshots` -> PNGs of every screen in ../screenshots/ (gitignored), rendered on the JVM.
tasks.register("screenshots") {
    group = "verification"
    description = "Render every screen to mobile/android/screenshots/ (no emulator)."
    dependsOn("recordRoborazziDebug")
}
