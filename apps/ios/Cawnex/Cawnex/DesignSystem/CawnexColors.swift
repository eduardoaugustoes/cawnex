import SwiftUI

enum CawnexColors {

    // MARK: - Backgrounds

    static let background = Color(hex: 0x0A0A0A)
    static let card = Color(hex: 0x1A1C1E)
    static let muted = Color(hex: 0x2D2F31)

    // MARK: - Foregrounds

    static let cardForeground = Color.white
    static let mutedForeground = Color(hex: 0x9CA3AF)

    // MARK: - Brand

    static let primary = Color(hex: 0x7C3AED)
    static let primaryLight = Color(hex: 0x9F67FF)
    static let primaryForeground = Color.white

    // MARK: - Semantic

    static let success = Color(hex: 0x22C55E)
    static let warning = Color(hex: 0xF59E0B)
    static let destructive = Color(hex: 0xEF4444)
    static let info = Color(hex: 0x3B82F6)
    static let accent = Color(hex: 0xF97316)

    // MARK: - Extended Palette

    static let pink = Color(hex: 0xEC4899)
    static let deepNavy = Color(hex: 0x0F172A)

    // MARK: - Borders

    static let border = Color(hex: 0x404244)
}

extension Color {
    init(hex: UInt, opacity: Double = 1.0) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}
