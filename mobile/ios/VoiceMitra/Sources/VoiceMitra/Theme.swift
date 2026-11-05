import SwiftUI
import UIKit

/// The web app's design system (web/src/app/globals.css), as SwiftUI colours and components: sage green is
/// the brand, the darkest ink-green carries the primary action; status colours are for state only and always
/// come with an icon and a word. Light and dark re-step the same hues.
enum VM {
    static let page = Color(light: 0xE9ECE7, dark: 0x0C110C)
    static let surface = Color(light: 0xFBFBF9, dark: 0x151B14)
    static let sunken = Color(light: 0xF0F2EC, dark: 0x1C231B)
    static let ink = Color(light: 0x10200F, dark: 0xEEF2EA)
    static let ink2 = Color(light: 0x435041, dark: 0xC5CDBF)
    static let muted = Color(light: 0x6B7668, dark: 0x98A393)
    static let line = Color(light: 0xE0E4DA, dark: 0x262E25)
    static let lineStrong = Color(light: 0xC9CFC1, dark: 0x3A4439)

    static let accent = Color(light: 0x4D7A37, dark: 0x8FBC72)
    static let accentSoft = Color(light: 0xE2EBD6, dark: 0x1F2E19)
    static let btn = Color(light: 0x12261A, dark: 0x8FBC72)
    static let onBtn = Color(light: 0xFFFFFF, dark: 0x0C1A0A)
    static let sage = Color(light: 0xD9E3CB, dark: 0x22301D)

    static let good = Color(light: 0x3F9163, dark: 0x4CB37C)
    static let goodInk = Color(light: 0x1F6A43, dark: 0x6FD09A)
    static let goodSoft = Color(light: 0xE4F3EA, dark: 0x14301F)
    static let warnInk = Color(light: 0x7A4D00, dark: 0xF0B84A)
    static let warnSoft = Color(light: 0xFBF1DC, dark: 0x3A2D0B)
    static let seriousInk = Color(light: 0x9B3A14, dark: 0xF4A384)
    static let seriousSoft = Color(light: 0xFBE9E0, dark: 0x3B2118)
    static let crit = Color(light: 0xC53A3A, dark: 0xE06666)
    static let critInk = Color(light: 0xA02626, dark: 0xF08A8A)
    static let critSoft = Color(light: 0xFBE8E8, dark: 0x3D1A1A)
    static let neutralSoft = Color(light: 0xEAEDE4, dark: 0x232A22)

    static let radius: CGFloat = 24
    static let radiusSmall: CGFloat = 14
}

extension Color {
    init(light: UInt32, dark: UInt32) {
        self = Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light) })
    }
}

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
    }
}

// MARK: - Components

/// A rounded surface card (the web's `.card`).
struct CardBackground: ViewModifier {
    var fill: Color = VM.surface
    var stroke: Color? = VM.line
    var padding: CGFloat = 20

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: VM.radius, style: .continuous).fill(fill))
            .overlay {
                if let stroke {
                    RoundedRectangle(cornerRadius: VM.radius, style: .continuous).strokeBorder(stroke, lineWidth: 1)
                }
            }
    }
}

extension View {
    func card(fill: Color = VM.surface, stroke: Color? = VM.line, padding: CGFloat = 20) -> some View {
        modifier(CardBackground(fill: fill, stroke: stroke, padding: padding))
    }
}

/// Small caps label above a section ("NEXT DOSE", "CURRENT").
struct Eyebrow: View {
    let text: String
    var color: Color = VM.muted

    var body: some View {
        Text(text.uppercased())
            .font(.footnote.weight(.semibold))
            .tracking(0.8)
            .foregroundStyle(color)
    }
}

/// The app mark: a sage tile with a microphone (the web header's logo).
struct BrandMark: View {
    var size: CGFloat = 44

    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
            .fill(VM.accent)
            .frame(width: size, height: size)
            .overlay {
                Image(systemName: "mic.fill")
                    .font(.system(size: size * 0.46, weight: .semibold))
                    .foregroundStyle(VM.onBtn)
            }
            .accessibilityHidden(true)
    }
}

/// Primary action: full-width ink-green capsule.
struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.title3.weight(.bold))
            .foregroundStyle(VM.onBtn)
            .frame(maxWidth: .infinity, minHeight: 60)
            .padding(.horizontal, 20)
            .background(Capsule().fill(VM.btn.opacity(isEnabled ? (configuration.isPressed ? 0.85 : 1) : 0.35)))
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Secondary action: outlined capsule.
struct SecondaryButtonStyle: ButtonStyle {
    var tint: Color = VM.ink

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.semibold))
            .foregroundStyle(tint)
            .frame(maxWidth: .infinity, minHeight: 54)
            .padding(.horizontal, 16)
            .background(Capsule().fill(configuration.isPressed ? VM.sunken : Color.clear))
            .overlay(Capsule().strokeBorder(VM.lineStrong, lineWidth: 1.5))
    }
}

/// A status word with its icon on a soft tint (doses, check-ins). Never colour alone.
struct StatusPill: View {
    let label: String
    let icon: String
    let ink: Color
    let soft: Color

    var body: some View {
        Label(label, systemImage: icon)
            .font(.subheadline.weight(.semibold))
            .labelStyle(.titleAndIcon)
            .foregroundStyle(ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(Capsule().fill(soft))
            .fixedSize()
    }
}

/// EN | हि segmented pill (the web header's language switch).
struct LangToggle: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        HStack(spacing: 0) {
            segment(.en, "EN")
            segment(.hi, "हि")
        }
        .padding(3)
        .background(Capsule().fill(VM.sunken))
        .overlay(Capsule().strokeBorder(VM.line, lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityLabel(model.t("Language", "भाषा"))
    }

    private func segment(_ lang: Lang, _ title: String) -> some View {
        let on = model.lang == lang
        return Button {
            withAnimation(.easeOut(duration: 0.15)) { model.lang = lang }
        } label: {
            Text(title)
                .font(.subheadline.weight(.bold))
                .foregroundStyle(on ? VM.onBtn : VM.ink2)
                .frame(minWidth: 44, minHeight: 34)
                .background(Capsule().fill(on ? VM.accent : Color.clear))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
    }
}

/// The top bar on every tab: mark + name on the left, language on the right.
struct AppHeader: View {
    var body: some View {
        HStack(spacing: 10) {
            BrandMark(size: 38)
            Text("VoiceMitra").font(.title3.weight(.bold)).foregroundStyle(VM.ink)
            Spacer()
            LangToggle()
        }
    }
}

/// The big heading at the top of a tab ("Your medicines"). Large Title, so it grows with Dynamic Type.
struct PageTitle: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.largeTitle.bold())
            .foregroundStyle(VM.ink)
            .padding(.top, 6)
            .accessibilityAddTraits(.isHeader)
    }
}

/// A round icon badge (pill, shield...) used at the start of card rows.
struct IconBadge: View {
    let systemName: String
    var tint: Color = VM.accent
    var fill: Color = VM.accentSoft
    var size: CGFloat = 46

    var body: some View {
        Circle()
            .fill(fill)
            .frame(width: size, height: size)
            .overlay { Image(systemName: systemName).font(.system(size: size * 0.42, weight: .semibold)).foregroundStyle(tint) }
            .accessibilityHidden(true)
    }
}
