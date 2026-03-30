import AppKit
import Foundation

struct BrandPalette {
    static let canvas = NSColor(calibratedRed: 0.94, green: 0.97, blue: 0.95, alpha: 1.0)
    static let primary = NSColor(calibratedRed: 0.09, green: 0.35, blue: 0.28, alpha: 1.0)
    static let secondary = NSColor(calibratedRed: 0.16, green: 0.58, blue: 0.47, alpha: 1.0)
    static let highlight = NSColor(calibratedRed: 0.89, green: 0.66, blue: 0.24, alpha: 1.0)
    static let ink = NSColor(calibratedRed: 0.07, green: 0.14, blue: 0.12, alpha: 1.0)
}

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let appIconDir = root.appendingPathComponent("macos/AIOSMac/Assets.xcassets/AppIcon.appiconset", isDirectory: true)
let statusGlyphDir = root.appendingPathComponent("macos/AIOSMac/Assets.xcassets/StatusGlyph.imageset", isDirectory: true)

let iconSizes: [(String, CGFloat)] = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]

try FileManager.default.createDirectory(at: appIconDir, withIntermediateDirectories: true)
try FileManager.default.createDirectory(at: statusGlyphDir, withIntermediateDirectories: true)

func drawBadge(in rect: CGRect, showWordmark: Bool) {
    let radius = rect.width * 0.23
    let panelRect = rect.insetBy(dx: rect.width * 0.06, dy: rect.height * 0.06)

    let shadow = NSShadow()
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.12)
    shadow.shadowBlurRadius = rect.width * 0.04
    shadow.shadowOffset = NSSize(width: 0, height: -(rect.height * 0.02))
    shadow.set()

    let background = NSBezierPath(roundedRect: panelRect, xRadius: radius, yRadius: radius)
    NSGradient(colors: [BrandPalette.canvas, NSColor.white])?.draw(in: background, angle: 90)

    BrandPalette.primary.withAlphaComponent(0.12).setStroke()
    background.lineWidth = max(2, rect.width * 0.02)
    background.stroke()

    NSGraphicsContext.current?.saveGraphicsState()
    background.addClip()

    let wave = NSBezierPath()
    wave.move(to: CGPoint(x: panelRect.minX, y: panelRect.midY))
    wave.curve(
        to: CGPoint(x: panelRect.maxX, y: panelRect.maxY - rect.height * 0.18),
        controlPoint1: CGPoint(x: panelRect.minX + rect.width * 0.2, y: panelRect.maxY - rect.height * 0.06),
        controlPoint2: CGPoint(x: panelRect.minX + rect.width * 0.58, y: panelRect.minY + rect.height * 0.2)
    )
    wave.line(to: CGPoint(x: panelRect.maxX, y: panelRect.minY))
    wave.line(to: CGPoint(x: panelRect.minX, y: panelRect.minY))
    wave.close()
    NSGradient(colors: [BrandPalette.secondary, BrandPalette.primary])?.draw(in: wave, angle: -35)

    let orbitRect = CGRect(
        x: panelRect.minX + rect.width * 0.18,
        y: panelRect.minY + rect.height * 0.2,
        width: rect.width * 0.64,
        height: rect.height * 0.64
    )
    let orbit = NSBezierPath(ovalIn: orbitRect)
    BrandPalette.highlight.withAlphaComponent(0.55).setStroke()
    orbit.lineWidth = max(3, rect.width * 0.03)
    orbit.stroke()

    let dotRect = CGRect(
        x: orbitRect.maxX - rect.width * 0.08,
        y: orbitRect.midY - rect.height * 0.04,
        width: rect.width * 0.09,
        height: rect.height * 0.09
    )
    let dot = NSBezierPath(ovalIn: dotRect)
    BrandPalette.highlight.setFill()
    dot.fill()

    if showWordmark {
        let text = "AI"
        let font = NSFont.systemFont(ofSize: rect.width * 0.23, weight: .bold)
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: BrandPalette.ink
        ]
        let size = text.size(withAttributes: attrs)
        let point = CGPoint(
            x: panelRect.minX + rect.width * 0.2,
            y: panelRect.minY + rect.height * 0.18
        )
        text.draw(at: point, withAttributes: attrs)

        let osText = "OS"
        let osAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: rect.width * 0.13, weight: .semibold),
            .foregroundColor: BrandPalette.canvas
        ]
        osText.draw(
            at: CGPoint(x: point.x + size.width + rect.width * 0.03, y: point.y + rect.height * 0.08),
            withAttributes: osAttrs
        )
    }

    NSGraphicsContext.current?.restoreGraphicsState()
}

func renderPNG(size: CGFloat, showWordmark: Bool) -> Data? {
    let image = NSImage(size: NSSize(width: size, height: size))
    image.lockFocus()
    defer { image.unlockFocus() }

    drawBadge(in: CGRect(origin: .zero, size: CGSize(width: size, height: size)), showWordmark: showWordmark)

    guard let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff) else {
        return nil
    }
    return rep.representation(using: .png, properties: [:])
}

for (filename, size) in iconSizes {
    if let data = renderPNG(size: size, showWordmark: size >= 64) {
        try data.write(to: appIconDir.appendingPathComponent(filename))
    }
}

if let glyphData = renderPNG(size: 512, showWordmark: false) {
    try glyphData.write(to: statusGlyphDir.appendingPathComponent("StatusGlyph.png"))
}
