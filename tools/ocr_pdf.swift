// Local OCR for scanned PDFs and images using Apple's Vision framework. Nothing leaves this computer.
// Usage: ocr_pdf <file.pdf|image> [max_pages]   -> prints a JSON array with one string per page.
import Foundation
import PDFKit
import Vision
import ImageIO

func recognize(_ cg: CGImage) -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
    let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    return lines.joined(separator: " ")
}

guard CommandLine.arguments.count >= 2 else {
    FileHandle.standardError.write(Data("usage: ocr_pdf <file> [max_pages]\n".utf8))
    exit(1)
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let limit = CommandLine.arguments.count > 2 ? Int(CommandLine.arguments[2]) ?? 60 : 60
var pages: [String] = []
if let document = PDFDocument(url: url) {
    for index in 0..<min(document.pageCount, limit) {
        guard let page = document.page(at: index) else { pages.append(""); continue }
        let bounds = page.bounds(for: .mediaBox)
        let scale: CGFloat = 2.0
        let size = CGSize(width: bounds.width * scale, height: bounds.height * scale)
        let image = page.thumbnail(of: size, for: .mediaBox)
        guard let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { pages.append(""); continue }
        pages.append(recognize(cg))
    }
} else if let source = CGImageSourceCreateWithURL(url as CFURL, nil), let cg = CGImageSourceCreateImageAtIndex(source, 0, nil) {
    pages.append(recognize(cg))
} else {
    FileHandle.standardError.write(Data("cannot open file\n".utf8))
    exit(1)
}
let data = try JSONSerialization.data(withJSONObject: pages)
print(String(data: data, encoding: .utf8)!)
