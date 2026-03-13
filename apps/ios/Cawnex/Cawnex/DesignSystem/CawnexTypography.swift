import SwiftUI

enum CawnexTypography {

    // MARK: - Display

    static func display(_ size: CGFloat, weight: Font.Weight = .bold) -> Font {
        .custom("Inter", size: size).weight(weight)
    }

    // MARK: - Preset Styles

    static let wordmark = Font.custom("Inter", size: 36).weight(.bold)
    static let tagline = Font.custom("Inter", size: 14).weight(.regular)
    static let heading0 = Font.custom("Inter", size: 28).weight(.bold)
    static let heading1 = Font.custom("Inter", size: 24).weight(.bold)
    static let heading2 = Font.custom("Inter", size: 20).weight(.heavy)
    static let heading3 = Font.custom("Inter", size: 17).weight(.bold)
    static let sectionTitle = Font.custom("Inter", size: 16).weight(.semibold)
    static let subheading = Font.custom("Inter", size: 14).weight(.semibold)
    static let body = Font.custom("Inter", size: 15).weight(.regular)
    static let bodyBold = Font.custom("Inter", size: 15).weight(.semibold)
    static let caption = Font.custom("Inter", size: 13).weight(.regular)
    static let captionMedium = Font.custom("Inter", size: 13).weight(.medium)
    static let captionBold = Font.custom("Inter", size: 13).weight(.semibold)
    static let footnote = Font.custom("Inter", size: 12).weight(.regular)
    static let footnoteMedium = Font.custom("Inter", size: 12).weight(.medium)
    static let label = Font.custom("Inter", size: 11).weight(.semibold)
    static let tiny = Font.custom("Inter", size: 10).weight(.regular)
    static let tinyMedium = Font.custom("Inter", size: 10).weight(.medium)
    static let mono = Font.custom("JetBrains Mono", size: 12).weight(.regular)
    static let monoBold = Font.custom("JetBrains Mono", size: 12).weight(.bold)
    static let monoSemibold = Font.custom("JetBrains Mono", size: 11).weight(.semibold)
    static let microBold = Font.custom("Inter", size: 9).weight(.semibold)
}
