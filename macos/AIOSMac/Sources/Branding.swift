import SwiftUI

enum Brand {
    static let pine = Color(red: 0.09, green: 0.35, blue: 0.28)
    static let mint = Color(red: 0.16, green: 0.58, blue: 0.47)
    static let amber = Color(red: 0.89, green: 0.66, blue: 0.24)
    static let ink = Color(red: 0.07, green: 0.14, blue: 0.12)
    static let coral = Color(red: 0.78, green: 0.28, blue: 0.22)
    static let mist = Color(red: 0.94, green: 0.97, blue: 0.95)
    static let fog = Color(red: 0.98, green: 0.99, blue: 0.98)

    static let action = mint
    static let active = pine
    static let waiting = amber
    static let reference = ink
    static let danger = coral

    static func dashboardGradient(for colorScheme: ColorScheme) -> LinearGradient {
        switch colorScheme {
        case .dark:
            return LinearGradient(
                colors: [
                    Color(nsColor: .windowBackgroundColor),
                    Color(red: 0.08, green: 0.12, blue: 0.11),
                    Color(red: 0.05, green: 0.08, blue: 0.08)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .light:
            return LinearGradient(
                colors: [mist, fog, Color.white],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        @unknown default:
            return LinearGradient(
                colors: [mist, fog, Color.white],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
    }

    static func panelFill(for colorScheme: ColorScheme) -> Color {
        switch colorScheme {
        case .dark:
            return Color.white.opacity(0.08)
        case .light:
            return fog.opacity(0.9)
        @unknown default:
            return fog.opacity(0.9)
        }
    }

    static func panelStroke(for colorScheme: ColorScheme) -> Color {
        switch colorScheme {
        case .dark:
            return Color.white.opacity(0.10)
        case .light:
            return mist.opacity(0.95)
        @unknown default:
            return mist.opacity(0.95)
        }
    }

    static func panelShadow(for colorScheme: ColorScheme) -> Color {
        switch colorScheme {
        case .dark:
            return .black.opacity(0.28)
        case .light:
            return .black.opacity(0.04)
        @unknown default:
            return .black.opacity(0.04)
        }
    }
}
