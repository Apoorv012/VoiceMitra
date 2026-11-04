plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
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
        // Where the app talks to the backend unless changed in its settings: the tunnel's public hostname.
        buildConfigField("String", "DEFAULT_SERVER_URL", "\"https://test-voicemitra.apoorvm.com\"")
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
        // ApiContractTest talks to a running backend when given one: -PvmServer=http://127.0.0.1:8100
        unitTests.all { it.systemProperty("vm.server", providers.gradleProperty("vmServer").getOrElse("")) }
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
}
