pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // LiveKit's audio routing library (audioswitch) is only on JitPack; nothing else comes from there.
        maven("https://jitpack.io") {
            content { includeGroup("com.github.davidliu") }
        }
    }
}
rootProject.name = "VoiceMitra"
include(":app")
